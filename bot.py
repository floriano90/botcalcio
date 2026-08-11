import json
import os
import re
import requests

# CONFIGURAZIONE SICURA (Legge le chiavi dalle GitHub Secrets)
API_KEY = os.environ.get("API_FOOTBALL_KEY")
API_HOST = "apifootball3.p.rapidapi.com"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

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
  if not TELEGRAM_TOKEN or not CHAT_ID:
    print(
        "ERRORE CRITICO: Token o Chat ID di Telegram non trovati nelle variabili"
        " d'ambiente!"
    )
    return
  url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
  try:
    response = requests.post(
        url, data={"chat_id": CHAT_ID, "text": testo, "parse_mode": "Markdown"}
    )
    print(f"Risposta Telegram: {response.text}")
  except Exception as e:
    print(f"Errore invio telegram: {e}")


def get_stats(stats, tipo):
  for s in stats:
    if s.get("type") == tipo:
      try:
        h = int(str(s.get("home", 0)).replace("%", "").strip() or 0)
        a = int(str(s.get("away", 0)).replace("%", "").strip() or 0)
        return h + a
      except:
        return 0
  return 0


def analizza_storico_h2h(team_id_1, team_id_2, headers, url_base):
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
      return "Nessun dato H2H."
    tot_gol = sum(
        int(p.get("match_hometeam_score", 0) or 0)
        + int(p.get("match_awayteam_score", 0) or 0)
        for p in partite[:3]
    )
    media = tot_gol / len(partite[:3])
    return f"📈 Media gol ultimi 3 scontri: {media:.1f}"
  except:
    return ""


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

      tiri_tot = get_stats(stats, "On Target") + get_stats(stats, "Off Target")
      tiri_porta = get_stats(stats, "On Target")
      attacchi = get_stats(stats, "Dangerous Attacks")
      corner_tot = get_stats(stats, "Corners")

      status = str(m.get("match_status", "0"))
      min_match = re.findall(r"\d+", status)
      minuto = int(min_match[0]) if min_match else 0

      gol_c = int(m.get("match_hometeam_score", 0) or 0)
      gol_o = int(m.get("match_awayteam_score", 0) or 0)
      gol = gol_c + gol_o

      casa, ospite = m.get("match_hometeam_name"), m.get(
          "match_awayteam_name"
      )

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

      segnale = None
      consiglio = None
      motivo_allerta = ""

      # --- LOGICA FILTRI ---
      if (
          15 <= minuto <= 25
          and gol == 0
          and tiri_tot >= 3
          and attacchi >= 15
          and corner_tot >= 3
      ):
        segnale, consiglio = (
            "⭐ TOP FILTRO: OVER 0.5 HT",
            "👉 PUNTA: OVER 0.5 HT (Quota 1.50-1.65)",
        )
        motivo_allerta = f"📊 Totali: Tiri {tiri_tot} | Attacchi {attacchi} | Corner {corner_tot}"
      elif 23 <= minuto <= 41 and gol == 0 and tiri_tot >= 4 and attacchi >= 10:
        segnale, consiglio = "🎯 OVER 0.5 1°T", "👉 PUNTA: OVER 0.5 HT"
        motivo_allerta = f"📊 Totali: Tiri {tiri_tot} | Attacchi {attacchi}"
      elif minuto >= 60 and gol <= 2 and tiri_tot >= 10 and attacchi >= 18:
        segnale, consiglio = (
            "⚽ GOL IMMINENTE",
            "👉 PUNTA: OVER 0.5 LIVE (2°T)",
        )
        motivo_allerta = f"📊 Totali: Tiri {tiri_tot} | Attacchi {attacchi}"
      elif 48 <= minuto <= 80 and tiri_tot >= 15 and tiri_porta >= 4:
        segnale, consiglio = (
            "⚡ ASSALTO MOSTRUOSO",
            "👉 PUNTA: OVER GOL / SEGNA GOAL",
        )
        motivo_allerta = (
            f"📊 Totali: Tiri {tiri_tot} (In porta {tiri_porta})"
        )

      if segnale:
        h2h = analizza_storico_h2h(
            m.get("match_hometeam_id"),
            m.get("match_awayteam_id"),
            headers,
            url,
        )
        messaggio = (
            f"🔔 *SEGNALE: {segnale}*\n"
            f"⚽ {casa} vs {ospite}\n"
            f"⏱️ Min: {minuto} | 🥅 Ris: {gol_c}-{gol_o}\n\n"
            f"{consiglio}\n"
            f"ℹ️ _{motivo_allerta}_\n"
            f"🔥 _Crescita ultimi 10min: +{delta_tiri} tiri, +{delta_attacchi}"
            f" attacchi, +{delta_corner} corner_\n\n"
            f"{h2h}"
        )
        invia_telegram(messaggio)
        segnali_inviati += 1
        print(f"✅ Segnale inviato: {casa} vs {ospite}")

  if segnali_inviati == 0 and isinstance(partite, list):
    pass

  salva_stato(nuovo_stato)

except Exception as e:
  print(f"⚠️ Errore: {e}")
  invia_telegram(f"⚠️ Errore nel bot: {e}")
