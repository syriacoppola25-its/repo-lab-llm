"""Avvio: python -m assistente"""

import os
import sys

from assistente.calcolatrice_mcp import ClientCalcolatrice
from assistente.conferma import crea_conferma_eliminazione, testo_nota
from assistente.config import ConfigErrata, carica_config
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello, istruzioni_sistema
from assistente.note_mcp import ClientNote
from assistente.registro import configura_registro
from assistente.strumenti import ErroreCollegamento, crea_orologio
from assistente.terminale import SALUTO, esegui_sessione


def main() -> int:
    try:
        config = carica_config(os.environ)
    except ConfigErrata as errore:
        print(f"{errore} Vedi .env.example.")
        return 1
    registro = configura_registro(config.percorso_log)
    log_note = config.percorso_log.parent / "server_note.log"
    log_calcolatrice = config.percorso_log.parent / "server_calcolatrice.log"
    note = ClientNote(config.percorso_note, config.fuso_predefinito, log_note)
    calcolatrice = ClientCalcolatrice(log_calcolatrice)
    try:
        for client, descrizione, log in (
            (note, "delle note", log_note),
            (calcolatrice, "della calcolatrice", log_calcolatrice),
        ):
            try:
                client.apri()
            except ErroreCollegamento as errore:
                print(f"Impossibile avviare il server {descrizione} ({errore}). Vedi {log}.")
                return 1
            except KeyboardInterrupt:
                # Ctrl+C mentre parte un server: si esce come da una sessione interrotta.
                print(SALUTO)
                return 0
        # Orologio locale + strumenti scoperti dai due server MCP.
        strumenti = [
            crea_orologio(config.fuso_predefinito),
            *note.strumenti(),
            *calcolatrice.strumenti(),
        ]
        conferma = crea_conferma_eliminazione(lambda note_id: testo_nota(note, note_id))
        grafo = costruisci_grafo(
            crea_modello(config, strumenti),
            istruzioni_sistema(config.fuso_predefinito),
            strumenti=strumenti,
            limite=config.limite_chiamate,
            registro=registro,
            conferme={"delete_note": conferma},
        )
        esegui_sessione(grafo)
    finally:
        # chiudi() è sicuro anche su un client mai aperto.
        calcolatrice.chiudi()
        note.chiudi()
    return 0


if __name__ == "__main__":
    sys.exit(main())
