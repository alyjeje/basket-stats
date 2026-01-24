#!/usr/bin/env python3
"""
Module de chat IA pour l'analyse des statistiques basketball
Utilise Claude pour analyser les données du club et répondre aux questions
"""

import os
import json
from datetime import datetime
from anthropic import Anthropic

# Client Anthropic (la clé API sera dans les variables d'environnement)
client = None

def get_client():
    """Initialise le client Anthropic si nécessaire"""
    global client
    if client is None:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY non configurée")
        # Initialisation simple sans paramètres supplémentaires
        try:
            client = Anthropic(api_key=api_key)
        except TypeError as e:
            # Fallback si l'API a changé
            print(f"⚠️ Erreur init Anthropic avec api_key, tentative alternative: {e}")
            os.environ['ANTHROPIC_API_KEY'] = api_key
            client = Anthropic()
    return client


def build_system_prompt():
    """Construit le prompt système pour l'analyste basketball"""
    return """Tu es un analyste basketball expert pour le club CSMF Paris (Club Sportif du Ministère des Finances), 
équipe féminine évoluant en NF3 (Nationale Féminine 3).

Tu as accès à TOUTES les données statistiques du club :
- Résultats et scores de chaque match (par quart-temps)
- Statistiques individuelles de chaque joueuse (points, rebonds, passes, tirs, etc.)
- Combinaisons de 5 joueuses sur le terrain avec leur efficacité (+/-, temps de jeu, points marqués/encaissés)
- Stats par période

TON RÔLE :
1. Analyser les données pour répondre aux questions de manière précise et contextualisée
2. Identifier les tendances, forces et faiblesses
3. Donner des insights tactiques basés sur les chiffres
4. Comparer les performances (entre joueuses, entre matchs, contre différents adversaires)

STYLE DE RÉPONSE :
- Sois précis avec les chiffres mais explique ce qu'ils signifient
- Donne du CONTEXTE (pourquoi c'est bien/mal, comparé à quoi)
- Propose des insights actionables quand c'est pertinent
- Utilise un ton professionnel mais accessible
- Structure tes réponses de manière claire

DONNÉES DISPONIBLES :
Les données te seront fournies en JSON dans chaque message. Tu peux analyser :
- match_info : infos générales du match
- stats_joueuses : stats individuelles par match
- stats_equipes : totaux par équipe
- combinaisons_5 : efficacité des différentes compositions
- stats_periodes : évolution par quart-temps

Quand on te demande d'analyser "le dessus" ou "la domination", regarde :
- Les écarts de score par période
- Les runs (séries de points)
- Les combinaisons de 5 avec les meilleurs +/-
- Le différentiel rebonds, balles perdues, etc."""


