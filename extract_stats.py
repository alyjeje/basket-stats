#!/usr/bin/env python3
"""
Script d'extraction des statistiques de match de basket depuis les PDFs FFBB
Version améliorée supportant :
- FIBA_Box_Score (stats de base) - FICHIER PRINCIPAL
- Boxscore_Détaillée (stats par période + avancées)
- Analyse_des_5_en_jeu (combinaisons de 5 joueurs)
"""
import pdfplumber
import re
import json
from pathlib import Path
from datetime import datetime
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

def clean_team_name(name):
    """Nettoie un nom d'équipe"""
    if not name:
        return name
    return re.sub(r'\s+', ' ', name.replace('\n', ' ')).strip()

def normalize_team_name(name):
    """Normalise les noms d'équipe (variantes CSMF → CSMF PARIS)"""
    if not name:
        return name
    name = clean_team_name(name)
    # Normaliser toutes les variantes CSMF
    if 'CSMF' in name.upper():
        return 'CSMF PARIS'
    return name

def normalize_player_name(name):
    """
    Normalise le nom d'une joueuse pour éviter les doublons.
    - Supprime (C) pour capitaine
    - Normalise les espaces/tirets dans les noms composés
    - Garde une forme cohérente
    """
    if not name:
        return name
    
    # Supprimer les indicateurs de capitaine/starter
    name = re.sub(r'\s*\([A-Z]\)\s*', '', name)
    
    # Normaliser les espaces multiples
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Pour les noms composés : si "MOT1 MOT2" où les deux sont en majuscules
    # et ressemblent à un nom composé, mettre un tiret
    # Ex: "RIMBAUD CLOPPET" → "RIMBAUD-CLOPPET"
    parts = name.split()
    if len(parts) >= 2:
        # Vérifier si le dernier mot pourrait être un nom composé avec l'avant-dernier
        # Heuristique: si prénom (1er mot) est en minuscules/capitalize et 
        # les autres mots sont en MAJUSCULES, ce sont probablement des noms
        first_word = parts[0]
        rest = parts[1:]
        
        # Si tous les mots après le prénom sont en majuscules, 
        # les joindre avec des tirets
        if all(word.isupper() for word in rest) and len(rest) > 1:
            # C'est probablement Prénom NOM1 NOM2 → Prénom NOM1-NOM2
            name = first_word + ' ' + '-'.join(rest)
    
    return name

def parse_stat(stat_str):
    """Parse une statistique du format 'X/Y' ou 'X'"""
    if not stat_str or stat_str == '':
        return 0, 0
    
    stat_str = str(stat_str).strip()
    
    if '/' in stat_str:
        try:
            parts = stat_str.split('/')
            return int(parts[0]), int(parts[1])
        except:
            return 0, 0
    else:
        try:
            return int(float(stat_str)), 0
        except:
            return 0, 0

def parse_time_to_seconds(time_str):
    """Convertit un temps MM:SS en secondes"""
    if not time_str:
        return 0
    try:
        parts = time_str.strip().split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return 0
    except:
        return 0

def detect_pdf_type(text, filename):
    """
    Détecte le type de PDF de manière robuste.
    Priorité au contenu du fichier, puis au nom de fichier en fallback.
    
    Types supportés:
    - FIBA_BOX_SCORE: Stats de base, crée le match
    - BOXSCORE_DETAILLEE: Stats par période, colonnes O/E et P/M
    - ANALYSE_5: Combinaisons de 5 joueurs
    - STATS_DETAILLEES: Tirs 2pts Int/Ext, stats avancées équipe
    - EVALUATION_JOUEUSE: Shot charts par joueuse (pour extraction tirs)
    - ZONES_TIRS / POSITION_TIRS: Visuels (ignorés sauf si on veut les tirs)
    """
    
    # ============================================
    # DÉTECTION PAR CONTENU (prioritaire et fiable)
    # ============================================
    
    # 1. FIBA Box Score - contient explicitement "FIBA Box Score"
    if 'FIBA Box Score' in text:
        return 'FIBA_BOX_SCORE'
    
    # 2. Boxscore Détaillée - contient "Boxscore Détaillée" ET les colonnes O/E, P/M
    if 'Boxscore Détaillée' in text or ('O/E' in text and 'P/M' in text):
        return 'BOXSCORE_DETAILLEE'
    
    # 3. Analyse des 5 en jeu - contient explicitement ce titre
    if 'Analyse des 5 en jeu' in text or '5 en jeu' in text:
        return 'ANALYSE_5'
    
    # 4. Evaluation Joueuse - contient "Evaluation Joueur" (shot charts individuels)
    if 'Evaluation Joueur' in text:
        return 'EVALUATION_JOUEUSE'
    
    # 5. Zones de Tirs - titre explicite
    if 'Zones de Tirs' in text:
        return 'ZONES_TIRS'
    
    # 6. Position des Tirs - titre explicite
    if 'Position des Tirs' in text:
        return 'POSITION_TIRS'
    
    # 7. Stats Détaillées (Feuille) - contient "2 pts Ext" et "2 pts Int" 
    #    MAIS n'est pas Boxscore Détaillée (pas de O/E, P/M)
    if '2 pts Ext' in text and '2 pts Int' in text:
        return 'STATS_DETAILLEES'
    
    # ============================================
    # FALLBACK PAR NOM DE FICHIER (si contenu non détecté)
    # ============================================
    filename_lower = filename.lower()
    
    if 'fiba' in filename_lower and 'box' in filename_lower:
        return 'FIBA_BOX_SCORE'
    elif 'analyse' in filename_lower and '5' in filename_lower:
        return 'ANALYSE_5'
    elif 'boxscore' in filename_lower and ('détaillé' in filename_lower or 'detaille' in filename_lower):
        return 'BOXSCORE_DETAILLEE'
    elif 'statistiques' in filename_lower or 'feuille' in filename_lower:
        return 'STATS_DETAILLEES'
    elif 'evaluation' in filename_lower:
        return 'EVALUATION_JOUEUSE'
    elif 'zone' in filename_lower and 'tir' in filename_lower:
        return 'ZONES_TIRS'
    elif 'position' in filename_lower and 'tir' in filename_lower:
        return 'POSITION_TIRS'
    
    # Par défaut, essayer comme FIBA Box Score
    return 'UNKNOWN'

