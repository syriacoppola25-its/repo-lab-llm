"""Client MCP del server delle note, usabile da codice sincrono.

Il server (`python -m server_note`) viene avviato come sottoprocesso e parla
MCP su stdio. Il client MCP è asincrono: qui gira in un event loop su un thread
dedicato, così grafo e terminale restano sincroni.

Gli strumenti NON sono descritti in questo file: nome, descrizione e schema
arrivano dal server con la discovery (`tools/list`).
"""

import asyncio
import os
import sys
import threading
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from assistente.strumenti import ErroreCollegamento

RADICE_PROGETTO = Path(__file__).resolve().parent.parent


def _testo(risultato) -> str:
    """Il testo dei blocchi `text` restituiti dallo strumento MCP."""
    if isinstance(risultato, str):
        return risultato
    return "\n".join(b["text"] for b in risultato if b.get("type") == "text")


class ClientNote:
    def __init__(
        self,
        percorso_note: Path,
        fuso: str,
        percorso_log_server: Path,
        timeout: float = 20.0,
        python: str = sys.executable,
    ):
        self.percorso_note = Path(percorso_note).resolve()
        self.fuso = fuso
        self.percorso_log_server = Path(percorso_log_server)
        self.timeout = timeout
        self.python = python
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._task: asyncio.Task | None = None
        self._fine: asyncio.Event | None = None
        self._log = None
        self._scoperti: dict[str, BaseTool] = {}

    def __enter__(self) -> "ClientNote":
        self.apri()
        return self

    def __exit__(self, *errore) -> None:
        self.chiudi()

    def apri(self) -> None:
        """Avvia il server, apre la sessione MCP e legge il catalogo degli strumenti."""
        self.percorso_log_server.parent.mkdir(parents=True, exist_ok=True)
        # Lo stderr del server (avvisi, errori) va su file: il terminale resta pulito.
        self._log = open(self.percorso_log_server, "a", encoding="utf-8")
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        try:
            futuro = asyncio.run_coroutine_threadsafe(self._avvia(), self._loop)
            strumenti = futuro.result(self.timeout)
        except Exception as errore:
            self.chiudi()
            raise ErroreCollegamento(
                f"server delle note non avviato ({type(errore).__name__}: {errore})"
            ) from None
        for strumento in strumenti:
            # Di default l'adattatore restituirebbe l'errore come testo normale:
            # lo vogliamo invece come eccezione, per non confonderlo con un successo.
            strumento.handle_tool_error = False
        self._scoperti = {s.name: s for s in strumenti}

    async def _avvia(self) -> list[BaseTool]:
        pronta = asyncio.get_running_loop().create_future()
        self._fine = asyncio.Event()
        self._task = asyncio.create_task(self._vivi(pronta))
        sessione = await pronta
        return await load_mcp_tools(sessione)

    async def _vivi(self, pronta: asyncio.Future) -> None:
        # Apertura e chiusura del collegamento devono avvenire nello stesso task.
        parametri = StdioServerParameters(
            command=self.python,
            args=["-m", "server_note"],
            cwd=str(RADICE_PROGETTO),
            env={
                **os.environ,
                "PERCORSO_NOTE": str(self.percorso_note),
                "FUSO_PREDEFINITO": self.fuso,
            },
        )
        try:
            async with stdio_client(parametri, errlog=self._log) as (lettura, scrittura):
                async with ClientSession(lettura, scrittura) as sessione:
                    await sessione.initialize()
                    pronta.set_result(sessione)
                    await self._fine.wait()
        except BaseException as errore:
            if not pronta.done():
                pronta.set_exception(errore)
            if not isinstance(errore, Exception):
                raise

    def strumenti(self) -> list[BaseTool]:
        """Strumenti LangChain sincroni, uno per ogni tool scoperto sul server."""
        return [
            StructuredTool(
                name=scoperto.name,
                description=scoperto.description,
                args_schema=scoperto.args_schema,
                func=lambda nome=scoperto.name, **argomenti: self.chiama(nome, argomenti),
            )
            for scoperto in self._scoperti.values()
        ]

    def chiama(self, nome: str, argomenti: dict) -> str:
        """Esegue il tool `nome` sul server e ne restituisce il testo.

        Errore del tool → `ToolException`; server irraggiungibile → `ErroreCollegamento`.
        """
        if self._loop is None or self._task is None or self._task.done():
            raise ErroreCollegamento("server delle note non collegato")
        if nome not in self._scoperti:
            raise ToolException(f"strumento sconosciuto '{nome}'")
        futuro = asyncio.run_coroutine_threadsafe(
            self._scoperti[nome].ainvoke(argomenti), self._loop
        )
        try:
            return _testo(futuro.result(self.timeout))
        except ToolException:
            raise
        except TimeoutError:
            futuro.cancel()
            raise ErroreCollegamento(f"nessuna risposta entro {self.timeout:g} secondi") from None
        except Exception as errore:
            raise ErroreCollegamento(f"{type(errore).__name__}: {errore}") from None

    def chiudi(self) -> None:
        """Chiude sessione e server; si può chiamare più volte."""
        loop, self._loop = self._loop, None
        if loop is not None:
            if self._task is not None and self._fine is not None:
                loop.call_soon_threadsafe(self._fine.set)
                try:
                    asyncio.run_coroutine_threadsafe(self._attendi_task(), loop).result(self.timeout)
                except Exception:
                    pass
            loop.call_soon_threadsafe(loop.stop)
            self._thread.join(self.timeout)
            loop.close()
        if self._log is not None:
            self._log.close()
            self._log = None

    async def _attendi_task(self) -> None:
        await asyncio.wait({self._task})
