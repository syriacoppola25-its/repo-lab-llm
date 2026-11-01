"""Il grafo LangGraph: stato, nodi e collegamenti tra i nodi.

    START → modello ──fine──────→ END
              ↑  │ ──limite──→ limite → END
              │  └─strumenti─→ strumenti
              └───────────────────┘
"""

import logging
from typing import Annotated, Literal, Sequence, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

MESSAGGIO_LIMITE = (
    "Non sono riuscito a completare la risposta (limite di passaggi raggiunto). "
    "Riprova o riformula la domanda."
)


class Stato(TypedDict):
    """Ciò che il grafo si passa da un nodo all'altro.

    `messaggi` usa `add_messages`: quando un nodo restituisce nuovi messaggi,
    vengono aggiunti in coda invece di sostituire la lista.
    `chiamate_strumento` conta gli strumenti eseguiti per la domanda corrente.
    """

    messaggi: Annotated[list[AnyMessage], add_messages]
    chiamate_strumento: int


def _richieste(stato: Stato) -> list[dict]:
    """Le chiamate a strumenti chieste dall'ultimo messaggio del modello."""
    ultimo = stato["messaggi"][-1]
    return list(ultimo.tool_calls) if isinstance(ultimo, AIMessage) else []


def instrada(stato: Stato, limite: int) -> Literal["strumenti", "limite", "fine"]:
    """Sceglie il nodo dopo `modello`: risposta finale, strumenti o stop per limite."""
    richieste = _richieste(stato)
    if not richieste:
        return "fine"
    if stato["chiamate_strumento"] + len(richieste) > limite:
        return "limite"
    return "strumenti"


def _registro_muto() -> logging.Logger:
    """Logger che non scrive nulla, usato quando non ne viene passato uno."""
    registro = logging.getLogger("assistente.muto")
    if not registro.handlers:
        registro.addHandler(logging.NullHandler())
    registro.propagate = False
    return registro


def costruisci_grafo(
    modello,
    istruzioni: str = "",
    strumenti: Sequence[BaseTool] = (),
    limite: int = 5,
    registro: logging.Logger | None = None,
):
    """Costruisce il grafo con i nodi `modello`, `strumenti` e `limite`."""
    per_nome = {s.name: s for s in strumenti}
    registro = registro or _registro_muto()

    def nodo_modello(stato: Stato) -> dict:
        # Il modello legge tutta la conversazione e aggiunge la sua risposta.
        # Le istruzioni di sistema vanno al modello ma non entrano nella cronologia.
        messaggi = stato["messaggi"]
        if istruzioni:
            messaggi = [SystemMessage(istruzioni), *messaggi]
        return {"messaggi": [modello.invoke(messaggi)]}

    def nodo_strumenti(stato: Stato) -> dict:
        # Esegue davvero ogni strumento richiesto e restituisce il risultato al modello.
        # Gli errori diventano testo per il modello, mai eccezioni.
        risultati = []
        passaggio = stato["chiamate_strumento"]
        for richiesta in _richieste(stato):
            passaggio += 1
            strumento = per_nome.get(richiesta["name"])
            if strumento is None:
                testo = f"Errore: strumento sconosciuto '{richiesta['name']}'."
            else:
                try:
                    testo = str(strumento.invoke(richiesta["args"]))
                except Exception as errore:
                    testo = f"Errore: argomenti non validi ({type(errore).__name__})."
            registro.info(
                f"passaggio={passaggio} strumento={richiesta['name']} "
                f"argomenti={richiesta['args']} risultato={testo}"
            )
            risultati.append(ToolMessage(testo, tool_call_id=richiesta["id"]))
        return {"messaggi": risultati, "chiamate_strumento": passaggio}

    def nodo_limite(stato: Stato) -> dict:
        # Chiude le chiamate rimaste senza esito (la cronologia resta valida per la
        # domanda successiva) e risponde con il messaggio fisso.
        richieste = _richieste(stato)
        registro.warning(
            f"limite raggiunto: chiamate={stato['chiamate_strumento']} "
            f"richieste={len(richieste)} limite={limite}"
        )
        chiusure = [
            ToolMessage("non eseguita: limite raggiunto", tool_call_id=r["id"]) for r in richieste
        ]
        return {"messaggi": [*chiusure, AIMessage(MESSAGGIO_LIMITE)]}

    grafo = StateGraph(Stato)
    grafo.add_node("modello", nodo_modello)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_node("limite", nodo_limite)
    grafo.add_edge(START, "modello")
    grafo.add_conditional_edges(
        "modello",
        lambda stato: instrada(stato, limite),
        {"strumenti": "strumenti", "limite": "limite", "fine": END},
    )
    grafo.add_edge("strumenti", "modello")
    grafo.add_edge("limite", END)
    return grafo.compile()