def extract_match_info(text):
    """Extrait les informations générales du match"""
    match_info = {}
    
    # Date et heure - plusieurs formats
    date_patterns = [
        r'(\d{1,2}\s+\w+\.?\s+\d{4})\s*Heure\s*:?\s*(\d{2}:\d{2})',
        r'Date:\s*\w+\.?\s*(\d{1,2}\s+\w+\.?\s+\d{4})',
        r'(\d{1,2}/\d{1,2}/\d{4})',
    ]
    
    for pattern in date_patterns:
        date_match = re.search(pattern, text, re.IGNORECASE)
        if date_match:
            match_info['date'] = date_match.group(1).strip()
            if len(date_match.groups()) > 1:
                match_info['heure'] = date_match.group(2)
            break
    
    # Heure seule si pas trouvée
    if 'heure' not in match_info:
        heure_match = re.search(r'Heure\s*:?\s*(\d{2}:\d{2})', text)
        if heure_match:
            match_info['heure'] = heure_match.group(1)
    
    # Score final - Format "EQUIPE1 XX – YY EQUIPE2"
    # Peut être sur une ou deux lignes
    score_patterns = [
        # Format standard sur une ligne
        r'([A-Z][A-Z\s\'\-]+?)\s+(\d{1,3})\s*[–\-]\s*(\d{1,3})\s+([A-Z][A-Z\s\'\-]+)',
        r'([A-Z][A-Z\s]+)\s+(\d+)\s*-\s*(\d+)\s+([A-Z][A-Z\s]+)',
    ]
    
    for pattern in score_patterns:
        score_match = re.search(pattern, text)
        if score_match:
            match_info['equipe_domicile'] = clean_team_name(score_match.group(1))
            match_info['score_domicile'] = int(score_match.group(2))
            match_info['score_exterieur'] = int(score_match.group(3))
            match_info['equipe_exterieur'] = clean_team_name(score_match.group(4))
            break
    
    # Si pas trouvé, essayer le format multi-lignes (EQUIPE1 XX – YY sur une ligne, EQUIPE2 quelques lignes après)
    if 'equipe_domicile' not in match_info:
        # Chercher le score avec équipe domicile
        score_line = re.search(r'([A-Z][A-Z\s\'\-]+)\s+(\d{1,3})\s*[–\-]\s*(\d{1,3})\s*$', text, re.MULTILINE)
        if score_line:
            match_info['equipe_domicile'] = clean_team_name(score_line.group(1))
            match_info['score_domicile'] = int(score_line.group(2))
            match_info['score_exterieur'] = int(score_line.group(3))
            
            # Chercher l'équipe extérieure dans les lignes suivantes
            # Elle devrait être une ligne qui contient uniquement un nom d'équipe en majuscules
            lines = text.split('\n')
            score_line_idx = None
            for i, line in enumerate(lines):
                if score_line.group(0).strip() in line:
                    score_line_idx = i
                    break
            
            if score_line_idx is not None:
                # Chercher dans les 5 lignes suivantes un nom d'équipe
                for i in range(score_line_idx + 1, min(score_line_idx + 6, len(lines))):
                    line = lines[i].strip()
                    # Ligne qui contient un nom d'équipe (majuscules, pas de chiffres, pas de mots-clés)
                    if (line and 
                        line.isupper() or line[0].isupper() and 
                        not any(kw in line.lower() for kw in ['durée', 'rapport', 'crew', 'arbitre', 'match', 'affluence']) and
                        not re.search(r'\d{2}:\d{2}', line) and
                        len(line) > 3):
                        # Vérifier que c'est bien un nom d'équipe (pas de caractères spéciaux autres que espaces et tirets)
                        if re.match(r'^[A-Z][A-Za-z\s\'\-]+$', line):
                            match_info['equipe_exterieur'] = clean_team_name(line)
                            break
    
    # Score par quart-temps
    quarters = re.search(r'\((\d+)-(\d+),\s*(\d+)-(\d+),\s*(\d+)-(\d+),\s*(\d+)-(\d+)\)', text)
    if quarters:
        match_info['q1_domicile'] = int(quarters.group(1))
        match_info['q1_exterieur'] = int(quarters.group(2))
        match_info['q2_domicile'] = int(quarters.group(3))
        match_info['q2_exterieur'] = int(quarters.group(4))
        match_info['q3_domicile'] = int(quarters.group(5))
        match_info['q3_exterieur'] = int(quarters.group(6))
        match_info['q4_domicile'] = int(quarters.group(7))
        match_info['q4_exterieur'] = int(quarters.group(8))
    
    # Match No et affluence
    match_no = re.search(r'Match\s*No\.?:?\s*(\d+)', text)
    if match_no:
        match_info['match_no'] = match_no.group(1)
    
    affluence = re.search(r'Affluence:?\s*(\d+)', text)
    if affluence:
        match_info['affluence'] = int(affluence.group(1))
    
    # Lieu
    lieu_patterns = [
        r'NATIONALE\s+\d+\s+FEMININE\s+([^,\n]+)',
        r'([A-Z][A-Z\s]+),\s*\w+\.\s*\d+',
    ]
    for pattern in lieu_patterns:
        lieu = re.search(pattern, text)
        if lieu:
            match_info['lieu'] = lieu.group(1).strip()
            break
    
    return match_info

def extract_team_names(text, match_info):
    """Extrait les noms des équipes depuis le texte"""
    team_pattern = r'([A-Z][A-Z\s\']+)\s*\(([A-Z]+)\)\s+Entra[îi]neur'
    teams_found = re.findall(team_pattern, text)
    
    if len(teams_found) < 2:
        teams_found = [
            (match_info.get('equipe_domicile', 'Équipe 1'), 'DOM'),
            (match_info.get('equipe_exterieur', 'Équipe 2'), 'EXT')
        ]
    
    team1 = clean_team_name(teams_found[0][0]) if teams_found else 'Équipe 1'
    team2 = clean_team_name(teams_found[1][0]) if len(teams_found) > 1 else 'Équipe 2'
    
    return team1, team2