def prepare_data_context(db):
    """Prépare toutes les données du club pour le contexte"""
    data = {
        "metadata": {
            "club": "CSMF Paris",
            "competition": "NF3",
            "date_export": datetime.now().isoformat(),
        },
        "matchs": [],
        "joueuses_aggregees": {},
        "combinaisons_5_toutes": []
    }
    
    # Récupérer tous les matchs avec leurs stats
    matchs = db.get_all_matches()
    
    for match in matchs:
        match_detail = db.get_match_by_id(match['id'])
        if match_detail:
            # Simplifier les données pour réduire la taille
            match_data = {
                "id": match_detail.get('id'),
                "date": str(match_detail.get('date', '')),
                "competition": match_detail.get('competition'),
                "domicile": match_detail.get('equipe_domicile'),
                "exterieur": match_detail.get('equipe_exterieur'),
                "score": f"{match_detail.get('score_domicile', 0)}-{match_detail.get('score_exterieur', 0)}",
                "scores_qt": {
                    "Q1": f"{match_detail.get('q1_domicile', 0)}-{match_detail.get('q1_exterieur', 0)}",
                    "Q2": f"{match_detail.get('q2_domicile', 0)}-{match_detail.get('q2_exterieur', 0)}",
                    "Q3": f"{match_detail.get('q3_domicile', 0)}-{match_detail.get('q3_exterieur', 0)}",
                    "Q4": f"{match_detail.get('q4_domicile', 0)}-{match_detail.get('q4_exterieur', 0)}",
                },
                "stats_joueuses": [],
                "combinaisons_5": []
            }
            
            # Stats joueuses (simplifiées)
            for j in match_detail.get('stats_joueuses', []):
                match_data["stats_joueuses"].append({
                    "nom": j.get('nom'),
                    "equipe": j.get('equipe'),
                    "min": j.get('minutes', 0),
                    "pts": j.get('points', 0),
                    "reb": j.get('rebonds_total', 0),
                    "reb_off": j.get('rebonds_offensifs', 0),
                    "reb_def": j.get('rebonds_defensifs', 0),
                    "passe": j.get('passes_decisives', 0),
                    "inter": j.get('interceptions', 0),
                    "bp": j.get('balles_perdues', 0),
                    "fautes": j.get('fautes_commises', 0),
                    "2pts": f"{j.get('tirs_2pts_reussis', 0)}/{j.get('tirs_2pts_tentes', 0)}",
                    "3pts": f"{j.get('tirs_3pts_reussis', 0)}/{j.get('tirs_3pts_tentes', 0)}",
                    "lf": f"{j.get('lf_reussis', 0)}/{j.get('lf_tentes', 0)}",
                    "+/-": j.get('plus_moins', 0),
                    "eval": j.get('evaluation', 0)
                })
                
                # Agréger les stats par joueuse CSMF
                if 'CSMF' in j.get('equipe', ''):
                    nom = j.get('nom')
                    if nom not in data["joueuses_aggregees"]:
                        data["joueuses_aggregees"][nom] = {
                            "matchs_joues": 0,
                            "minutes_total": 0,
                            "points_total": 0,
                            "rebonds_total": 0,
                            "passes_total": 0,
                            "interceptions_total": 0,
                            "bp_total": 0,
                            "plus_moins_total": 0,
                            "eval_total": 0
                        }
                    agg = data["joueuses_aggregees"][nom]
                    agg["matchs_joues"] += 1
                    agg["minutes_total"] += j.get('minutes', 0)
                    agg["points_total"] += j.get('points', 0)
                    agg["rebonds_total"] += j.get('rebonds_total', 0)
                    agg["passes_total"] += j.get('passes_decisives', 0)
                    agg["interceptions_total"] += j.get('interceptions', 0)
                    agg["bp_total"] += j.get('balles_perdues', 0)
                    agg["plus_moins_total"] += j.get('plus_moins', 0)
                    agg["eval_total"] += j.get('evaluation', 0)
            
            # Combinaisons de 5 (simplifiées)
            for c in match_detail.get('stats_cinq_majeur', []):
                combo = {
                    "match_id": match_detail.get('id'),
                    "adversaire": match_detail.get('equipe_exterieur') if 'CSMF' in match_detail.get('equipe_domicile', '') else match_detail.get('equipe_domicile'),
                    "equipe": c.get('equipe'),
                    "joueurs": c.get('joueurs'),
                    "temps": c.get('temps_jeu'),
                    "temps_sec": c.get('temps_secondes', 0),
                    "pour": c.get('score_pour', 0),
                    "contre": c.get('score_contre', 0),
                    "+/-": c.get('ecart', 0),
                    "reb": c.get('rebonds', 0),
                    "inter": c.get('interceptions', 0),
                    "bp": c.get('balles_perdues', 0),
                    "passes": c.get('passes_decisives', 0)
                }
                match_data["combinaisons_5"].append(combo)
                
                # Garder toutes les combinaisons CSMF pour analyse globale
                if 'CSMF' in c.get('equipe', ''):
                    data["combinaisons_5_toutes"].append(combo)
            
            data["matchs"].append(match_data)
    
    # Calculer les moyennes pour les joueuses
    for nom, stats in data["joueuses_aggregees"].items():
        if stats["matchs_joues"] > 0:
            m = stats["matchs_joues"]
            stats["moyennes"] = {
                "pts": round(stats["points_total"] / m, 1),
                "reb": round(stats["rebonds_total"] / m, 1),
                "passe": round(stats["passes_total"] / m, 1),
                "inter": round(stats["interceptions_total"] / m, 1),
                "bp": round(stats["bp_total"] / m, 1),
                "+/-": round(stats["plus_moins_total"] / m, 1),
                "eval": round(stats["eval_total"] / m, 1),
                "min": round(stats["minutes_total"] / m, 1)
            }
    
    return data


