#!/usr/bin/env python3
"""
Serveur API Flask pour les statistiques de basket - Version PostgreSQL + Blob Storage
Fournit une API REST et sert l'interface web
Multi-tenant avec authentification
"""
from flask import Flask, jsonify, send_from_directory, request, g
from flask_cors import CORS
from config import Config
from database import get_db
from storage_service import get_storage
from extract_stats import extract_from_pdf, extract_boxscore_detaillee_excel, extract_stats_detaillees
import json
import os
import io
from werkzeug.utils import secure_filename
from datetime import datetime

# Import du module de chat IA
try:
    import chat_analyst
    CHAT_AVAILABLE = True
except ImportError as e:
    CHAT_AVAILABLE = False
    print(f"⚠️ Module chat_analyst non disponible: {e}")

# Import du module d'authentification
try:
    from auth import AuthManager, require_auth, require_admin, require_feature
    from auth_routes import auth_bp
    AUTH_AVAILABLE = True
except ImportError as e:
    AUTH_AVAILABLE = False
    print(f"⚠️ Module auth non disponible: {e}")

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

# Enregistrer le blueprint d'authentification
if AUTH_AVAILABLE:
    app.register_blueprint(auth_bp)
    print("✅ Routes d'authentification activées")

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

def parse_french_date(date_str):
    """Convertit une date française en format ISO (YYYY-MM-DD)"""
    if not date_str:
        return None
    
    # Mapping des mois français
    mois = {
        'janv.': '01', 'janvier': '01',
        'févr.': '02', 'février': '02', 'fevr.': '02',
        'mars': '03',
        'avr.': '04', 'avril': '04',
        'mai': '05',
        'juin': '06',
        'juil.': '07', 'juillet': '07',
        'août': '08', 'aout': '08',
        'sept.': '09', 'septembre': '09',
        'oct.': '10', 'octobre': '10',
        'nov.': '11', 'novembre': '11',
        'déc.': '12', 'décembre': '12', 'dec.': '12'
    }
    
    try:
        parts = date_str.strip().split()
        if len(parts) >= 3:
            jour = parts[0].zfill(2)
            mois_str = parts[1].lower()
            annee = parts[2]
            
            if mois_str in mois:
                return f"{annee}-{mois[mois_str]}-{jour}"
    except:
        pass
    
    return date_str

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
    """Landing page commerciale"""
    return send_from_directory('.', 'landing.html')

@app.route('/app')
def app_dashboard():
    """Application principale (dashboard club)"""
    return send_from_directory('.', 'index.html')

