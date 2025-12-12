# 🤖 Configuration des AI Agents pour Basket-Stats

Guide pour configurer les AI agents pour qu'ils gèrent automatiquement le repo basket-stats.

## 📋 Prérequis

### 1. GitHub Personal Access Token

**Créer un token avec les permissions suivantes :**

1. Aller sur https://github.com/settings/tokens
2. "Generate new token (classic)"
3. Sélectionner les scopes :
   - ✅ `repo` (Full control of private repositories)
   - ✅ `workflow` (Update GitHub Action workflows)
   - ✅ `write:packages` (si besoin)
4. Copier le token : `ghp_xxxxxxxxxxxxxxxxxxxx`

### 2. Azure Service Principal

**Créer les credentials Azure :**

```bash
az ad sp create-for-rbac \
  --name "basket-stats-github-actions" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/Groupe \
  --sdk-auth
```

**Copier la sortie JSON :**
```json
{
  "clientId": "xxx",
  "clientSecret": "xxx",
  "subscriptionId": "xxx",
  "tenantId": "xxx"
}
```

### 3. Configurer les Secrets GitHub

Dans le repo GitHub → Settings → Secrets and variables → Actions :

**Ajouter :**
- `AZURE_CREDENTIALS` : Le JSON complet du service principal
- `DB_PASSWORD` : Password PostgreSQL
- `AZURE_STORAGE_CONNECTION_STRING` : Connection string du storage
- `FFBB_PASSWORD` : Password FFBB API

## 🔧 Configuration des Agents

### Agent Configuration File

**Créer `agents_config.json` dans l'app agents (csmf-stats) :**

```json
{
  "github": {
    "token": "ghp_xxxxxxxxxxxxxxxxxxxx",
    "repo": "jeremy/basket-stats",
    "default_branch": "main"
  },
  "azure": {
    "resource_group": "Groupe",
    "webapp_name": "csmf-stats-basket",
    "subscription_id": "xxx"
  },
  "agents": {
    "product_owner": {
      "model": "claude-sonnet-4-5-20250929",
      "temperature": 0.3
    },
    "ux_designer": {
      "model": "claude-sonnet-4-5-20250929",
      "temperature": 0.7
    },
    "security": {
      "model": "claude-sonnet-4-5-20250929",
      "temperature": 0.1
    },
    "developer": {
      "model": "claude-sonnet-4-5-20250929",
      "temperature": 0.2
    },
    "tester": {
      "model": "claude-sonnet-4-5-20250929",
      "temperature": 0.1
    },
    "devops": {
      "model": "claude-sonnet-4-5-20250929",
      "temperature": 0.1
    }
  }
}
```

## 🔌 Installation des Dépendances

**Dans l'app agents, installer :**

```bash
pip install PyGithub gitpython azure-cli-core
```

## 📝 Code pour les Agents

### 1. GitHub Integration Module

**Créer `github_integration.py` dans l'app agents :**

