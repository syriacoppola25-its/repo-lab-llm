"""Client MCP del server delle note (`python -m server_note`).

Gli strumenti NON sono descritti in questo file: nome, descrizione e schema
arrivano dal server con la discovery (`tools/list`).
"""

import sys
from pathlib import Path

from assistente.client_mcp import ClientMCP


class ClientNote(ClientMCP):
    def __init__(
        self,
        percorso_note: Path,
        fuso: str,
        percorso_log_server: Path,
        timeout: float = 20.0,
        python: str = sys.executable,
    ):
        super().__init__(
            "server_note",
            "delle note",
            percorso_log_server,
            # Percorso assoluto: il server parte con la radice del progetto come cartella.
            ambiente={
                "PERCORSO_NOTE": str(Path(percorso_note).resolve()),
                "FUSO_PREDEFINITO": fuso,
            },
            timeout=timeout,
            python=python,
        )
