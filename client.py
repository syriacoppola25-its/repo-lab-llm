"""Client minimo per il server locale di LM Studio.

Scheletro da completare con Claude Code (slide 19-22):
configurazione, messaggi, payload e chiamata HTTP.
Import e gestione degli errori sono gia' presenti: conservarli.
"""

import json
import os

import requests
from dotenv import load_dotenv

# --- Configurazione -------------------------------------------------------
load_dotenv(".env", override=False)
base_url = os.environ["LM_BASE_URL"].rstrip("/")
model = os.environ["LM_MODEL"]

# --- Messaggi -------------------------------------------------------------
system_message = {
    "role": "system",
    "content": "Sei un assistente tecnico. Rispondi in italiano, in modo chiaro e conciso.",
}

# --- Risposta progressiva -------------------------------------------------
def ask(payload):
    """Invia il payload, stampa i frammenti appena arrivano e restituisce il testo completo."""
    pieces = []
    with requests.post(
        f"{base_url}/chat/completions", json=payload, timeout=120, stream=True
    ) as response:
        if not response.ok:
            response.content  # con stream=True il corpo va letto prima di chiudere la connessione
        response.raise_for_status()
        for raw_line in response.iter_lines():
            # Byte decodificati a mano: senza charset requests assumerebbe ISO-8859-1.
            line = raw_line.decode("utf-8")
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            choices = json.loads(data).get("choices")
            if not choices:
                continue
            piece = choices[0].get("delta", {}).get("content")
            if piece:
                print(piece, end="", flush=True)
                pieces.append(piece)
    print()
    return "".join(pieces)


# --- Ciclo domanda-risposta -----------------------------------------------
# Ogni giro e' indipendente: nuova richiesta, nessuna memoria dei giri precedenti.
try:
    while True:
        question = input("Domanda (scrivi 'esci' per uscire): ").strip()
        if not question:
            continue
        if question.lower() == "esci":
            break

        # --- Payload ----------------------------------------------------------
        payload = {
            "model": model,
            "messages": [system_message, {"role": "user", "content": question}],
            "temperature": 0.3,
            "max_tokens": 500,
            "reasoning_effort": "none",
            "stream": True,
        }

        # --- Chiamata ---------------------------------------------------------
        try:
            ask(payload)
        except requests.exceptions.Timeout:
            print("Attesa scaduta: controllare server, carico e tempi.")
        except requests.exceptions.ConnectionError:
            print("Connessione fallita: controllare server, URL e porta.")
        except requests.exceptions.HTTPError as error:
            print("Errore HTTP:", error.response.status_code, error.response.text)
except (KeyboardInterrupt, EOFError):
    print("\nInterrotto. Arrivederci.")
