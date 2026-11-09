"""Server MCP della calcolatrice: espone il valutatore sicuro come un tool FastMCP.

Nome, descrizione e schema del tool sono definiti solo qui: l'assistente li
ottiene con la discovery (`tools/list`), senza riscriverli.
"""

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from server_calcolatrice.valutatore import ErroreEspressione, formatta, valuta


def crea_server() -> FastMCP:
    server = FastMCP("Calcolatrice del laboratorio")

    @server.tool
    def calculate(expression: str) -> dict:
        """Calcola un'espressione aritmetica e restituisce espressione e risultato.
        Operazioni ammesse: + - * / // % ** e parentesi tonde, con numeri interi o decimali.
        I decimali si scrivono con il punto (12.5). % è il resto della divisione, non la percentuale:
        per una percentuale moltiplica (il 15% di 240 è 240 * 15 / 100).
        Funzioni, nomi e altri simboli non sono ammessi: in quel caso restituisce un errore."""
        # Un'espressione rifiutata diventa un errore MCP (isError), mai un falso successo.
        try:
            risultato = formatta(valuta(expression))
        except ErroreEspressione as errore:
            raise ToolError(str(errore)) from None
        return {"espressione": expression.strip(), "risultato": risultato}

    return server
