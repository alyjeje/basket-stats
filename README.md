# 🏀 CSMF Paris - Statistiques Basketball

Application de statistiques de basketball pour l'équipe CSMF Paris (Nationale Féminine 3).

## 📊 Fonctionnalités

- **Gestion des matchs** : Importation depuis PDFs FIBA Box Score
- **Statistiques joueuses** : Points, rebonds, passes, minutes, etc.
- **Statistiques équipes** : Tirs, LF, rebonds collectifs
- **Combinaisons de 5** : Analyse des lineups utilisés
- **Scores par quart-temps** : Détails Q1, Q2, Q3, Q4
- **API REST** : Endpoints JSON pour intégration

## 🚀 Déploiement

### Production
- **URL** : https://csmf-stats-basket.azurewebsites.net
- **Infrastructure** : Azure Web App + PostgreSQL + Blob Storage
- **Région** : France Central

### CI/CD Automatique

Le déploiement est automatique via GitHub Actions :

```
Push sur main → Tests → Build → Deploy Azure → Health Check
```

## 🏗️ Architecture

```
┌─────────────────┐
│  Frontend (SPA) │
│   index.html    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Flask API     │
│  api_server.py  │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌───────────┐
│PostgreSQL  Blob Storage│
│  Matches │ │   PDFs    │
│  Stats   │ └───────────┘
└──────────┘
```

## 🛠️ Stack Technique

- **Backend** : Python 3.11, Flask, Gunicorn
- **Base de données** : PostgreSQL (Azure Flexible Server)
- **Stockage** : Azure Blob Storage
- **Frontend** : HTML/CSS/JS (Vanilla)
- **Déploiement** : GitHub Actions, Azure CLI

## 📦 Installation Locale

```bash
# Cloner le repo
git clone https://github.com/[username]/basket-stats.git
cd basket-stats

# Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec vos credentials

# Lancer l'application
python api_server.py
```

L'application sera accessible sur http://localhost:5000

## 🧪 Tests

```bash
# Installer les dépendances de test
pip install pytest pytest-cov

# Lancer les tests
pytest tests/ -v

# Avec couverture
pytest tests/ -v --cov=. --cov-report=html
```

## 🔐 Variables d'Environnement

Créer un fichier `.env` avec :

```env
# PostgreSQL
DB_HOST=your-server.postgres.database.azure.com
DB_NAME=csmf_stats_db
DB_USER=your-username
DB_PASSWORD=your-password

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...

# FFBB API
FFBB_USERNAME=your-username
FFBB_PASSWORD=your-password

# Application
TEAM_NAME=CSMF
FLASK_ENV=production
```

## 🤖 Workflow avec AI Agents

Ce repo est géré automatiquement par des AI agents :

### Architecture des Agents

```
Email Request
    ↓
┌───────────────────────────────────┐
│  Product Owner Agent              │
│  - Analyse des besoins            │
│  - Priorisation                   │
└──────────────┬────────────────────┘
               ↓
┌───────────────────────────────────┐
│  UX Designer Agent                │
│  - Maquettes                      │
│  - Design system                  │
└──────────────┬────────────────────┘
               ↓
┌───────────────────────────────────┐
│  Security Agent                   │
│  - Code review sécurité           │
│  - Scan vulnérabilités            │
└──────────────┬────────────────────┘
               ↓
┌───────────────────────────────────┐
│  Developer Agent                  │
│  - Implémentation                 │
│  - Tests unitaires                │
└──────────────┬────────────────────┘
               ↓
┌───────────────────────────────────┐
│  Tester Agent                     │
│  - Tests E2E                      │
│  - Validation QA                  │
└──────────────┬────────────────────┘
               ↓
┌───────────────────────────────────┐
│  DevOps Agent                     │
│  - Déploiement Azure              │
│  - Monitoring                     │
└───────────────────────────────────┘
```

### Pour soumettre une demande

Envoyer un email à : `agents@csmf-basket-stats.com` (à configurer)

**Format du mail :**
```
Subject: [FEATURE] Titre de la demande

Description détaillée de ce que tu veux...

Exemples :
- Ajouter un graphique d'évolution des stats
- Modifier la couleur du menu
- Corriger le bug sur les minutes
```

Les agents :
1. Analysent la demande
2. Créent une branche `feature/xxx`
3. Implémentent les changements
4. Lancent les tests
5. Créent une Pull Request
6. Mergent si tests OK
7. Déploient automatiquement

## 📡 API Endpoints

### Matchs

```bash
# Liste des matchs
GET /api/matches

# Détails d'un match
GET /api/matches/{id}

# Lineups d'un match
GET /api/matches/{id}/lineups
```

### Health Check

```bash
GET /health
```

Réponse :
```json
{
  "status": "ok",
  "database": "connected",
  "storage": "connected"
}
```

## 📊 Structure des Données

### Match
```json
{
  "id": 1,
  "date": "2025-09-21",
  "equipe_domicile": "ARRAS",
  "equipe_exterieur": "CSMF PARIS",
  "score_domicile": 66,
  "score_exterieur": 61,
  "q1_domicile": 23,
  "q1_exterieur": 12,
  "stats_joueuses": [...],
  "stats_equipes": [...],
  "combinaisons_5": [...]
}
```

## 🔧 Configuration Azure

### Secrets GitHub

Configurer dans Settings → Secrets and variables → Actions :

```yaml
AZURE_CREDENTIALS:
{
  "clientId": "<APP_ID>",
  "clientSecret": "<PASSWORD>",
  "subscriptionId": "<SUBSCRIPTION_ID>",
  "tenantId": "<TENANT_ID>"
}
```

### Azure CLI

Créer le service principal :

```bash
az ad sp create-for-rbac \
  --name "github-basket-stats" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/Groupe \
  --sdk-auth
```

## 📝 Changelog

### v2.0.0 - 2025-12-12
- ✅ Migration vers Azure (PostgreSQL + Blob Storage)
- ✅ Ajout scores par quart-temps (Q1-Q4)
- ✅ Correction conversion minutes (MM:SS → INT)
- ✅ Import combinaisons de 5
- ✅ CI/CD GitHub Actions
- ✅ Tests automatiques

### v1.0.0 - 2025-09-01
- ✅ Version initiale (SQLite local)
- ✅ Import PDFs FIBA Box Score
- ✅ Stats joueuses et équipes

## 🤝 Contribution

Les contributions se font via les AI agents. Pour contribuer manuellement :

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📄 License

Ce projet est privé - CSMF Paris Basketball

## 👥 Équipe

- **Coach** : Jérémy (Assistant Coach CSMF Paris)
- **AI Agents** : Développement automatisé
- **Équipe** : CSMF Paris Féminine (NF3)

## 📞 Contact

- Email : agents@csmf-basket-stats.com
- Site web : https://csmf-stats-basket.azurewebsites.net

---

Made with ❤️ and 🤖 for CSMF Paris Basketball
