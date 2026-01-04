#!/usr/bin/env python3
"""
Serveur API Flask pour les statistiques de basket - Version PostgreSQL + Blob Storage
Fournit une API REST et sert l'interface web
"""
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
from config import Config
from database import get_db
from storage_service import get_storage
from extract_stats import extract_from_pdf
import json
import os
import io
from werkzeug.utils import secure_filename
from datetime import datetime

print('test')
# Import du cache FFBB pour le calendrier
try:
    from ffbb_cache import FFBBCache
    from apscheduler.schedulers.background import BackgroundScheduler
    FFBB_AVAILABLE = True
except ImportError:
    FFBB_AVAILABLE = False
    print("⚠️ ffbb_cache ou apscheduler non disponible - calendrier FFBB désactivé")

app = Flask(__name__, static_folder='.')
CORS(app)

def convert_minutes_to_int(minutes_str):
    """
    Convertit les minutes de format string vers int
    Exemples:
    - "29:18" -> 29
    - "NPJ" -> 0
    - 25 -> 25
    """
    if minutes_str is None or minutes_str == '':
        return 0
    
    # Si c'est déjà un int
    if isinstance(minutes_str, int):
        return minutes_str
    
    # Convertir en string
    minutes_str = str(minutes_str).strip()
    
    # Si c'est "NPJ" (N'a Pas Joué)
    if minutes_str.upper() == 'NPJ':
        return 0
    
    # Si c'est au format "MM:SS"
    if ':' in minutes_str:
        parts = minutes_str.split(':')
        try:
            return int(parts[0])  # Retourner juste les minutes
        except:
            return 0
    
    # Essayer de convertir directement
    try:
        return int(minutes_str)
    except:
        return 0

# Configuration
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_UPLOAD_SIZE
ALLOWED_EXTENSIONS = Config.ALLOWED_EXTENSIONS

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialiser les services
try:
    db = get_db()
    storage = get_storage()
    print("✅ Services initialisés (PostgreSQL + Blob Storage)")
except Exception as e:
    print(f"❌ Erreur lors de l'initialisation des services: {e}")
    db = None
    storage = None

# Nom de l'équipe pour la recherche
TEAM_NAME = Config.TEAM_NAME

# Initialiser le cache FFBB si disponible
ffbb_cache = None
if FFBB_AVAILABLE:
    ffbb_cache = FFBBCache()
    
    # Fonction de mise à jour automatique
    def update_ffbb_cache_job():
        print(f"[{datetime.now()}] 🔄 Mise à jour automatique du cache FFBB...")
        try:
            success = ffbb_cache.update_calendar(Config.FFBB_USERNAME, Config.FFBB_PASSWORD, force=True)
            if success:
                info = ffbb_cache.get_cache_info()
                print(f"[FFBB] ✅ Cache mis à jour: {info['nb_matches']} matchs")
            else:
                print("[FFBB] ❌ Échec de la mise à jour")
        except Exception as e:
            print(f"[FFBB] ❌ Erreur: {e}")
    
    # Scheduler : mise à jour tous les jours à 6h00
    scheduler = BackgroundScheduler()
    scheduler.add_job(update_ffbb_cache_job, 'cron', hour=6, minute=0)
    scheduler.start()
    print("[FFBB] ✅ Scheduler démarré - MAJ automatique à 6h00 chaque jour")

@app.route('/')
def index():
    """Page d'accueil - Interface de visualisation"""
    return send_from_directory('.', 'index.html')

@app.route('/health')
def health():
    """Health check endpoint"""
    status = {
        'status': 'ok',
        'message': 'Server is running'
    }
    
    # Vérifier la base de données
    if db:
        try:
            if db.health_check():
                status['database'] = 'connected'
            else:
                status['database'] = 'error'
                status['status'] = 'degraded'
        except Exception as e:
            status['database'] = f'error: {str(e)}'
            status['status'] = 'degraded'
    else:
        status['database'] = 'not initialized'
        status['status'] = 'error'
    
    # Vérifier le stockage
    if storage:
        status['storage'] = 'connected'
    else:
        status['storage'] = 'not initialized'
        status['status'] = 'degraded'
    
    return jsonify(status), 200 if status['status'] == 'ok' else 503