def extract_fiba_box_score(pdf_path):
    """Extrait les données depuis un FIBA Box Score"""
    print(f"📄 Extraction FIBA Box Score: {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
        
        all_tables = []
        for page in pdf.pages:
            tables = page.extract_tables()
            all_tables.extend(tables)
    
    match_info = extract_match_info(full_text)
    team1, team2 = extract_team_names(full_text, match_info)
    
    print(f"📋 {team1} vs {team2}")
    print(f"📋 Score: {match_info.get('score_domicile')}-{match_info.get('score_exterieur')}")
    
    # Extraire les stats des joueuses ET les totaux d'équipe
    player_stats = []
    team_stats = []  # Pour stocker les stats d'équipe (lignes Totaux)
    player_tables = [t for t in all_tables if len(t) > 5 and len(t[0]) >= 15]
    
    for table_idx, table in enumerate(player_tables[:2]):
        current_team = normalize_team_name(team1 if table_idx == 0 else team2)
        print(f"\n🔍 Extraction {current_team}")
        
        for row in table[1:]:
            if len(row) < 15:
                continue
            
            # Ignorer les lignes sans données
            if not row[0] and not row[1]:
                continue
            
            nom = str(row[1]).strip() if row[1] else ''
            
            # Traiter les lignes "Totaux" comme stats d'équipe
            if nom == 'Totaux' or (row[0] and str(row[0]).strip() == 'Totaux'):
                try:
                    num_cols = len(row)
                    has_eval_column = num_cols >= 23
                    
                    tirs_tot = str(row[3]) if len(row) > 3 and row[3] else '0/0'
                    tirs_2pts = str(row[5]) if len(row) > 5 and row[5] else '0/0'
                    tirs_3pts = str(row[7]) if len(row) > 7 and row[7] else '0/0'
                    lf = str(row[9]) if len(row) > 9 and row[9] else '0/0'
                    
                    # Index pour points selon le nombre de colonnes
                    if has_eval_column:
                        pts_val = str(row[22]) if row[22] else '0'
                    else:
                        pts_val = str(row[21]) if row[21] else '0'
                    
                    team_stat = {
                        'equipe': current_team,
                        'tirs_total': tirs_tot,
                        'tirs_2pts': tirs_2pts,
                        'tirs_3pts': tirs_3pts,
                        'lancers_francs': lf,
                        'rebonds_off': str(row[11]) if len(row) > 11 and row[11] else '0',
                        'rebonds_def': str(row[12]) if len(row) > 12 and row[12] else '0',
                        'rebonds_tot': str(row[13]) if len(row) > 13 and row[13] else '0',
                        'passes_dec': str(row[14]) if len(row) > 14 and row[14] else '0',
                        'balles_perdues': str(row[15]) if len(row) > 15 and row[15] else '0',
                        'interceptions': str(row[16]) if len(row) > 16 and row[16] else '0',
                        'contres': str(row[17]) if len(row) > 17 and row[17] else '0',
                        'fautes': str(row[18]) if len(row) > 18 and row[18] else '0',
                        'points': pts_val,
                    }
                    
                    # Calculer l'évaluation d'équipe
                    pts = parse_stat(team_stat['points'])[0]
                    reb = parse_stat(team_stat['rebonds_tot'])[0]
                    pd = parse_stat(team_stat['passes_dec'])[0]
                    inter = parse_stat(team_stat['interceptions'])[0]
                    ctr = parse_stat(team_stat['contres'])[0]
                    tirs_r, tirs_t = parse_stat(team_stat['tirs_total'])
                    lf_r, lf_t = parse_stat(team_stat['lancers_francs'])
                    bp = parse_stat(team_stat['balles_perdues'])[0]
                    
                    evaluation = pts + reb + pd + inter + ctr - (tirs_t - tirs_r) - (lf_t - lf_r) - bp
                    team_stat['eval'] = str(evaluation)
                    
                    team_stats.append(team_stat)
                    print(f"  📊 TOTAUX {current_team}: {pts} pts, RO: {team_stat['rebonds_off']}, RD: {team_stat['rebonds_def']}")
                except Exception as e:
                    print(f"  ⚠️ Erreur extraction totaux: {e}")
                continue
            
            # Ignorer les autres lignes non-joueur
            if not nom or nom in ['Equipe/Coach', 'Nom', '']:
                continue
            
            try:
                # Format FIBA variable selon les PDFs:
                # - 23 colonnes: No, Nom, Min, Tirs, %, 2pts, %, 3pts, %, LF, %, RO, RD, TOT, PD, BP, IN, Ctr, F, FP, +/-, Ev, PTS
                # - 22 colonnes: No, Nom, Min, Tirs, %, 2pts, %, 3pts, %, LF, %, RO, RD, TOT, PD, BP, IN, Ctr, F, FP, +/-, PTS (pas de Ev)
                
                num_cols = len(row)
                has_eval_column = num_cols >= 23
                
                tirs_tot = str(row[3]) if len(row) > 3 and row[3] else '0/0'
                tirs_2pts = str(row[5]) if len(row) > 5 and row[5] else '0/0'
                tirs_3pts = str(row[7]) if len(row) > 7 and row[7] else '0/0'
                lf = str(row[9]) if len(row) > 9 and row[9] else '0/0'
                
                # Index pour points et eval selon le nombre de colonnes
                if has_eval_column:
                    # 23 colonnes: eval à [21], points à [22]
                    eval_val = str(row[21]) if row[21] else '0'
                    pts_val = str(row[22]) if row[22] else '0'
                else:
                    # 22 colonnes: pas de eval, points à [21]
                    eval_val = '0'  # Sera calculé plus tard
                    pts_val = str(row[21]) if row[21] else '0'
                
                player = {
                    'equipe': current_team,
                    'numero': str(row[0]).strip().replace('*', '') if row[0] else '',
                    'nom': normalize_player_name(nom),
                    'minutes': str(row[2]).strip() if len(row) > 2 and row[2] else '',
                    'tirs_total': tirs_tot,
                    'tirs_2pts': tirs_2pts,
                    'tirs_3pts': tirs_3pts,
                    'lancers_francs': lf,
                    'rebonds_off': str(row[11]) if len(row) > 11 and row[11] else '0',
                    'rebonds_def': str(row[12]) if len(row) > 12 and row[12] else '0',
                    'rebonds_tot': str(row[13]) if len(row) > 13 and row[13] else '0',
                    'passes_dec': str(row[14]) if len(row) > 14 and row[14] else '0',
                    'balles_perdues': str(row[15]) if len(row) > 15 and row[15] else '0',
                    'interceptions': str(row[16]) if len(row) > 16 and row[16] else '0',
                    'contres': str(row[17]) if len(row) > 17 and row[17] else '0',
                    'fautes': str(row[18]) if len(row) > 18 and row[18] else '0',
                    'fautes_provoquees': str(row[19]) if len(row) > 19 and row[19] else '0',
                    'plus_moins': str(row[20]) if len(row) > 20 and row[20] else '0',
                    'eval': eval_val,
                    'points': pts_val,
                }
                
                # Calculer l'évaluation seulement si pas déjà présente dans le PDF
                pts = parse_stat(player['points'])[0]
                if not has_eval_column or player['eval'] == '0':
                    reb = parse_stat(player['rebonds_tot'])[0]
                    pd = parse_stat(player['passes_dec'])[0]
                    inter = parse_stat(player['interceptions'])[0]
                    ctr = parse_stat(player['contres'])[0]
                    tirs_r, tirs_t = parse_stat(player['tirs_total'])
                    lf_r, lf_t = parse_stat(player['lancers_francs'])
                    bp = parse_stat(player['balles_perdues'])[0]
                    
                    evaluation = pts + reb + pd + inter + ctr - (tirs_t - tirs_r) - (lf_t - lf_r) - bp
                    player['evaluation'] = str(evaluation)
                else:
                    player['evaluation'] = player['eval']
                
                player_stats.append(player)
                print(f"  ✓ {nom}: {pts} pts")
                
            except Exception as e:
                print(f"  ⚠️ Erreur: {e}")
                continue
    
    # Extraire les stats avancées
    advanced_stats = []
    
    # Points dans la raquette, contre-attaque, etc.
    for team in [team1, team2]:
        adv = {'equipe': normalize_team_name(team)}
        
        # Chercher les stats avancées dans le texte
        pbp = re.search(rf'{re.escape(team)}.*?Points de Balles Perdues\s+(\d+)', full_text, re.DOTALL)
        if not pbp:
            pbp = re.search(r'Points de Balles Perdues\s+(\d+)\s+(\d+)', full_text)
        
        prq = re.search(r'Points dans la raquette\s+(\d+)[^\d]+(\d+)', full_text)
        pca = re.search(r'Pts en contre-attaque\s+(\d+)\s+(\d+)', full_text)
        p2c = re.search(r'Points sur 2ème chance\s+(\d+)\s+(\d+)', full_text)
        pbanc = re.search(r'Points Banc\s+(\d+)\s+(\d+)', full_text)
        
        if prq:
            idx = 0 if team == team1 else 1
            adv['points_raquette'] = int(prq.group(idx + 1)) if len(prq.groups()) > idx else None
        if pca:
            idx = 0 if team == team1 else 1
            adv['points_contre_attaque'] = int(pca.group(idx + 1)) if len(pca.groups()) > idx else None
        if p2c:
            idx = 0 if team == team1 else 1
            adv['points_2eme_chance'] = int(p2c.group(idx + 1)) if len(p2c.groups()) > idx else None
        if pbanc:
            idx = 0 if team == team1 else 1
            adv['points_banc'] = int(pbanc.group(idx + 1)) if len(pbanc.groups()) > idx else None
        
        advanced_stats.append(adv)
    
    print(f"\n📊 Stats d'équipe extraites: {len(team_stats)} équipes")
    for ts in team_stats:
        print(f"   - {ts['equipe']}: RO={ts['rebonds_off']}, RD={ts['rebonds_def']}")
    
    return {
        'match_info': match_info,
        'player_stats': player_stats,
        'team_stats': team_stats,
        'advanced_stats': advanced_stats,
        'period_stats': [],
        'lineup_stats': [],
    }

def extract_boxscore_detaillee(pdf_path, existing_data=None):
    """Extrait les stats par période depuis une Boxscore Détaillée"""
    print(f"📄 Extraction Boxscore Détaillée: {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
        
        all_tables = []
        for page in pdf.pages:
            tables = page.extract_tables()
            all_tables.extend(tables)
    
    match_info = extract_match_info(full_text)
    team1, team2 = extract_team_names(full_text, match_info)
    
    period_stats = []
    advanced_stats = []
    
    # Chercher les lignes de stats par période dans les tables
    for table in all_tables:
        for row in table:
            if not row or len(row) < 5:
                continue
            
            row_str = str(row[0]) if row[0] else ''
            
            # Détecter les lignes "Période X" ou "50:00" (durée d'une période)
            if 'Période' in row_str or row_str == '50:00':
                try:
                    periode_match = re.search(r'Période\s*(\d+)', row_str)
                    if periode_match:
                        periode = int(periode_match.group(1))
                    elif row_str == '50:00':
                        # Trouver le numéro de période dans une autre colonne
                        continue
                    
                    # Le reste des colonnes contient les stats
                    # Format: Période, PTS, 2pts R/T, %, 3pts R/T, %, Tirs Tot R/T, %, LF R/T, %, RO, RD, TOT, ...
                    
                except Exception as e:
                    continue
    
    # Extraire les stats avancées (% rebonds, points raquette, etc.)
    for team in [team1, team2]:
        adv = {'equipe': normalize_team_name(team)}
        
        # % Rebonds
        pct_ro = re.search(r'%\s*Rebonds\s*Offensifs\s+(\d+)%', full_text)
        pct_rd = re.search(r'%\s*Rebonds\s*Défensifs\s+(\d+)%', full_text)
        pct_rt = re.search(r'%\s*Rebond\s*Total\s+(\d+)%', full_text)
        
        if pct_ro:
            adv['pct_rebonds_offensifs'] = int(pct_ro.group(1))
        if pct_rd:
            adv['pct_rebonds_defensifs'] = int(pct_rd.group(1))
        if pct_rt:
            adv['pct_rebonds_total'] = int(pct_rt.group(1))
        
        # Points spéciaux
        pbp = re.search(r'Points de Balles Perdues\s+(\d+)', full_text)
        prq = re.search(r'Points dans la raquette\s+(\d+)', full_text)
        pca = re.search(r'Pts en contre-attaque\s+(\d+)', full_text)
        p2c = re.search(r'Points sur 2ème chance\s+(\d+)', full_text)
        
        advanced_stats.append(adv)
    
    result = {
        'match_info': match_info,
        'period_stats': period_stats,
        'team_advanced_stats': advanced_stats,
    }
    
    # Fusionner avec les données existantes si fournies
    if existing_data:
        existing_data['period_stats'] = period_stats
        if advanced_stats:
            existing_data['advanced_stats'] = advanced_stats
        return existing_data
    
    return result

def extract_boxscore_detaillee_excel(excel_path, existing_data=None):
    """Extrait les stats detaillees depuis un fichier Excel de Boxscore Detaillee"""
    if not PANDAS_AVAILABLE:
        print("pandas non disponible pour l'extraction Excel")
        return existing_data
    
    print(f"Extraction Boxscore Detaillee Excel: {excel_path}")
    
    # Liste des joueuses CSMF connues pour identifier l'équipe
    CSMF_PLAYERS = ['JACOB', 'RIMBAUD', 'SOYEZ', 'REGANI', 'PIGNARRE', 'LIPARO', 'KNOBLOCH', 'MENDES', 'UZEL', 'MUSIC', 'MUSIC PULJIC', 'MUSIC PULJK', 'MUSIC PULJI', 'MUSIC PULJIZ']
    
    try:
        df = pd.read_excel(excel_path, sheet_name=0, header=None)
        
        period_stats = []
        team_advanced_stats = {}
        
        # Première passe : identifier les blocs d'équipes
        # On cherche les lignes "Totaux" et on regarde si le bloc contient des joueuses CSMF
        team_blocks = []  # [(start_idx, end_idx, team_name), ...]
        
        totaux_indices = []
        for idx, row in df.iterrows():
            first_cell = str(row[0]) if pd.notna(row[0]) else ''
            if first_cell == 'Totaux':
                totaux_indices.append(idx)
        
        # Pour chaque bloc entre les Totaux, déterminer l'équipe
        prev_idx = 0
        for totaux_idx in totaux_indices:
            # Chercher si ce bloc contient des joueuses CSMF
            is_csmf = False
            for check_idx in range(prev_idx, totaux_idx):
                player_name = str(df.iloc[check_idx, 1]) if pd.notna(df.iloc[check_idx, 1]) else ''
                player_upper = player_name.upper()
                for csmf_player in CSMF_PLAYERS:
                    if csmf_player in player_upper:
                        is_csmf = True
                        break
                if is_csmf:
                    break
            
            team_name = 'CSMF PARIS' if is_csmf else 'ADVERSAIRE'
            team_blocks.append((prev_idx, totaux_idx, team_name))
            print(f"  Bloc {prev_idx}-{totaux_idx}: {team_name}")
            prev_idx = totaux_idx + 1
        
        # Deuxième passe : extraire les stats par période
        current_team = None
        for idx, row in df.iterrows():
            first_cell = str(row[0]) if pd.notna(row[0]) else ''
            
            # Déterminer l'équipe courante basé sur les blocs
            for start, end, team in team_blocks:
                if start <= idx <= end + 10:  # +10 pour inclure les lignes de période après Totaux
                    current_team = team
                    break
            
            # Détecter les lignes de période
            if first_cell.startswith('Periode') or first_cell.startswith('Période'):
                try:
                    periode_match = re.search(r'P[eé]riode\s*(\d+)', first_cell)
                    if periode_match:
                        periode_num = int(periode_match.group(1))
                        
                        period_data = {
                            'equipe': current_team or 'UNKNOWN',
                            'periode': periode_num,
                            'points': int(float(row[3])) if pd.notna(row[3]) else 0,
                            'rebonds_offensifs': int(float(row[16])) if len(row) > 16 and pd.notna(row[16]) else 0,
                            'rebonds_defensifs': int(float(row[17])) if len(row) > 17 and pd.notna(row[17]) else 0,
                            'rebonds_total': int(float(row[18])) if len(row) > 18 and pd.notna(row[18]) else 0,
                            'passes_decisives': int(float(row[19])) if len(row) > 19 and pd.notna(row[19]) else 0,
                            'interceptions': int(float(row[21])) if len(row) > 21 and pd.notna(row[21]) else 0,
                            'balles_perdues': int(float(row[23])) if len(row) > 23 and pd.notna(row[23]) else 0,
                        }
                        
                        period_stats.append(period_data)
                        print(f"  {current_team} Q{periode_num}: {period_data['points']} pts")
                except Exception as e:
                    print(f"  Erreur période: {e}")
            
            # Détecter stats avancées (elles sont dans les colonnes à droite)
            col34 = str(row[34]) if len(row) > 34 and pd.notna(row[34]) else ''
            col38 = row[38] if len(row) > 38 and pd.notna(row[38]) else None
            
            if 'Points de Balles Perdues' in col34 and col38:
                try: team_advanced_stats['points_balles_perdues'] = int(float(col38))
                except: pass
            if 'Points dans la raquette' in col34 and col38:
                try: team_advanced_stats['points_raquette'] = int(float(col38))
                except: pass
            if 'contre-attaque' in col34.lower() and col38:
                try: team_advanced_stats['points_contre_attaque'] = int(float(col38))
                except: pass
            if 'chance' in col34.lower() and col38:
                try: team_advanced_stats['points_2eme_chance'] = int(float(col38))
                except: pass
        
        print(f"\nStats periodes extraites: {len(period_stats)}")
        for p in period_stats:
            print(f"  - {p['equipe']} Q{p['periode']}: {p['points']} pts")
        
        result = {
            'period_stats': period_stats,
            'team_advanced_stats': team_advanced_stats,
            'has_boxscore_detaillee': True
        }
        
        if existing_data:
            existing_data['period_stats'] = period_stats
            existing_data['team_advanced_stats'] = team_advanced_stats
            existing_data['has_boxscore_detaillee'] = True
            return existing_data
        
        return result
        
    except Exception as e:
        print(f"Erreur extraction Excel: {e}")
        return existing_data

def extract_analyse_5_en_jeu(pdf_path, existing_data=None):
    """Extrait les combinaisons de 5 joueurs depuis l'Analyse des 5 en jeu"""
    print(f"📄 Extraction Analyse des 5 en jeu: {pdf_path}")
    
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
        
        all_tables = []
        for page in pdf.pages:
            tables = page.extract_tables()
            all_tables.extend(tables)
    
    match_info = extract_match_info(full_text)
    
    lineup_stats = []
    current_team = None
    
    for table in all_tables:
        # Chercher les tables de 5 en jeu (9 colonnes avec header "5 en jeu")
        if len(table) < 2 or len(table[0]) < 9:
            continue
        
        for row_idx, row in enumerate(table):
            if not row or len(row) < 2:
                continue
            
            first_cell = str(row[0]).replace('\u200b', '').strip() if row[0] else ''
            
            # Détecter le nom d'équipe (première ligne du bloc)
            if first_cell and not '/' in first_cell and row_idx == 0:
                if 'CSMF' in first_cell.upper():
                    current_team = 'CSMF PARIS'
                elif first_cell.upper() not in ['5 EN JEU', '']:
                    current_team = normalize_team_name(first_cell)
                continue
            
            # Ignorer les lignes d'en-tête
            if first_cell == '5 en jeu' or first_cell == '':
                continue
            
            # Détecter une ligne de combinaison (contient des numéros de joueurs séparés par /)
            # Format: "1- NOM M/ 4- NOM C/ 7- NOM J/ ..."
            if '/' in first_cell and re.search(r'\d+\s*-', first_cell):
                try:
                    # Nettoyer les caractères invisibles
                    joueurs = first_cell.replace('\u200b', '').strip()
                    
                    # Extraire les autres colonnes
                    temps = str(row[1]).strip() if len(row) > 1 and row[1] else ''
                    score = str(row[2]).strip() if len(row) > 2 and row[2] else ''
                    ecart_str = str(row[3]).strip() if len(row) > 3 and row[3] else '0'
                    pts_min_str = str(row[4]).strip() if len(row) > 4 and row[4] else '0'
                    rebonds_str = str(row[5]).strip() if len(row) > 5 and row[5] else '0'
                    inter_str = str(row[6]).strip() if len(row) > 6 and row[6] else '0'
                    bp_str = str(row[7]).strip() if len(row) > 7 and row[7] else '0'
                    pd_str = str(row[8]).strip() if len(row) > 8 and row[8] else '0'
                    
                    # Parser le score "X-Y"
                    score_parts = score.split('-') if '-' in score else [score, '0']
                    score_pour = int(score_parts[0]) if score_parts[0].isdigit() else 0
                    score_contre = int(score_parts[1]) if len(score_parts) > 1 and score_parts[1].isdigit() else 0
                    
                    # Parser l'écart (peut être négatif)
                    try:
                        ecart = int(ecart_str)
                    except:
                        ecart = 0
                    
                    # Parser pts/min (format français avec virgule)
                    try:
                        pts_min = float(pts_min_str.replace(',', '.'))
                        # Protection contre NaN et Inf
                        import math
                        if math.isnan(pts_min) or math.isinf(pts_min):
                            pts_min = 0.0
                    except:
                        pts_min = 0.0
                    
                    lineup = {
                        'equipe': normalize_team_name(current_team) if current_team else 'CSMF PARIS',
                        'joueurs': joueurs,
                        'temps_jeu': temps,
                        'temps_secondes': parse_time_to_seconds(temps),
                        'score_pour': score_pour,
                        'score_contre': score_contre,
                        'ecart': ecart,
                        'pts_par_minute': pts_min,
                        'rebonds': int(rebonds_str) if rebonds_str.isdigit() else 0,
                        'interceptions': int(inter_str) if inter_str.isdigit() else 0,
                        'balles_perdues': int(bp_str) if bp_str.isdigit() else 0,
                        'passes_decisives': int(pd_str) if pd_str.isdigit() else 0,
                    }
                    
                    lineup_stats.append(lineup)
                    ecart_display = f"+{ecart}" if ecart > 0 else str(ecart)
                    print(f"  ✓ {current_team}: {joueurs[:40]}... | {temps} | {score} ({ecart_display})")
                    
                except Exception as e:
                    print(f"  ⚠️ Erreur parsing lineup: {e}")
                    continue
    
    print(f"\n📊 Total: {len(lineup_stats)} combinaisons de 5 extraites")
    
    result = {
        'match_info': match_info,
        'lineup_stats': lineup_stats,
    }
    
    if existing_data:
        existing_data['lineup_stats'] = lineup_stats
        return existing_data
    
    return result


def extract_stats_detaillees(pdf_path, existing_data=None):
    """
    Extrait les données du fichier Statistiques_détaillées
    Contient des stats avancées non présentes dans le FIBA Box Score :
    - Tirs 2pts Intérieur vs Extérieur par joueuse
    - Ratios PB/BP, IN/BP, F/FPR par équipe
    - Stats 5 de départ vs Banc
    - Stats par mi-temps
    - Avantage max, Séries, Changements de leader
    """
    print(f"📄 Extraction Statistiques Détaillées: {pdf_path}")
    
    result = existing_data if existing_data else {
        'match_info': {},
        'player_stats': [],
        'team_stats': [],
        'advanced_stats': {},
        'period_stats': [],
        'lineup_stats': []
    }
    
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) == 0:
            return result
        
        page = pdf.pages[0]
        tables = page.extract_tables()
        text = page.extract_text() or ""
        
        # Détecter les équipes depuis le texte (format: EQUIPE1 - EQUIPE2 XX-XX)
        match_info = re.search(r'([A-Z][A-Z\s\-\']+)\s+-\s+([A-Z][A-Z\s\-\']+)\s+(\d+)-(\d+)', text)
        equipe1 = None
        equipe2 = None
        if match_info:
            equipe1 = match_info.group(1).strip()
            equipe2 = match_info.group(2).strip()
        
        # Trouver quelle équipe est CSMF
        is_csmf_equipe1 = equipe1 and 'CSMF' in equipe1.upper()
        is_csmf_equipe2 = equipe2 and 'CSMF' in equipe2.upper()
        
        # Extraire les stats avancées - on cherche TOUTES les occurrences
        advanced = {}
        
        # Points dans la raquette (2 valeurs: équipe1, équipe2)
        matches = re.findall(r'Points dans la raquette\s+(\d+)', text)
        if len(matches) >= 2:
            # Première valeur = équipe1, deuxième = équipe2
            if is_csmf_equipe2:
                advanced['points_raquette'] = int(matches[1])  # CSMF est équipe2
            else:
                advanced['points_raquette'] = int(matches[0])  # CSMF est équipe1 ou par défaut
        elif len(matches) == 1:
            advanced['points_raquette'] = int(matches[0])
        
        # Points en contre-attaque
        matches = re.findall(r'Pts en contre-attaque\s+(\d+)', text)
        if len(matches) >= 2:
            advanced['points_contre_attaque'] = int(matches[1]) if is_csmf_equipe2 else int(matches[0])
        elif len(matches) == 1:
            advanced['points_contre_attaque'] = int(matches[0])
        
        # Points sur 2ème chance
        matches = re.findall(r'Points sur 2ème chance\s+(\d+)', text)
        if len(matches) >= 2:
            advanced['points_2eme_chance'] = int(matches[1]) if is_csmf_equipe2 else int(matches[0])
        elif len(matches) == 1:
            advanced['points_2eme_chance'] = int(matches[0])
        
        # Avantage Maximum
        matches = re.findall(r'Avantage Maximum\s+(\d+)', text)
        if len(matches) >= 2:
            advanced['avantage_max'] = int(matches[1]) if is_csmf_equipe2 else int(matches[0])
        elif len(matches) == 1:
            advanced['avantage_max'] = int(matches[0])
        
        # Série Maximum
        matches = re.findall(r'Série Maximum\s+(\d+-\d+)', text)
        if len(matches) >= 2:
            advanced['serie_max'] = matches[1] if is_csmf_equipe2 else matches[0]
        elif len(matches) == 1:
            advanced['serie_max'] = matches[0]
        
        # Égalités (valeur unique, partagée)
        match = re.search(r'Egalités\s+(\d+)', text)
        if match:
            advanced['egalites'] = int(match.group(1))
        
        # Changements de Leader (valeur unique, partagée)
        match = re.search(r'Changements de Leader\s+(\d+)', text)
        if match:
            advanced['changements_leader'] = int(match.group(1))
        
        # % Rebonds (prendre les valeurs CSMF)
        matches = re.findall(r'% Rebonds Offensifs\s+(\d+)%', text)
        if len(matches) >= 2:
            advanced['pct_rebonds_off'] = int(matches[1]) if is_csmf_equipe2 else int(matches[0])
        elif len(matches) == 1:
            advanced['pct_rebonds_off'] = int(matches[0])
            
        matches = re.findall(r'% Rebonds Défensifs\s+(\d+)%', text)
        if len(matches) >= 2:
            advanced['pct_rebonds_def'] = int(matches[1]) if is_csmf_equipe2 else int(matches[0])
        elif len(matches) == 1:
            advanced['pct_rebonds_def'] = int(matches[0])
            
        matches = re.findall(r'% Rebond Total\s+(\d+)%', text)
        if len(matches) >= 2:
            advanced['pct_rebonds_total'] = int(matches[1]) if is_csmf_equipe2 else int(matches[0])
        elif len(matches) == 1:
            advanced['pct_rebonds_total'] = int(matches[0])
        
        # Parser les tables pour les stats joueuses avec tirs int/ext
        player_stats_detailed = []
        csmf_cinq_depart = None
        csmf_banc = None
        
        for table in tables:
            if not table or len(table) < 3:
                continue
            
            # Détecter si c'est une table de stats joueuses (contient "Min", "PTS", etc.)
            header_row = table[0] if table else []
            second_row = table[1] if len(table) > 1 else []
            
            # Chercher les indices des colonnes
            header_str = ' '.join([str(c) for c in header_row + second_row if c])
            
            if '2 pts Ext' in header_str or '2 pts Int' in header_str:
                # C'est une table de stats détaillées joueuses
                equipe = None
                is_csmf_table = False
                for cell in header_row:
                    cell_str = str(cell).upper() if cell else ''
                    if 'CSMF' in cell_str or 'PARIS' in cell_str:
                        equipe = str(cell).strip()
                        is_csmf_table = True
                        break
                    elif cell and len(cell_str) > 3:
                        equipe = str(cell).strip()
                
                # Parser chaque ligne de joueuse
                for row in table[2:]:  # Skip header rows
                    if not row or len(row) < 20:
                        continue
                    
                    # Vérifier si c'est une ligne de joueuse (commence par numéro ou *numéro)
                    first_cell = str(row[0] or '').strip()
                    if not first_cell or first_cell in ['Equipe/Coach', 'Totaux', '5 de Départ', 'Banc']:
                        # Lignes spéciales - on ne prend que celles de CSMF
                        if is_csmf_table:
                            if '5 de Départ' in first_cell or (row[1] and '5 de Départ' in str(row[1])):
                                # Stats du 5 de départ CSMF
                                csmf_cinq_depart = {
                                    'points': _safe_int(row[3]) if len(row) > 3 else 0,
                                    'tirs': row[4] if len(row) > 4 else '0/0',
                                }
                            elif 'Banc' in first_cell or (row[1] and 'Banc' in str(row[1])):
                                # Stats du banc CSMF
                                csmf_banc = {
                                    'points': _safe_int(row[3]) if len(row) > 3 else 0,
                                    'tirs': row[4] if len(row) > 4 else '0/0',
                                }
                        continue
                    
                    # C'est une joueuse
                    try:
                        # Format: [num, nom, min, pts, tirs_tot, %, 3pts, %, 2pts_ext, %, 2pts_int, %, du, lf, %, ...]
                        numero = first_cell.replace('*', '')
                        nom = str(row[1] or '').strip()
                        
                        if not nom or nom == 'None':
                            continue
                        
                        player_data = {
                            'numero': numero,
                            'nom': nom,
                            'equipe': equipe,
                            'starter': '*' in first_cell,
                            'tirs_2pts_ext': row[8] if len(row) > 8 else '0/0',
                            'tirs_2pts_int': row[10] if len(row) > 10 else '0/0',
                            'dunks': _safe_int(row[12]) if len(row) > 12 else 0,
                        }
                        player_stats_detailed.append(player_data)
                        print(f"  ✓ {nom}: 2pts Ext={player_data['tirs_2pts_ext']}, 2pts Int={player_data['tirs_2pts_int']}")
                    except Exception as e:
                        continue
        
        # Ajouter les stats 5 de départ et banc CSMF
        if csmf_cinq_depart:
            advanced['cinq_depart'] = csmf_cinq_depart
        if csmf_banc:
            advanced['banc'] = csmf_banc
        
        # Stocker les résultats
        result['stats_detaillees'] = {
            'advanced': advanced,
            'player_details': player_stats_detailed
        }
        
        print(f"📊 Stats avancées extraites: {list(advanced.keys())}")
        print(f"📊 Joueuses avec détail tirs: {len(player_stats_detailed)}")
    
    return result


def _safe_int(val):
    """Convertit en int de manière sécurisée"""
    if val is None:
        return 0
    try:
        return int(str(val).strip())
    except:
        return 0


def extract_from_pdf(pdf_path):
    """Fonction principale d'extraction - détecte automatiquement le type de PDF"""
    pdf_path = Path(pdf_path)
    
    if not pdf_path.exists():
        print(f"❌ Fichier {pdf_path} introuvable")
        return None
    
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages[:2]:  # Lire seulement les 2 premières pages pour la détection
            page_text = page.extract_text()
            if page_text:
                full_text += page_text + "\n"
    
    pdf_type = detect_pdf_type(full_text, pdf_path.name)
    print(f"📋 Type détecté: {pdf_type}")
    
    if pdf_type == 'FIBA_BOX_SCORE':
        return extract_fiba_box_score(pdf_path)
    elif pdf_type == 'BOXSCORE_DETAILLEE':
        return extract_boxscore_detaillee(pdf_path)
    elif pdf_type == 'ANALYSE_5':
        return extract_analyse_5_en_jeu(pdf_path)
    elif pdf_type == 'STATS_DETAILLEES':
        return extract_stats_detaillees(pdf_path)
    elif pdf_type == 'EVALUATION_JOUEUSE':
        # Pour l'instant, retourner le type pour traitement spécial (extraction tirs)
        return {'pdf_type': 'EVALUATION_JOUEUSE', 'path': str(pdf_path)}
    elif pdf_type in ['ZONES_TIRS', 'POSITION_TIRS']:
        print(f"⏭️ Type {pdf_type} ignoré (visuel uniquement)")
        return {'pdf_type': pdf_type, 'path': str(pdf_path), 'ignored': True}
    elif pdf_type == 'UNKNOWN':
        print(f"⚠️ Type de fichier non reconnu: {pdf_path.name}")
        return {'pdf_type': 'UNKNOWN', 'path': str(pdf_path), 'error': 'Type non reconnu'}
    
    return extract_fiba_box_score(pdf_path)

def extract_match_complete(fiba_path, boxscore_path=None, analyse5_path=None):
    """
    Extraction complète d'un match avec tous les fichiers disponibles
    
    Args:
        fiba_path: Chemin vers le FIBA_Box_Score (obligatoire)
        boxscore_path: Chemin vers Boxscore_Détaillée (optionnel)
        analyse5_path: Chemin vers Analyse_des_5_en_jeu (optionnel)
    
    Returns:
        dict: Données complètes du match
    """
    print("="*60)
    print("EXTRACTION COMPLÈTE DU MATCH")
    print("="*60)
    
    # 1. Extraire les données de base depuis FIBA Box Score
    data = extract_fiba_box_score(fiba_path)
    
    if not data:
        print("❌ Échec extraction FIBA Box Score")
        return None
    
    # 2. Enrichir avec Boxscore Détaillée si disponible
    if boxscore_path and Path(boxscore_path).exists():
        print("\n" + "-"*40)
        data = extract_boxscore_detaillee(boxscore_path, data)
    
    # 3. Enrichir avec Analyse des 5 si disponible
    if analyse5_path and Path(analyse5_path).exists():
        print("\n" + "-"*40)
        data = extract_analyse_5_en_jeu(analyse5_path, data)
    
    print("\n" + "="*60)
    print("RÉSUMÉ")
    print("="*60)
    print(f"Match: {data['match_info'].get('equipe_domicile')} vs {data['match_info'].get('equipe_exterieur')}")
    print(f"Score: {data['match_info'].get('score_domicile')}-{data['match_info'].get('score_exterieur')}")
    print(f"Joueuses: {len(data['player_stats'])}")
    print(f"Stats par période: {len(data.get('period_stats', []))}")
    print(f"Combinaisons de 5: {len(data.get('lineup_stats', []))}")
    
    return data

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python extract_stats.py <fiba_box_score.pdf>")
        print("  python extract_stats.py <fiba.pdf> <boxscore.pdf> <analyse5.pdf>")
        return
    
    fiba_path = sys.argv[1]
    boxscore_path = sys.argv[2] if len(sys.argv) > 2 else None
    analyse5_path = sys.argv[3] if len(sys.argv) > 3 else None
    
    if boxscore_path or analyse5_path:
        data = extract_match_complete(fiba_path, boxscore_path, analyse5_path)
    else:
        data = extract_from_pdf(fiba_path)
    
    if data:
        output_path = "extracted_data.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Données sauvegardées: {output_path}")

if __name__ == "__main__":
    main()
