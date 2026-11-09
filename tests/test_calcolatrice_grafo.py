"""Grafo con i server veri della calcolatrice e delle note (via stdio) e un modello finto."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.calcolatrice_mcp import ClientCalcolatrice
from assistente.grafo import costruisci_grafo
from assistente.modello import istruzioni_sistema
from assistente.note_mcp import ClientNote
from assistente.registro import configura_registro
from tests.finti import ModelloFinto


def richiesta(id, nome, argomenti):
    return {"name": nome, "args": argomenti, "id": id, "type": "tool_call"}


@pytest.fixture
def calcolatrice(tmp_path):
    with ClientCalcolatrice(tmp_path / "server_calcolatrice.log") as client:
        yield client


def esegui(tmp_path, strumenti, richieste, risposta="fatto"):
    """Il modello finto chiede `richieste` in un solo turno, poi risponde `risposta`."""
    modello = ModelloFinto([AIMessage("", tool_calls=richieste), AIMessage(risposta)])
    grafo = costruisci_grafo(
        modello, strumenti=strumenti, registro=configura_registro(tmp_path / "a.log")
    )
    esito = grafo.invoke({"messaggi": [HumanMessage("calcola")], "chiamate_strumento": 0})
    risultati = {m.tool_call_id: m.content for m in esito["messaggi"] if isinstance(m, ToolMessage)}
    righe = (tmp_path / "a.log").read_text(encoding="utf-8").splitlines()
    return esito, risultati, righe


def test_chiamata_alla_calcolatrice(calcolatrice, tmp_path):
    esito, risultati, righe = esegui(
        tmp_path, calcolatrice.strumenti(), [richiesta("c1", "calculate", {"expression": "2 + 3"})], "Fa 5."
    )

    assert '"risultato":5' in risultati["c1"].replace(" ", "")
    assert esito["messaggi"][-1].content == "Fa 5."
    assert "strumento=calculate" in righe[0] and "esito=ok" in righe[0]
    assert "c1" in righe[0]


def test_errore_della_calcolatrice_arriva_al_modello(calcolatrice, tmp_path):
    _, risultati, righe = esegui(
        tmp_path, calcolatrice.strumenti(), [richiesta("c1", "calculate", {"expression": "10 / 0"})]
    )

    assert "divisione per zero" in risultati["c1"]
    assert "esito=errore_strumento" in righe[0]


def test_calcolatrice_chiusa_gli_altri_funzionano(tmp_path):
    with ClientNote(tmp_path / "note.db", "Europe/Rome", tmp_path / "server_note.log") as note:
        calcolatrice = ClientCalcolatrice(tmp_path / "server_calcolatrice.log")
        calcolatrice.apri()
        strumenti = [*note.strumenti(), *calcolatrice.strumenti()]
        calcolatrice.chiudi()

        _, risultati, righe = esegui(
            tmp_path,
            strumenti,
            [
                richiesta("c1", "calculate", {"expression": "1 + 1"}),
                richiesta("n1", "list_notes", {}),
            ],
        )

    assert risultati["c1"].startswith("Errore di collegamento:")
    assert "strumento=calculate" in righe[0] and "esito=errore_collegamento" in righe[0]
    assert "strumento=list_notes" in righe[1] and "esito=ok" in righe[1]


def test_istruzioni_citano_la_calcolatrice():
    istruzioni = istruzioni_sistema("Europe/Rome")

    assert "`calculate`" in istruzioni
    assert "punto" in istruzioni
    assert "240 * 15 / 100" in istruzioni