@app.route('/api/matches', methods=['GET'])
def get_matches():
    """Récupère tous les matchs"""
    try:
        matches = db.get_all_matches()
        return jsonify({
            'success': True,
            'data': matches
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/matches/latest', methods=['GET'])
def get_latest_match():
    """Récupère le dernier match joué (par date)"""
    try:
        matches = db.get_all_matches()
        if not matches:
            return jsonify({
                'success': False,
                'error': 'Aucun match disponible'
            }), 404
        
        # Trier par date (plus récente en premier)
        sorted_matches = sorted(matches, key=lambda x: x.get('date', ''), reverse=True)
        latest_match_id = sorted_matches[0]['id']
        
        # Récupérer les détails du match le plus récent
        match = db.get_match_by_id(latest_match_id)
        if match:
            return jsonify({
                'success': True,
                'data': match
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Match non trouvé'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/matches/<int:match_id>', methods=['GET'])
def get_match_details(match_id):
    """Récupère les détails d'un match spécifique"""
    try:
        match = db.get_match_by_id(match_id)
        if match:
            return jsonify({
                'success': True,
                'data': match
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Match non trouvé'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/matches/<int:match_id>/lineups', methods=['GET'])
def get_match_lineups(match_id):
    """Récupère les combinaisons de 5 d'un match"""
    try:
        lineups = db.get_lineups_by_match(match_id)
        return jsonify({
            'success': True,
            'data': lineups
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/matches/find', methods=['GET'])
def find_matches():
    """Recherche des matchs par adversaire"""
    opponent = request.args.get('opponent', '')
    if not opponent:
        return jsonify({
            'success': False,
            'error': 'Paramètre opponent requis'
        }), 400
    
    try:
        matches = db.search_matches_by_opponent(opponent)
        return jsonify({
            'success': True,
            'data': matches
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/players/<player_name>', methods=['GET'])
def get_player_stats(player_name):
    """Récupère les stats d'une joueuse"""
    try:
        stats = db.get_player_stats(player_name)
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    """
    Upload intelligent de PDF - Détecte automatiquement le type
    Supporte: FIBA Box Score, Boxscore Détaillée, Analyse des 5 en jeu
    """
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'Aucun fichier fourni'
        }), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({
            'success': False,
            'error': 'Nom de fichier vide'
        }), 400
    
    if not allowed_file(file.filename):
        return jsonify({
            'success': False,
            'error': 'Type de fichier non autorisé (PDF uniquement)'
        }), 400
    
    try:
        filename = secure_filename(file.filename)
        
        # Lire le contenu du fichier
        file_content = file.read()
        file_stream = io.BytesIO(file_content)
        
        # Upload vers Blob Storage
        print(f"📤 Upload du PDF vers Blob Storage: {filename}")
        blob_url = storage.upload_pdf(file_stream, filename)
        print(f"✅ PDF uploadé: {blob_url}")
        
        # Réinitialiser le stream pour l'extraction
        file_stream.seek(0)
        
        # Extraire les stats
        print(f"📊 Extraction des stats du PDF...")
        result = extract_from_pdf(file_stream)
        
        if not result.get('success'):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Erreur lors de l\'extraction')
            }), 400
        
        # Insérer le match
        match_data = result['data']['match_info']
        match_data['pdf_source'] = result['data']['source']
        match_data['pdf_blob_url'] = blob_url
        
        match_id = db.insert_match(match_data)
        print(f"✅ Match {match_id} inséré")
        
        # Insérer les stats des joueuses
        for player in result['data']['stats_joueuses']:
            db.insert_player_stats(match_id, player)
        print(f"✅ {len(result['data']['stats_joueuses'])} joueuses insérées")
        
        # Insérer les stats des équipes
        for team in result['data']['stats_equipes']:
            db.insert_team_stats(match_id, team)
        print(f"✅ {len(result['data']['stats_equipes'])} équipes insérées")
        
        # Insérer les combinaisons de 5 si disponibles
        if 'combinaisons_5' in result['data']:
            for lineup in result['data']['combinaisons_5']:
                db.insert_lineup(match_id, lineup)
            print(f"✅ {len(result['data']['combinaisons_5'])} combinaisons insérées")
        
        return jsonify({
            'success': True,
            'match_id': match_id,
            'source': result['data']['source'],
            'message': f'Match importé avec succès (ID: {match_id})'
        })
        
    except Exception as e:
        print(f"❌ Erreur lors de l'upload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/reset-database', methods=['POST'])
def reset_database():
    """
    DANGER: Vide complètement la base de données
    À utiliser seulement pour recommencer l'import à zéro
    """
    # Vérifier un token de sécurité
    data = request.get_json() or {}
    confirm = data.get('confirm', '')
    
    if confirm != 'RESET_EVERYTHING':
        return jsonify({
            'success': False,
            'error': 'Confirmation requise. Envoyer {"confirm": "RESET_EVERYTHING"}'
        }), 400
    
    try:
        print("⚠️ RESET DATABASE - Suppression de toutes les données...")
        
        # Supprimer dans l'ordre (à cause des foreign keys)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM combinaisons_5')
            deleted_combos = cursor.rowcount
            
            cursor.execute('DELETE FROM stats_equipes')
            deleted_teams = cursor.rowcount
            
            cursor.execute('DELETE FROM stats_joueuses')
            deleted_players = cursor.rowcount
            
            cursor.execute('DELETE FROM matchs')
            deleted_matchs = cursor.rowcount
            
            # Reset les sequences
            cursor.execute('ALTER SEQUENCE matchs_id_seq RESTART WITH 1')
            cursor.execute('ALTER SEQUENCE stats_joueuses_id_seq RESTART WITH 1')
            cursor.execute('ALTER SEQUENCE stats_equipes_id_seq RESTART WITH 1')
            cursor.execute('ALTER SEQUENCE combinaisons_5_id_seq RESTART WITH 1')
            
            conn.commit()
        
        print(f"✅ Base vidée:")
        print(f"  • {deleted_matchs} matchs supprimés")
        print(f"  • {deleted_players} stats joueuses supprimées")
        print(f"  • {deleted_teams} stats équipes supprimées")
        print(f"  • {deleted_combos} combinaisons supprimées")
        
        return jsonify({
            'success': True,
            'message': 'Base de données vidée',
            'deleted': {
                'matchs': deleted_matchs,
                'stats_joueuses': deleted_players,
                'stats_equipes': deleted_teams,
                'combinaisons_5': deleted_combos
            }
        })
        
    except Exception as e:
        print(f"❌ Erreur lors du reset: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/import-json', methods=['POST'])
def import_json_data():
    """
    Import de données JSON depuis export SQLite
    Permet de migrer les données d'une base SQLite vers PostgreSQL
    """
    if 'file' not in request.files:
        return jsonify({
            'success': False,
            'error': 'Aucun fichier fourni'
        }), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({
            'success': False,
            'error': 'Nom de fichier vide'
        }), 400
    
    try:
        # Lire le JSON
        print("📂 Lecture du fichier JSON...")
        content = file.read().decode('utf-8')
        data = json.loads(content)
        
        print(f"✅ JSON chargé:")
        print(f"  • {len(data.get('matchs', []))} matchs")
        print(f"  • {len(data.get('stats_joueuses', []))} stats joueuses")
        print(f"  • {len(data.get('stats_equipes', []))} stats équipes")
        print(f"  • {len(data.get('combinaisons_5', []))} combinaisons")
        
        # Mapping ancien_id → nouveau_id
        match_id_mapping = {}
        errors = []
        
        # Import matchs
        imported_matchs = 0
        for match in data.get('matchs', []):
            old_match_id = match.get('id')
            
            try:
                match_data = {
                    'match_no': match.get('match_no'),
                    'date': match.get('date'),
                    'heure': match.get('heure'),
                    'competition': match.get('competition'),
                    'saison': match.get('saison'),
                    'equipe_domicile': match.get('equipe_domicile'),
                    'equipe_exterieur': match.get('equipe_exterieur'),
                    'score_domicile': match.get('score_domicile'),
                    'score_exterieur': match.get('score_exterieur'),
                    'q1_domicile': match.get('q1_domicile'),
                    'q1_exterieur': match.get('q1_exterieur'),
                    'q2_domicile': match.get('q2_domicile'),
                    'q2_exterieur': match.get('q2_exterieur'),
                    'q3_domicile': match.get('q3_domicile'),
                    'q3_exterieur': match.get('q3_exterieur'),
                    'q4_domicile': match.get('q4_domicile'),
                    'q4_exterieur': match.get('q4_exterieur'),
                    'lieu': match.get('lieu'),
                    'ville': match.get('ville'),
                    'affluence': match.get('affluence'),
                    'arbitres': match.get('arbitres'),
                    'pdf_source': match.get('pdf_source'),
                    'pdf_blob_url': match.get('pdf_blob_url')
                }
                
                new_match_id = db.insert_match(match_data)
                match_id_mapping[old_match_id] = new_match_id
                imported_matchs += 1
                
            except Exception as e:
                error_msg = f"Erreur match {old_match_id}: {str(e)}"
                print(f"⚠️ {error_msg}")
                errors.append(error_msg)
        
        print(f"\n📊 Mapping créé: {match_id_mapping}")
        
        # Import stats joueuses
        imported_players = 0
        skipped_players = 0
        for stat in data.get('stats_joueuses', []):
            old_match_id = stat.get('match_id')
            
            if old_match_id not in match_id_mapping:
                skipped_players += 1
                if skipped_players <= 3:
                    error_msg = f"Stats joueuse skip - match_id {old_match_id} introuvable dans mapping {list(match_id_mapping.keys())}"
                    print(f"⚠️ {error_msg}")
                    errors.append(error_msg)
                continue
            
            new_match_id = match_id_mapping[old_match_id]
            
            try:
                player_data = {
                    'equipe': stat.get('equipe'),
                    'numero': stat.get('numero'),
                    'nom': stat.get('nom'),
                    'prenom': stat.get('prenom'),
                    'minutes': convert_minutes_to_int(stat.get('minutes', 0)),
                    'points': stat.get('points', 0),
                    'tirs_reussis': stat.get('tirs_reussis', 0),
                    'tirs_tentes': stat.get('tirs_tentes', 0),
                    'tirs_2pts_reussis': stat.get('tirs_2pts_reussis', 0),
                    'tirs_2pts_tentes': stat.get('tirs_2pts_tentes', 0),
                    'tirs_3pts_reussis': stat.get('tirs_3pts_reussis', 0),
                    'tirs_3pts_tentes': stat.get('tirs_3pts_tentes', 0),
                    'lf_reussis': stat.get('lf_reussis', 0),
                    'lf_tentes': stat.get('lf_tentes', 0),
                    'rebonds_offensifs': stat.get('rebonds_offensifs', 0),
                    'rebonds_defensifs': stat.get('rebonds_defensifs', 0),
                    'rebonds_total': stat.get('rebonds_total', 0),
                    'passes_decisives': stat.get('passes_decisives', 0),
                    'interceptions': stat.get('interceptions', 0),
                    'balles_perdues': stat.get('balles_perdues', 0),
                    'contres': stat.get('contres', 0),
                    'fautes_provoquees': stat.get('fautes_provoquees', 0),
                    'fautes_commises': stat.get('fautes_commises', 0),
                    'plus_moins': stat.get('plus_moins', 0),
                    'evaluation': stat.get('evaluation', 0)
                }
                
                db.insert_player_stats(new_match_id, player_data)
                imported_players += 1
                
            except Exception as e:
                error_msg = f"Erreur stat joueuse: {str(e)}"
                print(f"⚠️ {error_msg}")
                errors.append(error_msg)
        
        if skipped_players > 0:
            print(f"\n⚠️ {skipped_players} stats joueuses skippées (match_id introuvable)")
        
        # Import stats équipes
        imported_teams = 0
        for stat in data.get('stats_equipes', []):
            old_match_id = stat.get('match_id')
            
            if old_match_id not in match_id_mapping:
                continue
            
            new_match_id = match_id_mapping[old_match_id]
            
            try:
                team_data = {
                    'equipe': stat.get('equipe'),
                    'points': stat.get('points', 0),
                    'tirs_reussis': stat.get('tirs_reussis', 0),
                    'tirs_tentes': stat.get('tirs_tentes', 0),
                    'tirs_2pts_reussis': stat.get('tirs_2pts_reussis', 0),
                    'tirs_2pts_tentes': stat.get('tirs_2pts_tentes', 0),
                    'tirs_3pts_reussis': stat.get('tirs_3pts_reussis', 0),
                    'tirs_3pts_tentes': stat.get('tirs_3pts_tentes', 0),
                    'lf_reussis': stat.get('lf_reussis', 0),
                    'lf_tentes': stat.get('lf_tentes', 0),
                    'rebonds_offensifs': stat.get('rebonds_offensifs', 0),
                    'rebonds_defensifs': stat.get('rebonds_defensifs', 0),
                    'rebonds_total': stat.get('rebonds_total', 0),
                    'passes_decisives': stat.get('passes_decisives', 0),
                    'interceptions': stat.get('interceptions', 0),
                    'balles_perdues': stat.get('balles_perdues', 0),
                    'contres': stat.get('contres', 0),
                    'fautes_commises': stat.get('fautes_commises', 0)
                }
                
                db.insert_team_stats(new_match_id, team_data)
                imported_teams += 1
                
            except Exception as e:
                print(f"⚠️ Erreur stat équipe: {e}")
        
        # Import combinaisons
        imported_combos = 0
        for combo in data.get('combinaisons_5', []):
            old_match_id = combo.get('match_id')
            
            if old_match_id not in match_id_mapping:
                continue
            
            new_match_id = match_id_mapping[old_match_id]
            
            try:
                lineup_data = {
                    'equipe': combo.get('equipe'),
                    'joueurs': combo.get('joueurs'),
                    'duree_secondes': combo.get('duree_secondes', 0),
                    'points_marques': combo.get('points_marques', 0),
                    'points_encaisses': combo.get('points_encaisses', 0),
                    'plus_minus': combo.get('plus_minus', 0)
                }
                
                db.insert_lineup(new_match_id, lineup_data)
                imported_combos += 1
                
            except Exception as e:
                print(f"⚠️ Erreur combinaison: {e}")
        
        return jsonify({
            'success': True,
            'message': 'Import réussi',
            'imported': {
                'matchs': imported_matchs,
                'stats_joueuses': imported_players,
                'stats_equipes': imported_teams,
                'combinaisons_5': imported_combos
            },
            'errors': errors[:10] if errors else [],  # Max 10 erreurs pour ne pas surcharger
            'total_errors': len(errors)
        })
        
    except Exception as e:
        print(f"❌ Erreur lors de l'import: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================
# ROUTES CALENDRIER FFBB
# ============================================

@app.route('/api/calendar/update', methods=['POST'])
def update_calendar():
    """Force la mise à jour du cache FFBB"""
    if not ffbb_cache:
        return jsonify({
            'success': False,
            'error': 'Cache FFBB non disponible'
        }), 503
    
    try:
        success = ffbb_cache.update_calendar(Config.FFBB_USERNAME, Config.FFBB_PASSWORD, force=True)
        info = ffbb_cache.get_cache_info()
        
        return jsonify({
            'success': success,
            'data': info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calendar', methods=['GET'])
def get_calendar():
    """Récupère tout le calendrier"""
    if not ffbb_cache:
        return jsonify({
            'success': False,
            'error': 'Cache FFBB non disponible'
        }), 503
    
    try:
        data = ffbb_cache.get_all_matches()
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calendar/upcoming', methods=['GET'])
def get_upcoming_matches():
    """Récupère les prochains matchs"""
    if not ffbb_cache:
        return jsonify({
            'success': False,
            'error': 'Cache FFBB non disponible'
        }), 503
    
    try:
        days = int(request.args.get('days', 30))
        data = ffbb_cache.get_upcoming_matches(days)
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calendar/results', methods=['GET'])
def get_recent_results():
    """Récupère les résultats récents"""
    if not ffbb_cache:
        return jsonify({
            'success': False,
            'error': 'Cache FFBB non disponible'
        }), 503
    
    try:
        days = int(request.args.get('days', 30))
        data = ffbb_cache.get_recent_results(days)
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calendar/classement', methods=['GET'])
def get_classement():
    """Récupère le classement"""
    if not ffbb_cache:
        return jsonify({
            'success': False,
            'error': 'Cache FFBB non disponible'
        }), 503
    
    try:
        data = ffbb_cache.get_classement()
        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/calendar/info', methods=['GET'])
def get_calendar_info():
    """Récupère les infos sur le cache"""
    if not ffbb_cache:
        return jsonify({
            'success': False,
            'error': 'Cache FFBB non disponible'
        }), 503
    
    try:
        info = ffbb_cache.get_cache_info()
        return jsonify({
            'success': True,
            'data': info
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



if __name__ == '__main__':
    print("\n" + "="*60)
    print("🏀 API CSMF Basketball Stats - Version PostgreSQL + Blob Storage")
    print("="*60)
    print("\n📋 Configuration:")
    print(f"  • Database: PostgreSQL ({Config.DB_HOST})")
    print(f"  • Storage: Azure Blob Storage")
    print(f"  • Team: {TEAM_NAME}")
    print(f"  • FFBB: {'✅ Activé' if FFBB_AVAILABLE else '❌ Désactivé'}")
    print("\n🌐 Endpoints disponibles:")
    print("  📄 GET  /                        - Interface web")
    print("  ❤️  GET  /health                  - Health check")
    print("  🏀 GET  /api/matches              - Liste des matchs")
    print("  📊 GET  /api/matches/<id>         - Détails d'un match")
    print("  👥 GET  /api/matches/<id>/lineups - Combinaisons de 5")
    print("  🔍 GET  /api/matches/find?opponent=X - Recherche par adversaire")
    print("  👤 GET  /api/players/<nom>        - Stats d'une joueuse")
    print("  📤 POST /api/upload               - Upload PDF (intelligent)")
    if FFBB_AVAILABLE:
        print("\n📅 Calendrier FFBB:")
        print("  📅 GET  /api/calendar             - Tout le calendrier")
        print("  ⏭️  GET  /api/calendar/upcoming   - Prochains matchs")
        print("  📊 GET  /api/calendar/results     - Résultats récents")
        print("  🏆 GET  /api/calendar/classement  - Classement")
        print("  ℹ️  GET  /api/calendar/info       - Info sur le cache")
        print("  🔄 POST /api/calendar/update      - Forcer MAJ cache")
    print("\n" + "="*60)
    print("🚀 Serveur démarré sur http://0.0.0.0:8000")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=8000, debug=False)
