"""Avvio: python -m assistente"""

import os
import sys

from assistente.config import ConfigErrata, carica_config
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello, istruzioni_sistema
from assistente.terminale import esegui_sessione


def main() -> int:
    try:
        config = carica_config(os.environ)
    except ConfigErrata as errore:
        print(f"{errore} Vedi .env.example.")
        return 1
    modello = crea_modello(config, [])
    esegui_sessione(costruisci_grafo(modello, istruzioni_sistema(config.fuso_predefinito)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
