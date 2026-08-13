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

# PERCORSI PER GITHUB (Crea una cartella dedicata sul Desktop per la sincronizzazione)
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
GITHUB_DIR = os.path.join(desktop_path, "BotCalcioGitHub")

# Assicura che la cartella per GitHub esista sul Desktop
if not os.path.exists(GITHUB_DIR):
    os.makedirs(GITHUB_DIR)

STATE_FILE = os.path.join(GITHUB_DIR, "stato_precedente.json")
STORICO_FILE = os.path.join(GITHUB_DIR, "storico_pronostici.json")


def carica_stato():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def salva_stato(stato):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(stato, f, indent=4)
    except Exception as e:
        print(f"Errore salvataggio stato per GitHub: {e}")


def registra_storico(nuovo_record):
    storico = []
    if os.path.exists(STORICO_FILE):
        try:
            with open(STORICO_FILE, "r", encoding="utf-8") as f:
                storico = json.load(f)
        except:
            storico = []
    
    storico.append(nuovo_record)
    try:
        with open(STORICO_FILE, "w", encoding="utf-8") as f:
            json.dump(storico, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Errore salvataggio storico per GitHub: {e}")


def invia_telegram(testo):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(
            url, data={"chat_id": CHAT_ID, "text": testo, "parse_mode": "Markdown"}
        )
    except:
        pass


def get_stats(stats, tipo):
    tipi_da_cercare = [tipo]
    if tipo == "On Target":
        tipi_da_cercare = ["On Target", "Shots on Goal", "Shots On Target"]
    elif tipo == "Off Target":
        tipi_da_cercare = ["Off Target", "Shots Off Goal", "Shots Off Target"]
    elif tipo == "Dangerous Attacks":
        tipi_da_cercare = ["Dangerous Attacks", "dangerous_attacks"]
    elif tipo == "Corners":
        tipi_da_cercare = ["Corners", "Corner Kicks"]

    for s in stats:
        if s.get("type") in tipi_da_cercare:
            try:
                h = int(str(s.get("home", 0)).replace("%", "").strip() or 0)
                a = int(str(s.get("away", 0)).replace("%", "").strip() or 0)
                return h, a
            except:
                return 0, 0
    return 0, 0


def estrai_minuto(status_str):
    numeri = re.findall(r"\d+", str(status_str))
    return int(numeri[0]) if numeri else 0


def analizza_h2h_completo(team_id_1, team_id_2, headers, url_base):
    if not team_id_1 or not team_id_2:
        return 2.5, "📈 H2H: Dati non disponibili."
    querystring = {
        "action": "get_H2H",
        "firstTeamId": team_id_1,
        "secondTeamId": team_id_2,
    }
    try:
        response = requests.get(url_base, headers=headers, params=querystring)
        dati = response.json()
        partite = (
            dati.get("result", dati.get("data", []))
            if isinstance(dati, dict)
            else dati
        )
        if not partite:
            return 2.5, "📈 H2H: Nessun precedente."
        ultime = partite[:4]
        tot_gol = sum(
            int(p.get("match_hometeam_score", 0) or 0)
            + int(p.get("match_awayteam_score", 0) or 0)
            for p in ultime
        )
        media = tot_gol / len(ultime)
        return media, f"📈 Media gol ultimi precedenti: {media:.1f}"
    except:
        return 2.5, "📈 H2H: Errore."


def calcolo_totale_ia(minuto, gol_totali, attacchi_pericolosi, tiri_porta, corner_tot, delta_attacchi_pericolosi, delta_tiri_porta, delta_corner, apm, score_prec=0):
    score_ia = 0
    stato_match = "PARTITA IN STALLO / LENTA"
    consiglio = None
    segnale = None

    if gol_totali >= 4:
        base_consiglio = "OVER 4.5 / OVER 5.5 LIVE / NEXT GOAL"
    elif gol_totali == 3:
        base_consiglio = "OVER 3.5 / OVER 4.5 LIVE / NEXT GOAL"
    elif gol_totali == 2:
        base_consiglio = "OVER 2.5 / OVER 3.5 LIVE / NEXT GOAL"
    elif gol_totali == 1:
        base_consiglio = "OVER 1.5 / OVER 2.5 LIVE"
    else:
        base_consiglio = "OVER 0.5 HT / OVER 1.5"

    # PALETTO RIGIDO ANTI-STERILITÀ: Richiede almeno 3 tiri in porta totali
    if tiri_porta < 3:
        return 20, "Partita con tiri in porta insufficienti (Sterile)", None, None

    if 10 <= minuto <= 30:
        if delta_attacchi_pericolosi >= 3 and apm >= 0.8:
            score_ia = 75
            stato_match = "ALTA VELOCITÀ INIZIALE (Pressione alta)"
            segnale = "OVER INIZIALE"
            consiglio = base_consiglio
        else:
            score_ia = 35
            stato_match = "Fase iniziale bloccata o di studio"

    elif 30 <= minuto <= 45:
        if delta_attacchi_pericolosi >= 4 or delta_tiri_porta >= 2:
            score_ia = 85
            stato_match = "ACCELERAZIONE FORTE 1°T"
            segnale = "PRESSIONE FINALE 1°T"
            consiglio = base_consiglio
        else:
            score_ia = 40
            stato_match = "Ritmo basso fine 1°T"

    elif 45 <= minuto <= 65:
        if score_prec >= 75 and minuto <= 52:
            score_ia = 85
            stato_match = "MOMENTUM DAL 1° TEMPO"
            segnale = "CONTINUITÀ 2°T"
            consiglio = base_consiglio
        elif (delta_attacchi_pericolosi >= 5 or delta_tiri_porta >= 2) and (tiri_porta >= 4 or corner_tot >= 5):
            score_ia = 90
            stato_match = "ASSALTO D'INIZIO 2°T"
            segnale = "GOL IN ARRIVO 2°T"
            consiglio = base_consiglio
        else:
            score_ia = 45
            stato_match = "Inizio 2°T compassato"

    elif 65 <= minuto <= 88:
        if delta_attacchi_pericolosi >= 6 or delta_tiri_porta >= 3:
            score_ia = 95
            stato_match = "ASSALTO MOSTRUOSO FINALE"
            segnale = "ASSALTO FINALE"
            consiglio = base_consiglio
        else:
            score_ia = 25
            stato_match = "Rischio Under"

    return score_ia, stato_match, segnale, consiglio


print(f"🤖 Bot Calcio Live - Pronto per GitHub nella cartella: {GITHUB_DIR}")

if __name__ == "__main__":
    while True:
        stato_precedente = carica_stato()
        new_state = {}
        
        tabella_per_partita = {}
        selezioni_master_ai = []

        try:
            resp = requests.get(
                "https://apifootball3.p.rapidapi.com/",
                headers={
                    "x-rapidapi-key": API_KEY,
                    "x-rapidapi-host": API_HOST,
                },
                params={"action": "get_events", "match_live": "1"},
            )
            partite = resp.json()

            if isinstance(partite, list):
                for m in partite:
                    match_id = str(m.get("match_id"))
                    
                    nazione = m.get("country_name") or m.get("league_country") or "Internazionale"
                    campionato = m.get("league_name") or "Campionato"

                    stats = m.get("statistics", [])
                    h_tiri_porta, a_tiri_porta = get_stats(stats, "On Target")
                    h_tiri_off, a_tiri_off = get_stats(stats, "Off Target")
                    h_attacchi_pericolosi, a_attacchi_pericolosi = get_stats(stats, "Dangerous Attacks")
                    h_corner, a_corner = get_stats(stats, "Corners")

                    minuto = estrai_minuto(m.get("match_status", "0"))
                    if minuto == 0:
                        continue

                    tiri_porta = h_tiri_porta + a_tiri_porta
                    tiri_tot = (h_tiri_porta + h_tiri_off) + (a_tiri_porta + a_tiri_off)
                    attacchi_pericolosi = h_attacchi_pericolosi + a_attacchi_pericolosi
                    corner_tot = h_corner + a_corner
                    gol_c = int(m.get("match_hometeam_score", 0) or 0)
                    gol_o = int(m.get("match_awayteam_score", 0) or 0)
                    gol_totali = gol_c + gol_o

                    casa = m.get("match_hometeam_name")
                    ospite = m.get("match_awayteam_name")
                    id_casa = m.get("match_hometeam_id") or m.get("home_team_id")
                    id_ospite = m.get("match_awayteam_id") or m.get("away_team_id")

                    vecchio = stato_precedente.get(
                        match_id,
                        {
                            "attacchi_pericolosi": attacchi_pericolosi,
                            "tiri_porta": tiri_porta,
                            "corner": corner_tot,
                            "score_ia": 0,
                        },
                    )

                    if "h2h_data" not in vecchio:
                        media_h2h, testo_h2h = analizza_h2h_completo(
                            id_casa, id_ospite,
                            {"x-rapidapi-key": API_KEY, "x-rapidapi-host": API_HOST},
                            "https://apifootball3.p.rapidapi.com/"
                        )
                    else:
                        media_h2h = vecchio["h2h_data"]
                        testo_h2h = vecchio["h2h_text"]

                    delta_attacchi_pericolosi = attacchi_pericolosi - vecchio.get("attacchi_pericolosi", attacchi_pericolosi)
                    delta_tiri_porta = tiri_porta - vecchio.get("tiri_porta", tiri_porta)
                    delta_corner = corner_tot - vecchio.get("corner", corner_tot)
                    score_prec = vecchio.get("score_ia", 0)
                    apm_totale = attacchi_pericolosi / minuto if minuto > 0 else 0

                    score_ia, stato_match, segnale_filtro, consiglio_filtro = calcolo_totale_ia(
                        minuto, gol_totali, attacchi_pericolosi, tiri_porta, corner_tot, 
                        delta_attacchi_pericolosi, delta_tiri_porta, delta_corner, apm_totale, score_prec
                    )

                    conferma_ia = "✅ POSITIVA" if score_ia >= 75 else "❌ NEUTRA"
                    timestamp_attuale = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    if segnale_filtro and score_ia >= 75:
                        if match_id not in tabella_per_partita:
                            tabella_per_partita[match_id] = {
                                "campionato": f"{nazione} - {campionato}",
                                "partita": f"{casa} vs {ospite}",
                                "minuto": minuto,
                                "risultato": f"{gol_c}-{gol_o}",
                                "delta_ap": delta_attacchi_pericolosi,
                                "tiri": tiri_porta,
                                "filtri_attivi": []
                            }
                        
                        tabella_per_partita[match_id]["filtri_attivi"].append({
                            "segnale": segnale_filtro,
                            "consiglio": consiglio_filtro,
                            "score": score_ia
                        })
                        
                        registra_storico({
                            "data_ora": timestamp_attuale,
                            "match_id": match_id,
                            "tipo_segnale": segnale_filtro,
                            "nazione": nazione,
                            "campionato": campionato,
                            "partita": f"{casa} vs {ospite}",
                            "minuto_invio": minuto,
                            "risultato_live_invio": f"{gol_c}-{gol_o}",
                            "consiglio": consiglio_filtro,
                            "score_ia": score_ia,
                            "stato_ia_descrizione": stato_match,
                            "ia_status": conferma_ia,
                            "statistiche_match": {
                                "tiri_porta": tiri_porta,
                                "tiri_totali": tiri_tot,
                                "attacchi_pericolosi": attacchi_pericolosi,
                                "delta_attacchi_pericolosi": delta_attacchi_pericolosi,
                                "delta_tiri_porta": delta_tiri_porta,
                                "apm": round(apm_totale, 2)
                            },
                            "esito_finale_da_verificare": "DA_COMPLETARE"
                        })

                    if 15 <= minuto <= 82:
                        if score_ia >= 75:
                            if gol_totali == 0:
                                mercato_ai = "OVER 1.5 LIVE"
                            elif gol_totali == 1:
                                mercato_ai = "OVER 2.5 LIVE"
                            elif gol_totali == 2:
                                mercato_ai = "OVER 3.5 LIVE"
                            else:
                                mercato_ai = f"OVER {gol_totali + 1}.5 LIVE"

                            selezioni_master_ai.append({
                                "match": f"{casa} vs {ospite}",
                                "campionato": f"{nazione} - {campionato}",
                                "minuto": minuto,
                                "risultato": f"{gol_c}-{gol_o}",
                                "score": score_ia,
                                "mercato": mercato_ai,
                            })

                    new_state[match_id] = {
                        "attacchi_pericolosi": attacchi_pericolosi,
                        "tiri_porta": tiri_porta,
                        "corner": corner_tot,
                        "score_ia": score_ia,
                        "h2h_data": media_h2h,
                        "h2h_text": testo_h2h,
                    }

            if len(tabella_per_partita) > 0:
                testo_tabella = "📊 *TABELLA LIVE: SEGNALI ATTIVI* ⚡\n\n"
                for idx, (m_id, item) in enumerate(tabella_per_partita.items(), 1):
                    testo_tabella += (
                        f"*{idx}. {item['partita']}* (Min {item['minuto']} | 🥅 {item['risultato']})\n"
                        f"🌍 _{item['campionato']}_\n"
                    )
                    for f in item["filtri_attivi"]:
                        testo_tabella += f"   🎯 Filtro: *{f['segnale']}* ➔ {f['consiglio']} (Score: {f['score']})\n"
                    
                    testo_tabella += (
                        f"   📈 Δ Attacchi Pericolosi: +{item['delta_ap']} | Tiri in porta totali: {item['tiri']}\n"
                        f"----------------------------------------\n"
                    )
                invia_telegram(testo_tabella)

            if len(selezioni_master_ai) >= 2:
                selezioni_master_ai.sort(key=lambda x: x["score"], reverse=True)
                testo_m2 = (
                    f"👑 *AI QUANT ACCUMULATOR (MULTIPLA MASTER)* 🚀\n\n"
                )
                for idx, item in enumerate(selezioni_master_ai[:3], 1):
                    testo_m2 += (
                        f"{idx}. *{item['match']}* (Min {item['minuto']} | {item['risultato']})\n"
                        f"   ➔ Puntata: *{item['mercato']}* (Confidence: {item['score']}%)\n\n"
                    )
                testo_m2 += "🎯 _Stake ridotto consigliato (es. 2€)._"
                invia_telegram(testo_m2)

            salva_stato(new_state)

        except Exception as e:
            print(f"Errore nel ciclo: {e}")

        print("⏳ [Cloud] Attendo 5 minuti per la prossima scansione...")
        time.sleep(300)
