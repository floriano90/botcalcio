
import os
import requests

# 1. Recupero sicuro del token di Telegram dalle variabili d'ambiente (GitHub Secrets)
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID') # Opzionale se lo usi, altrimenti inseriscilo o gestiscilo qui

# Configurazione API (puoi usare le variabili d'ambiente anche per la chiave API se vuoi renderla sicura al 100%)
API_KEY = os.environ.get('API_FOOTBALL_KEY') 

def invia_messaggio_telegram(testo):
    """Invia una notifica al tuo bot Telegram"""
    if not TELEGRAM_TOKEN:
        print("Errore: Token di Telegram non trovato!")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, # Assicurati di avere il tuo chat ID configurato
        "text": testo,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Errore nell'invio del messaggio Telegram: {e}")

def controlla_partite_live():
    """Esegue la chiamata all'API per controllare le partite live"""
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    querystring = {"live": "all"}
    
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring)
        response.raise_for_status()
        dati = response.json()
        
        partite = dati.get("response", [])
        print(foro=f"Trovate {len(partite)} partite live.") # Controllo di esecuzione
        
        # Esempio di ciclo di analisi sulle partite trovate
        for partita in partite:
            status = partita.get("fixture", {}).get("status", {})
            minuto = status.get("elapsed", 0)
            
            teams = partita.get("teams", {})
            casa = teams.get("home", {}).get("name")
            trasferta = teams.get("away", {}).get("name")
            
            # Inserisci qui la tua logica di filtro (es. minuti, tiri, corner)
            # Esempio: if minuto >= 70: ...
            
    except Exception as e:
        print(f"Errore durante la chiamata API: {e}")

if __name__ == "__main__":
    print("Avvio script bot calcio...")
    controlla_partite_live()
