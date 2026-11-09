"""Conferma dell'utente, nel terminale, prima di eliminare una nota."""

import json
from typing import Callable

from assistente.note_mcp import ClientNote

RISPOSTE_AFFERMATIVE = {"s", "si", "sì"}


def crea_conferma_eliminazione(
    trova_testo: Callable[[int], str | None],
    leggi: Callable[[str], str] = input,
) -> Callable[[dict], bool]:
    """Funzione di conferma per il grafo: riceve gli argomenti di `delete_note`.

    Elimina solo con `s`/`si`/`sì`; la fine dell'input vale come "no".
    Ctrl+C non viene intercettato: chiude la sessione come altrove.
    """

    def conferma(argomenti: dict) -> bool:
        try:
            note_id = int(argomenti.get("note_id"))
        except (TypeError, ValueError):
            # ID non numerico: nessuna nota da mostrare, il server risponderà con l'errore.
            return True
        testo = trova_testo(note_id)
        nota = f"la nota {note_id}: «{testo}»" if testo is not None else f"la nota {note_id}"
        try:
            risposta = leggi(f"Eliminare {nota}? (s/n) ")
        except EOFError:
            return False
        return risposta.strip().lower() in RISPOSTE_AFFERMATIVE

    return conferma


def testo_nota(client: ClientNote, note_id: int) -> str | None:
    """Il testo della nota `note_id` letto dal server; `None` se non si trova."""
    try:
        elenco = json.loads(client.chiama("list_notes", {"limit": 100}))
    except Exception:
        return None
    for nota in elenco.get("note", []):
        if nota.get("id") == note_id:
            return nota.get("testo")
    return None
