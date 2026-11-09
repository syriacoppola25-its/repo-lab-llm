"""Conferma dell'utente, nel terminale, prima di eliminare una nota."""

import json
import re
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
        note_id = _id_intero(argomenti.get("note_id"))
        if note_id is None:
            # Mai eliminare senza domanda: un ID che non è un intero annulla.
            return False
        testo = trova_testo(note_id)
        nota = f"la nota {note_id}: «{testo}»" if testo is not None else f"la nota {note_id}"
        try:
            risposta = leggi(f"Eliminare {nota}? (s/n) ")
        except EOFError:
            return False
        return risposta.strip().lower() in RISPOSTE_AFFERMATIVE

    return conferma


def _id_intero(valore) -> int | None:
    """L'ID come intero se è un `int` (non `bool`) o una stringa di cifre ASCII; altrimenti `None`."""
    if isinstance(valore, int) and not isinstance(valore, bool):
        return valore
    if isinstance(valore, str) and re.fullmatch(r"[0-9]+", valore):
        return int(valore)
    return None


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
