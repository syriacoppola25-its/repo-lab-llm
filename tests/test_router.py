from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.router import istruzioni_router, leggi_decisione, messaggi_per_router, risposta_grezza
from tests.finti import decisione, illeggibile


def uscita(parsed) -> dict:
    """Uscita del router con un `parsed` qualsiasi (letto come JSON ma da controllare)."""
    return {"raw": AIMessage(str(parsed)), "parsed": parsed, "parsing_error": None}


def test_decisione_valida():
    assert leggi_decisione(decisione("conversazione", "mail di lavoro")) == {
        "categoria": "conversazione",
        "motivo": "mail di lavoro",
    }


def test_parsing_fallito():
    assert leggi_decisione(illeggibile()) is None


def test_categoria_sconosciuta():
    assert leggi_decisione(uscita({"categoria": "sport", "motivo": "x"})) is None


def test_categoria_non_esatta():
    assert leggi_decisione(uscita({"categoria": "Conversazione ", "motivo": "x"})) is None


def test_motivo_vuoto():
    assert leggi_decisione(uscita({"categoria": "conversazione", "motivo": "   "})) is None


def test_motivo_non_stringa():
    assert leggi_decisione(uscita({"categoria": "conversazione", "motivo": 3})) is None


def test_campo_mancante():
    assert leggi_decisione(uscita({"categoria": "conversazione"})) is None


def test_parsed_non_dizionario():
    assert leggi_decisione(uscita("conversazione")) is None


def test_motivo_su_una_riga():
    esito = leggi_decisione(decisione("fuori_ambito", "  parla\n di   sport "))
    assert esito["motivo"] == "parla di sport"


def test_router_riceve_solo_testo():
    messaggi = [
        HumanMessage("che ore sono?"),
        AIMessage("", tool_calls=[{"name": "orologio", "args": {}, "id": "1", "type": "tool_call"}]),
        ToolMessage("14:00", tool_call_id="1"),
        AIMessage("Sono le 14:00."),
        HumanMessage("e a Tokyo?"),
    ]
    assert [m.content for m in messaggi_per_router(messaggi)] == [
        "che ore sono?",
        "Sono le 14:00.",
        "e a Tokyo?",
    ]


def test_router_scarta_testo_con_chiamate():
    messaggi = [
        HumanMessage("quanto fa 2+2?"),
        AIMessage("Calcolo…", tool_calls=[{"name": "calculate", "args": {}, "id": "1", "type": "tool_call"}]),
    ]
    assert [m.content for m in messaggi_per_router(messaggi)] == ["quanto fa 2+2?"]


def test_istruzioni_nominano_categorie_e_ambito():
    testo = istruzioni_router().lower()
    for parola in ("conversazione", "fuori_ambito", "ufficio", "ricette", "sport", "medic"):
        assert parola in testo


def test_risposta_grezza_dal_modello():
    assert risposta_grezza(illeggibile("ciao")) == "ciao"
    assert risposta_grezza({"raw": None, "parsed": None, "parsing_error": None}) == ""
