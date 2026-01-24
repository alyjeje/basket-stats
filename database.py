#!/usr/bin/env python3
"""
Gestionnaire de base de données PostgreSQL avec connection pooling
"""
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from datetime import datetime
from config import Config

class DatabaseManager:
    """Gestionnaire PostgreSQL avec connection pooling"""
    
    def __init__(self):
        """Initialise le pool de connexions"""
        if not Config.DATABASE_URL:
            raise ValueError("DATABASE_URL n'est pas configurée")
        
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=Config.DB_POOL_MIN,
                maxconn=Config.DB_POOL_MAX,
                dsn=Config.DATABASE_URL
            )
            print("✅ Connection pool PostgreSQL créé avec succès")
            self._init_tables()
        except Exception as e:
            print(f"❌ Erreur lors de la création du pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Context manager pour les connexions avec auto-commit/rollback"""
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                self.connection_pool.putconn(conn)
    
    def _init_tables(self):
        """Crée les tables si elles n'existent pas"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # Table matchs
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS matchs (
                        id SERIAL PRIMARY KEY,
                        match_no VARCHAR(50),
                        date DATE NOT NULL,
                        heure VARCHAR(10),
                        competition VARCHAR(255),
                        saison VARCHAR(50),
                        equipe_domicile VARCHAR(255) NOT NULL,
                        equipe_exterieur VARCHAR(255) NOT NULL,
                        score_domicile INTEGER,
                        score_exterieur INTEGER,
                        q1_domicile INTEGER,
                        q1_exterieur INTEGER,
                        q2_domicile INTEGER,
                        q2_exterieur INTEGER,
                        q3_domicile INTEGER,
                        q3_exterieur INTEGER,
                        q4_domicile INTEGER,
                        q4_exterieur INTEGER,
                        lieu VARCHAR(255),
                        ville VARCHAR(255),
                        affluence INTEGER,
                        arbitres TEXT,
                        pdf_source VARCHAR(255),
                        pdf_blob_url TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Ajouter les colonnes Q1-Q4 si elles n'existent pas déjà (migration)
                try:
                    cursor.execute('''
                        ALTER TABLE matchs 
                        ADD COLUMN IF NOT EXISTS q1_domicile INTEGER,
                        ADD COLUMN IF NOT EXISTS q1_exterieur INTEGER,
                        ADD COLUMN IF NOT EXISTS q2_domicile INTEGER,
                        ADD COLUMN IF NOT EXISTS q2_exterieur INTEGER,
                        ADD COLUMN IF NOT EXISTS q3_domicile INTEGER,
                        ADD COLUMN IF NOT EXISTS q3_exterieur INTEGER,
                        ADD COLUMN IF NOT EXISTS q4_domicile INTEGER,
                        ADD COLUMN IF NOT EXISTS q4_exterieur INTEGER,
                        ADD COLUMN IF NOT EXISTS has_boxscore_detaillee BOOLEAN DEFAULT FALSE
                    ''')
                except Exception as e:
                    # Les colonnes existent peut-être déjà
                    pass
                
                # Migration: Ajouter les colonnes stats détaillées à matchs
                try:
                    cursor.execute('''
                        ALTER TABLE matchs 
                        ADD COLUMN IF NOT EXISTS points_raquette_dom INTEGER,
                        ADD COLUMN IF NOT EXISTS points_raquette_ext INTEGER,
                        ADD COLUMN IF NOT EXISTS points_contre_attaque_dom INTEGER,
                        ADD COLUMN IF NOT EXISTS points_contre_attaque_ext INTEGER,
                        ADD COLUMN IF NOT EXISTS points_2eme_chance_dom INTEGER,
                        ADD COLUMN IF NOT EXISTS points_2eme_chance_ext INTEGER,
                        ADD COLUMN IF NOT EXISTS avantage_max_dom INTEGER,
                        ADD COLUMN IF NOT EXISTS avantage_max_ext INTEGER,
                        ADD COLUMN IF NOT EXISTS serie_max_dom VARCHAR(50),
                        ADD COLUMN IF NOT EXISTS serie_max_ext VARCHAR(50),
                        ADD COLUMN IF NOT EXISTS egalites INTEGER,
                        ADD COLUMN IF NOT EXISTS changements_leader INTEGER,
                        ADD COLUMN IF NOT EXISTS pts_5_depart_dom INTEGER,
                        ADD COLUMN IF NOT EXISTS pts_5_depart_ext INTEGER,
                        ADD COLUMN IF NOT EXISTS pts_banc_dom INTEGER,
                        ADD COLUMN IF NOT EXISTS pts_banc_ext INTEGER
                    ''')
                except Exception as e:
                    pass
                
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
                        tirs_2pts_ext_reussis INTEGER DEFAULT 0,
                        tirs_2pts_ext_tentes INTEGER DEFAULT 0,
                        tirs_2pts_int_reussis INTEGER DEFAULT 0,
                        tirs_2pts_int_tentes INTEGER DEFAULT 0,
                        dunks INTEGER DEFAULT 0,
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
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Table combinaisons_5 (lineups) - avec TOUTES les colonnes
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
                
                # Table stats_periodes (stats par quart-temps)
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
                
                # Indexes pour améliorer les performances
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchs_date ON matchs(date DESC)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchs_equipe_dom ON matchs(equipe_domicile)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchs_equipe_ext ON matchs(equipe_exterieur)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_stats_match ON stats_joueuses(match_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_stats_nom ON stats_joueuses(nom)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_stats_equipe ON stats_joueuses(equipe)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_equipes_match ON stats_equipes(match_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_lineups_match ON combinaisons_5(match_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_periodes_match ON stats_periodes(match_id)')
                
                # Migration: Ajouter les colonnes supplémentaires à combinaisons_5
                try:
                    cursor.execute('''
                        ALTER TABLE combinaisons_5 
                        ADD COLUMN IF NOT EXISTS rebonds INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS interceptions INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS balles_perdues INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS passes_decisives INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS pts_par_minute REAL DEFAULT 0.0
                    ''')
                except Exception as e:
                    pass
                
                # Migration: Ajouter les colonnes avancées à stats_joueuses
                try:
                    cursor.execute('''
                        ALTER TABLE stats_joueuses 
                        ADD COLUMN IF NOT EXISTS pts_par_minute REAL DEFAULT 0.0,
                        ADD COLUMN IF NOT EXISTS efficacite REAL DEFAULT 0.0,
                        ADD COLUMN IF NOT EXISTS contres_subis INTEGER DEFAULT 0
                    ''')
                except Exception as e:
                    pass
                
                # Migration: Ajouter les colonnes tirs 2pts int/ext et dunks
                try:
                    cursor.execute('''
                        ALTER TABLE stats_joueuses 
                        ADD COLUMN IF NOT EXISTS tirs_2pts_ext_reussis INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS tirs_2pts_ext_tentes INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS tirs_2pts_int_reussis INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS tirs_2pts_int_tentes INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS dunks INTEGER DEFAULT 0
                    ''')
                except Exception as e:
                    pass
                
                # Migration: Ajouter les colonnes avancées à stats_equipes
                try:
                    cursor.execute('''
                        ALTER TABLE stats_equipes 
                        ADD COLUMN IF NOT EXISTS points_balles_perdues INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS points_raquette INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS points_contre_attaque INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS points_2eme_chance INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS points_banc INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS pct_rebonds_offensifs REAL DEFAULT 0.0,
                        ADD COLUMN IF NOT EXISTS pct_rebonds_defensifs REAL DEFAULT 0.0,
                        ADD COLUMN IF NOT EXISTS pct_rebonds_total REAL DEFAULT 0.0,
                        ADD COLUMN IF NOT EXISTS pts_5_depart INTEGER DEFAULT 0,
                        ADD COLUMN IF NOT EXISTS pts_banc_pct REAL DEFAULT 0.0
                    ''')
                except Exception as e:
                    pass
                
                print("✅ Tables PostgreSQL créées avec succès")
    
    def get_all_matches(self):
        """Récupère tous les matchs triés par date décroissante"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT * FROM matchs 
                    ORDER BY date DESC, id DESC
                ''')
                return [dict(row) for row in cursor.fetchall()]
    
    def get_match_by_id(self, match_id):
        """Récupère un match par son ID avec toutes ses stats"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Récupérer le match
                cursor.execute('SELECT * FROM matchs WHERE id = %s', (match_id,))
                match = cursor.fetchone()
                
                if not match:
                    return None
                
                match_data = dict(match)
                
                # Récupérer les stats des joueuses
                cursor.execute('''
                    SELECT *, fautes_commises as fautes FROM stats_joueuses 
                    WHERE match_id = %s 
                    ORDER BY equipe, points DESC
                ''', (match_id,))
                match_data['stats_joueuses'] = [dict(row) for row in cursor.fetchall()]
                
                # Récupérer les stats des équipes
                cursor.execute('''
                    SELECT * FROM stats_equipes 
                    WHERE match_id = %s
                ''', (match_id,))
                match_data['stats_equipes'] = [dict(row) for row in cursor.fetchall()]
                
                # Récupérer les combinaisons de 5
                cursor.execute('''
                    SELECT * FROM combinaisons_5 
                    WHERE match_id = %s
                    ORDER BY duree_secondes DESC
                ''', (match_id,))
                lineups_raw = [dict(row) for row in cursor.fetchall()]
                
                # Transformer les noms de champs pour le frontend
                import math
                
                def safe_val(val, default=0):
                    """Protège contre NaN et None"""
                    if val is None:
                        return default
                    try:
                        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                            return default
                        return val
                    except:
                        return default
                
                match_data['stats_cinq_majeur'] = []
                for lineup in lineups_raw:
                    # Convertir duree_secondes en temps_jeu (format MM:SS)
                    duree = safe_val(lineup.get('duree_secondes', 0), 0)
                    minutes = duree // 60
                    secondes = duree % 60
                    temps_jeu = f"{minutes}:{secondes:02d}"
                    
                    match_data['stats_cinq_majeur'].append({
                        'id': lineup.get('id'),
                        'match_id': lineup.get('match_id'),
                        'equipe': lineup.get('equipe'),
                        'joueurs': lineup.get('joueurs'),
                        'temps_jeu': temps_jeu,
                        'temps_secondes': duree,  # Pour le frontend
                        'duree_secondes': duree,  # Pour compatibilité
                        'score_pour': safe_val(lineup.get('points_marques', 0), 0),
                        'score_contre': safe_val(lineup.get('points_encaisses', 0), 0),
                        'ecart': safe_val(lineup.get('plus_minus', 0), 0),
                        'rebonds': safe_val(lineup.get('rebonds', 0), 0),
                        'interceptions': safe_val(lineup.get('interceptions', 0), 0),
                        'balles_perdues': safe_val(lineup.get('balles_perdues', 0), 0),
                        'passes_decisives': safe_val(lineup.get('passes_decisives', 0), 0),
                        'pts_par_minute': safe_val(lineup.get('pts_par_minute', 0.0), 0.0)
                    })
                
                # Garder aussi combinaisons_5 pour compatibilité
                match_data['combinaisons_5'] = match_data['stats_cinq_majeur']
                
                # Récupérer les stats par période
                cursor.execute('''
                    SELECT * FROM stats_periodes 
                    WHERE match_id = %s
                    ORDER BY equipe, periode
                ''', (match_id,))
                match_data['stats_periodes'] = [dict(row) for row in cursor.fetchall()]
                
                # Si on a des stats joueuses, considérer qu'on a la boxscore détaillée
                if match_data.get('stats_joueuses') and len(match_data['stats_joueuses']) > 0:
                    match_data['has_boxscore_detaillee'] = True
                
                return match_data
    
    def insert_match(self, match_data):
        """Insère un nouveau match et retourne son ID"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO matchs 
                    (match_no, date, heure, competition, saison, equipe_domicile, equipe_exterieur, 
                     score_domicile, score_exterieur, 
                     q1_domicile, q1_exterieur, q2_domicile, q2_exterieur,
                     q3_domicile, q3_exterieur, q4_domicile, q4_exterieur,
                     lieu, ville, affluence, arbitres, 
                     pdf_source, pdf_blob_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (
                    match_data.get('match_no'),
                    match_data.get('date'),
                    match_data.get('heure'),
                    match_data.get('competition'),
                    match_data.get('saison'),
                    match_data.get('equipe_domicile'),
                    match_data.get('equipe_exterieur'),
                    match_data.get('score_domicile'),
                    match_data.get('score_exterieur'),
                    match_data.get('q1_domicile'),
                    match_data.get('q1_exterieur'),
                    match_data.get('q2_domicile'),
                    match_data.get('q2_exterieur'),
                    match_data.get('q3_domicile'),
                    match_data.get('q3_exterieur'),
                    match_data.get('q4_domicile'),
                    match_data.get('q4_exterieur'),
                    match_data.get('lieu'),
                    match_data.get('ville'),
                    match_data.get('affluence'),
                    match_data.get('arbitres'),
                    match_data.get('pdf_source'),
                    match_data.get('pdf_blob_url')
                ))
                match_id = cursor.fetchone()[0]
                print(f"✅ Match {match_id} inséré")
                return match_id
    
    def insert_player_stats(self, match_id, player_data):
        """Insère les stats d'une joueuse avec mapping des clés"""
        
        # Helper pour parser les tirs "3/8" -> (3, 8)
        def parse_tirs(val):
            if isinstance(val, str) and '/' in val:
                parts = val.split('/')
                try:
                    return int(parts[0]), int(parts[1])
                except:
                    return 0, 0
            return 0, 0
        
        # Helper pour parser les minutes "28:13" -> 28
        def parse_minutes(val):
            if isinstance(val, str) and ':' in val:
                try:
                    parts = val.split(':')
                    return int(parts[0])
                except:
                    return 0
            try:
                return int(val) if val else 0
            except:
                return 0
        
        # Parser les tirs
        tirs_2pts_r, tirs_2pts_t = parse_tirs(player_data.get('tirs_2pts', '0/0'))
        tirs_3pts_r, tirs_3pts_t = parse_tirs(player_data.get('tirs_3pts', '0/0'))
        tirs_tot_r, tirs_tot_t = parse_tirs(player_data.get('tirs_total', '0/0'))
        lf_r, lf_t = parse_tirs(player_data.get('lancers_francs', '0/0'))
        
        # Tirs 2pts intérieur/extérieur (depuis Feuille Stats Détaillées)
        tirs_2pts_ext_r, tirs_2pts_ext_t = parse_tirs(player_data.get('tirs_2pts_ext', '0/0'))
        tirs_2pts_int_r, tirs_2pts_int_t = parse_tirs(player_data.get('tirs_2pts_int', '0/0'))
        
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO stats_joueuses 
                    (match_id, equipe, numero, nom, prenom, minutes, points,
                     tirs_reussis, tirs_tentes, tirs_2pts_reussis, tirs_2pts_tentes,
                     tirs_2pts_ext_reussis, tirs_2pts_ext_tentes, 
                     tirs_2pts_int_reussis, tirs_2pts_int_tentes, dunks,
                     tirs_3pts_reussis, tirs_3pts_tentes, lf_reussis, lf_tentes,
                     rebonds_offensifs, rebonds_defensifs, rebonds_total, passes_decisives,
                     interceptions, balles_perdues, contres,
                     fautes_provoquees, fautes_commises, plus_moins, evaluation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    match_id,
                    player_data.get('equipe'),
                    player_data.get('numero'),
                    player_data.get('nom'),
                    player_data.get('prenom'),
                    parse_minutes(player_data.get('minutes', 0)),
                    player_data.get('points', 0),
                    # Tirs - utiliser les valeurs parsées ou les clés directes
                    player_data.get('tirs_reussis', tirs_tot_r),
                    player_data.get('tirs_tentes', tirs_tot_t),
                    player_data.get('tirs_2pts_reussis', tirs_2pts_r),
                    player_data.get('tirs_2pts_tentes', tirs_2pts_t),
                    # Tirs 2pts ext/int
                    player_data.get('tirs_2pts_ext_reussis', tirs_2pts_ext_r),
                    player_data.get('tirs_2pts_ext_tentes', tirs_2pts_ext_t),
                    player_data.get('tirs_2pts_int_reussis', tirs_2pts_int_r),
                    player_data.get('tirs_2pts_int_tentes', tirs_2pts_int_t),
                    player_data.get('dunks', 0),
                    player_data.get('tirs_3pts_reussis', tirs_3pts_r),
                    player_data.get('tirs_3pts_tentes', tirs_3pts_t),
                    player_data.get('lf_reussis', lf_r),
                    player_data.get('lf_tentes', lf_t),
                    # Rebonds - mapper les deux formats
                    player_data.get('rebonds_offensifs', player_data.get('rebonds_off', 0)),
                    player_data.get('rebonds_defensifs', player_data.get('rebonds_def', 0)),
                    player_data.get('rebonds_total', player_data.get('rebonds_tot', 0)),
                    # Autres stats - mapper les deux formats
                    player_data.get('passes_decisives', player_data.get('passes_dec', 0)),
                    player_data.get('interceptions', 0),
                    player_data.get('balles_perdues', 0),
                    player_data.get('contres', 0),
                    player_data.get('fautes_provoquees', 0),
                    player_data.get('fautes_commises', player_data.get('fautes', 0)),
                    player_data.get('plus_moins', 0),
                    player_data.get('evaluation', player_data.get('eval', 0))
                ))
    
    def insert_team_stats(self, match_id, team_data):
        """Insère les stats d'une équipe avec mapping des clés"""
        
        # Helper pour parser les tirs "3/8" -> (3, 8)
        def parse_tirs(val):
            if isinstance(val, str) and '/' in val:
                parts = val.split('/')
                try:
                    return int(parts[0]), int(parts[1])
                except:
                    return 0, 0
            return 0, 0
        
        # Parser les tirs
        tirs_2pts_r, tirs_2pts_t = parse_tirs(team_data.get('tirs_2pts', '0/0'))
        tirs_3pts_r, tirs_3pts_t = parse_tirs(team_data.get('tirs_3pts', '0/0'))
        tirs_tot_r, tirs_tot_t = parse_tirs(team_data.get('tirs_total', '0/0'))
        lf_r, lf_t = parse_tirs(team_data.get('lancers_francs', '0/0'))
        
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO stats_equipes 
                    (match_id, equipe, points, tirs_reussis, tirs_tentes,
                     tirs_2pts_reussis, tirs_2pts_tentes, tirs_3pts_reussis, tirs_3pts_tentes,
                     lf_reussis, lf_tentes, rebonds_offensifs, rebonds_defensifs, rebonds_total,
                     passes_decisives, interceptions, balles_perdues, contres, fautes_commises)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    match_id,
                    team_data.get('equipe'),
                    team_data.get('points', 0),
                    team_data.get('tirs_reussis', tirs_tot_r),
                    team_data.get('tirs_tentes', tirs_tot_t),
                    team_data.get('tirs_2pts_reussis', tirs_2pts_r),
                    team_data.get('tirs_2pts_tentes', tirs_2pts_t),
                    team_data.get('tirs_3pts_reussis', tirs_3pts_r),
                    team_data.get('tirs_3pts_tentes', tirs_3pts_t),
                    team_data.get('lf_reussis', lf_r),
                    team_data.get('lf_tentes', lf_t),
                    team_data.get('rebonds_offensifs', team_data.get('rebonds_off', 0)),
                    team_data.get('rebonds_defensifs', team_data.get('rebonds_def', 0)),
                    team_data.get('rebonds_total', team_data.get('rebonds_tot', 0)),
                    team_data.get('passes_decisives', team_data.get('passes_dec', 0)),
                    team_data.get('interceptions', 0),
                    team_data.get('balles_perdues', 0),
                    team_data.get('contres', 0),
                    team_data.get('fautes_commises', team_data.get('fautes', 0))
                ))
    
    def insert_lineup(self, match_id, lineup_data):
        """Insère une combinaison de 5"""
        import math
        
        # Protection contre NaN et valeurs invalides
        def safe_float(val, default=0.0):
            try:
                f = float(val) if val is not None else default
                return default if (math.isnan(f) or math.isinf(f)) else f
            except:
                return default
        
        def safe_int(val, default=0):
            try:
                return int(val) if val is not None else default
            except:
                return default
        
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO combinaisons_5 
                    (match_id, equipe, joueurs, duree_secondes, points_marques, points_encaisses, plus_minus,
                     rebonds, interceptions, balles_perdues, passes_decisives, pts_par_minute)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    match_id,
                    lineup_data.get('equipe'),
                    lineup_data.get('joueurs'),
                    safe_int(lineup_data.get('temps_secondes', lineup_data.get('duree_secondes', 0))),
                    safe_int(lineup_data.get('score_pour', lineup_data.get('points_marques', 0))),
                    safe_int(lineup_data.get('score_contre', lineup_data.get('points_encaisses', 0))),
                    safe_int(lineup_data.get('ecart', lineup_data.get('plus_minus', 0))),
                    safe_int(lineup_data.get('rebonds', 0)),
                    safe_int(lineup_data.get('interceptions', 0)),
                    safe_int(lineup_data.get('balles_perdues', 0)),
                    safe_int(lineup_data.get('passes_decisives', 0)),
                    safe_float(lineup_data.get('pts_par_minute', 0.0))
                ))
    
    def get_lineups_by_match(self, match_id):
        """Récupère les combinaisons de 5 d'un match avec mapping des champs pour le frontend"""
        import math
        
        def safe_val(val, default=0):
            """Protège contre NaN et None"""
            if val is None:
                return default
            try:
                if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                    return default
                return val
            except:
                return default
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT * FROM combinaisons_5 
                    WHERE match_id = %s
                    ORDER BY duree_secondes DESC
                ''', (match_id,))
                
                result = []
                for row in cursor.fetchall():
                    lineup = dict(row)
                    duree = safe_val(lineup.get('duree_secondes', 0), 0)
                    minutes = duree // 60
                    secondes = duree % 60
                    
                    result.append({
                        'id': lineup.get('id'),
                        'match_id': lineup.get('match_id'),
                        'equipe': lineup.get('equipe'),
                        'joueurs': lineup.get('joueurs'),
                        'temps_jeu': f"{minutes}:{secondes:02d}",
                        'temps_secondes': duree,
                        'duree_secondes': duree,
                        'score_pour': safe_val(lineup.get('points_marques', 0), 0),
                        'score_contre': safe_val(lineup.get('points_encaisses', 0), 0),
                        'ecart': safe_val(lineup.get('plus_minus', 0), 0),
                        'rebonds': safe_val(lineup.get('rebonds', 0), 0),
                        'interceptions': safe_val(lineup.get('interceptions', 0), 0),
                        'balles_perdues': safe_val(lineup.get('balles_perdues', 0), 0),
                        'passes_decisives': safe_val(lineup.get('passes_decisives', 0), 0),
                        'pts_par_minute': safe_val(lineup.get('pts_par_minute', 0.0), 0.0)
                    })
                
                return result
    
    def insert_period_stats(self, match_id, period_data):
        """Insère les stats d'une période"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO stats_periodes 
                    (match_id, equipe, periode, points, tirs_reussis, tirs_tentes,
                     tirs_2pts_reussis, tirs_2pts_tentes, tirs_3pts_reussis, tirs_3pts_tentes,
                     lf_reussis, lf_tentes, rebonds_offensifs, rebonds_defensifs, rebonds_total,
                     passes_decisives, interceptions, balles_perdues, fautes_commises, evaluation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    match_id,
                    period_data.get('equipe'),
                    period_data.get('periode'),
                    period_data.get('points', 0),
                    period_data.get('tirs_reussis', 0),
                    period_data.get('tirs_tentes', 0),
                    period_data.get('tirs_2pts_reussis', 0),
                    period_data.get('tirs_2pts_tentes', 0),
                    period_data.get('tirs_3pts_reussis', 0),
                    period_data.get('tirs_3pts_tentes', 0),
                    period_data.get('lf_reussis', 0),
                    period_data.get('lf_tentes', 0),
                    period_data.get('rebonds_offensifs', 0),
                    period_data.get('rebonds_defensifs', 0),
                    period_data.get('rebonds_total', 0),
                    period_data.get('passes_decisives', 0),
                    period_data.get('interceptions', 0),
                    period_data.get('balles_perdues', 0),
                    period_data.get('fautes_commises', 0),
                    period_data.get('evaluation', 0)
                ))
    
    def get_period_stats_by_match(self, match_id):
        """Récupère les stats par période d'un match"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT * FROM stats_periodes 
                    WHERE match_id = %s
                    ORDER BY equipe, periode
                ''', (match_id,))
                return [dict(row) for row in cursor.fetchall()]
    
    def update_team_advanced_stats(self, match_id, equipe, advanced_data):
        """Met à jour les stats avancées d'une équipe"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    UPDATE stats_equipes SET
                        points_balles_perdues = %s,
                        points_raquette = %s,
                        points_contre_attaque = %s,
                        points_2eme_chance = %s,
                        points_banc = %s,
                        pct_rebonds_offensifs = %s,
                        pct_rebonds_defensifs = %s,
                        pct_rebonds_total = %s
                    WHERE match_id = %s AND equipe = %s
                ''', (
                    advanced_data.get('points_balles_perdues', 0),
                    advanced_data.get('points_raquette', 0),
                    advanced_data.get('points_contre_attaque', 0),
                    advanced_data.get('points_2eme_chance', 0),
                    advanced_data.get('points_banc', 0),
                    advanced_data.get('pct_rebonds_offensifs', 0.0),
                    advanced_data.get('pct_rebonds_defensifs', 0.0),
                    advanced_data.get('pct_rebonds_total', 0.0),
                    match_id,
                    equipe
                ))
    
    def delete_period_stats(self, match_id):
        """Supprime les stats par période d'un match"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('DELETE FROM stats_periodes WHERE match_id = %s', (match_id,))
                return cursor.rowcount
    
    def update_match_advanced_stats(self, match_id, advanced_data):
        """Met à jour les stats avancées d'un match (depuis Statistiques Détaillées)"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # Détecter si c'est pour l'équipe domicile (CSMF généralement)
                cursor.execute('SELECT equipe_domicile FROM matchs WHERE id = %s', (match_id,))
                result = cursor.fetchone()
                is_csmf_home = result and 'CSMF' in str(result[0]).upper()
                
                # Suffixe pour les colonnes
                suffix = '_dom' if is_csmf_home else '_ext'
                
                updates = []
                values = []
                
                if 'points_raquette' in advanced_data:
                    updates.append(f'points_raquette{suffix} = %s')
                    values.append(advanced_data['points_raquette'])
                
                if 'points_contre_attaque' in advanced_data:
                    updates.append(f'points_contre_attaque{suffix} = %s')
                    values.append(advanced_data['points_contre_attaque'])
                
                if 'points_2eme_chance' in advanced_data:
                    updates.append(f'points_2eme_chance{suffix} = %s')
                    values.append(advanced_data['points_2eme_chance'])
                
                if 'avantage_max' in advanced_data:
                    updates.append(f'avantage_max{suffix} = %s')
                    values.append(advanced_data['avantage_max'])
                
                if 'serie_max' in advanced_data:
                    updates.append(f'serie_max{suffix} = %s')
                    values.append(advanced_data['serie_max'])
                
                if 'egalites' in advanced_data:
                    updates.append('egalites = %s')
                    values.append(advanced_data['egalites'])
                
                if 'changements_leader' in advanced_data:
                    updates.append('changements_leader = %s')
                    values.append(advanced_data['changements_leader'])
                
                # Stats 5 de départ / banc
                if 'cinq_depart' in advanced_data and 'points' in advanced_data['cinq_depart']:
                    updates.append(f'pts_5_depart{suffix} = %s')
                    values.append(advanced_data['cinq_depart']['points'])
                
                if 'banc' in advanced_data and 'points' in advanced_data['banc']:
                    updates.append(f'pts_banc{suffix} = %s')
                    values.append(advanced_data['banc']['points'])
                
                if updates:
                    values.append(match_id)
                    query = f"UPDATE matchs SET {', '.join(updates)} WHERE id = %s"
                    cursor.execute(query, values)
                    print(f"✅ Stats avancées mises à jour pour match {match_id}")
    
    def update_players_detailed_stats(self, match_id, player_details):
        """
        Met à jour les stats détaillées des joueuses (tirs 2pts int/ext, dunks)
        à partir des données extraites du fichier Feuille Statistiques Détaillées
        """
        # Helper pour parser "1/5" -> (1, 5)
        def parse_tirs(val):
            if isinstance(val, str) and '/' in val:
                parts = val.split('/')
                try:
                    return int(parts[0]), int(parts[1])
                except:
                    return 0, 0
            return 0, 0
        
        updated_count = 0
        
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                for player in player_details:
                    nom = player.get('nom', '').strip()
                    if not nom:
                        continue
                    
                    # Parser les tirs
                    ext_r, ext_t = parse_tirs(player.get('tirs_2pts_ext', '0/0'))
                    int_r, int_t = parse_tirs(player.get('tirs_2pts_int', '0/0'))
                    dunks = player.get('dunks', 0)
                    
                    # Normaliser le nom pour la recherche (enlever parenthèses comme "(C)")
                    nom_search = nom.replace('(C)', '').replace('(c)', '').strip()
                    
                    # Mettre à jour la joueuse dans ce match
                    cursor.execute('''
                        UPDATE stats_joueuses 
                        SET tirs_2pts_ext_reussis = %s,
                            tirs_2pts_ext_tentes = %s,
                            tirs_2pts_int_reussis = %s,
                            tirs_2pts_int_tentes = %s,
                            dunks = %s
                        WHERE match_id = %s AND nom ILIKE %s
                    ''', (ext_r, ext_t, int_r, int_t, dunks, match_id, f'%{nom_search}%'))
                    
                    if cursor.rowcount > 0:
                        updated_count += cursor.rowcount
                        print(f"  ✓ {nom}: 2pts Ext={ext_r}/{ext_t}, Int={int_r}/{int_t}, Dunks={dunks}")
                
                conn.commit()
        
        return updated_count
    
    def search_matches_by_opponent(self, opponent):
        """Recherche des matchs par nom d'adversaire"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT * FROM matchs 
                    WHERE equipe_domicile ILIKE %s OR equipe_exterieur ILIKE %s
                    ORDER BY date DESC
                ''', (f'%{opponent}%', f'%{opponent}%'))
                return [dict(row) for row in cursor.fetchall()]
    
    def get_player_stats(self, player_name):
        """Récupère toutes les stats d'une joueuse"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT sj.*, sj.fautes_commises as fautes, m.date, m.equipe_domicile, m.equipe_exterieur, 
                           m.score_domicile, m.score_exterieur
                    FROM stats_joueuses sj
                    JOIN matchs m ON sj.match_id = m.id
                    WHERE sj.nom ILIKE %s
                    ORDER BY m.date DESC
                ''', (f'%{player_name}%',))
                return [dict(row) for row in cursor.fetchall()]
    
    def health_check(self):
        """Vérifie que la connexion à la base fonctionne"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('SELECT 1')
                    cursor.fetchone()
            return True
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False
    
    def close(self):
        """Ferme le pool de connexions"""
        if hasattr(self, 'connection_pool'):
            self.connection_pool.closeall()
            print("✅ Connection pool fermé")

# Instance globale
db = None

def get_db():
    """Retourne l'instance de DatabaseManager (singleton)"""
    global db
    if db is None:
        db = DatabaseManager()
    return db
