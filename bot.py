import json
import os
import re
import requests

# CONFIGURAZIONE
API_KEY = "25a50b1640mshe6f07a04788a9e5p146782jsne750194545aa"
API_HOST = "apifootball3.p.rapidapi.com"
TELEGRAM_TOKEN = "8943323226:AAGZo6K4Vnw-P2fF8QIP2q-5B_oPRHk-6cg"
CHAT_ID = "7417588888"

# File per memorizzare lo stato precedente
STATE_FILE = "stato_precedente.json"


def carica_stato():
  if os.path.exists(STATE_FILE):
    try:
      with open(STATE_FILE, "r") as f:
        return json.load(f)
    except:
      return {}
  return {}


def salva_stato(stato):
  try:
    with open(STATE_FILE, "w") as f:
      json.dump(stato, f)
  except:
    pass


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
  if not status_str:
    return 0
  numeri = re.findall(r"\d+", str(status_str))
  if numeri:
    min_val = int(numeri[0])
    for n in numeri:
      val = int(n)
      if 0 <= val <= 120:
        return val
    return min_val if min_val <= 120 else 0
  return 0


def analizza_storico_h2h(team_id_1, team_id_2, headers, url_base):
  if not team_id_1 or not team_id_2:
    return "📈 H2H: ID squadre non disponibili."

  querystring = {
      "action": "get_H2H",
      "firstTeamId": team_id_1,
      "secondTeamId": team_id_2,
  }
  try:
    response = requests.get(url_base, headers=headers, params=querystring)
    dati = response.json()
    partite = dati if isinstance(dati, list) else []
    if not partite:
      return "📈 H2H: Nessun precedente trovato."
    tot_gol = sum(
        int(p.get("match_hometeam_score", 0) or 0)
        + int(p.get("match_awayteam_score", 0) or 0)
        for p in partite[:3]
    )
    media = tot_gol / len(partite[:3])
    return f"📈 Media gol ultimi 3 scontri: {media:.1f}"
  except Exception as e:
    return f"📈 H2H: Errore nel recupero dati."


print("🔍 Eseguo scansione con controllo del ritmo...")
stato_precedente = carica_stato()
nuovo_stato = {}
segnali_inviati = 0

