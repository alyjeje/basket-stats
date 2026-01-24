#!/usr/bin/env python3
"""
Routes API pour l'authentification
"""

from flask import Blueprint, request, jsonify, g
from auth import AuthManager, require_auth, require_admin, PLANS
from database import get_db

# Blueprint pour les routes auth
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """Inscription d'un nouveau club"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Données manquantes'}), 400
    
    required_fields = ['club_nom', 'email', 'password']
    for field in required_fields:
        if field not in data:
            return jsonify({'success': False, 'error': f'Champ requis: {field}'}), 400
    
    # Validation email
    email = data['email'].strip().lower()
    if '@' not in email or '.' not in email:
        return jsonify({'success': False, 'error': 'Email invalide'}), 400
    
    # Validation mot de passe
    password = data['password']
    if len(password) < 8:
        return jsonify({'success': False, 'error': 'Le mot de passe doit faire au moins 8 caractères'}), 400
    
    try:
        auth = AuthManager(get_db())
        result = auth.create_club(
            nom=data['club_nom'].strip(),
            email=email,
            password=password,
            prenom=data.get('prenom', '').strip() or None,
            nom_user=data.get('nom', '').strip() or None
        )
        
        # Auto-login après inscription
        login_result = auth.login(email, password)
        
        return jsonify({
            'success': True,
            'message': 'Club créé avec succès',
            'data': login_result
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        print(f"❌ Erreur register: {e}")
        return jsonify({'success': False, 'error': 'Erreur serveur'}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Connexion utilisateur"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Données manquantes'}), 400
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'success': False, 'error': 'Email et mot de passe requis'}), 400
    
    try:
        auth = AuthManager(get_db())
        result = auth.login(email, password)
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        print(f"❌ Erreur login: {e}")
        return jsonify({'success': False, 'error': 'Erreur serveur'}), 500


@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_me():
    """Récupère les infos de l'utilisateur connecté"""
    try:
        auth = AuthManager(get_db())
        user = auth.get_user(g.user_id)
        club = auth.get_club(g.club_id)
        
        if not user or not club:
            return jsonify({'success': False, 'error': 'Utilisateur non trouvé'}), 404
        
        return jsonify({
            'success': True,
            'data': {
                'user': user,
                'club': club
            }
        })
        
    except Exception as e:
        print(f"❌ Erreur get_me: {e}")
        return jsonify({'success': False, 'error': 'Erreur serveur'}), 500


