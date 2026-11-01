"""Collegamento al modello servito da LM Studio e istruzioni di sistema."""

from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from assistente.config import Config


def istruzioni_sistema(fuso_predefinito: str) -> str:
    """Istruzioni mandate al modello all'inizio di ogni richiesta."""
    return "Sei l'assistente del laboratorio. Rispondi sempre in italiano e in modo conciso."


def crea_modello(config: Config, strumenti: list[BaseTool]) -> Runnable:
    """Client per l'API compatibile con OpenAI di LM Studio.

    LM Studio non controlla la chiave, ma il client ne richiede una qualsiasi.
    """
    modello = ChatOpenAI(base_url=config.url_server, model=config.modello, api_key="lm-studio")
    if strumenti:
        return modello.bind_tools(strumenti)
    return modello
