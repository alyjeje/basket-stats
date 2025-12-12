"""
FFBB Cache Manager - Version Blob Storage
==================
Récupère et cache le calendrier CSMF depuis l'API FFBB.
Stocke le cache dans Azure Blob Storage pour persistance.

Usage:
    from ffbb_cache import FFBBCache
    cache = FFBBCache()
    cache.update_if_needed()  # Met à jour si > 24h
    calendar = cache.get_calendar()
"""

import json
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import logging
from storage_service import get_storage

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('ffbb_cache')

# URLs API FFBB (serveur officiel)
FFBB_API_URL = "https://ffbbserver3.ffbb.com/ffbbserver3/api"

# Nom du fichier de cache dans Blob Storage
CACHE_FILENAME = 'ffbb_calendar_cache.json'

class FFBBCache:
    def __init__(self):
        """
        Initialise le gestionnaire de cache FFBB.
        Utilise Azure Blob Storage pour la persistance.
        """
        self.api_url = FFBB_API_URL
        self.token = None
        self.token_expiry = None
        self.storage = get_storage()
        self.cache = self._load_cache()
        
        # Config CSMF
        self.club_name = "CSMF"
        self.club_id = None  # Sera trouvé automatiquement
        
    def _load_cache(self) -> Dict:
        """Charge le cache depuis Blob Storage."""
        try:
            logger.info("Chargement du cache FFBB depuis Blob Storage...")
            content = self.storage.download_cache_file(CACHE_FILENAME)
            
            if content:
                cache = json.loads(content)
                logger.info(f"✅ Cache FFBB chargé: {cache.get('last_update')}")
                return cache
            else:
                logger.info("Aucun cache trouvé, création d'un nouveau cache")
                return self._empty_cache()
        except Exception as e:
            logger.error(f"Erreur chargement cache: {e}")
            return self._empty_cache()
    
    def _empty_cache(self) -> Dict:
        """Retourne un cache vide."""
        return {
            'last_update': None,
            'club_id': None,
            'engagements': [],
            'calendar': [],
            'classement': []
        }
    
    def _save_cache(self):
        """Sauvegarde le cache dans Blob Storage."""
        try:
            content = json.dumps(self.cache, ensure_ascii=False, indent=2, default=str)
            self.storage.upload_cache_file(content, CACHE_FILENAME)
            logger.info(f"✅ Cache FFBB sauvegardé dans Blob Storage")
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde cache: {e}")
    
    def cache_age_hours(self) -> Optional[float]:
        """Retourne l'âge du cache en heures, ou None si pas de cache."""
        # Méthode 1: Utiliser last_update dans le cache
        if self.cache.get('last_update'):
            try:
                last_update = datetime.fromisoformat(self.cache['last_update'].replace('Z', '+00:00'))
                age = (datetime.now(last_update.tzinfo) - last_update).total_seconds() / 3600
                return age
            except Exception as e:
                logger.error(f"Erreur calcul âge cache (méthode 1): {e}")
        
        # Méthode 2: Demander à Blob Storage
        try:
            age = self.storage.get_cache_file_age(CACHE_FILENAME)
            return age
        except Exception as e:
            logger.error(f"Erreur calcul âge cache (méthode 2): {e}")
            return None
    
    def authenticate(self, username: str, password: str) -> bool:
        """
        Authentification à l'API FFBB.
        
        Args:
            username: Identifiant FFBB
            password: Mot de passe FFBB
            
        Returns:
            True si authentification réussie
        """
        try:
            logger.info(f"Authentification FFBB avec {username}...")
            
            response = requests.post(
                f"{self.api_url}/authentication.ws",
                json={'userName': username, 'password': password},
                timeout=30
            )
            
            if response.status_code == 200:
                raw_text = response.text.strip()
                
                # Le token est souvent retourné en texte brut
                token = None
                
                # Essayer JSON d'abord
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        token = data.get('token') or data.get('accessToken') or data.get('access_token')
                    elif isinstance(data, str):
                        token = data
                except:
                    # Si pas JSON, prendre le texte brut
                    token = raw_text
                
                if token and len(token) > 10:
                    self.token = token
                    self.token_expiry = datetime.now() + timedelta(hours=23)
                    logger.info(f"✅ Authentification réussie (token: {token[:20]}...)")
                    return True
                else:
                    logger.error(f"Token invalide reçu: {token}")
                    return False
            else:
                logger.error(f"Échec authentification: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur authentification: {e}")
            return False
    
    def get_engagements(self) -> List[Dict]:
        """Récupère les engagements (équipes du club)."""
        if not self.token:
            logger.error("Pas de token, authentification requise")
            return []
        
        try:
            response = requests.get(
                f"{self.api_url}/federations/engagements.ws",
                headers={'Authorization': self.token},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                engagements = data.get('engagements', []) if isinstance(data, dict) else data
                
                # Filtrer pour CSMF
                csmf_engagements = [
                    e for e in engagements 
                    if self.club_name in e.get('clubLibelle', '')
                ]
                
                logger.info(f"✅ {len(csmf_engagements)} engagements CSMF trouvés")
                return csmf_engagements
            else:
                logger.error(f"Erreur récupération engagements: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Erreur get_engagements: {e}")
            return []
    
    def get_calendar_for_engagement(self, engagement_id: int) -> List[Dict]:
        """Récupère le calendrier pour un engagement."""
        if not self.token:
            return []
        
        try:
            response = requests.get(
                f"{self.api_url}/federations/engagements/{engagement_id}/matchs.ws",
                headers={'Authorization': self.token},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                matchs = data.get('matchs', []) if isinstance(data, dict) else data
                return matchs
            else:
                return []
                
        except Exception as e:
            logger.error(f"Erreur get_calendar: {e}")
            return []
    
    def get_classement_for_engagement(self, engagement_id: int) -> List[Dict]:
        """Récupère le classement pour un engagement."""
        if not self.token:
            return []
        
        try:
            response = requests.get(
                f"{self.api_url}/federations/engagements/{engagement_id}/classement.ws",
                headers={'Authorization': self.token},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                classement = data.get('classement', []) if isinstance(data, dict) else data
                return classement
            else:
                return []
                
        except Exception as e:
            logger.error(f"Erreur get_classement: {e}")
            return []
    
    def update_calendar(self, username: str, password: str, force: bool = False) -> bool:
        """
        Met à jour le calendrier depuis l'API FFBB.
        
        Args:
            username: Identifiant FFBB
            password: Mot de passe FFBB
            force: Force la mise à jour même si cache récent
            
        Returns:
            True si mise à jour réussie
        """
        # Vérifier si mise à jour nécessaire
        if not force:
            age = self.cache_age_hours()
            if age is not None and age < 24:
                logger.info(f"Cache récent ({age:.1f}h), pas de mise à jour nécessaire")
                return True
        
        # Authentification
        if not self.authenticate(username, password):
            return False
        
        try:
            # Récupérer les engagements
            engagements = self.get_engagements()
            if not engagements:
                logger.error("Aucun engagement trouvé")
                return False
            
            self.cache['engagements'] = engagements
            
            # Récupérer le calendrier pour chaque engagement
            all_matchs = []
            all_classement = []
            
            for engagement in engagements:
                eng_id = engagement.get('id')
                if eng_id:
                    matchs = self.get_calendar_for_engagement(eng_id)
                    all_matchs.extend(matchs)
                    
                    classement = self.get_classement_for_engagement(eng_id)
                    if classement:
                        all_classement.append({
                            'engagement_id': eng_id,
                            'equipe': engagement.get('equipeLibelle'),
                            'classement': classement
                        })
            
            self.cache['calendar'] = all_matchs
            self.cache['classement'] = all_classement
            self.cache['last_update'] = datetime.now().isoformat()
            
            # Sauvegarder
            self._save_cache()
            
            logger.info(f"✅ Cache mis à jour: {len(all_matchs)} matchs")
            return True
            
        except Exception as e:
            logger.error(f"Erreur update_calendar: {e}")
            return False
    
    def update_if_needed(self, username: str, password: str) -> bool:
        """Met à jour le cache s'il a plus de 24h."""
        return self.update_calendar(username, password, force=False)
    
    def get_all_matches(self) -> List[Dict]:
        """Retourne tous les matchs du calendrier."""
        return self.cache.get('calendar', [])
    
    def get_upcoming_matches(self, days: int = 30) -> List[Dict]:
        """Retourne les prochains matchs."""
        now = datetime.now()
        upcoming = []
        
        for match in self.cache.get('calendar', []):
            try:
                date_str = match.get('dateMatch') or match.get('date')
                if date_str:
                    match_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    if match_date >= now and (match_date - now).days <= days:
                        upcoming.append(match)
            except:
                continue
        
        return sorted(upcoming, key=lambda m: m.get('dateMatch', ''))
    
    def get_recent_results(self, days: int = 30) -> List[Dict]:
        """Retourne les résultats récents."""
        now = datetime.now()
        recent = []
        
        for match in self.cache.get('calendar', []):
            try:
                date_str = match.get('dateMatch') or match.get('date')
                score = match.get('score')
                
                if date_str and score:
                    match_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    if match_date < now and (now - match_date).days <= days:
                        recent.append(match)
            except:
                continue
        
        return sorted(recent, key=lambda m: m.get('dateMatch', ''), reverse=True)
    
    def get_classement(self) -> List[Dict]:
        """Retourne le classement."""
        return self.cache.get('classement', [])
    
    def get_cache_info(self) -> Dict:
        """Retourne les infos sur le cache."""
        age = self.cache_age_hours()
        return {
            'last_update': self.cache.get('last_update'),
            'age_hours': round(age, 1) if age else None,
            'nb_matchs': len(self.cache.get('calendar', [])),
            'nb_engagements': len(self.cache.get('engagements', []))
        }
