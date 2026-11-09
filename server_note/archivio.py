"""Archivio delle note su file SQLite: aggiunta, elenco, eliminazione."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

LUNGHEZZA_MASSIMA = 500
LIMITE_PREDEFINITO = 20
LIMITE_MASSIMO = 100

# AUTOINCREMENT: un ID eliminato non viene mai riassegnato a una nota nuova.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS note (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creata TEXT NOT NULL,
    testo TEXT NOT NULL
)
"""


class ErroreNote(ValueError):
    """Operazione rifiutata; il messaggio, in italiano, è pronto per l'utente."""


def _nota(riga: tuple) -> dict:
    return {"id": riga[0], "creata": riga[1], "testo": riga[2]}


class ArchivioNote:
    def __init__(
        self,
        percorso: Path,
        fuso: str = "Europe/Rome",
        adesso: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.percorso = Path(percorso)
        self.fuso = ZoneInfo(fuso)
        self.adesso = adesso

    def _esegui(self, operazione: Callable[[sqlite3.Connection], object]):
        """Apre l'archivio, esegue `operazione` in una transazione e lo richiude."""
        try:
            self.percorso.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(self.percorso)) as connessione:
                with connessione:
                    connessione.execute(_SCHEMA)
                    return operazione(connessione)
        except (sqlite3.Error, OSError) as errore:
            raise ErroreNote(f"Archivio delle note non accessibile: {errore}.") from None

    def aggiungi(self, testo: str) -> dict:
        testo = testo.strip()
        if not testo:
            raise ErroreNote("Il testo della nota è vuoto.")
        if len(testo) > LUNGHEZZA_MASSIMA:
            raise ErroreNote(f"Il testo della nota supera i {LUNGHEZZA_MASSIMA} caratteri.")
        creata = self.adesso().astimezone(self.fuso).strftime("%Y-%m-%d %H:%M")

        def inserisci(connessione):
            cursore = connessione.execute(
                "INSERT INTO note (creata, testo) VALUES (?, ?)", (creata, testo)
            )
            return {"id": cursore.lastrowid, "creata": creata, "testo": testo}

        return self._esegui(inserisci)

    def elenca(self, limite: int = LIMITE_PREDEFINITO) -> dict:
        if not 1 <= limite <= LIMITE_MASSIMO:
            raise ErroreNote(f"limit deve essere un intero tra 1 e {LIMITE_MASSIMO}.")

        def leggi(connessione):
            righe = connessione.execute(
                "SELECT id, creata, testo FROM note ORDER BY id LIMIT ?", (limite,)
            ).fetchall()
            (totale,) = connessione.execute("SELECT COUNT(*) FROM note").fetchone()
            return {"note": [_nota(r) for r in righe], "totale": totale}

        return self._esegui(leggi)

    def elimina(self, note_id: int) -> dict:
        def cancella(connessione):
            riga = connessione.execute(
                "SELECT id, creata, testo FROM note WHERE id = ?", (note_id,)
            ).fetchone()
            if riga is None:
                raise ErroreNote(f"Nessuna nota con ID {note_id}.")
            connessione.execute("DELETE FROM note WHERE id = ?", (note_id,))
            return {"eliminata": _nota(riga)}

        return self._esegui(cancella)
