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
# Cronologia in memoria: si perde alla chiusura, non viene salvata su file.
messages = [system_message]

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
# Ogni giro e' una nuova richiesta che invia l'intera cronologia. Lo scambio
# entra in messages solo se la richiesta riesce.
try:
    while True:
        question = input("Domanda (scrivi 'esci' per uscire): ").strip()
        if not question:
            continue
        if question.lower() == "esci":
            break

        # --- Payload ----------------------------------------------------------
        user_message = {"role": "user", "content": question}
        payload = {
            "model": model,
            "messages": messages + [user_message],
            "temperature": 0.3,
            "max_tokens": 500,
            "reasoning_effort": "none",
            "stream": True,
        }

        # --- Chiamata ---------------------------------------------------------
        try:
            answer = ask(payload)
        except requests.exceptions.Timeout:
            print("Attesa scaduta: controllare server, carico e tempi.")
        except requests.exceptions.ConnectionError:
            print("Connessione fallita: controllare server, URL e porta.")
        except requests.exceptions.HTTPError as error:
            print("Errore HTTP:", error.response.status_code, error.response.text)
        else:
            if answer:
                messages.extend([user_message, {"role": "assistant", "content": answer}])
except (KeyboardInterrupt, EOFError):
    print("\nInterrotto. Arrivederci.")
