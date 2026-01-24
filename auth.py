#!/usr/bin/env python3
"""
Module d'authentification multi-tenant pour BasketStats Pro
Gère les clubs, utilisateurs, sessions et permissions
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify, g
import bcrypt
import jwt

# Clé secrète pour JWT (à mettre dans les variables d'environnement en prod)
JWT_SECRET = os.environ.get('JWT_SECRET', 'basketstats-secret-key-change-in-production')
JWT_EXPIRATION_HOURS = 24 * 7  # 7 jours

# Plans disponibles
PLANS = {
    'trial': {
        'name': 'Essai',
        'max_teams': 1,
        'max_users': 2,
        'features': ['basic_stats', 'import_pdf'],
        'price_monthly': 0,
        'price_yearly': 0,
        'trial_days': 14
    },
    'essentiel': {
        'name': 'Essentiel',
        'max_teams': 1,
        'max_users': 2,
        'features': ['basic_stats', 'import_pdf', 'season_history'],
        'price_monthly': 39,
        'price_yearly': 380
    },
    'pro': {
        'name': 'Pro',
        'max_teams': 3,
        'max_users': 5,
        'features': ['basic_stats', 'import_pdf', 'season_history', 'lineups', 'advanced_stats', 'export'],
        'price_monthly': 79,
        'price_yearly': 780
    },
    'premium': {
        'name': 'Premium',
        'max_teams': 999,
        'max_users': 999,
        'features': ['basic_stats', 'import_pdf', 'season_history', 'lineups', 'advanced_stats', 'export', 'ai_chat', 'priority_support'],
        'price_monthly': 139,
        'price_yearly': 1380
    }
}


class AuthManager:
    """Gestionnaire d'authentification"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self._init_auth_tables()
    
    def _init_auth_tables(self):
        """Crée les tables d'authentification si elles n'existent pas"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                # Table clubs
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS clubs (
                        id SERIAL PRIMARY KEY,
                        nom VARCHAR(255) NOT NULL,
                        slug VARCHAR(100) UNIQUE NOT NULL,
                        logo_url TEXT,
                        couleur_primaire VARCHAR(7) DEFAULT '#1e40af',
                        couleur_secondaire VARCHAR(7) DEFAULT '#3b82f6',
                        plan VARCHAR(50) DEFAULT 'trial',
                        plan_expire_at TIMESTAMP,
                        stripe_customer_id VARCHAR(255),
                        stripe_subscription_id VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Table users
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        club_id INTEGER REFERENCES clubs(id) ON DELETE CASCADE,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password_hash VARCHAR(255) NOT NULL,
                        nom VARCHAR(255),
                        prenom VARCHAR(255),
                        role VARCHAR(50) DEFAULT 'member',
                        is_active BOOLEAN DEFAULT TRUE,
                        last_login TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Table sessions (pour tokens de refresh si besoin)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                        token_hash VARCHAR(255) NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        ip_address VARCHAR(50),
                        user_agent TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Table invitations
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS invitations (
                        id SERIAL PRIMARY KEY,
                        club_id INTEGER REFERENCES clubs(id) ON DELETE CASCADE,
                        email VARCHAR(255) NOT NULL,
                        role VARCHAR(50) DEFAULT 'member',
                        token VARCHAR(255) UNIQUE NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        used_at TIMESTAMP,
                        created_by INTEGER REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Ajouter club_id à la table matchs si pas présent
                try:
                    cursor.execute('''
                        ALTER TABLE matchs 
                        ADD COLUMN IF NOT EXISTS club_id INTEGER REFERENCES clubs(id) ON DELETE CASCADE
                    ''')
                except:
                    pass
                
                # Index pour performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_club ON users(club_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_matchs_club ON matchs(club_id)')
                
                print("✅ Tables d'authentification créées")
    
    # ============================================
    # GESTION DES CLUBS
    # ============================================
    
    def create_club(self, nom, email, password, prenom=None, nom_user=None):
        """Crée un nouveau club avec son admin"""
        # Générer un slug unique
        slug = self._generate_slug(nom)
        
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                # Vérifier si l'email existe déjà
                cursor.execute('SELECT id FROM users WHERE email = %s', (email.lower(),))
                if cursor.fetchone():
                    raise ValueError("Cet email est déjà utilisé")
                
                # Créer le club
                cursor.execute('''
                    INSERT INTO clubs (nom, slug, plan, plan_expire_at)
                    VALUES (%s, %s, 'trial', %s)
                    RETURNING id
                ''', (nom, slug, datetime.now() + timedelta(days=14)))
                club_id = cursor.fetchone()[0]
                
                # Créer l'admin du club
                password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute('''
                    INSERT INTO users (club_id, email, password_hash, nom, prenom, role)
                    VALUES (%s, %s, %s, %s, %s, 'admin')
                    RETURNING id
                ''', (club_id, email.lower(), password_hash, nom_user, prenom))
                user_id = cursor.fetchone()[0]
                
                print(f"✅ Club '{nom}' créé avec admin {email}")
                
                return {
                    'club_id': club_id,
                    'user_id': user_id,
                    'slug': slug
                }
    
    def get_club(self, club_id):
        """Récupère les infos d'un club"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT id, nom, slug, logo_url, couleur_primaire, couleur_secondaire,
                           plan, plan_expire_at, created_at
                    FROM clubs WHERE id = %s
                ''', (club_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'nom': row[1],
                        'slug': row[2],
                        'logo_url': row[3],
                        'couleur_primaire': row[4],
                        'couleur_secondaire': row[5],
                        'plan': row[6],
                        'plan_expire_at': row[7].isoformat() if row[7] else None,
                        'created_at': row[8].isoformat() if row[8] else None,
                        'plan_details': PLANS.get(row[6], PLANS['trial'])
                    }
                return None
    
    def update_club(self, club_id, **kwargs):
        """Met à jour les infos d'un club"""
        allowed_fields = ['nom', 'logo_url', 'couleur_primaire', 'couleur_secondaire']
        updates = []
        values = []
        
        for field in allowed_fields:
            if field in kwargs:
                updates.append(f"{field} = %s")
                values.append(kwargs[field])
        
        if not updates:
            return False
        
        values.append(club_id)
        
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f'''
                    UPDATE clubs SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                ''', values)
                return cursor.rowcount > 0
    
    def _generate_slug(self, nom):
        """Génère un slug unique pour le club"""
        import re
        # Normaliser le nom
        slug = nom.lower()
        slug = re.sub(r'[^a-z0-9]+', '-', slug)
        slug = slug.strip('-')
        
        # Vérifier l'unicité
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                base_slug = slug
                counter = 1
                while True:
                    cursor.execute('SELECT id FROM clubs WHERE slug = %s', (slug,))
                    if not cursor.fetchone():
                        break
                    slug = f"{base_slug}-{counter}"
                    counter += 1
        
        return slug
    
    # ============================================
    # GESTION DES UTILISATEURS
    # ============================================
    
    def login(self, email, password):
        """Authentifie un utilisateur et retourne un token JWT"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT u.id, u.club_id, u.email, u.password_hash, u.nom, u.prenom, u.role, u.is_active,
                           c.nom as club_nom, c.slug as club_slug, c.plan, c.plan_expire_at,
                           c.logo_url, c.couleur_primaire, c.couleur_secondaire
                    FROM users u
                    JOIN clubs c ON u.club_id = c.id
                    WHERE u.email = %s
                ''', (email.lower(),))
                row = cursor.fetchone()
                
                if not row:
                    raise ValueError("Email ou mot de passe incorrect")
                
                user_id, club_id, email, password_hash, nom, prenom, role, is_active, \
                club_nom, club_slug, plan, plan_expire_at, logo_url, couleur_primaire, couleur_secondaire = row
                
                if not is_active:
                    raise ValueError("Ce compte est désactivé")
                
                # Vérifier le mot de passe
                if not bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8')):
                    raise ValueError("Email ou mot de passe incorrect")
                
                # Vérifier si le plan n'est pas expiré
                plan_active = True
                if plan_expire_at and plan_expire_at < datetime.now():
                    plan_active = False
                
                # Générer le token JWT
                token = self._generate_token(user_id, club_id, role)
                
                # Mettre à jour last_login
                cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s', (user_id,))
                
                return {
                    'token': token,
                    'user': {
                        'id': user_id,
                        'email': email,
                        'nom': nom,
                        'prenom': prenom,
                        'role': role
                    },
                    'club': {
                        'id': club_id,
                        'nom': club_nom,
                        'slug': club_slug,
                        'logo_url': logo_url,
                        'couleur_primaire': couleur_primaire,
                        'couleur_secondaire': couleur_secondaire,
                        'plan': plan,
                        'plan_active': plan_active,
                        'plan_details': PLANS.get(plan, PLANS['trial'])
                    }
                }
    
    def _generate_token(self, user_id, club_id, role):
        """Génère un token JWT"""
        payload = {
            'user_id': user_id,
            'club_id': club_id,
            'role': role,
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, JWT_SECRET, algorithm='HS256')
    
    def verify_token(self, token):
        """Vérifie et décode un token JWT"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expiré")
        except jwt.InvalidTokenError:
            raise ValueError("Token invalide")
    
    def get_user(self, user_id):
        """Récupère les infos d'un utilisateur"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT id, club_id, email, nom, prenom, role, is_active, last_login, created_at
                    FROM users WHERE id = %s
                ''', (user_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'club_id': row[1],
                        'email': row[2],
                        'nom': row[3],
                        'prenom': row[4],
                        'role': row[5],
                        'is_active': row[6],
                        'last_login': row[7].isoformat() if row[7] else None,
                        'created_at': row[8].isoformat() if row[8] else None
                    }
                return None
    
    def get_club_users(self, club_id):
        """Récupère tous les utilisateurs d'un club"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT id, email, nom, prenom, role, is_active, last_login, created_at
                    FROM users WHERE club_id = %s
                    ORDER BY role DESC, created_at ASC
                ''', (club_id,))
                users = []
                for row in cursor.fetchall():
                    users.append({
                        'id': row[0],
                        'email': row[1],
                        'nom': row[2],
                        'prenom': row[3],
                        'role': row[4],
                        'is_active': row[5],
                        'last_login': row[6].isoformat() if row[6] else None,
                        'created_at': row[7].isoformat() if row[7] else None
                    })
                return users
    
    def invite_user(self, club_id, email, role, invited_by_user_id):
        """Crée une invitation pour un nouvel utilisateur"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=7)
        
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                # Vérifier si l'utilisateur existe déjà
                cursor.execute('SELECT id FROM users WHERE email = %s', (email.lower(),))
                if cursor.fetchone():
                    raise ValueError("Cet utilisateur existe déjà")
                
                # Vérifier le nombre d'utilisateurs du club
                cursor.execute('SELECT COUNT(*) FROM users WHERE club_id = %s', (club_id,))
                user_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT plan FROM clubs WHERE id = %s', (club_id,))
                plan = cursor.fetchone()[0]
                max_users = PLANS.get(plan, PLANS['trial'])['max_users']
                
                if user_count >= max_users:
                    raise ValueError(f"Limite d'utilisateurs atteinte ({max_users}). Passez à un plan supérieur.")
                
                # Créer l'invitation
                cursor.execute('''
                    INSERT INTO invitations (club_id, email, role, token, expires_at, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (club_id, email.lower(), role, token, expires_at, invited_by_user_id))
                
                return {
                    'token': token,
                    'expires_at': expires_at.isoformat()
                }
    
    def accept_invitation(self, token, password, nom=None, prenom=None):
        """Accepte une invitation et crée le compte utilisateur"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                # Récupérer l'invitation
                cursor.execute('''
                    SELECT id, club_id, email, role, expires_at, used_at
                    FROM invitations WHERE token = %s
                ''', (token,))
                row = cursor.fetchone()
                
                if not row:
                    raise ValueError("Invitation invalide")
                
                inv_id, club_id, email, role, expires_at, used_at = row
                
                if used_at:
                    raise ValueError("Cette invitation a déjà été utilisée")
                
                if expires_at < datetime.now():
                    raise ValueError("Cette invitation a expiré")
                
                # Créer l'utilisateur
                password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute('''
                    INSERT INTO users (club_id, email, password_hash, nom, prenom, role)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                ''', (club_id, email, password_hash, nom, prenom, role))
                user_id = cursor.fetchone()[0]
                
                # Marquer l'invitation comme utilisée
                cursor.execute('''
                    UPDATE invitations SET used_at = CURRENT_TIMESTAMP WHERE id = %s
                ''', (inv_id,))
                
                return {'user_id': user_id, 'club_id': club_id}
    
    def change_password(self, user_id, old_password, new_password):
        """Change le mot de passe d'un utilisateur"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT password_hash FROM users WHERE id = %s', (user_id,))
                row = cursor.fetchone()
                
                if not row:
                    raise ValueError("Utilisateur non trouvé")
                
                if not bcrypt.checkpw(old_password.encode('utf-8'), row[0].encode('utf-8')):
                    raise ValueError("Mot de passe actuel incorrect")
                
                new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cursor.execute('''
                    UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                ''', (new_hash, user_id))
                
                return True
    
    # ============================================
    # PERMISSIONS
    # ============================================
    
    def has_feature(self, club_id, feature):
        """Vérifie si un club a accès à une fonctionnalité"""
        club = self.get_club(club_id)
        if not club:
            return False
        
        plan = club['plan']
        plan_details = PLANS.get(plan, PLANS['trial'])
        
        # Vérifier si le plan est actif
        if club['plan_expire_at']:
            expire_date = datetime.fromisoformat(club['plan_expire_at'])
            if expire_date < datetime.now():
                return False
        
        return feature in plan_details['features']
    
    def can_add_team(self, club_id):
        """Vérifie si le club peut ajouter une équipe"""
        club = self.get_club(club_id)
        if not club:
            return False
        
        plan_details = PLANS.get(club['plan'], PLANS['trial'])
        
        # Compter les équipes actuelles (à implémenter selon ta logique)
        # Pour l'instant, on retourne True
        return True


# ============================================
# DÉCORATEURS POUR LES ROUTES
# ============================================

def require_auth(f):
    """Décorateur pour exiger une authentification"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Récupérer le token du header Authorization
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'success': False, 'error': 'Token manquant'}), 401
        
        try:
            # Vérifier le token
            from database import get_db
            auth = AuthManager(get_db())
            payload = auth.verify_token(token)
            
            # Stocker les infos dans g pour les utiliser dans la route
            g.user_id = payload['user_id']
            g.club_id = payload['club_id']
            g.user_role = payload['role']
            
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 401
        
        return f(*args, **kwargs)
    
    return decorated


def require_admin(f):
    """Décorateur pour exiger un rôle admin"""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if g.user_role != 'admin':
            return jsonify({'success': False, 'error': 'Accès réservé aux administrateurs'}), 403
        return f(*args, **kwargs)
    
    return decorated


def require_feature(feature):
    """Décorateur pour exiger une fonctionnalité du plan"""
    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            from database import get_db
            auth = AuthManager(get_db())
            
            if not auth.has_feature(g.club_id, feature):
                return jsonify({
                    'success': False, 
                    'error': 'Cette fonctionnalité nécessite un plan supérieur',
                    'required_feature': feature
                }), 403
            
            return f(*args, **kwargs)
        return decorated
    return decorator