```python
"""
Module d'intégration GitHub pour les agents
"""
from github import Github
import git
import os
import tempfile
import json

class GitHubIntegration:
    def __init__(self, token, repo_name):
        self.github = Github(token)
        self.repo = self.github.get_repo(repo_name)
        self.token = token
        
    def clone_repo(self):
        """Clone le repo dans un dossier temporaire"""
        temp_dir = tempfile.mkdtemp()
        repo_url = f"https://{self.token}@github.com/{self.repo.full_name}.git"
        git.Repo.clone_from(repo_url, temp_dir)
        return temp_dir
    
    def create_branch(self, branch_name, from_branch="main"):
        """Crée une nouvelle branche"""
        try:
            source = self.repo.get_branch(from_branch)
            self.repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=source.commit.sha
            )
            return True
        except:
            return False
    
    def commit_and_push(self, local_repo_path, branch_name, commit_message):
        """Commit et push les changements"""
        repo = git.Repo(local_repo_path)
        
        # Add tous les fichiers modifiés
        repo.git.add(A=True)
        
        # Commit
        repo.index.commit(commit_message)
        
        # Push
        origin = repo.remote('origin')
        origin.push(branch_name)
        
        return True
    
    def create_pull_request(self, title, body, head_branch, base_branch="main"):
        """Crée une Pull Request"""
        pr = self.repo.create_pull(
            title=title,
            body=body,
            head=head_branch,
            base=base_branch
        )
        return pr
    
    def merge_pull_request(self, pr_number, commit_message="Auto-merge by agents"):
        """Merge une Pull Request"""
        pr = self.repo.get_pull(pr_number)
        pr.merge(commit_message=commit_message)
        return True
    
    def get_file_content(self, file_path, branch="main"):
        """Récupère le contenu d'un fichier"""
        try:
            content = self.repo.get_contents(file_path, ref=branch)
            return content.decoded_content.decode('utf-8')
        except:
            return None
    
    def update_file(self, file_path, content, message, branch="main"):
        """Met à jour un fichier"""
        try:
            file = self.repo.get_contents(file_path, ref=branch)
            self.repo.update_file(
                file_path,
                message,
                content,
                file.sha,
                branch=branch
            )
            return True
        except:
            return False

# Exemple d'utilisation
if __name__ == "__main__":
    # Charger la config
    with open('agents_config.json') as f:
        config = json.load(f)
    
    gh = GitHubIntegration(
        token=config['github']['token'],
        repo_name=config['github']['repo']
    )
    
    print(f"✅ Connecté au repo: {gh.repo.full_name}")
    print(f"⭐ Stars: {gh.repo.stargazers_count}")
```

### 2. Workflow Orchestrator

**Créer `workflow_orchestrator.py` :**

