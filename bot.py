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

# Percorsi sul Desktop per i file di stato e storico
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
STATE_FILE = os.path.join(desktop_path, "stato_precedente.json")
STORICO_FILE = os.path.join(desktop_path, "storico_pronostici.json")


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
  except:
    pass


def registra_storico(nuovo_record):
  """Registra ogni pronostico inviato con tutti i parametri di telemetria per il backtesting."""
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
    print(f"Errore salvataggio storico: {e}")


def invia_telegram(testo):
  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  try:
    requests.post(
        url, data={"chat_id": CHAT_ID, "text": testo, "parse_mode": "Markdown"}
    )
  except:
    pass


def get_stats(stats, tipo):
  for s in stats:
    if s.get("type") == tipo:
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


def calcolo_totale_ia(minuto, gol_totali, attacchi, tiri_porta, corner_tot, delta_attacchi, delta_tiri_porta, delta_corner, apm, score_prec=0):
    score_ia = 0
    stato_match = "PARTITA IN STALLO / LENTA"
    consiglio = None
    segnale = None

    if 10 <= minuto <= 30:
        if (delta_attacchi >= 3 and apm >= 1.0) or (tiri_porta >= 2 and attacchi >= 5):
            score_ia = 75
            stato_match = "ALTA VELOCITÀ INIZIALE (Pressione alta)"
            segnale = "🎯 OVER INIZIALE"
            consiglio = "OVER 0.5 HT / OVER 1.5"
        else:
            score_ia = 35
            stato_match = "Fase iniziale bloccata o di studio"

    elif 30 <= minuto <= 45 and gol_totali <= 1:
        if (delta_attacchi >= 4 or delta_tiri_porta >= 2) or (attacchi >= 8 and tiri_porta >= 3):
            score_ia = 85
            stato_match = "ACCELERAZIONE FORTE 1°T"
            segnale = "🔥 PRESSIONE FINALE 1°T"
            consiglio = "OVER 0.5 HT / OVER 1.5 LIVE"
        else:
            score_ia = 40
            stato_match = "Ritmo basso fine 1°T"

    elif 45 <= minuto <= 65 and gol_totali < 3:
        if score_prec >= 75 and minuto <= 52:
            score_ia = 85
            stato_match = "MOMENTUM DAL 1° TEMPO"
            segnale = "💥 CONTINUITÀ 2°T"
            consiglio = "OVER 1.5 / OVER 2.5 LIVE"
        elif (delta_attacchi >= 5 or delta_tiri_porta >= 2) and (tiri_porta >= 4 or corner_tot >= 5):
            score_ia = 90
            stato_match = "ASSALTO D'INIZIO 2°T"
            segnale = "💥 GOL IN ARRIVO 2°T"
            consiglio = "OVER 1.5 / OVER 2.5 LIVE"
        else:
            score_ia = 45
            stato_match = "Inizio 2°T compassato"

    elif 65 <= minuto <= 88 and gol_totali < 4:
        if (delta_attacchi >= 6 or delta_tiri_porta >= 3) or (attacchi >= 15 and tiri_porta >= 6):
            score_ia = 95
            stato_match = "ASSALTO MOSTRUOSO FINALE"
            segnale = "⚡ ASSALTO FINALE"
            consiglio = "OVER 2.5 / OVER 3.5 LIVE"
        else:
            score_ia = 25
            stato_match = "Rischio Under"

    return score_ia, stato_match, segnale, consiglio


print(
    "🤖 Bot Calcio Live - Tabella Unica con Gestione Filtri Multipli per Match."
)

