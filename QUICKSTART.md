# 🚀 Quick Start Guide

Guide rapide pour démarrer avec basket-stats.

## ⚡ Setup en 5 minutes

### 1. Cloner le repo

```bash
git clone https://github.com/[username]/basket-stats.git
cd basket-stats
```

### 2. Configurer l'environnement

```bash
# Copier le template
cp .env.example .env

# Éditer avec tes credentials
nano .env  # ou vim, code, etc.
```

### 3. Installer les dépendances

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 4. Lancer l'application

```bash
python api_server.py
```

🎉 **Application disponible sur http://localhost:5000**

---

## 🤖 Utiliser les AI Agents

### Envoyer une demande par email

**À :** agents@csmf-basket-stats.com

**Sujet :** [FEATURE] Titre de ta demande

**Corps :**
```
Description détaillée de ce que tu veux.

Exemples :
- Ajouter un graphique des stats
- Modifier la couleur du header
- Corriger le bug sur les minutes
```

### Les agents vont :
1. ✅ Analyser la demande
2. ✅ Créer une branche
3. ✅ Implémenter
4. ✅ Tester
5. ✅ Déployer

**Temps estimé :** 5-15 minutes selon la complexité

---

## 📊 Endpoints principaux

```bash
# Health check
curl https://csmf-stats-basket.azurewebsites.net/health

# Liste des matchs
curl https://csmf-stats-basket.azurewebsites.net/api/matches

# Détails d'un match
curl https://csmf-stats-basket.azurewebsites.net/api/matches/1
```

---

## 🐛 Debug

### Logs en local

```bash
python api_server.py
# Les logs s'affichent dans le terminal
```

### Logs sur Azure

```bash
az webapp log tail --resource-group Groupe --name csmf-stats-basket
```

### Tester la connexion DB

```python
from database import BasketStatsDB

db = BasketStatsDB()
matches = db.get_all_matches()
print(f"✅ {len(matches)} matchs trouvés")
```

---

## 🧪 Lancer les tests

```bash
# Tous les tests
pytest

# Avec couverture
pytest --cov

# Tests spécifiques
pytest tests/test_api.py -v
```

---

## 🚀 Déploiement manuel

```bash
# Avec le script
./deploy.sh

# Ou manuellement
zip -r deploy.zip .
az webapp deploy --resource-group Groupe --name csmf-stats-basket --src-path deploy.zip --type zip
```

---

## 📚 Documentation complète

- **README.md** : Vue d'ensemble du projet
- **AGENTS_SETUP.md** : Configuration des AI agents
- **API.md** : Documentation de l'API (à créer)

---

## 🆘 Besoin d'aide ?

1. Vérifier les logs
2. Relire la doc
3. Contacter Jérémy
4. Envoyer un email aux agents

---

## 🎯 Prochaines étapes

Après le setup :

1. ✅ Explorer l'interface web
2. ✅ Tester les endpoints API
3. ✅ Importer des matchs
4. ✅ Envoyer ta première demande aux agents !

---

**Happy coding! 🏀🤖**