```python
"""
Orchestrateur du workflow de développement
"""
import asyncio
from github_integration import GitHubIntegration
import json

class WorkflowOrchestrator:
    def __init__(self, config_path='agents_config.json'):
        with open(config_path) as f:
            self.config = json.load(f)
        
        self.github = GitHubIntegration(
            token=self.config['github']['token'],
            repo_name=self.config['github']['repo']
        )
    
    async def process_request(self, email_content):
        """
        Traite une demande de modification
        
        Workflow:
        1. PO analyse la demande
        2. Création branche feature
        3. UX fait les maquettes si nécessaire
        4. Security review
        5. Dev implémente
        6. Tests automatiques
        7. PR créée
        8. Si tests OK → merge + deploy
        """
        
        # 1. Analyser la demande avec PO
        print("📊 Product Owner analyse la demande...")
        requirements = await self.analyze_with_po(email_content)
        
        # 2. Créer une branche
        branch_name = f"feature/{requirements['feature_id']}"
        print(f"🌿 Création branche: {branch_name}")
        self.github.create_branch(branch_name)
        
        # 3. Clone le repo
        repo_path = self.github.clone_repo()
        print(f"📂 Repo cloné dans: {repo_path}")
        
        # 4. UX Design (si nécessaire)
        if requirements['needs_ux']:
            print("🎨 UX Designer crée les maquettes...")
            design = await self.create_ux_design(requirements)
        
        # 5. Security Review
        print("🔒 Security Agent review...")
        security_ok = await self.security_review(requirements)
        if not security_ok:
            print("❌ Security review failed!")
            return False
        
        # 6. Développement
        print("💻 Developer Agent implémente...")
        code_changes = await self.implement_feature(
            repo_path, 
            requirements
        )
        
        # 7. Commit et push
        commit_msg = f"feat: {requirements['title']}\n\n{requirements['description']}"
        self.github.commit_and_push(repo_path, branch_name, commit_msg)
        
        # 8. Créer PR
        pr = self.github.create_pull_request(
            title=f"[AUTO] {requirements['title']}",
            body=self.generate_pr_body(requirements),
            head_branch=branch_name
        )
        print(f"🔃 Pull Request créée: #{pr.number}")
        
        # 9. Attendre les tests GitHub Actions
        print("🧪 Tests en cours...")
        await self.wait_for_checks(pr.number)
        
        # 10. Si tests OK, merger
        tests_passed = await self.check_tests_status(pr.number)
        if tests_passed:
            print("✅ Tests passés, merge en cours...")
            self.github.merge_pull_request(pr.number)
            print("🚀 Déploiement automatique en cours...")
            return True
        else:
            print("❌ Tests échoués, merge annulé")
            return False
    
    async def analyze_with_po(self, email_content):
        """Product Owner analyse la demande"""
        # Appel à l'API Anthropic pour analyse
        # Retourne un dict avec requirements structurés
        return {
            'feature_id': 'stats-graph',
            'title': 'Ajouter graphique stats',
            'description': '...',
            'needs_ux': True,
            'priority': 'high'
        }
    
    async def create_ux_design(self, requirements):
        """UX Designer crée les maquettes"""
        # Utilise Claude pour générer des maquettes
        pass
    
    async def security_review(self, requirements):
        """Security Agent review"""
        # Scan de sécurité
        return True
    
    async def implement_feature(self, repo_path, requirements):
        """Developer implémente la feature"""
        # Modifications du code
        pass
    
    def generate_pr_body(self, requirements):
        """Génère le body de la PR"""
        return f"""
## 🤖 Pull Request Automatique

**Feature**: {requirements['title']}

**Description**: {requirements['description']}

**Priority**: {requirements['priority']}

---

### ✅ Checklist
- [x] Product Owner review
- [x] UX Design
- [x] Security review
- [x] Implementation
- [ ] Tests automatiques
- [ ] Déploiement

---

*Généré automatiquement par les AI Agents*
"""
    
    async def wait_for_checks(self, pr_number):
        """Attend que les checks GitHub Actions soient terminés"""
        await asyncio.sleep(60)  # Attendre 1 min
    
    async def check_tests_status(self, pr_number):
        """Vérifie si les tests sont passés"""
        pr = self.github.repo.get_pull(pr_number)
        commits = pr.get_commits()
        last_commit = list(commits)[-1]
        
        # Vérifier les statuses
        statuses = last_commit.get_statuses()
        for status in statuses:
            if status.state == "failure":
                return False
        
        return True

# Exemple d'utilisation
if __name__ == "__main__":
    orchestrator = WorkflowOrchestrator()
    
    # Simuler une demande
    email = """
    Subject: Ajouter un graphique d'évolution des stats
    
    Salut les agents,
    
    J'aimerais avoir un graphique qui montre l'évolution
    des stats de chaque joueuse au fil des matchs.
    
    Format: Line chart avec Chart.js
    Position: En dessous des stats individuelles
    
    Merci !
    """
    
    # Lancer le workflow
    asyncio.run(orchestrator.process_request(email))
```

## 📧 Email Integration

**Pour recevoir les emails, configurer un webhook ou IMAP :**

```python
import imaplib
import email

def check_emails():
    """Vérifie les nouveaux emails"""
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login('agents@csmf.com', 'password')
    mail.select('inbox')
    
    status, messages = mail.search(None, 'UNSEEN')
    
    for num in messages[0].split():
        status, msg = mail.fetch(num, '(RFC822)')
        email_msg = email.message_from_bytes(msg[0][1])
        
        subject = email_msg['subject']
        body = email_msg.get_payload()
        
        # Déclencher le workflow
        orchestrator = WorkflowOrchestrator()
        asyncio.run(orchestrator.process_request(body))
```

## 🚀 Déploiement

### 1. Cloner ce repo
```bash
git clone https://github.com/[username]/basket-stats.git
cd basket-stats
```

### 2. Configurer les secrets GitHub

Aller dans Settings → Secrets → ajouter `AZURE_CREDENTIALS`

### 3. Push sur main

Le déploiement se fait automatiquement !

## 📊 Monitoring

**Vérifier les déploiements :**
- GitHub Actions : https://github.com/[username]/basket-stats/actions
- Azure Portal : https://portal.azure.com

**Logs en temps réel :**
```bash
az webapp log tail --resource-group Groupe --name csmf-stats-basket
```

## 🆘 Support

En cas de problème, contacter Jérémy ou vérifier les logs GitHub Actions.

---

Made with 🤖 for CSMF Paris Basketball
