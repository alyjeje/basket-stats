#!/bin/bash

###############################################################################
# Script de déploiement manuel pour basket-stats
# Usage: ./deploy.sh
###############################################################################

set -e  # Exit on error

echo "🚀 DÉPLOIEMENT BASKET-STATS VERS AZURE"
echo "======================================"

# Configuration
RESOURCE_GROUP="Groupe"
WEBAPP_NAME="csmf-stats-basket"
ZIP_FILE="deploy.zip"

# Vérifier que Azure CLI est installé
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI n'est pas installé!"
    echo "📥 Installer: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Vérifier la connexion Azure
echo "🔐 Vérification connexion Azure..."
az account show > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Non connecté à Azure!"
    echo "🔑 Connectez-vous avec: az login"
    exit 1
fi

ACCOUNT=$(az account show --query name -o tsv)
echo "✅ Connecté à: $ACCOUNT"

# Créer le package de déploiement
echo ""
echo "📦 Création du package de déploiement..."
if [ -f "$ZIP_FILE" ]; then
    rm "$ZIP_FILE"
fi

zip -r "$ZIP_FILE" . \
    -x "*.git*" \
    -x "tests/*" \
    -x "*.md" \
    -x ".github/*" \
    -x "venv/*" \
    -x "env/*" \
    -x "__pycache__/*" \
    -x "*.pyc" \
    -x ".env" \
    -x "$ZIP_FILE"

echo "✅ Package créé: $ZIP_FILE ($(du -h $ZIP_FILE | cut -f1))"

# Déployer
echo ""
echo "🚀 Déploiement vers Azure..."
az webapp deployment source config-zip \
    --resource-group "$RESOURCE_GROUP" \
    --name "$WEBAPP_NAME" \
    --src "$ZIP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Déploiement réussi!"
else
    echo "❌ Déploiement échoué!"
    exit 1
fi

# Attendre que l'app redémarre
echo ""
echo "⏳ Attente du redémarrage (30s)..."
sleep 30

# Health check
echo ""
echo "🏥 Health check..."
HEALTH_URL="https://$WEBAPP_NAME.azurewebsites.net/health"

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL")

if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ Application opérationnelle!"
    echo ""
    echo "🌐 URL: https://$WEBAPP_NAME.azurewebsites.net"
    echo "📊 API: https://$WEBAPP_NAME.azurewebsites.net/api/matches"
else
    echo "⚠️  Health check échoué (HTTP $HTTP_CODE)"
    echo "📋 Vérifier les logs:"
    echo "   az webapp log tail --resource-group $RESOURCE_GROUP --name $WEBAPP_NAME"
fi

# Nettoyer
rm "$ZIP_FILE"

echo ""
echo "✨ Déploiement terminé!"
