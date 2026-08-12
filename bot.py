import json
import os
import re
import requests
import time

# CONFIGURAZIONE
API_KEY = "25a50b1640mshe6f07a04788a9e5p146782jsne750194545aa"
API_HOST = "apifootball3.p.rapidapi.com"
TELEGRAM_TOKEN = "8943323226:AAGZo6K4Vnw-P2fF8QIP2q-5B_oPRHk-6cg"
CHAT_ID = "7417588888"

# Percorso di salvataggio sul Cloud di Google Colab
STATE_FILE = "stato_precedente.json"


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


def get_quota_over(match_id, headers, url_base):
  querystring = {"action": "get_odds", "match_id": match_id}
  try:
    response = requests.get(url_base, headers=headers, params=querystring)
    dati = response.json()
    odds = (
        dati.get("result", dati.get("data", [dati]))
        if isinstance(dati, dict)
        else dati
    )
    for item in odds:
      for book in item.get("bookmakers", []):
        for bet in book.get("bets", []):
          if "over/under" in str(bet.get("bet_name", "")).lower():
            for val in bet.get("values", []):
              if "2.5" in str(val.get("value", "")).lower() and "over" in str(
                  val.get("value", "")
              ).lower():
                return float(val.get("odd", 1.85)), str(val.get("odd", 1.85))
    return 1.85, "N/A"
  except:
    return 1.85, "N/A"


print(
    "🤖 Bot Calcio Live - Versione Cloud (Google Colab) Pronta e in esecuzione."
)

