"""Registro (log) su file delle chiamate agli strumenti."""

import logging
from pathlib import Path


def configura_registro(percorso: Path) -> logging.Logger:
    """Logger che scrive solo su file, così il terminale resta pulito."""
    registro = logging.getLogger("assistente.strumenti")
    # Una nuova configurazione sostituisce la precedente invece di sommarsi.
    for gestore in list(registro.handlers):
        registro.removeHandler(gestore)
        gestore.close()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    gestore = logging.FileHandler(percorso, encoding="utf-8")
    gestore.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    registro.addHandler(gestore)
    registro.setLevel(logging.INFO)
    registro.propagate = False
    return registro
