"""Collegamento al modello servito da LM Studio e istruzioni di sistema."""

from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from assistente.config import Config


def istruzioni_sistema(fuso_predefinito: str) -> str:
    """Istruzioni mandate al modello all'inizio di ogni richiesta."""
    return (
        "Sei l'assistente del laboratorio. Rispondi sempre in italiano e in modo conciso.\n"
        "Per sapere data o ora usa sempre lo strumento `orologio`: non inventarle e non "
        "usare orari presenti nei messaggi precedenti.\n"
        "Se la domanda riguarda una città o un paese, passa a `orologio` il suo fuso orario "
        "IANA (per esempio Asia/Tokyo per Tokyo).\n"
        f"Il fuso predefinito è {fuso_predefinito}. Se l'utente non indica un luogo, "
        "rispondi con data e ora senza scrivere il nome del fuso. Se l'utente indica un "
        "luogo, scrivi anche il fuso usato.\n"
        "Note: quando l'utente chiede di ricordare o annotare qualcosa, usa `add_note` una "
        "sola volta. Per mostrare le note usa `list_notes`.\n"
        "Per eliminare una nota descritta a parole, prima cerca il suo ID con `list_notes`, "
        "poi chiama `delete_note` con quell'ID. Non inventare mai un ID.\n"
        "Non chiedere conferma nel testo prima di eliminare: la chiede il programma "
        "all'utente. Riferisci sempre l'esito reale restituito dallo strumento.\n"
        "Calcoli: per ogni calcolo usa sempre lo strumento `calculate`, non fare i conti a "
        "mente. Scrivi i decimali con il punto. Il simbolo % è il resto della divisione: "
        "traduci le percentuali in moltiplicazioni (il 15% di 240 è 240 * 15 / 100). Se "
        "`calculate` restituisce un errore, riferiscilo all'utente senza inventare un risultato."
    )


def crea_modello(config: Config, strumenti: list[BaseTool]) -> Runnable:
    """Client per l'API compatibile con OpenAI di LM Studio.

    LM Studio non controlla la chiave, ma il client ne richiede una qualsiasi.
    """
    modello = ChatOpenAI(base_url=config.url_server, model=config.modello, api_key="lm-studio")
    if strumenti:
        return modello.bind_tools(strumenti)
    return modello