if __name__ == "__main__":
  while True:
    stato_precedente = carica_stato()
    nuovo_stato = {}
    match_per_multipla_filtri = []
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
              },
          )
          delta_attacchi = attacchi - vecchio["attacchi"]
          delta_tiri_porta = tiri_porta - vecchio.get("tiri_porta", tiri_porta)
          delta_corner = corner_tot - vecchio["corner"]
          apm_totale = attacchi / minuto if minuto > 0 else 0

          media_h2h, testo_h2h = analizza_h2h_completo(
              id_casa,
              id_ospite,
              {"x-rapidapi-key": API_KEY, "x-rapidapi-host": API_HOST},
              "https://apifootball3.p.rapidapi.com/",
          )
          quota_o25, testo_quota = get_quota_over(
              match_id,
              {"x-rapidapi-key": API_KEY, "x-rapidapi-host": API_HOST},
              "https://apifootball3.p.rapidapi.com/",
          )

          score_ia = 0
          if media_h2h >= 2.6:
            score_ia += 20
          if quota_o25 <= 1.90:
            score_ia += 20
          if apm_totale >= 1.2 or delta_attacchi >= 5:
            score_ia += 35
          if tiri_porta >= 4:
            score_ia += 25

          conferma_ia = "✅ POSITIVA" if score_ia >= 70 else "❌ NEUTRA"

          segnale_filtro = None
          consiglio_filtro = None
          motivo_filtro = ""

          if (
              15 <= minuto <= 38
              and gol_totali <= 1
              and tiri_porta >= 3
              and apm_totale >= 1.0
          ):
            segnale_filtro, consiglio_filtro = (
                "🎯 HT ALPHA-FIRST (HT)",
                "OVER 0.5 HT",
            )
            motivo_filtro = f"Tiri porta: {tiri_porta} | APM: {apm_totale:.2f}"
          elif (
              45 <= minuto <= 75
              and gol_totali < 3
              and (delta_attacchi >= 6 or tiri_porta >= 7)
          ):
            segnale_filtro, consiglio_filtro = (
                "🔥 OVER 2.5 DYNAMIC",
                "OVER 2.5 / 1.5 LIVE",
            )
            motivo_filtro = (
                f"Parziale: {gol_c}-{gol_o} | Delta attacchi: +{delta_attacchi}"
            )
          elif (
              52 <= minuto <= 78
              and delta_attacchi >= 7
              and delta_tiri_porta >= 2
          ):
            segnale_filtro, consiglio_filtro = "💥 ALPHA-SURGE", "OVER 0.5 LIVE"
            motivo_filtro = (
                f"Accelerazione: +{delta_attacchi} attacchi, +"
                f"{delta_tiri_porta} tiri porta"
            )
          elif (
              50 <= minuto <= 78
              and tiri_porta >= 6
              and tiri_tot >= 14
              and gol_totali < 3
          ):
            segnale_filtro, consiglio_filtro = (
                "⚡ ASSALTO MOSTRUOSO",
                "OVER 0.5 / 1.5 LIVE",
            )
            motivo_filtro = (
                f"Tiri totali: {tiri_tot} | In porta: {tiri_porta} (Pressione"
                " estrema)"
            )

          if segnale_filtro:
            msg_filtro = (
                f"🔔 *SEGNALE STRATEGICO: {segnale_filtro}*\n"
                f"⚽ {casa} vs {ospite}\n"
                f"⏱️ Min: {minuto} | 🥅 Ris: {gol_c}-{gol_o}\n\n"
                f"👉 PUNTA: *{consiglio_filtro}*\n"
                f"📊 CONFERMA IA: {conferma_ia} (Score: {score_ia}/100)\n"
                f"ℹ️ _{motivo_filtro}_\n"
                f"📈 Quota Over 2.5: {testo_quota} | {testo_h2h}"
            )
            invia_telegram(msg_filtro)
            match_per_multipla_filtri.append({
                "match": f"{casa} vs {ospite}",
                "minuto": minuto,
                "risultato": f"{gol_c}-{gol_o}",
                "consiglio": consiglio_filtro,
                "segnale": segnale_filtro,
            })

          if 15 <= minuto <= 82 and gol_totali < 3:
            if score_ia >= 70:
              mercato_ai = "OVER 1.5 LIVE" if gol_totali == 0 else "OVER 2.5 LIVE"
              selezioni_master_ai.append({
                  "match": f"{casa} vs {ospite}",
                  "minuto": minuto,
                  "risultato": f"{gol_c}-{gol_o}",
                  "score": score_ia,
                  "mercato": mercato_ai,
                  "logica": "Modello quantitativo globale superato",
              })
              invia_telegram(
                  f"🤖 *AI TRADER ALERT (Score: {score_ia}/100)*\n"
                  f"⚽ {casa} vs {ospite} (Min {minuto} | {gol_c}-{gol_o})\n"
                  f"👉 SCELTA: *{mercato_ai}*\n"
                  f"📈 Condizioni ideali rilevate dai flussi di mercato e H2H."
              )

          nuovo_stato[match_id] = {
              "attacchi": attacchi,
              "tiri_porta": tiri_porta,
              "corner": corner_tot,
          }

      if len(match_per_multipla_filtri) >= 2:
        testo_m1 = (
            f"🎯 *MULTI-SYSTEM ALPHA (MULTIPLA DEI TUOI FILTRI)* 🚀\n"
            f"⚡ Rilevate {len(match_per_multipla_filtri)} partite con i tuoi"
            " criteri di assalto!\n\n"
        )
        for idx, item in enumerate(match_per_multipla_filtri, 1):
          testo_m1 += (
              f"{idx}. *{item['match']}* (Min {item['minuto']} |"
              f" {item['risultato']}) ➔ {item['consiglio']}\n"
          )
        invia_telegram(testo_m1)

      if len(selezioni_master_ai) >= 2:
        selezioni_master_ai.sort(key=lambda x: x["score"], reverse=True)
        testo_m2 = (
            f"👑 *AI QUANT ACCUMULATOR (LA MULTIPLA MASTER DELL'IA)* 🚀\n\n"
        )
        for idx, item in enumerate(selezioni_master_ai[:3], 1):
          testo_m2 += (
              f"{idx}. *{item['match']}* (Min {item['minuto']} |"
              f" {item['risultato']})\n   ➔ Puntata: *{item['mercato']}*"
              f" (Confidence: {item['score']}%)\n\n"
          )
        testo_m2 += "🎯 _Stake ridotto consigliato (es. 2€)._"
        invia_telegram(testo_m2)

      salva_stato(nuovo_stato)

    except Exception as e:
      print(f"Errore nel ciclo: {e}")

    print("⏳ [Cloud] Attendo 5 minuti per la prossima scansione...")
    time.sleep(300)