try:
  url = "https://apifootball3.p.rapidapi.com/"
  headers = {"x-rapidapi-key": API_KEY, "x-rapidapi-host": API_HOST}
  resp = requests.get(
      url, headers=headers, params={"action": "get_events", "match_live": "1"}
  )
  partite = resp.json()

  if isinstance(partite, list):
    print(f"Trovate {len(partite)} partite live.")
    for m in partite:
      match_id = str(m.get("match_id"))
      stats = m.get("statistics", [])

      h_tiri_porta, a_tiri_porta = get_stats(stats, "On Target")
      h_tiri_off, a_tiri_off = get_stats(stats, "Off Target")
      h_attacchi, a_attacchi = get_stats(stats, "Dangerous Attacks")
      h_corner, a_corner = get_stats(stats, "Corners")

      tiri_tot_h = h_tiri_porta + h_tiri_off
      tiri_tot_a = a_tiri_porta + a_tiri_off

      tiri_tot = tiri_tot_h + tiri_tot_a
      tiri_porta = h_tiri_porta + a_tiri_porta
      attacchi = h_attacchi + a_attacchi
      corner_tot = h_corner + a_corner

      status_raw = m.get("match_status", "0")
      minuto = estrai_minuto(status_raw)

      if minuto == 0:
        continue

      gol_c = int(m.get("match_hometeam_score", 0) or 0)
      gol_o = int(m.get("match_awayteam_score", 0) or 0)
      gol = gol_c + gol_o

      casa, ospite = m.get("match_hometeam_name"), m.get(
          "match_awayteam_name"
      )

      # Estrazione sicura degli ID squadra con fallback
      id_casa = m.get("match_hometeam_id") or m.get("home_team_id")
      id_ospite = m.get("match_awayteam_id") or m.get("away_team_id")

      nuovo_stato[match_id] = {
          "tiri": tiri_tot,
          "attacchi": attacchi,
          "corner": corner_tot,
      }

      vecchio = stato_precedente.get(
          match_id, {"tiri": tiri_tot, "attacchi": attacchi, "corner": corner_tot}
      )
      delta_tiri = tiri_tot - vecchio["tiri"]
      delta_attacchi = attacchi - vecchio["attacchi"]
      delta_corner = corner_tot - vecchio["corner"]

      apm_totale = attacchi / minuto if minuto > 0 else 0
      apm_10min = delta_attacchi / 10 if minuto > 0 else 0

      diff_attacchi = abs(h_attacchi - a_attacchi)
      diff_tiri_porta = abs(h_tiri_porta - a_tiri_porta)

      segnale = None
      consiglio = None
      motivo_allerta = ""

      # --- LOGICA FILTRI ---

      # 1. TEST ATTACCHI: minuto <= 35, diff attacchi >= 15, diff tiri porta >= 4
      if minuto <= 35 and diff_attacchi >= 15 and diff_tiri_porta >= 4:
        segnale, consiglio = (
            "🚀 TEST ATTACCHI",
            "👉 PUNTA: OVER 0.5 HT",
        )
        motivo_allerta = (
            f"📊 Diff. Attacchi Pericolosi: {diff_attacchi} | Diff. Tiri in"
            f" porta: {diff_tiri_porta}"
        )

      # 2. ASSALTO MOSTRUOSO: 50°-75° min, tiri in porta >= 6, tiri totali >= 15
      elif 50 <= minuto <= 75 and tiri_porta >= 6 and tiri_tot >= 15:
        segnale, consiglio = (
            "⚡ ASSALTO MOSTRUOSO",
            "👉 PUNTA: OVER GOL / SEGNA GOAL",
        )
        motivo_allerta = (
            f"📊 Totali: Tiri {tiri_tot} | In porta {tiri_porta} | Attacchi"
            f" {attacchi}"
        )

      # 3. TEST OVER 0.5 NUOVO: minuto fino al 30, tiri in porta >= 3, APM > 1, corner >= 2
      elif minuto <= 30 and tiri_porta >= 3 and apm_totale > 1 and corner_tot >= 2:
        segnale, consiglio = (
            "🔥 TEST OVER 0.5 NUOVO",
            "👉 PUNTA: OVER 0.5 HT",
        )
        motivo_allerta = (
            f"📊 Tiri in porta: {tiri_porta} | Corner: {corner_tot} | APM:"
            f" {apm_totale:.2f}"
        )

      # 4. OVER 0.5 FINO AL MINUTO 30
      elif (
          minuto <= 30
          and gol == 0
          and tiri_porta >= 2
          and corner_tot >= 3
          and apm_totale >= 1
      ):
        segnale, consiglio = (
            "🎯 OVER 0.5 (1° TEMPO)",
            "👉 PUNTA: OVER 0.5 HT",
        )
        motivo_allerta = (
            f"📊 Tiri in porta: {tiri_porta} | Corner: {corner_tot} | APM:"
            f" {apm_totale:.2f}"
        )

      # 5. GOL IMMINENTE: 50°-75° min, APM ultimi 10 min >= 1.1
      elif 50 <= minuto <= 75 and apm_10min >= 1.1:
        segnale, consiglio = (
            "⚽ GOL IMMINENTE",
            "👉 PUNTA: OVER 0.5 LIVE (2°T)",
        )
        motivo_allerta = (
            f"🔥 Crescita ultimi 10 min: +{delta_attacchi} attacchi"
            f" pericolosi (APM 10min: {apm_10min:.2f})"
        )

      if segnale:
        h2h = analizza_storico_h2h(id_casa, id_ospite, headers, url)
        messaggio = (
            f"🔔 *SEGNALE: {segnale}*\n"
            f"⚽ {casa} vs {ospite}\n"
            f"⏱️ Min: {minuto} | 🥅 Ris: {gol_c}-{gol_o}\n\n"
            f"{consiglio}\n"
            f"ℹ️ _{motivo_allerta}_\n"
            f"📈 _Variazione: +{delta_tiri} tiri, +{delta_attacchi} attacchi,"
            f" +{delta_corner} corner_\n\n"
            f"{h2h}"
        )
        invia_telegram(messaggio)
        segnali_inviati += 1
        print(f"✅ Segnale inviato: {casa} vs {ospite}")

  if segnali_inviati == 0:
    invia_telegram(
        "🔍 *Bot Calcio Live:* Scansione completata. Nessun match rispetta i"
        " filtri in questo momento."
    )

  salva_stato(nuovo_stato)

except Exception as e:
  print(f"⚠️ Errore: {e}")
  invia_telegram(f"⚠️ Errore nel bot: {e}")
