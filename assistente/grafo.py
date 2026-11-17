"""Il grafo LangGraph: stato, nodi e collegamenti tra i nodi.

    START → router ──conversazione──→ agente ──fine──────→ END
               │                        ↑  │ ──limite──→ limite → END
               │                        │  └─strumenti─→ strumenti
               │                        └───────────────────┘
               ├──fuori_ambito──→ rifiuto ──→ END
               └──non_leggibile─→ riformula ─→ END
"""

import json
import logging
from typing import Annotated, Callable, Literal, Mapping, Sequence, TypedDict

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    AnyMessage,
    SystemMessage,
    ToolMessage,
    message_chunk_to_message,
)
from langchain_core.tools import BaseTool, ToolException
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from assistente.router import (
    MESSAGGIO_RIFIUTO,
    MESSAGGIO_RIFORMULA,
    istruzioni_router,
    leggi_decisione,
    messaggi_per_router,
    risposta_grezza,
)
from assistente.strumenti import ErroreCollegamento

MESSAGGIO_LIMITE = (
    "Non sono riuscito a completare la risposta (limite di passaggi raggiunto). "
    "Riprova o riformula la domanda."
)
MESSAGGIO_ANNULLATA = "Eliminazione annullata dall'utente: nessuna nota è stata eliminata."


class Stato(TypedDict):
    """Ciò che il grafo si passa da un nodo all'altro.

    `messaggi` usa `add_messages`: quando un nodo restituisce nuovi messaggi,
    vengono aggiunti in coda invece di sostituire la lista.
    `chiamate_strumento` conta gli strumenti eseguiti per la domanda corrente.
    `decisione` è la decisione del router (`categoria`, `motivo`), None se non leggibile.
    """

    messaggi: Annotated[list[AnyMessage], add_messages]
    chiamate_strumento: int
    decisione: dict | None


def _richieste(stato: Stato) -> list[dict]:
    """Le chiamate a strumenti chieste dall'ultimo messaggio del modello.

    Include quelle con argomenti non leggibili (`invalid_tool_calls`): anche loro
    devono ricevere una risposta, altrimenti la cronologia non è più valida.
    """
    ultimo = stato["messaggi"][-1]
    if not isinstance(ultimo, AIMessage):
        return []
    return [*ultimo.tool_calls, *ultimo.invalid_tool_calls]


def instrada_router(stato: Stato) -> Literal["agente", "rifiuto", "riformula"]:
    """Sceglie il nodo dopo `router`: agente, rifiuto o richiesta di riformulare."""
    decisione = stato["decisione"]
    if decisione is None:
        return "riformula"
    if decisione["categoria"] == "conversazione":
        return "agente"
    return "rifiuto"


def instrada(stato: Stato, limite: int) -> Literal["strumenti", "limite", "fine"]:
    """Sceglie il nodo dopo `agente`: risposta finale, strumenti o stop per limite."""
    richieste = _richieste(stato)
    if not richieste:
        return "fine"
    if stato["chiamate_strumento"] + len(richieste) > limite:
        return "limite"
    return "strumenti"


