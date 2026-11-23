"""Il router: decide se la domanda rientra nell'ambito dell'assistente d'ufficio.

Il router non risponde e non sceglie strumenti: classifica l'ultima domanda in
`conversazione` (va all'agente) o `fuori_ambito` (riceve un rifiuto), con un motivo.
"""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from assistente.config import Config

CATEGORIE = ("conversazione", "fuori_ambito")

# Con `name` e `schema` langchain_openai lo passa così com'è a LM Studio come
# `response_format` di tipo `json_schema`.
SCHEMA_DECISIONE = {
    "name": "decisione_router",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "categoria": {"type": "string", "enum": list(CATEGORIE)},
            "motivo": {"type": "string"},
        },
        "required": ["categoria", "motivo"],
        "additionalProperties": False,
    },
}

MESSAGGIO_RIFIUTO = (
    "Mi dispiace, posso aiutarti solo con il lavoro d'ufficio "
    "(mail, testi, organizzazione, note, orari, calcoli)."
)
MESSAGGIO_RIFORMULA = "Non ho capito bene la richiesta: puoi riformularla?"


def istruzioni_router() -> str:
    """Istruzioni di sistema del router."""
    return (
        "Sei il filtro di un assistente d'ufficio. Non rispondere alla domanda: classifica "
        "soltanto l'ULTIMA domanda dell'utente. I messaggi precedenti servono solo come "
        "contesto per capire i seguiti (per esempio «e a Tokyo?»).\n"
        "Categorie:\n"
        "- conversazione: data e ora (anche di altre città), note da salvare, elencare o "
        "eliminare, calcoli; lavoro d'ufficio come scrivere o rivedere mail, riassumere o "
        "riformulare testi, organizzare la giornata, riunioni e scadenze, chiarire termini "
        "di lavoro; saluti, ringraziamenti, «che cosa sai fare?» e seguiti di una "
        "conversazione già in ambito.\n"
        "- fuori_ambito: sport, gossip, storie o contenuti di fantasia, consigli medici, "
        "ricette e cucina, e tutto ciò che non riguarda il lavoro d'ufficio.\n"
        "Regola che vale prima delle altre: se l'utente chiede di salvare, elencare o "
        "eliminare note, di fare un calcolo o di sapere data e ora, la categoria è "
        "conversazione qualunque sia l'argomento (anche sport o cucina).\n"
        "Esempi:\n"
        "- «Scrivimi una mail per spostare la riunione» → conversazione\n"
        "- «Che ore sono a New York?» → conversazione\n"
        "- «Quanto fa il 15% di 240?» → conversazione\n"
        "- «Ricordami di comprare il guanciale» → conversazione\n"
        "- «Salva una nota: vedere la partita sabato» → conversazione\n"
        "- «Chi ha vinto la partita ieri?» → fuori_ambito\n"
        "- «Come si prepara la carbonara?» → fuori_ambito\n"
        "- «Ho mal di testa, che medicina prendo?» → fuori_ambito\n"
        "Rispondi solo con il JSON richiesto: `categoria` (conversazione oppure "
        "fuori_ambito) e `motivo` (una frase breve in italiano)."
    )


def messaggi_per_router(messaggi: list[AnyMessage]) -> list[AnyMessage]:
    """La conversazione ridotta ai testi di utente e assistente, senza strumenti."""
    tenuti = []
    for messaggio in messaggi:
        if isinstance(messaggio, HumanMessage):
            tenuti.append(messaggio)
        elif (
            isinstance(messaggio, AIMessage)
            and not messaggio.tool_calls
            and not messaggio.invalid_tool_calls
            and isinstance(messaggio.content, str)
            and messaggio.content
        ):
            tenuti.append(messaggio)
    return tenuti


def leggi_decisione(uscita: dict) -> dict | None:
    """La decisione `{"categoria", "motivo"}` controllata, oppure None se non è leggibile.

    `uscita` è quella di `with_structured_output(..., include_raw=True)`: lo schema non
    basta, i valori si controllano qui.
    """
    if uscita.get("parsing_error") is not None:
        return None
    dati = uscita.get("parsed")
    if not isinstance(dati, dict):
        return None
    categoria, motivo = dati.get("categoria"), dati.get("motivo")
    if categoria not in CATEGORIE or not isinstance(motivo, str):
        return None
    motivo = " ".join(motivo.split())  # una sola riga nel log
    if not motivo:
        return None
    return {"categoria": categoria, "motivo": motivo}


def risposta_grezza(uscita: dict) -> str:
    """Il testo ricevuto dal modello, per il log (vuoto se manca)."""
    grezzo = uscita.get("raw")
    if grezzo is None:
        return ""
    return grezzo.content if isinstance(grezzo.content, str) else str(grezzo.content)


def modello_router(config: Config) -> ChatOpenAI:
    """Lo stesso modello di LM Studio, a temperatura 0: stessa domanda, stessa categoria."""
    return ChatOpenAI(
        base_url=config.url_server, model=config.modello, api_key="lm-studio", temperature=0
    )


def crea_router(config: Config) -> Runnable:
    """Il router: stesso modello di LM Studio, senza strumenti, con output strutturato."""
    return modello_router(config).with_structured_output(
        SCHEMA_DECISIONE, method="json_schema", include_raw=True
    )
