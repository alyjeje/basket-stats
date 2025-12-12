#!/usr/bin/env python3
"""
Script client pour uploader export_data.json vers l'API Azure
"""
import requests
import json
from pathlib import Path

# Configuration
API_URL = "https://csmf-stats-basket.azurewebsites.net/api/import-json"
JSON_FILE = r"C:\wamp64\www\basket-stats\export_data.json"

def upload_json():
    """Upload le fichier JSON vers l'API"""
    
    print("="*60)
    print("📤 UPLOAD JSON VERS AZURE")
    print("="*60)
    
    # Vérifier que le fichier existe
    if not Path(JSON_FILE).exists():
        print(f"❌ Fichier introuvable: {JSON_FILE}")
        return False
    
    # Lire le fichier pour afficher les stats
    print(f"\n📂 Lecture de {JSON_FILE}...")
    try:
        with open(JSON_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✅ Fichier chargé:")
        print(f"  • {len(data.get('matchs', []))} matchs")
        print(f"  • {len(data.get('stats_joueuses', []))} stats joueuses")
        print(f"  • {len(data.get('stats_equipes', []))} stats équipes")
        print(f"  • {len(data.get('combinaisons_5', []))} combinaisons")
        
        file_size = Path(JSON_FILE).stat().st_size / 1024  # KB
        print(f"  • Taille: {file_size:.1f} KB")
        
    except Exception as e:
        print(f"❌ Erreur lecture fichier: {e}")
        return False
    
    # Demander confirmation
    print(f"\n🌐 API cible: {API_URL}")
    print("\n⚠️ Prêt à uploader ?")
    confirm = input("Taper 'oui' pour continuer: ")
    
    if confirm.lower() not in ['oui', 'o', 'yes', 'y']:
        print("❌ Upload annulé")
        return False
    
    # Upload vers l'API
    print("\n📤 Upload en cours...")
    try:
        with open(JSON_FILE, 'rb') as f:
            files = {'file': ('export_data.json', f, 'application/json')}
            
            response = requests.post(
                API_URL,
                files=files,
                timeout=300  # 5 minutes max
            )
        
        # Vérifier la réponse
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                print("\n" + "="*60)
                print("🎉 IMPORT RÉUSSI !")
                print("="*60)
                
                imported = result.get('imported', {})
                print(f"  • Matchs importés: {imported.get('matchs', 0)}")
                print(f"  • Stats joueuses: {imported.get('stats_joueuses', 0)}")
                print(f"  • Stats équipes: {imported.get('stats_equipes', 0)}")
                print(f"  • Combinaisons: {imported.get('combinaisons_5', 0)}")
                
                # Afficher les erreurs s'il y en a
                total_errors = result.get('total_errors', 0)
                if total_errors > 0:
                    print("\n" + "="*60)
                    print(f"⚠️ {total_errors} ERREUR(S) DÉTECTÉE(S)")
                    print("="*60)
                    errors = result.get('errors', [])
                    for i, error in enumerate(errors[:10], 1):
                        print(f"  {i}. {error}")
                    if total_errors > 10:
                        print(f"  ... et {total_errors - 10} autres erreurs")
                
                print("="*60)
                
                print("\n✅ Vérifie ton site:")
                print("   https://csmf-stats-basket.azurewebsites.net/")
                
                return True
            else:
                print(f"\n❌ Erreur API: {result.get('error', 'Erreur inconnue')}")
                return False
        else:
            print(f"\n❌ Erreur HTTP {response.status_code}")
            print(f"Réponse: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print("\n❌ Timeout ! L'import prend trop de temps.")
        print("⚠️ L'import continue peut-être en arrière-plan.")
        print("✅ Vérifie ton site dans quelques minutes.")
        return False
        
    except Exception as e:
        print(f"\n❌ Erreur lors de l'upload: {e}")
        return False

if __name__ == '__main__':
    try:
        # Installer requests si nécessaire
        import requests
    except ImportError:
        print("❌ Module 'requests' manquant !")
        print("\n🔧 Installe-le avec:")
        print("   pip install requests")
        print("\n   OU:")
        print("   C:\\Users\\PC\\anaconda3\\python.exe -m pip install requests")
        exit(1)
    
    success = upload_json()
    
    if not success:
        print("\n❌ UPLOAD ÉCHOUÉ !")
        exit(1)