def _ricomponi(totale: AIMessageChunk) -> AIMessage:
    """Il messaggio intero dai pezzi ricevuti, con gli argomenti letti in modo rigoroso.

    Ricomponendo i pezzi LangChain legge anche un JSON troncato (`{"a` diventa `{}`):
    qui una chiamata con argomenti non leggibili resta tra le `invalid_tool_calls`,
    come con una risposta intera, così lo strumento non parte con argomenti parziali.
    """
    validi, non_validi = [], []
    for pezzo in totale.tool_call_chunks:
        testo = pezzo["args"] or "{}"
        try:
            argomenti = json.loads(testo)
        except ValueError:
            argomenti = None
        if isinstance(argomenti, dict):
            validi.append(
                {"name": pezzo["name"], "args": argomenti, "id": pezzo["id"], "type": "tool_call"}
            )
        else:
            non_validi.append(
                {
                    "name": pezzo["name"],
                    "args": testo,
                    "id": pezzo["id"],
                    "error": None,
                    "type": "invalid_tool_call",
                }
            )
    messaggio = message_chunk_to_message(totale)
    return messaggio.model_copy(update={"tool_calls": validi, "invalid_tool_calls": non_validi})


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
    conferme: Mapping[str, Callable[[dict], bool]] = {},
    *,
    router,
):
    """Costruisce il grafo con i nodi `router`, `agente`, `strumenti`, `limite`,
    `rifiuto` e `riformula`.

    `router` classifica la domanda: riceve una lista di messaggi e restituisce l'uscita
    di `with_structured_output(..., include_raw=True)` (vedi `assistente.router`).
    `conferme` associa al nome di uno strumento una funzione che riceve gli
    argomenti e decide se eseguirlo (per esempio chiedendo all'utente).
    """
    per_nome = {s.name: s for s in strumenti}
    registro = registro or _registro_muto()

    def nodo_router(stato: Stato) -> dict:
        # Classifica l'ultima domanda; non va in streaming e non sceglie strumenti.
        # Gli errori di collegamento (o HTTP) risalgono; solo una risposta illeggibile
        # porta a `riformula`.
        uscita = router.invoke(
            [SystemMessage(istruzioni_router()), *messaggi_per_router(stato["messaggi"])]
        )
        decisione = leggi_decisione(uscita)
        if decisione is None:
            registro.warning(
                f"router risposta non leggibile risposta={risposta_grezza(uscita)[:200]} "
                "prossimo=riformula"
            )
        else:
            prossimo = "agente" if decisione["categoria"] == "conversazione" else "rifiuto"
            registro.info(
                f"router categoria={decisione['categoria']} motivo={decisione['motivo']} "
                f"prossimo={prossimo}"
            )
        return {"decisione": decisione}

    def risposta_fissa(testo: str) -> dict:
        # Il messaggio esce come testo in streaming ed entra nella cronologia.
        get_stream_writer()({"tipo": "testo", "testo": testo})
        return {"messaggi": [AIMessage(testo)]}

    def nodo_rifiuto(stato: Stato) -> dict:
        return risposta_fissa(MESSAGGIO_RIFIUTO)

    def nodo_riformula(stato: Stato) -> dict:
        return risposta_fissa(MESSAGGIO_RIFORMULA)

    def nodo_agente(stato: Stato) -> dict:
        registro.info("nodo=agente")
        # Il modello legge tutta la conversazione e aggiunge la sua risposta, che arriva
        # a pezzi: ogni pezzo di testo esce subito come evento, e i pezzi ricomposti
        # formano il messaggio intero per lo stato.
        # Le istruzioni di sistema vanno al modello ma non entrano nella cronologia.
        messaggi = stato["messaggi"]
        if istruzioni:
            messaggi = [SystemMessage(istruzioni), *messaggi]
        scrivi = get_stream_writer()
        totale = None
        for pezzo in modello.stream(messaggi):
            if isinstance(pezzo.content, str) and pezzo.content:
                scrivi({"tipo": "testo", "testo": pezzo.content})
            totale = pezzo if totale is None else totale + pezzo
        risposta = AIMessage("") if totale is None else _ricomponi(totale)
        return {"messaggi": [risposta]}

    def esegui(richiesta: dict) -> tuple[str, str, str]:
        """Esegue una richiesta: restituisce (testo per il modello, esito, nota di conferma)."""
        nome = richiesta["name"]
        strumento = per_nome.get(nome)
        if richiesta.get("type") == "invalid_tool_call":
            return "Errore: argomenti non validi (JSON non leggibile).", "argomenti_non_validi", ""
        if strumento is None:
            return f"Errore: strumento sconosciuto '{nome}'.", "strumento_sconosciuto", ""
        conferma = ""
        if nome in conferme:
            # La conferma avviene prima dell'esecuzione: con un "no" lo strumento non parte.
            if not conferme[nome](richiesta["args"]):
                return MESSAGGIO_ANNULLATA, "annullata", " conferma=no"
            conferma = " conferma=si"
        try:
            return str(strumento.invoke(richiesta["args"])), "ok", conferma
        except ToolException as errore:
            return f"Errore dello strumento: {errore}", "errore_strumento", conferma
        except ErroreCollegamento as errore:
            return f"Errore di collegamento: {errore}", "errore_collegamento", conferma
        except Exception as errore:
            testo = f"Errore: argomenti non validi ({type(errore).__name__})."
            return testo, "argomenti_non_validi", conferma

    def nodo_strumenti(stato: Stato) -> dict:
        # Esegue davvero ogni strumento richiesto e restituisce il risultato al modello.
        # Gli errori diventano testo per il modello, mai eccezioni.
        risultati = []
        passaggio = stato["chiamate_strumento"]
        scrivi = get_stream_writer()
        for richiesta in _richieste(stato):
            passaggio += 1
            # L'evento esce prima dell'esecuzione (e quindi prima di un'eventuale conferma).
            scrivi({"tipo": "strumento", "nome": richiesta["name"]})
            testo, esito, conferma = esegui(richiesta)
            registro.info(
                f"passaggio={passaggio} id={richiesta['id']} strumento={richiesta['name']} "
                f"argomenti={richiesta['args']}{conferma} esito={esito} risultato={testo}"
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
        # Il messaggio del limite non viene dal modello: è un nuovo tratto di risposta.
        get_stream_writer()({"tipo": "testo", "testo": MESSAGGIO_LIMITE, "nuovo_tratto": True})
        return {"messaggi": [*chiusure, AIMessage(MESSAGGIO_LIMITE)]}

    grafo = StateGraph(Stato)
    grafo.add_node("router", nodo_router)
    grafo.add_node("agente", nodo_agente)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_node("limite", nodo_limite)
    grafo.add_node("rifiuto", nodo_rifiuto)
    grafo.add_node("riformula", nodo_riformula)
    grafo.add_edge(START, "router")
    grafo.add_conditional_edges(
        "router",
        instrada_router,
        {"agente": "agente", "rifiuto": "rifiuto", "riformula": "riformula"},
    )
    grafo.add_conditional_edges(
        "agente",
        lambda stato: instrada(stato, limite),
        {"strumenti": "strumenti", "limite": "limite", "fine": END},
    )
    grafo.add_edge("strumenti", "agente")
    grafo.add_edge("limite", END)
    grafo.add_edge("rifiuto", END)
    grafo.add_edge("riformula", END)
    return grafo.compile()
