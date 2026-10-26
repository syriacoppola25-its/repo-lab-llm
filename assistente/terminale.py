"""Il ciclo domanda/risposta da terminale, con la cronologia della sessione."""

from typing import Callable

from langchain_core.messages import BaseMessage, HumanMessage

SALUTO = "Arrivederci!"
PENSANDO = "sto pensando…"
PROMPT = "Tu: "
COMANDO_USCITA = "esci"


def esegui_sessione(
    grafo,
    leggi: Callable[[str], str] = input,
    scrivi: Callable[[str], None] = print,
) -> None:
    """Conversa finché l'utente scrive `esci`, preme Ctrl+C o chiude l'input.

    La cronologia vive solo in questa funzione: alla fine della sessione va persa.
    """
    cronologia: list[BaseMessage] = []
    try:
        while True:
            domanda = leggi(PROMPT).strip()
            if not domanda:
                continue
            if domanda.lower() == COMANDO_USCITA:
                break
            scrivi(PENSANDO)
            esito = grafo.invoke(
                {"messaggi": cronologia + [HumanMessage(domanda)], "chiamate_strumento": 0}
            )
            cronologia = esito["messaggi"]
            scrivi(f"Assistente: {cronologia[-1].content}")
    except (KeyboardInterrupt, EOFError):
        pass
    scrivi(SALUTO)
