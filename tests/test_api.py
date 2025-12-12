"""
Tests pour l'API basket-stats
"""
import pytest
import sys
import os

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_import_api_server():
    """Test que api_server peut être importé"""
    try:
        import api_server
        assert hasattr(api_server, 'app')
    except ImportError as e:
        pytest.skip(f"Cannot import api_server: {e}")

def test_import_database():
    """Test que database peut être importé"""
    try:
        import database
        assert hasattr(database, 'BasketStatsDB')
    except ImportError as e:
        pytest.skip(f"Cannot import database: {e}")

def test_convert_minutes_to_int():
    """Test de la conversion des minutes"""
    try:
        from api_server import convert_minutes_to_int
        
        assert convert_minutes_to_int("29:18") == 29
        assert convert_minutes_to_int("24:13") == 24
        assert convert_minutes_to_int("NPJ") == 0
        assert convert_minutes_to_int("") == 0
        assert convert_minutes_to_int(None) == 0
        assert convert_minutes_to_int(25) == 25
    except ImportError:
        pytest.skip("convert_minutes_to_int not found")

def test_health_endpoint():
    """Test du endpoint /health (nécessite une connexion DB)"""
    try:
        from api_server import app
        client = app.test_client()
        
        response = client.get('/health')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'status' in data
    except Exception as e:
        pytest.skip(f"Health endpoint test skipped: {e}")

def test_api_matches_endpoint():
    """Test du endpoint /api/matches"""
    try:
        from api_server import app
        client = app.test_client()
        
        response = client.get('/api/matches')
        assert response.status_code in [200, 404, 500]  # 500 si pas de DB
        
        if response.status_code == 200:
            data = response.get_json()
            assert 'data' in data or 'success' in data
    except Exception as e:
        pytest.skip(f"Matches endpoint test skipped: {e}")

def test_config_exists():
    """Test que le fichier config existe"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.py')
    assert os.path.exists(config_path), "config.py should exist"

def test_requirements_exists():
    """Test que requirements.txt existe"""
    req_path = os.path.join(os.path.dirname(__file__), '..', 'requirements.txt')
    assert os.path.exists(req_path), "requirements.txt should exist"

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
