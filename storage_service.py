#!/usr/bin/env python3
"""
Service de gestion Azure Blob Storage
"""
from azure.storage.blob import BlobServiceClient, ContentSettings
from config import Config
import os
from datetime import datetime, timedelta

class StorageService:
    """Service pour gérer les fichiers dans Azure Blob Storage"""
    
    def __init__(self):
        """Initialise le client Azure Blob Storage"""
        if not Config.AZURE_STORAGE_CONNECTION_STRING:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING n'est pas configurée")
        
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                Config.AZURE_STORAGE_CONNECTION_STRING
            )
            print("✅ Client Azure Blob Storage initialisé")
            self._ensure_containers()
        except Exception as e:
            print(f"❌ Erreur lors de l'initialisation du Blob Storage: {e}")
            raise
    
    def _ensure_containers(self):
        """Crée les containers s'ils n'existent pas"""
        containers = [
            Config.CONTAINER_PDFS,
            Config.CONTAINER_CACHE,
            Config.CONTAINER_IMAGES,
            Config.CONTAINER_OVERLAYS
        ]
        
        for container_name in containers:
            try:
                container_client = self.blob_service_client.get_container_client(container_name)
                if not container_client.exists():
                    container_client.create_container()
                    print(f"✅ Container '{container_name}' créé")
                else:
                    print(f"✓ Container '{container_name}' existe déjà")
            except Exception as e:
                print(f"⚠️ Erreur pour le container '{container_name}': {e}")
    
    def upload_pdf(self, file_stream, filename):
        """
        Upload un PDF dans le container 'pdfs'
        
        Args:
            file_stream: Stream du fichier
            filename: Nom du fichier
        
        Returns:
            str: URL du blob
        """
        try:
            # Générer un nom de fichier unique avec timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = f"{timestamp}_{filename}"
            
            blob_client = self.blob_service_client.get_blob_client(
                container=Config.CONTAINER_PDFS,
                blob=blob_name
            )
            
            # Upload avec content type
            content_settings = ContentSettings(content_type='application/pdf')
            blob_client.upload_blob(
                file_stream,
                overwrite=True,
                content_settings=content_settings
            )
            
            blob_url = blob_client.url
            print(f"✅ PDF uploadé: {blob_name}")
            return blob_url
        
        except Exception as e:
            print(f"❌ Erreur lors de l'upload du PDF: {e}")
            raise
    
    def upload_cache_file(self, content, filename):
        """
        Upload un fichier de cache (JSON) dans le container 'cache'
        
        Args:
            content: Contenu du fichier (string ou bytes)
            filename: Nom du fichier
        
        Returns:
            str: URL du blob
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=Config.CONTAINER_CACHE,
                blob=filename
            )
            
            # Upload avec content type JSON
            content_settings = ContentSettings(content_type='application/json')
            
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            blob_client.upload_blob(
                content,
                overwrite=True,
                content_settings=content_settings
            )
            
            blob_url = blob_client.url
            print(f"✅ Fichier de cache uploadé: {filename}")
            return blob_url
        
        except Exception as e:
            print(f"❌ Erreur lors de l'upload du cache: {e}")
            raise
    
    def download_cache_file(self, filename):
        """
        Télécharge un fichier de cache depuis le container 'cache'
        
        Args:
            filename: Nom du fichier
        
        Returns:
            str: Contenu du fichier
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=Config.CONTAINER_CACHE,
                blob=filename
            )
            
            if not blob_client.exists():
                return None
            
            download_stream = blob_client.download_blob()
            content = download_stream.readall().decode('utf-8')
            
            print(f"✅ Fichier de cache téléchargé: {filename}")
            return content
        
        except Exception as e:
            print(f"❌ Erreur lors du téléchargement du cache: {e}")
            return None
    
    def cache_file_exists(self, filename):
        """
        Vérifie si un fichier de cache existe
        
        Args:
            filename: Nom du fichier
        
        Returns:
            bool: True si le fichier existe
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=Config.CONTAINER_CACHE,
                blob=filename
            )
            return blob_client.exists()
        except Exception as e:
            print(f"❌ Erreur lors de la vérification du cache: {e}")
            return False
    
    def get_cache_file_age(self, filename):
        """
        Retourne l'âge d'un fichier de cache en heures
        
        Args:
            filename: Nom du fichier
        
        Returns:
            float: Âge en heures, ou None si le fichier n'existe pas
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=Config.CONTAINER_CACHE,
                blob=filename
            )
            
            if not blob_client.exists():
                return None
            
            properties = blob_client.get_blob_properties()
            last_modified = properties.last_modified
            
            # Calculer l'âge en heures
            age = (datetime.now(last_modified.tzinfo) - last_modified).total_seconds() / 3600
            return age
        
        except Exception as e:
            print(f"❌ Erreur lors de la récupération de l'âge du cache: {e}")
            return None
    
    def upload_image(self, file_stream, filename, content_type='image/jpeg'):
        """
        Upload une image dans le container 'images'
        
        Args:
            file_stream: Stream du fichier
            filename: Nom du fichier
            content_type: Type MIME de l'image
        
        Returns:
            str: URL du blob
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = f"{timestamp}_{filename}"
            
            blob_client = self.blob_service_client.get_blob_client(
                container=Config.CONTAINER_IMAGES,
                blob=blob_name
            )
            
            content_settings = ContentSettings(content_type=content_type)
            blob_client.upload_blob(
                file_stream,
                overwrite=True,
                content_settings=content_settings
            )
            
            blob_url = blob_client.url
            print(f"✅ Image uploadée: {blob_name}")
            return blob_url
        
        except Exception as e:
            print(f"❌ Erreur lors de l'upload de l'image: {e}")
            raise
    
    def upload_overlay(self, file_stream, filename):
        """
        Upload une vidéo overlay dans le container 'overlays'
        
        Args:
            file_stream: Stream du fichier
            filename: Nom du fichier
        
        Returns:
            str: URL du blob
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            blob_name = f"{timestamp}_{filename}"
            
            blob_client = self.blob_service_client.get_blob_client(
                container=Config.CONTAINER_OVERLAYS,
                blob=blob_name
            )
            
            content_settings = ContentSettings(content_type='video/mp4')
            blob_client.upload_blob(
                file_stream,
                overwrite=True,
                content_settings=content_settings
            )
            
            blob_url = blob_client.url
            print(f"✅ Vidéo overlay uploadée: {blob_name}")
            return blob_url
        
        except Exception as e:
            print(f"❌ Erreur lors de l'upload de la vidéo: {e}")
            raise
    
    def delete_blob(self, container_name, blob_name):
        """
        Supprime un blob
        
        Args:
            container_name: Nom du container
            blob_name: Nom du blob
        
        Returns:
            bool: True si supprimé avec succès
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            
            blob_client.delete_blob()
            print(f"✅ Blob supprimé: {container_name}/{blob_name}")
            return True
        
        except Exception as e:
            print(f"❌ Erreur lors de la suppression du blob: {e}")
            return False
    
    def list_blobs(self, container_name, prefix=None):
        """
        Liste les blobs dans un container
        
        Args:
            container_name: Nom du container
            prefix: Préfixe pour filtrer les blobs (optionnel)
        
        Returns:
            list: Liste des noms de blobs
        """
        try:
            container_client = self.blob_service_client.get_container_client(container_name)
            
            if prefix:
                blobs = container_client.list_blobs(name_starts_with=prefix)
            else:
                blobs = container_client.list_blobs()
            
            blob_names = [blob.name for blob in blobs]
            print(f"✅ {len(blob_names)} blobs trouvés dans '{container_name}'")
            return blob_names
        
        except Exception as e:
            print(f"❌ Erreur lors du listage des blobs: {e}")
            return []
    
    def generate_sas_url(self, container_name, blob_name, expiry_hours=24):
        """
        Génère une URL SAS (Shared Access Signature) pour un blob
        
        Args:
            container_name: Nom du container
            blob_name: Nom du blob
            expiry_hours: Durée de validité en heures
        
        Returns:
            str: URL SAS
        """
        try:
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            
            # Générer le SAS token
            sas_token = generate_blob_sas(
                account_name=self.blob_service_client.account_name,
                container_name=container_name,
                blob_name=blob_name,
                account_key=self.blob_service_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
            )
            
            sas_url = f"{blob_client.url}?{sas_token}"
            return sas_url
        
        except Exception as e:
            print(f"❌ Erreur lors de la génération du SAS: {e}")
            return blob_client.url  # Retourner l'URL normale en cas d'erreur

# Instance globale
storage = None

def get_storage():
    """Retourne l'instance de StorageService (singleton)"""
    global storage
    if storage is None:
        storage = StorageService()
    return storage
