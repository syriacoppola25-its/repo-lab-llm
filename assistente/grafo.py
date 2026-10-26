"""Il grafo LangGraph: stato, nodi e collegamenti tra i nodi."""

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages


class Stato(TypedDict):
    """Ciò che il grafo si passa da un nodo all'altro.

    `messaggi` usa `add_messages`: quando un nodo restituisce nuovi messaggi,
    vengono aggiunti in coda invece di sostituire la lista.
    """

    messaggi: Annotated[list[AnyMessage], add_messages]
    chiamate_strumento: int


class RispostaFissa:
    """Sostituto provvisorio del modello: risponde sempre la stessa frase."""

    def invoke(self, messaggi: list[BaseMessage]) -> AIMessage:
        return AIMessage("Risposta fissa: il modello non è ancora collegato.")


def costruisci_grafo(modello):
    """Costruisce il grafo START → modello → END."""

    def nodo_modello(stato: Stato) -> dict:
        # Il modello legge tutta la conversazione e aggiunge la sua risposta.
        return {"messaggi": [modello.invoke(stato["messaggi"])]}

    grafo = StateGraph(Stato)
    grafo.add_node("modello", nodo_modello)
    grafo.add_edge(START, "modello")
    grafo.add_edge("modello", END)
    return grafo.compile()
