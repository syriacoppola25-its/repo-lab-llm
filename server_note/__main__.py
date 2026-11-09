"""Avvio del server delle note in stdio: python -m server_note

Con stdio, stdout è riservato ai messaggi del protocollo: niente banner e
solo avvisi nei log (che vanno su stderr).
"""

import os
from pathlib import Path

from server_note.archivio import ArchivioNote
from server_note.server import crea_server


def main() -> None:
    archivio = ArchivioNote(
        Path(os.environ.get("PERCORSO_NOTE") or "dati/note.db"),
        os.environ.get("FUSO_PREDEFINITO") or "Europe/Rome",
    )
    crea_server(archivio).run(show_banner=False, log_level="WARNING")


if __name__ == "__main__":
    main()