def prepare_single_match_context(db, match_id):
    """Prépare les données d'un seul match pour une question spécifique"""
    match = db.get_match_by_id(match_id)
    if not match:
        return None
    
    return {
        "match": {
            "id": match.get('id'),
            "date": str(match.get('date', '')),
            "competition": match.get('competition'),
            "domicile": match.get('equipe_domicile'),
            "exterieur": match.get('equipe_exterieur'),
            "score": f"{match.get('score_domicile', 0)}-{match.get('score_exterieur', 0)}",
            "scores_qt": {
                "Q1": f"{match.get('q1_domicile', 0)}-{match.get('q1_exterieur', 0)}",
                "Q2": f"{match.get('q2_domicile', 0)}-{match.get('q2_exterieur', 0)}",
                "Q3": f"{match.get('q3_domicile', 0)}-{match.get('q3_exterieur', 0)}",
                "Q4": f"{match.get('q4_domicile', 0)}-{match.get('q4_exterieur', 0)}",
            }
        },
        "stats_joueuses": match.get('stats_joueuses', []),
        "combinaisons_5": match.get('stats_cinq_majeur', []),
        "stats_periodes": match.get('stats_periodes', [])
    }


def chat(question: str, db, conversation_history: list = None, match_id: int = None):
    """
    Envoie une question à Claude avec le contexte des données
    
    Args:
        question: La question de l'utilisateur
        db: Instance de la base de données
        conversation_history: Historique de la conversation (optionnel)
        match_id: ID d'un match spécifique pour contexte ciblé (optionnel)
    
    Returns:
        dict avec la réponse et l'historique mis à jour
    """
    try:
        anthropic_client = get_client()
    except ValueError as e:
        return {
            "success": False,
            "error": str(e),
            "response": "Le chat IA n'est pas configuré. Veuillez ajouter ANTHROPIC_API_KEY dans les variables d'environnement."
        }
    
    # Préparer le contexte des données
    if match_id:
        data_context = prepare_single_match_context(db, match_id)
        context_info = f"Contexte: Analyse du match #{match_id}"
    else:
        data_context = prepare_data_context(db)
        context_info = f"Contexte: Toutes les données du club ({len(data_context.get('matchs', []))} matchs)"
    
    if not data_context:
        return {
            "success": False,
            "error": "Aucune donnée disponible",
            "response": "Je n'ai pas trouvé de données à analyser."
        }
    
    # Construire les messages
    messages = []
    
    # Ajouter l'historique si présent
    if conversation_history:
        messages.extend(conversation_history)
    
    # Ajouter la nouvelle question avec le contexte des données
    user_message = f"""Voici les données actuelles du club :

```json
{json.dumps(data_context, ensure_ascii=False, indent=2)}
```

Question : {question}"""
    
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    try:
        # Appel à Claude
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=build_system_prompt(),
            messages=messages
        )
        
        assistant_response = response.content[0].text
        
        # Mettre à jour l'historique (sans les données brutes pour économiser de l'espace)
        new_history = conversation_history.copy() if conversation_history else []
        new_history.append({
            "role": "user", 
            "content": question  # On garde juste la question, pas les données
        })
        new_history.append({
            "role": "assistant",
            "content": assistant_response
        })
        
        return {
            "success": True,
            "response": assistant_response,
            "context_info": context_info,
            "conversation_history": new_history,
            "tokens_used": {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "response": f"Erreur lors de l'analyse : {str(e)}"
        }


def get_suggested_questions():
    """Retourne des suggestions de questions pour guider l'utilisateur"""
    return [
        "Quelle est notre meilleure combinaison de 5 cette saison ?",
        "Quelles équipes ont réussi à prendre le dessus sur nous pendant un match ?",
        "Compare les performances de nos joueuses à domicile vs à l'extérieur",
        "Qui sont nos meilleures scoreuses et avec quelle efficacité au tir ?",
        "Dans quels quart-temps sommes-nous les plus vulnérables ?",
        "Quelle joueuse a le meilleur ratio passes/balles perdues ?",
        "Analyse nos rebonds offensifs : qui performe le mieux ?",
        "Quels sont nos points forts et points faibles cette saison ?",
        "Quelle composition utiliser dans les moments clutch (fin de match serré) ?",
        "Fais-moi un bilan de notre saison jusqu'ici"
    ]
