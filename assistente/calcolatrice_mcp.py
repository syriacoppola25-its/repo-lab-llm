"""Client MCP del server della calcolatrice (`python -m server_calcolatrice`).

Gli strumenti NON sono descritti in questo file: nome, descrizione e schema
arrivano dal server con la discovery (`tools/list`).
"""

import sys
from pathlib import Path

from assistente.client_mcp import ClientMCP


class ClientCalcolatrice(ClientMCP):
    def __init__(
        self,
        percorso_log_server: Path,
        timeout: float = 20.0,
        python: str = sys.executable,
    ):
        super().__init__(
            "server_calcolatrice",
            "della calcolatrice",
            percorso_log_server,
            timeout=timeout,
            python=python,
        )