# Route legacy pour compatibilité
@app.route('/dashboard')
def dashboard_redirect():
    """Redirection vers /app"""
    from flask import redirect
    return redirect('/app')

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
    
    # Vérifier la clé Anthropic (sans révéler la valeur)
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if api_key:
        # Masquer la clé mais montrer qu'elle existe
        status['anthropic_api'] = f'configured (starts with {api_key[:10]}...)'
    else:
        status['anthropic_api'] = 'not configured'
        # Lister les variables d'environnement qui contiennent "KEY" ou "API" pour debug
        env_keys = [k for k in os.environ.keys() if 'KEY' in k.upper() or 'API' in k.upper() or 'ANTHROP' in k.upper()]
        status['env_hint'] = f'Found env vars matching KEY/API/ANTHROP: {env_keys}'
    
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
    Upload intelligent multi-fichiers - Détecte automatiquement le type de chaque fichier
    Accepte 1 à N fichiers PDF (ou Excel pour Boxscore)
    
    Types détectés automatiquement:
    - FIBA_Box_Score (obligatoire - crée le match)
    - Analyse_des_5_en_jeu (combinaisons de 5)
    - Boxscore_Détaillée (stats avancées équipe, périodes)
    - Statistiques_détaillées (tirs int/ext, ratios, 5 départ vs banc)
    """
    import tempfile
    from extract_stats import detect_pdf_type, extract_from_pdf, extract_stats_detaillees
    
    # Récupérer tous les fichiers uploadés
    files = request.files.getlist('files')
    if not files or len(files) == 0:
        # Fallback sur 'file' pour compatibilité
        if 'file' in request.files:
            files = [request.files['file']]
        else:
            return jsonify({
                'success': False,
                'error': 'Aucun fichier fourni'
            }), 400
    
    # Filtrer les fichiers vides
    files = [f for f in files if f.filename and f.filename != '']
    
    if len(files) == 0:
        return jsonify({
            'success': False,
            'error': 'Aucun fichier valide fourni'
        }), 400
    
    try:
        temp_dir = tempfile.gettempdir()
        
        # Étape 1: Sauvegarder tous les fichiers et détecter leurs types
        file_info = []
        for f in files:
            filename = secure_filename(f.filename)
            temp_path = os.path.join(temp_dir, filename)
            f.save(temp_path)
            
            # Détecter le type
            ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
            
            if ext in ['xlsx', 'xls']:
                # Fichiers Excel = Boxscore Détaillée
                pdf_type = 'BOXSCORE_DETAILLEE_EXCEL'
            elif ext == 'pdf':
                # Lire le PDF pour détecter le type
                import pdfplumber
                with pdfplumber.open(temp_path) as pdf:
                    text = ""
                    for page in pdf.pages[:2]:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                pdf_type = detect_pdf_type(text, filename)
            else:
                pdf_type = 'UNKNOWN'
            
            file_info.append({
                'filename': filename,
                'path': temp_path,
                'type': pdf_type
            })
            print(f"📁 Fichier détecté: {filename} → {pdf_type}")
        
        # Étape 2: Trouver le fichier FIBA Box Score (obligatoire)
        fiba_file = next((f for f in file_info if f['type'] == 'FIBA_BOX_SCORE'), None)
        
        if not fiba_file:
            # Nettoyer les fichiers temporaires
            for f in file_info:
                try:
                    os.remove(f['path'])
                except:
                    pass
            return jsonify({
                'success': False,
                'error': 'Fichier FIBA Box Score non trouvé parmi les fichiers uploadés'
            }), 400
        
        # Étape 3: Extraire le FIBA Box Score (crée le match)
        print(f"\n📊 Extraction FIBA Box Score: {fiba_file['filename']}")
        result = extract_from_pdf(fiba_file['path'])
        
        if not result or not result.get('match_info'):
            for f in file_info:
                try:
                    os.remove(f['path'])
                except:
                    pass
            return jsonify({
                'success': False,
                'error': 'Erreur lors de l\'extraction du FIBA Box Score'
            }), 400
        
        # Préparer et insérer le match
        match_data = result['match_info']
        match_data['pdf_source'] = fiba_file['filename']
        
        if 'date' in match_data and match_data['date']:
            match_data['date'] = parse_french_date(match_data['date'])
        
        match_id = db.insert_match(match_data)
        print(f"✅ Match {match_id} inséré")
        
        # Insérer les stats des joueuses
        player_stats = result.get('player_stats', [])
        for player in player_stats:
            if 'minutes' in player:
                player['minutes'] = convert_minutes_to_int(player['minutes'])
            db.insert_player_stats(match_id, player)
        print(f"✅ {len(player_stats)} joueuses insérées")
        
        # Insérer les stats des équipes
        team_stats = result.get('team_stats', [])
        for team in team_stats:
            db.insert_team_stats(match_id, team)
        print(f"✅ {len(team_stats)} équipes insérées")
        
        # Compteurs pour le résumé
        lineups_count = 0
        periods_count = 0
        advanced_stats = {}
        
        # Étape 4: Traiter les autres fichiers
        for f in file_info:
            if f['type'] == 'FIBA_BOX_SCORE':
                continue  # Déjà traité
            
            try:
                if f['type'] == 'ANALYSE_5':
                    print(f"\n📊 Extraction Analyse des 5: {f['filename']}")
                    analyse_result = extract_from_pdf(f['path'])
                    if analyse_result and analyse_result.get('lineup_stats'):
                        for lineup in analyse_result['lineup_stats']:
                            db.insert_lineup(match_id, lineup)
                        lineups_count = len(analyse_result['lineup_stats'])
                        print(f"✅ {lineups_count} combinaisons de 5 insérées")
                
                elif f['type'] == 'BOXSCORE_DETAILLEE':
                    print(f"\n📊 Extraction Boxscore Détaillée (PDF): {f['filename']}")
                    boxscore_result = extract_from_pdf(f['path'])
                    if boxscore_result:
                        # Insérer les stats par période si présentes
                        if boxscore_result.get('period_stats'):
                            db.delete_period_stats(match_id)
                            for period in boxscore_result['period_stats']:
                                db.insert_period_stats(match_id, period)
                            periods_count = len(boxscore_result['period_stats'])
                        
                        # Mettre à jour le flag
                        with db.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute('UPDATE matchs SET has_boxscore_detaillee = TRUE WHERE id = %s', (match_id,))
                            conn.commit()
                        print(f"✅ Boxscore Détaillée traitée ({periods_count} périodes)")
                
                elif f['type'] == 'BOXSCORE_DETAILLEE_EXCEL':
                    print(f"\n📊 Extraction Boxscore Détaillée (Excel): {f['filename']}")
                    boxscore_result = extract_boxscore_detaillee_excel(f['path'])
                    if boxscore_result:
                        if boxscore_result.get('period_stats'):
                            db.delete_period_stats(match_id)
                            for period in boxscore_result['period_stats']:
                                db.insert_period_stats(match_id, period)
                            periods_count = len(boxscore_result['period_stats'])
                        
                        with db.get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute('UPDATE matchs SET has_boxscore_detaillee = TRUE WHERE id = %s', (match_id,))
                            conn.commit()
                        print(f"✅ Boxscore Détaillée Excel traitée ({periods_count} périodes)")
                
                elif f['type'] == 'STATS_DETAILLEES':
                    print(f"\n📊 Extraction Statistiques Détaillées: {f['filename']}")
                    stats_result = extract_stats_detaillees(f['path'])
                    if stats_result and stats_result.get('stats_detaillees'):
                        advanced_stats = stats_result['stats_detaillees'].get('advanced', {})
                        # Stocker les stats avancées dans la table stats_equipes
                        if advanced_stats:
                            db.update_match_advanced_stats(match_id, advanced_stats)
                        print(f"✅ Stats détaillées traitées: {list(advanced_stats.keys())}")
                
                elif f['type'] in ['EVALUATION_JOUEUSE', 'ZONES_TIRS', 'POSITION_TIRS']:
                    print(f"⏭️ Fichier ignoré (non nécessaire): {f['filename']}")
                
            except Exception as e:
                print(f"⚠️ Erreur traitement {f['filename']}: {e}")
        
        # Étape 5: Nettoyer les fichiers temporaires
        for f in file_info:
            try:
                os.remove(f['path'])
            except:
                pass
        
        # Retourner le résumé
        return jsonify({
            'success': True,
            'match_id': match_id,
            'files_processed': len(file_info),
            'files_details': [{'filename': f['filename'], 'type': f['type']} for f in file_info],
            'lineups_count': lineups_count,
            'periods_count': periods_count,
            'advanced_stats': list(advanced_stats.keys()) if advanced_stats else [],
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
        
    except Exception as e:
        print(f"❌ Erreur lors de l'upload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/matches/<int:match_id>', methods=['DELETE'])
def delete_match(match_id):
    """Supprimer un match et toutes ses données associées"""
    try:
        print(f"🗑️ Suppression du match {match_id}...")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Supprimer dans l'ordre (foreign keys)
            cursor.execute('DELETE FROM combinaisons_5 WHERE match_id = %s', (match_id,))
            deleted_combos = cursor.rowcount
            
            cursor.execute('DELETE FROM stats_equipes WHERE match_id = %s', (match_id,))
            deleted_teams = cursor.rowcount
            
            cursor.execute('DELETE FROM stats_joueuses WHERE match_id = %s', (match_id,))
            deleted_players = cursor.rowcount
            
            cursor.execute('DELETE FROM matchs WHERE id = %s', (match_id,))
            deleted_match = cursor.rowcount
            
            conn.commit()
        
        if deleted_match == 0:
            return jsonify({
                'success': False,
                'error': f'Match {match_id} non trouvé'
            }), 404
        
        print(f"✅ Match {match_id} supprimé")
        return jsonify({
            'success': True,
            'message': f'Match {match_id} supprimé',
            'deleted': {
                'match': deleted_match,
                'joueuses': deleted_players,
                'equipes': deleted_teams,
                'combinaisons': deleted_combos
            }
        })
        
    except Exception as e:
        print(f"❌ Erreur suppression: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/matches/<int:match_id>/lineups/upload', methods=['POST'])
def upload_lineups(match_id):
    """Upload de l'analyse des 5 pour un match existant"""
    import tempfile
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier fourni'}), 400
    
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'success': False, 'error': 'Fichier PDF requis'}), 400
    
    try:
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(temp_path)
        
        print(f"📊 Extraction Analyse des 5 pour match {match_id}: {temp_path}")
        result = extract_from_pdf(temp_path)
        
        try:
            os.remove(temp_path)
        except:
            pass
        
        if not result or not result.get('lineup_stats'):
            return jsonify({
                'success': False,
                'error': 'Aucune donnée de combinaisons trouvée dans le PDF'
            }), 400
        
        # Supprimer les anciennes combinaisons
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM combinaisons_5 WHERE match_id = %s', (match_id,))
            conn.commit()
        
        # Insérer les nouvelles
        count = 0
        for lineup in result['lineup_stats']:
            db.insert_lineup(match_id, lineup)
            count += 1
        
        print(f"✅ {count} combinaisons insérées pour match {match_id}")
        return jsonify({
            'success': True,
            'count': count,
            'message': f'{count} combinaisons importées'
        })
        
    except Exception as e:
        print(f"❌ Erreur upload lineups: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/matches/<int:match_id>/lineups', methods=['DELETE'])
def delete_lineups(match_id):
    """Supprimer les combinaisons de 5 d'un match"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM combinaisons_5 WHERE match_id = %s', (match_id,))
            deleted = cursor.rowcount
            conn.commit()
        
        return jsonify({
            'success': True,
            'deleted': deleted,
            'message': f'{deleted} combinaisons supprimées'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/matches/<int:match_id>/advanced-stats/upload', methods=['POST'])
def upload_advanced_stats(match_id):
    """Upload de la boxscore détaillée pour un match existant (PDF ou Excel)"""
    import tempfile
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier fourni'}), 400
    
    file = request.files['file']
    filename = file.filename.lower()
    
    if filename == '':
        return jsonify({'success': False, 'error': 'Nom de fichier vide'}), 400
    
    # Accepter PDF et Excel
    allowed_extensions = ['pdf', 'xlsx', 'xls']
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
    if ext not in allowed_extensions:
        return jsonify({'success': False, 'error': 'Fichier PDF ou Excel requis'}), 400
    
    try:
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(temp_path)
        
        print(f"📊 Extraction Boxscore Détaillée pour match {match_id}: {temp_path}")
        
        # Choisir la méthode d'extraction selon le type de fichier
        if ext in ['xlsx', 'xls']:
            result = extract_boxscore_detaillee_excel(temp_path)
        else:
            result = extract_from_pdf(temp_path)
        
        try:
            os.remove(temp_path)
        except:
            pass
        
        if not result:
            return jsonify({
                'success': False,
                'error': 'Erreur lors de l\'extraction du fichier'
            }), 400
        
        # Supprimer les anciennes stats par période
        db.delete_period_stats(match_id)
        
        # Insérer les nouvelles stats par période
        period_count = 0
        if result.get('period_stats'):
            for period in result['period_stats']:
                db.insert_period_stats(match_id, period)
                period_count += 1
        
        # Mettre à jour les stats avancées d'équipe
        if result.get('team_advanced_stats'):
            # Pour l'instant on stocke pour CSMF
            db.update_team_advanced_stats(match_id, 'CSMF PARIS', result['team_advanced_stats'])
        
        # Marquer le match comme ayant une boxscore détaillée
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE matchs SET has_boxscore_detaillee = TRUE WHERE id = %s
            ''', (match_id,))
            conn.commit()
        
        print(f"✅ Boxscore détaillée importée pour match {match_id}: {period_count} périodes")
        return jsonify({
            'success': True,
            'message': f'Stats avancées importées ({period_count} périodes)'
        })
        
    except Exception as e:
        print(f"❌ Erreur upload advanced stats: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/matches/<int:match_id>/advanced-stats', methods=['DELETE'])
def delete_advanced_stats(match_id):
    """Supprimer les stats avancées d'un match"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE matchs SET has_boxscore_detaillee = FALSE WHERE id = %s
            ''', (match_id,))
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Stats avancées supprimées'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/matches/<int:match_id>/stats-detaillees/upload', methods=['POST'])
def upload_stats_detaillees(match_id):
    """Upload de la feuille de statistiques détaillées pour un match existant"""
    import tempfile
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier fourni'}), 400
    
    file = request.files['file']
    filename = file.filename.lower()
    
    if filename == '':
        return jsonify({'success': False, 'error': 'Nom de fichier vide'}), 400
    
    if not filename.endswith('.pdf'):
        return jsonify({'success': False, 'error': 'Fichier PDF requis'}), 400
    
    try:
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(temp_path)
        
        print(f"📊 Extraction Stats Détaillées pour match {match_id}: {temp_path}")
        
        # Extraire les stats détaillées
        result = extract_stats_detaillees(temp_path)
        
        try:
            os.remove(temp_path)
        except:
            pass
        
        if not result or not result.get('stats_detaillees'):
            return jsonify({
                'success': False,
                'error': 'Erreur lors de l\'extraction du fichier (pas de stats détaillées trouvées)'
            }), 400
        
        # Mettre à jour le match avec les stats avancées d'équipe
        stats = result['stats_detaillees'].get('advanced', {})
        players_updated = 0
        
        if stats:
            db.update_match_advanced_stats(match_id, stats)
            print(f"✅ Stats équipe importées pour match {match_id}: {list(stats.keys())}")
        
        # Mettre à jour les stats des joueuses (tirs 2pts int/ext, dunks)
        player_details = result['stats_detaillees'].get('player_details', [])
        if player_details:
            players_updated = db.update_players_detailed_stats(match_id, player_details)
            print(f"✅ Stats joueuses mises à jour: {players_updated} joueuses")
        
        return jsonify({
            'success': True,
            'message': f'Stats détaillées importées ({len(stats)} métriques équipe, {players_updated} joueuses)'
        })
        
    except Exception as e:
        print(f"❌ Erreur upload stats détaillées: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/matches/<int:match_id>/stats-detaillees', methods=['DELETE'])
def delete_stats_detaillees(match_id):
    """Supprimer les stats détaillées d'un match"""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Remettre à NULL toutes les colonnes de stats détaillées
            cursor.execute('''
                UPDATE matchs SET 
                    points_raquette_dom = NULL,
                    points_raquette_ext = NULL,
                    points_contre_attaque_dom = NULL,
                    points_contre_attaque_ext = NULL,
                    points_2eme_chance_dom = NULL,
                    points_2eme_chance_ext = NULL,
                    avantage_max_dom = NULL,
                    avantage_max_ext = NULL,
                    serie_max_dom = NULL,
                    serie_max_ext = NULL,
                    egalites = NULL,
                    changements_leader = NULL,
                    pts_5_depart_dom = NULL,
                    pts_5_depart_ext = NULL,
                    pts_banc_dom = NULL,
                    pts_banc_ext = NULL
                WHERE id = %s
            ''', (match_id,))
            conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Stats détaillées supprimées'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reset-database', methods=['POST'])
def reset_database():
    """
    DANGER: Vide complètement la base de données et recrée les tables proprement
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
        
        deleted_counts = {
            'matchs': 0,
            'stats_joueuses': 0,
            'stats_equipes': 0,
            'combinaisons_5': 0,
            'stats_periodes': 0
        }
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Drop toutes les tables (CASCADE gère les foreign keys)
            # On ne fait pas de DELETE avant car DROP suffit
            cursor.execute('DROP TABLE IF EXISTS stats_periodes CASCADE')
            cursor.execute('DROP TABLE IF EXISTS combinaisons_5 CASCADE')
            cursor.execute('DROP TABLE IF EXISTS stats_equipes CASCADE')
            cursor.execute('DROP TABLE IF EXISTS stats_joueuses CASCADE')
            cursor.execute('DROP TABLE IF EXISTS matchs CASCADE')
            
            conn.commit()
            
            # Recréer les tables avec la bonne structure
            # Table matchs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS matchs (
                    id SERIAL PRIMARY KEY,
                    match_no VARCHAR(50),
                    date DATE,
                    heure VARCHAR(10),
                    competition VARCHAR(255),
                    saison VARCHAR(20),
                    equipe_domicile VARCHAR(255),
                    equipe_exterieur VARCHAR(255),
                    score_domicile INTEGER,
                    score_exterieur INTEGER,
                    q1_domicile INTEGER DEFAULT 0,
                    q1_exterieur INTEGER DEFAULT 0,
                    q2_domicile INTEGER DEFAULT 0,
                    q2_exterieur INTEGER DEFAULT 0,
                    q3_domicile INTEGER DEFAULT 0,
                    q3_exterieur INTEGER DEFAULT 0,
                    q4_domicile INTEGER DEFAULT 0,
                    q4_exterieur INTEGER DEFAULT 0,
                    lieu VARCHAR(255),
                    ville VARCHAR(255),
                    affluence INTEGER,
                    arbitres TEXT,
                    pdf_source VARCHAR(255),
                    pdf_blob_url TEXT,
                    has_boxscore_detaillee BOOLEAN DEFAULT FALSE,
                    -- Stats avancées (depuis Statistiques Détaillées)
                    points_raquette_dom INTEGER DEFAULT 0,
                    points_raquette_ext INTEGER DEFAULT 0,
                    points_contre_attaque_dom INTEGER DEFAULT 0,
                    points_contre_attaque_ext INTEGER DEFAULT 0,
                    points_2eme_chance_dom INTEGER DEFAULT 0,
                    points_2eme_chance_ext INTEGER DEFAULT 0,
                    avantage_max_dom INTEGER DEFAULT 0,
                    avantage_max_ext INTEGER DEFAULT 0,
                    serie_max_dom VARCHAR(20),
                    serie_max_ext VARCHAR(20),
                    egalites INTEGER DEFAULT 0,
                    changements_leader INTEGER DEFAULT 0,
                    pts_5_depart_dom INTEGER DEFAULT 0,
                    pts_5_depart_ext INTEGER DEFAULT 0,
                    pts_banc_dom INTEGER DEFAULT 0,
                    pts_banc_ext INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table stats_joueuses
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stats_joueuses (
                    id SERIAL PRIMARY KEY,
                    match_id INTEGER REFERENCES matchs(id) ON DELETE CASCADE,
                    equipe VARCHAR(255) NOT NULL,
                    numero INTEGER,
                    nom VARCHAR(255) NOT NULL,
                    prenom VARCHAR(255),
                    minutes INTEGER DEFAULT 0,
                    points INTEGER DEFAULT 0,
                    tirs_reussis INTEGER DEFAULT 0,
                    tirs_tentes INTEGER DEFAULT 0,
                    tirs_2pts_reussis INTEGER DEFAULT 0,
                    tirs_2pts_tentes INTEGER DEFAULT 0,
                    tirs_3pts_reussis INTEGER DEFAULT 0,
                    tirs_3pts_tentes INTEGER DEFAULT 0,
                    lf_reussis INTEGER DEFAULT 0,
                    lf_tentes INTEGER DEFAULT 0,
                    rebonds_offensifs INTEGER DEFAULT 0,
                    rebonds_defensifs INTEGER DEFAULT 0,
                    rebonds_total INTEGER DEFAULT 0,
                    passes_decisives INTEGER DEFAULT 0,
                    interceptions INTEGER DEFAULT 0,
                    balles_perdues INTEGER DEFAULT 0,
                    contres INTEGER DEFAULT 0,
                    fautes_provoquees INTEGER DEFAULT 0,
                    fautes_commises INTEGER DEFAULT 0,
                    plus_moins INTEGER DEFAULT 0,
                    evaluation INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table stats_equipes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stats_equipes (
                    id SERIAL PRIMARY KEY,
                    match_id INTEGER REFERENCES matchs(id) ON DELETE CASCADE,
                    equipe VARCHAR(255) NOT NULL,
                    points INTEGER DEFAULT 0,
                    tirs_reussis INTEGER DEFAULT 0,
                    tirs_tentes INTEGER DEFAULT 0,
                    tirs_2pts_reussis INTEGER DEFAULT 0,
                    tirs_2pts_tentes INTEGER DEFAULT 0,
                    tirs_3pts_reussis INTEGER DEFAULT 0,
                    tirs_3pts_tentes INTEGER DEFAULT 0,
                    lf_reussis INTEGER DEFAULT 0,
                    lf_tentes INTEGER DEFAULT 0,
                    rebonds_offensifs INTEGER DEFAULT 0,
                    rebonds_defensifs INTEGER DEFAULT 0,
                    rebonds_total INTEGER DEFAULT 0,
                    passes_decisives INTEGER DEFAULT 0,
                    interceptions INTEGER DEFAULT 0,
                    balles_perdues INTEGER DEFAULT 0,
                    contres INTEGER DEFAULT 0,
                    fautes_commises INTEGER DEFAULT 0,
                    points_balles_perdues INTEGER DEFAULT 0,
                    points_raquette INTEGER DEFAULT 0,
                    points_contre_attaque INTEGER DEFAULT 0,
                    points_2eme_chance INTEGER DEFAULT 0,
                    points_banc INTEGER DEFAULT 0,
                    pct_rebonds_offensifs REAL DEFAULT 0.0,
                    pct_rebonds_defensifs REAL DEFAULT 0.0,
                    pct_rebonds_total REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table combinaisons_5 avec TOUTES les colonnes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS combinaisons_5 (
                    id SERIAL PRIMARY KEY,
                    match_id INTEGER REFERENCES matchs(id) ON DELETE CASCADE,
                    equipe VARCHAR(255) NOT NULL,
                    joueurs TEXT NOT NULL,
                    duree_secondes INTEGER DEFAULT 0,
                    points_marques INTEGER DEFAULT 0,
                    points_encaisses INTEGER DEFAULT 0,
                    plus_minus INTEGER DEFAULT 0,
                    rebonds INTEGER DEFAULT 0,
                    interceptions INTEGER DEFAULT 0,
                    balles_perdues INTEGER DEFAULT 0,
                    passes_decisives INTEGER DEFAULT 0,
                    pts_par_minute REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Table stats_periodes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stats_periodes (
                    id SERIAL PRIMARY KEY,
                    match_id INTEGER REFERENCES matchs(id) ON DELETE CASCADE,
                    equipe VARCHAR(255) NOT NULL,
                    periode INTEGER NOT NULL,
                    points INTEGER DEFAULT 0,
                    tirs_reussis INTEGER DEFAULT 0,
                    tirs_tentes INTEGER DEFAULT 0,
                    tirs_2pts_reussis INTEGER DEFAULT 0,
                    tirs_2pts_tentes INTEGER DEFAULT 0,
                    tirs_3pts_reussis INTEGER DEFAULT 0,
                    tirs_3pts_tentes INTEGER DEFAULT 0,
                    lf_reussis INTEGER DEFAULT 0,
                    lf_tentes INTEGER DEFAULT 0,
                    rebonds_offensifs INTEGER DEFAULT 0,
                    rebonds_defensifs INTEGER DEFAULT 0,
                    rebonds_total INTEGER DEFAULT 0,
                    passes_decisives INTEGER DEFAULT 0,
                    interceptions INTEGER DEFAULT 0,
                    balles_perdues INTEGER DEFAULT 0,
                    fautes_commises INTEGER DEFAULT 0,
                    evaluation INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchs_date ON matchs(date DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stats_match ON stats_joueuses(match_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_equipes_match ON stats_equipes(match_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_lineups_match ON combinaisons_5(match_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_periodes_match ON stats_periodes(match_id)')
            
            conn.commit()
        
        print("✅ Base vidée et tables recréées avec succès!")
        
        return jsonify({
            'success': True,
            'message': 'Base de données vidée et tables recréées',
            'deleted': deleted_counts
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


# ============================================================
# ROUTES CHAT IA ANALYSTE
# ============================================================

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    """Endpoint pour le chat IA analyste"""
    if not CHAT_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module chat non disponible'
        }), 503
    
    data = request.get_json()
    if not data or 'question' not in data:
        return jsonify({
            'success': False,
            'error': 'Question requise'
        }), 400
    
    question = data.get('question', '').strip()
    if not question:
        return jsonify({
            'success': False,
            'error': 'Question vide'
        }), 400
    
    # Récupérer l'historique de conversation si présent
    conversation_history = data.get('conversation_history', [])
    
    # Match spécifique optionnel
    match_id = data.get('match_id')
    
    try:
        result = chat_analyst.chat(
            question=question,
            db=db,
            conversation_history=conversation_history,
            match_id=match_id
        )
        
        return jsonify(result)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'response': f"Erreur lors de l'analyse : {str(e)}"
        }), 500


@app.route('/api/chat/suggestions', methods=['GET'])
def chat_suggestions():
    """Retourne des suggestions de questions"""
    if not CHAT_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Module chat non disponible'
        }), 503
    
    return jsonify({
        'success': True,
        'suggestions': chat_analyst.get_suggested_questions()
    })


@app.route('/api/chat/status', methods=['GET'])
def chat_status():
    """Vérifie si le chat est disponible et configuré"""
    if not CHAT_AVAILABLE:
        return jsonify({
            'available': False,
            'reason': 'Module chat non importé'
        })
    
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({
            'available': False,
            'reason': 'ANTHROPIC_API_KEY non configurée'
        })
    
    return jsonify({
        'available': True,
        'model': 'claude-sonnet-4-20250514'
    })


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
    print("\n🤖 Chat IA Analyste:")
    print("  💬 POST /api/chat                 - Poser une question")
    print("  💡 GET  /api/chat/suggestions     - Questions suggérées")
    print("\n" + "="*60)
    print("🚀 Serveur démarré sur http://0.0.0.0:8000")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=8000, debug=False)