if __name__ == "__main__":
  while True:
    stato_precedente = carica_stato()
    nuovo_stato = {}
    
    # 📋 DIZIONARIO PER RAGGRUPPARE I FILTRI PER PARTITA NEL CICLO ATTUALE
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
          h_attacchi, a_attacchi = get_stats(stats, "Dangerous Attacks")
          h_corner, a_corner = get_stats(stats, "Corners")

          minuto = estrai_minuto(m.get("match_status", "0"))
          if minuto == 0:
            continue

          tiri_porta = h_tiri_porta + a_tiri_porta
          tiri_tot = (h_tiri_porta + h_tiri_off) + (a_tiri_porta + a_tiri_off)
          attacchi = h_attacchi + a_attacchi
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
                  "attacchi": attacchi,
                  "tiri_porta": tiri_porta,
                  "corner": corner_tot,
                  "score_ia": 0,
              },
          )
          delta_attacchi = attacchi - vecchio["attacchi"]
          delta_tiri_porta = tiri_porta - vecchio.get("tiri_porta", tiri_porta)
          delta_corner = corner_tot - vecchio["corner"]
          score_prec = vecchio.get("score_ia", 0)
          apm_totale = attacchi / minuto if minuto > 0 else 0

          score_ia, stato_match, segnale_filtro, consiglio_filtro = calcolo_totale_ia(
              minuto, gol_totali, attacchi, tiri_porta, corner_tot, 
              delta_attacchi, delta_tiri_porta, delta_corner, apm_totale, score_prec
          )

          conferma_ia = "✅ POSITIVA" if score_ia >= 75 else "❌ NEUTRA"
          timestamp_attuale = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

          # Se il filtro è positivo, lo raggruppiamo sotto lo stesso match_id
          if segnale_filtro and score_ia >= 75:
            if match_id not in tabella_per_partita:
              tabella_per_partita[match_id] = {
                  "campionato": f"{nazione} - {campionato}",
                  "partita": f"{casa} vs {ospite}",
                  "minuto": minuto,
                  "risultato": f"{gol_c}-{gol_o}",
                  "delta": delta_attacchi,
                  "tiri": tiri_porta,
                  "filtri_attivi": []
              }
            
            # Aggiungiamo il filtro specifico alla lista dei filtri di questa partita
            tabella_per_partita[match_id]["filtri_attivi"].append({
                "segnale": segnale_filtro,
                "consiglio": consiglio_filtro,
                "score": score_ia
            })
            
            # Registrazione nello storico sul Desktop
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
                    "attacchi_pericolosi": attacchi,
                    "corner": corner_tot,
                    "delta_attacchi": delta_attacchi,
                    "delta_tiri_porta": delta_tiri_porta,
                    "apm": round(apm_totale, 2)
                },
                "esito_finale_da_verificare": "DA_COMPLETARE"
            })

          if 15 <= minuto <= 82 and gol_totali < 3:
            if score_ia >= 75:
              mercato_ai = "OVER 1.5 LIVE" if gol_totali == 0 else "OVER 2.5 LIVE"
              selezioni_master_ai.append({
                  "match": f"{casa} vs {ospite}",
                  "campionato": f"{nazione} - {campionato}",
                  "minuto": minuto,
                  "risultato": f"{gol_c}-{gol_o}",
                  "score": score_ia,
                  "mercato": mercato_ai,
              })

          nuovo_stato[match_id] = {
              "attacchi": attacchi,
              "tiri_porta": tiri_porta,
              "corner": corner_tot,
              "score_ia": score_ia,
          }

      # 📊 INVIO DELLA TABELLA UNICA CON GESTIONE FILTRI MULTIPLI
      if len(tabella_per_partita) > 0:
        testo_tabella = "📊 *TABELLA LIVE: SEGNALI ATTIVI (ULTIMI 5 MIN)* ⚡\n\n"
        for idx, (m_id, item) in enumerate(tabella_per_partita.items(), 1):
          testo_tabella += (
              f"*{idx}. {item['partita']}* (Min {item['minuto']} | 🥅 {item['risultato']})\n"
              f"🌍 _{item['campionato']}_\n"
          )
          # Mostra tutti i filtri scattati per questa specifica partita
          for f in item["filtri_attivi"]:
            testo_tabella += f"   🎯 {f['segnale']} ➔ *{f['consiglio']}* (Score: {f['score']})\n"
          
          testo_tabella += (
              f"   📈 Δ Attacchi: +{item['delta']} | Tiri in porta: {item['tiri']}\n"
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

      salva_stato(nuovo_stato)

    except Exception as e:
      print(f"Errore nel ciclo: {e}")

    print("⏳ [Cloud] Attendo 5 minuti per la prossima scansione...")
    time.sleep(300)
