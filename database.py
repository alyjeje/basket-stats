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
                        ADD COLUMN IF NOT EXISTS q4_exterieur INTEGER
                    ''')
                except Exception as e:
                    # Les colonnes existent peut-être déjà
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
                
                # Table combinaisons_5 (lineups)
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
    
    def get_latest_match(self):
        """Récupère le dernier match en date avec toutes ses stats"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Récupérer le match le plus récent
                cursor.execute('''
                    SELECT * FROM matchs 
                    ORDER BY date DESC, id DESC 
                    LIMIT 1
                ''')
                match = cursor.fetchone()
                
                if not match:
                    return None
                
                match_data = dict(match)
                match_id = match_data['id']
                
                # Récupérer les stats des joueuses
                cursor.execute('''
                    SELECT * FROM stats_joueuses 
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
                match_data['combinaisons_5'] = [dict(row) for row in cursor.fetchall()]
                
                return match_data
    
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
                    SELECT * FROM stats_joueuses 
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
                match_data['combinaisons_5'] = [dict(row) for row in cursor.fetchall()]
                
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
        """Insère les stats d'une joueuse"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO stats_joueuses 
                    (match_id, equipe, numero, nom, prenom, minutes, points,
                     tirs_reussis, tirs_tentes, tirs_2pts_reussis, tirs_2pts_tentes,
                     tirs_3pts_reussis, tirs_3pts_tentes, lf_reussis, lf_tentes,
                     rebonds_offensifs, rebonds_defensifs, rebonds_total, passes_decisives,
                     interceptions, balles_perdues, contres,
                     fautes_provoquees, fautes_commises, plus_moins, evaluation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    match_id,
                    player_data.get('equipe'),
                    player_data.get('numero'),
                    player_data.get('nom'),
                    player_data.get('prenom'),
                    player_data.get('minutes', 0),
                    player_data.get('points', 0),
                    player_data.get('tirs_reussis', 0),
                    player_data.get('tirs_tentes', 0),
                    player_data.get('tirs_2pts_reussis', 0),
                    player_data.get('tirs_2pts_tentes', 0),
                    player_data.get('tirs_3pts_reussis', 0),
                    player_data.get('tirs_3pts_tentes', 0),
                    player_data.get('lf_reussis', 0),
                    player_data.get('lf_tentes', 0),
                    player_data.get('rebonds_offensifs', 0),
                    player_data.get('rebonds_defensifs', 0),
                    player_data.get('rebonds_total', 0),
                    player_data.get('passes_decisives', 0),
                    player_data.get('interceptions', 0),
                    player_data.get('balles_perdues', 0),
                    player_data.get('contres', 0),
                    player_data.get('fautes_provoquees', 0),
                    player_data.get('fautes_commises', 0),
                    player_data.get('plus_moins', 0),
                    player_data.get('evaluation', 0)
                ))
    
    def insert_team_stats(self, match_id, team_data):
        """Insère les stats d'une équipe"""
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
                    team_data.get('tirs_reussis', 0),
                    team_data.get('tirs_tentes', 0),
                    team_data.get('tirs_2pts_reussis', 0),
                    team_data.get('tirs_2pts_tentes', 0),
                    team_data.get('tirs_3pts_reussis', 0),
                    team_data.get('tirs_3pts_tentes', 0),
                    team_data.get('lf_reussis', 0),
                    team_data.get('lf_tentes', 0),
                    team_data.get('rebonds_offensifs', 0),
                    team_data.get('rebonds_defensifs', 0),
                    team_data.get('rebonds_total', 0),
                    team_data.get('passes_decisives', 0),
                    team_data.get('interceptions', 0),
                    team_data.get('balles_perdues', 0),
                    team_data.get('contres', 0),
                    team_data.get('fautes_commises', 0)
                ))
    
    def insert_lineup(self, match_id, lineup_data):
        """Insère une combinaison de 5"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO combinaisons_5 
                    (match_id, equipe, joueurs, duree_secondes, points_marques, points_encaisses, plus_minus)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', (
                    match_id,
                    lineup_data.get('equipe'),
                    lineup_data.get('joueurs'),
                    lineup_data.get('duree_secondes', 0),
                    lineup_data.get('points_marques', 0),
                    lineup_data.get('points_encaisses', 0),
                    lineup_data.get('plus_minus', 0)
                ))
    
    def get_lineups_by_match(self, match_id):
        """Récupère les combinaisons de 5 d'un match"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('''
                    SELECT * FROM combinaisons_5 
                    WHERE match_id = %s
                    ORDER BY duree_secondes DESC
                ''', (match_id,))
                return [dict(row) for row in cursor.fetchall()]
    
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
                    SELECT sj.*, m.date, m.equipe_domicile, m.equipe_exterieur, 
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
