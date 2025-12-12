#!/usr/bin/env python3
"""
Script pour vider complètement la base de données Azure
ATTENTION: Supprime TOUTES les données !
"""
import requests
import json

# Configuration
API_URL = "https://csmf-stats-basket.azurewebsites.net/api/reset-database"

def reset_database():
    """Vide complètement la base de données"""
    
    print("="*60)
    print("⚠️  RESET BASE DE DONNÉES AZURE")
    print("="*60)
    print("\n🚨 ATTENTION:")
    print("  Cette opération va SUPPRIMER TOUTES les données:")
    print("  • Tous les matchs")
    print("  • Toutes les stats joueuses")
    print("  • Toutes les stats équipes")
    print("  • Toutes les combinaisons de 5")
    print("\n❌ CETTE ACTION EST IRRÉVERSIBLE !")
    
    # Triple confirmation
    print("\n⚠️  Êtes-vous ABSOLUMENT SÛR ?")
    confirm1 = input("Taper 'OUI' en MAJUSCULES pour continuer: ")
    
    if confirm1 != 'OUI':
        print("❌ Reset annulé")
        return False
    
    print("\n⚠️  Dernière confirmation !")
    confirm2 = input("Taper 'SUPPRIMER' pour confirmer: ")
    
    if confirm2 != 'SUPPRIMER':
        print("❌ Reset annulé")
        return False
    
    # Effectuer le reset
    print("\n🔄 Reset en cours...")
    try:
        response = requests.post(
            API_URL,
            json={'confirm': 'RESET_EVERYTHING'},
            headers={'Content-Type': 'application/json'},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if result.get('success'):
                print("\n" + "="*60)
                print("✅ BASE DE DONNÉES VIDÉE !")
                print("="*60)
                
                deleted = result.get('deleted', {})
                print(f"  • Matchs supprimés: {deleted.get('matchs', 0)}")
                print(f"  • Stats joueuses: {deleted.get('stats_joueuses', 0)}")
                print(f"  • Stats équipes: {deleted.get('stats_equipes', 0)}")
                print(f"  • Combinaisons: {deleted.get('combinaisons_5', 0)}")
                print("="*60)
                
                print("\n➡️  Prochaine étape:")
                print("   python upload_json_v2.py")
                
                return True
            else:
                print(f"\n❌ Erreur API: {result.get('error', 'Erreur inconnue')}")
                return False
        else:
            print(f"\n❌ Erreur HTTP {response.status_code}")
            print(f"Réponse: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
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
    
    success = reset_database()
    
    if not success:
        print("\n❌ RESET ÉCHOUÉ !")
        exit(1)
