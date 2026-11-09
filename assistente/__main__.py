"""Avvio: python -m assistente"""

import os
import sys

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
    log_server = config.percorso_log.parent / "server_note.log"
    client = ClientNote(config.percorso_note, config.fuso_predefinito, log_server)
    try:
        try:
            client.apri()
        except ErroreCollegamento as errore:
            print(f"Impossibile avviare il server delle note ({errore}). Vedi {log_server}.")
            return 1
        except KeyboardInterrupt:
            # Ctrl+C mentre parte il server: si esce come da una sessione interrotta.
            print(SALUTO)
            return 0
        # Orologio locale + strumenti delle note scoperti dal server MCP.
        strumenti = [crea_orologio(config.fuso_predefinito), *client.strumenti()]
        conferma = crea_conferma_eliminazione(lambda note_id: testo_nota(client, note_id))
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
        client.chiudi()
    return 0


if __name__ == "__main__":
    sys.exit(main())
