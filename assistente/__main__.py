"""Avvio: python -m assistente"""

import os
import sys

from assistente.config import ConfigErrata, carica_config
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello, istruzioni_sistema
from assistente.registro import configura_registro
from assistente.strumenti import crea_orologio
from assistente.terminale import esegui_sessione


def main() -> int:
    try:
        config = carica_config(os.environ)
    except ConfigErrata as errore:
        print(f"{errore} Vedi .env.example.")
        return 1
    registro = configura_registro(config.percorso_log)
    orologio = crea_orologio(config.fuso_predefinito)
    grafo = costruisci_grafo(
        crea_modello(config, [orologio]),
        istruzioni_sistema(config.fuso_predefinito),
        strumenti=[orologio],
        limite=config.limite_chiamate,
        registro=registro,
    )
    esegui_sessione(grafo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
