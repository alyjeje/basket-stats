#!/usr/bin/env python3
"""
Configuration centralisée pour l'application CSMF Stats
"""
import os
from urllib.parse import quote_plus

class Config:
    """Configuration de l'application"""
    
    # ============================================
    # POSTGRESQL DATABASE
    # ============================================
    DB_HOST = os.getenv('DB_HOST', 'csmf-stats-server.postgres.database.azure.com')
    DB_NAME = os.getenv('DB_NAME', 'csmf_stats_db')
    DB_USER = os.getenv('DB_USER', '')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    
    # Construction de l'URL PostgreSQL complète
    if DB_USER and DB_PASSWORD:
        DATABASE_URL = f"postgresql://{DB_USER}:{quote_plus(DB_PASSWORD)}@{DB_HOST}/{DB_NAME}?sslmode=require"
    else:
        DATABASE_URL = None
    
    # Connection Pool Settings
    DB_POOL_MIN = 1
    DB_POOL_MAX = 10
    
    # ============================================
    # AZURE BLOB STORAGE
    # ============================================
    AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING', '')
    
    # Containers
    CONTAINER_PDFS = 'pdfs'
    CONTAINER_CACHE = 'cache'
    CONTAINER_IMAGES = 'images'
    CONTAINER_OVERLAYS = 'overlays'
    
    # ============================================
    # FFBB API
    # ============================================
    FFBB_USERNAME = os.getenv('FFBB_USERNAME', 'IDF0075079')
    FFBB_PASSWORD = os.getenv('FFBB_PASSWORD', 'hiUjMVDvRi4tfkY2YDe2uzvjqULxJ7Kq')
    
    # ============================================
    # VACANCES SCOLAIRES
    # ============================================
    # Zone académique pour les vacances (Paris = Zone C)
    VACANCES_ZONE = os.getenv('VACANCES_ZONE', 'C')
    # Cache des vacances en jours
    VACANCES_CACHE_DURATION = 24 * 60 * 60  # 24 heures
    
    # ============================================
    # APPLICATION
    # ============================================
    TEAM_NAME = os.getenv('TEAM_NAME', 'CSMF')
    MAX_UPLOAD_SIZE = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {'pdf'}
    
    # Flask
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    DEBUG = FLASK_ENV == 'development'
    
    # ============================================
    # VALIDATION
    # ============================================
    @classmethod
    def validate(cls):
        """Valide que la configuration est complète"""
        errors = []
        
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL manquante - vérifiez DB_USER et DB_PASSWORD")
        
        if not cls.AZURE_STORAGE_CONNECTION_STRING:
            errors.append("AZURE_STORAGE_CONNECTION_STRING manquante")
        
        if errors:
            raise ValueError(f"Configuration invalide: {', '.join(errors)}")
        
        return True
    
    @classmethod
    def is_configured(cls):
        """Vérifie si la configuration minimale est présente"""
        return bool(cls.DATABASE_URL and cls.AZURE_STORAGE_CONNECTION_STRING)
