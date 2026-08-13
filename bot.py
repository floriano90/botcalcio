import json
import os
import re
import requests
import time
import datetime

# CONFIGURAZIONE
API_KEY = "25a50b1640mshe6f07a04788a9e5p146782jsne750194545aa"
API_HOST = "apifootball3.p.rapidapi.com"
TELEGRAM_TOKEN = "8943323226:AAGZo6K4Vnw-P2fF8QIP2q-5B_oPRHk-6cg"
CHAT_ID = "7417588888"
STATE_FILE = "stato_precedente.json"

def carica_stato():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {"ultimi_segnali": {}}
    return {"ultimi_segnali": {}}

def salva_stato(stato):
    with open(STATE_FILE, "w", encoding="utf-8") as f: json.dump(stato, f, indent=4)

def invia_telegram(testo):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": testo, "parse_mode": "Markdown"})
    except: pass

def get_stats(stats, tipo):
    for s in stats:
        if s.get("type") == tipo:
            try: return int(str(s.get("home", 0)).replace("%", "").strip() or 0), int(str(s.get("away", 0)).replace("%", "").strip() or 0)
            except: return 0, 0
    return 0, 0

def analizza_h2h_completo(id1, id2):
    try:
        resp = requests.get("https://apifootball3.p.rapidapi.com/", headers={"x-rapidapi-key": API_KEY, "x-rapidapi-host": API_HOST}, params={"action": "get_H2H", "firstTeamId": id1, "secondTeamId": id2})
        dati = resp.json()
        partite = dati.get("result", [])
        if not partite: return 2.5
        media = sum(int(p.get("match_hometeam_score",0) or 0) + int(p.get("match_awayteam_score",0) or 0) for p in partite[:4]) / len(partite[:4])
        return media
    except: return 2.5

if __name__ == "__main__":
    while True:
        stato = carica_stato()
        nuovo_stato = {"ultimi_segnali": stato.get("ultimi_segnali", {})}
        
        try:
            partite = requests.get("https://apifootball3.p.rapidapi.com/", headers={"x-rapidapi-key": API_KEY, "x-rapidapi-host": API_HOST}, params={"action": "get_events", "match_live": "1"}).json()
            if isinstance(partite, list):
                for m in partite:
                    match_id = str(m.get("match_id"))
                    nazione = m.get("country_name", "N/A")
                    camp = m.get("league_name", "N/A")
                    if "friendly" in camp.lower(): continue
                    
                    minuto = int(re.findall(r"\d+", str(m.get("match_status", "0")))[0]) if re.findall(r"\d+", str(m.get("match_status", "0"))) else 0
                    gol_c, gol_o = int(m.get("match_hometeam_score", 0) or 0), int(m.get("match_awayteam_score", 0) or 0)
                    gol_tot = gol_c + gol_o
                    
                    h_tiri, a_tiri = get_stats(m.get("statistics", []), "On Target")
                    h_att, a_att = get_stats(m.get("statistics", []), "Dangerous Attacks")
                    tiri_porta = h_tiri + a_tiri
                    attacchi = h_att + a_att
                    apm = attacchi / minuto if minuto > 0 else 0
                    
                    # Confluenza & Score IA
                    score_ia = 20 if analizza_h2h_completo(m.get("match_hometeam_id"), m.get("match_awayteam_id")) >= 2.6 else 0
                    score_ia += 35 if apm >= 1.2 else 0
                    score_ia += 25 if tiri_porta >= 4 else 0
                    
                    is_confluenza = match_id in nuovo_stato["ultimi_segnali"]
                    
                    # FILTRI
                    segnale, consiglio = None, None
                    if 15 <= minuto <= 38 and gol_tot <= 1 and tiri_porta >= 3:
                        segnale, consiglio = "🎯 HT ALPHA-FIRST", "OVER 0.5 HT"
                    elif 45 <= minuto <= 75 and gol_tot < 3 and (attacchi >= 6 or tiri_porta >= 7):
                        consiglio = "OVER 0.5 LIVE" if gol_tot == 0 else "OVER 2.5 LIVE"
                        segnale = "🔥 OVER 2.5 DYNAMIC"
                    elif 52 <= minuto <= 78 and attacchi >= 7 and tiri_porta >= 2:
                        segnale, consiglio = "💥 ALPHA-SURGE", "OVER 0.5 LIVE"
                    elif 50 <= minuto <= 78 and tiri_porta >= 6 and gol_tot < 3:
                        segnale, consiglio = "⚡ ASSALTO MOSTRUOSO", "OVER 1.5 LIVE"

                    if segnale:
                        nuovo_stato["ultimi_segnali"][match_id] = True
                        titolo = "🚨 GOLDEN TRADE (CONFLUENZA)" if is_confluenza else f"🔔 {segnale}"
                        conferma = "✅ IA POSITIVA" if score_ia >= 70 else "⚠️ IA NEUTRA"
                        invia_telegram(f"*{titolo}*\n🌍 {nazione} - {camp}\n⚽ {m.get('match_hometeam_name')} vs {m.get('match_awayteam_name')}\n⏱️ Min: {minuto} | Ris: {gol_c}-{gol_o}\n👉 PUNTA: *{consiglio}*\n📊 {conferma} (Score {score_ia}/100)")
            
            salva_stato(nuovo_stato)
        except Exception as e: print(f"Errore: {e}")
        time.sleep(300)
