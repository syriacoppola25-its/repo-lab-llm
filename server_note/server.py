"""Server MCP delle note: espone l'archivio come tre tool FastMCP.

Nome, descrizione e schema dei tool sono definiti solo qui: l'assistente li
ottiene con la discovery (`tools/list`), senza riscriverli.
"""

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from server_note.archivio import LIMITE_PREDEFINITO, ArchivioNote, ErroreNote


def crea_server(archivio: ArchivioNote) -> FastMCP:
    server = FastMCP("Note del laboratorio")

    def esegui(operazione, *argomenti) -> dict:
        # Un errore dell'archivio diventa un errore MCP (isError), mai un falso successo.
        try:
            return operazione(*argomenti)
        except ErroreNote as errore:
            raise ToolError(str(errore)) from None

    @server.tool
    def add_note(text: str) -> dict:
        """Salva una nuova nota con il testo indicato e modifica l'archivio delle note.
        Usalo quando l'utente chiede di ricordare o annotare qualcosa.
        Restituisce la nota creata con ID, data di creazione e testo."""
        return esegui(archivio.aggiungi, text)

    @server.tool
    def list_notes(limit: int = LIMITE_PREDEFINITO) -> dict:
        """Elenca le note salvate, in ordine di creazione, con ID, data e testo.
        Non modifica nulla. limit: numero massimo di note, da 1 a 100.
        Il campo totale indica quante note ci sono in tutto."""
        return esegui(archivio.elenca, limit)

    @server.tool
    def delete_note(note_id: int) -> dict:
        """Elimina definitivamente una nota e modifica l'archivio delle note.
        note_id è l'ID della nota preso da list_notes: non inventarlo mai.
        Restituisce la nota eliminata."""
        return esegui(archivio.elimina, note_id)

    return server