@auth_bp.route('/club', methods=['PUT'])
@require_admin
def update_club():
    """Met à jour les infos du club (admin seulement)"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Données manquantes'}), 400
    
    try:
        auth = AuthManager(get_db())
        success = auth.update_club(g.club_id, **data)
        
        if success:
            club = auth.get_club(g.club_id)
            return jsonify({
                'success': True,
                'message': 'Club mis à jour',
                'data': club
            })
        else:
            return jsonify({'success': False, 'error': 'Aucune modification'}), 400
        
    except Exception as e:
        print(f"❌ Erreur update_club: {e}")
        return jsonify({'success': False, 'error': 'Erreur serveur'}), 500


@auth_bp.route('/users', methods=['GET'])
@require_admin
def get_users():
    """Liste les utilisateurs du club (admin seulement)"""
    try:
        auth = AuthManager(get_db())
        users = auth.get_club_users(g.club_id)
        
        return jsonify({
            'success': True,
            'data': users
        })
        
    except Exception as e:
        print(f"❌ Erreur get_users: {e}")
        return jsonify({'success': False, 'error': 'Erreur serveur'}), 500


@auth_bp.route('/invite', methods=['POST'])
@require_admin
def invite_user():
    """Invite un nouvel utilisateur (admin seulement)"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Données manquantes'}), 400
    
    email = data.get('email', '').strip().lower()
    role = data.get('role', 'member')
    
    if not email or '@' not in email:
        return jsonify({'success': False, 'error': 'Email invalide'}), 400
    
    if role not in ['admin', 'coach', 'member']:
        return jsonify({'success': False, 'error': 'Rôle invalide'}), 400
    
    try:
        auth = AuthManager(get_db())
        result = auth.invite_user(g.club_id, email, role, g.user_id)
        
        # TODO: Envoyer email d'invitation
        # Pour l'instant, on retourne le lien
        invite_url = f"/invite/{result['token']}"
        
        return jsonify({
            'success': True,
            'message': f'Invitation envoyée à {email}',
            'data': {
                'invite_url': invite_url,
                'expires_at': result['expires_at']
            }
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        print(f"❌ Erreur invite: {e}")
        return jsonify({'success': False, 'error': 'Erreur serveur'}), 500


@auth_bp.route('/invite/<token>', methods=['GET'])
def get_invitation(token):
    """Vérifie une invitation"""
    try:
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    SELECT i.email, i.role, i.expires_at, i.used_at, c.nom as club_nom
                    FROM invitations i
                    JOIN clubs c ON i.club_id = c.id
                    WHERE i.token = %s
                ''', (token,))
                row = cursor.fetchone()
                
                if not row:
                    return jsonify({'success': False, 'error': 'Invitation invalide'}), 404
                
                email, role, expires_at, used_at, club_nom = row
                
                from datetime import datetime
                if used_at:
                    return jsonify({'success': False, 'error': 'Invitation déjà utilisée'}), 400
                
                if expires_at < datetime.now():
                    return jsonify({'success': False, 'error': 'Invitation expirée'}), 400
                
                return jsonify({
                    'success': True,
                    'data': {
                        'email': email,
                        'role': role,
                        'club_nom': club_nom,
                        'expires_at': expires_at.isoformat()
                    }
                })
                
    except Exception as e:
        print(f"❌ Erreur get_invitation: {e}")
        return jsonify({'success': False, 'error': 'Erreur serveur'}), 500


@auth_bp.route('/invite/<token>/accept', methods=['POST'])
def accept_invitation(token):
    """Accepte une invitation"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Données manquantes'}), 400
    
    password = data.get('password', '')
    if len(password) < 8:
        return jsonify({'success': False, 'error': 'Le mot de passe doit faire au moins 8 caractères'}), 400
    
    try:
        auth = AuthManager(get_db())
        result = auth.accept_invitation(
            token=token,
            password=password,
            nom=data.get('nom'),
            prenom=data.get('prenom')
        )
        
        # Auto-login après inscription
        db = get_db()
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT email FROM users WHERE id = %s', (result['user_id'],))
                email = cursor.fetchone()[0]
        
        login_result = auth.login(email, password)
        
        return jsonify({
            'success': True,
            'message': 'Compte créé avec succès',
            'data': login_result
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        print(f"❌ Erreur accept_invitation: {e}")
        return jsonify({'success': False, 'error': 'Erreur serveur'}), 500


@auth_bp.route('/password', methods=['PUT'])
@require_auth
def change_password():
    """Change le mot de passe"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Données manquantes'}), 400
    
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    
    if not old_password or not new_password:
        return jsonify({'success': False, 'error': 'Mots de passe requis'}), 400
    
    if len(new_password) < 8:
        return jsonify({'success': False, 'error': 'Le nouveau mot de passe doit faire au moins 8 caractères'}), 400
    
    try:
        auth = AuthManager(get_db())
        auth.change_password(g.user_id, old_password, new_password)
        
        return jsonify({
            'success': True,
            'message': 'Mot de passe modifié'
        })
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        print(f"❌ Erreur change_password: {e}")
        return jsonify({'success': False, 'error': 'Erreur serveur'}), 500


@auth_bp.route('/plans', methods=['GET'])
def get_plans():
    """Retourne les plans disponibles"""
    return jsonify({
        'success': True,
        'data': PLANS
    })
