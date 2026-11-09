"""Prova reale con LM Studio: si esegue solo con PROVA_LMSTUDIO=1.

Richiede LM Studio avviato e le variabili LMSTUDIO_URL e LMSTUDIO_MODELLO.
Le note usano un archivio temporaneo; la conferma dell'eliminazione è fissa (sì).
"""

import json
import os

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.config import carica_config
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello, istruzioni_sistema
from assistente.note_mcp import ClientNote
from assistente.registro import configura_registro
from assistente.strumenti import crea_orologio

pytestmark = pytest.mark.skipif(
    os.environ.get("PROVA_LMSTUDIO") != "1",
    reason="prova reale: impostare PROVA_LMSTUDIO=1 con LM Studio avviato",
)

MEETING = "meeting giovedì 4 alle 10"


@pytest.fixture
def config():
    return carica_config(os.environ)


@pytest.fixture
def client(config, tmp_path):
    with ClientNote(tmp_path / "note.db", config.fuso_predefinito, tmp_path / "server_note.log") as c:
        yield c


def grafo_reale(config, tmp_path, strumenti):
    return costruisci_grafo(
        crea_modello(config, strumenti),
        istruzioni_sistema(config.fuso_predefinito),
        strumenti=strumenti,
        limite=config.limite_chiamate,
        registro=configura_registro(tmp_path / "assistente.log"),
        conferme={"delete_note": lambda argomenti: True},
    )


def chiedi(config, tmp_path, client, domanda):
    """Una domanda al modello vero; restituisce (nomi degli strumenti chiamati, risposta)."""
    strumenti = [crea_orologio(config.fuso_predefinito), *client.strumenti()]
    esito = grafo_reale(config, tmp_path, strumenti).invoke(
        {"messaggi": [HumanMessage(domanda)], "chiamate_strumento": 0}
    )
    chiamati = [c["name"] for m in esito["messaggi"] if isinstance(m, AIMessage) for c in m.tool_calls]
    ultimo = esito["messaggi"][-1]
    assert isinstance(ultimo, AIMessage) and not ultimo.tool_calls
    return chiamati, ultimo.content


def note(client):
    return [n["testo"] for n in json.loads(client.chiama("list_notes", {}))["note"]]


def test_modello_reale_usa_orologio(config, tmp_path):
    orologio = crea_orologio(config.fuso_predefinito)
    grafo = costruisci_grafo(
        crea_modello(config, [orologio]),
        istruzioni_sistema(config.fuso_predefinito),
        strumenti=[orologio],
        limite=config.limite_chiamate,
        registro=configura_registro(tmp_path / "assistente.log"),
    )

    esito = grafo.invoke(
        {"messaggi": [HumanMessage("Che ore sono a Tokyo?")], "chiamate_strumento": 0}
    )

    risultati = [m for m in esito["messaggi"] if isinstance(m, ToolMessage)]
    assert risultati, "il modello non ha chiesto lo strumento orologio"
    assert "Asia/Tokyo" in risultati[0].content
    ultimo = esito["messaggi"][-1]
    assert isinstance(ultimo, AIMessage) and not ultimo.tool_calls
    assert ultimo.content.strip()


def test_reale_aggiunge_nota(config, tmp_path, client):
    chiamati, _ = chiedi(config, tmp_path, client, f"Ricordami che ho un {MEETING}")

    assert chiamati.count("add_note") == 1
    salvate = note(client)
    assert len(salvate) == 1 and "meeting" in salvate[0].lower()


def test_reale_elenca_note(config, tmp_path, client):
    client.chiama("add_note", {"text": MEETING})

    chiamati, risposta = chiedi(config, tmp_path, client, "Fammi vedere le note")

    assert "list_notes" in chiamati
    assert "meeting" in risposta.lower()


def test_reale_elimina_descrivendo(config, tmp_path, client):
    client.chiama("add_note", {"text": MEETING})

    chiamati, _ = chiedi(
        config, tmp_path, client, "Cancella la nota dell'appuntamento di giovedì 4"
    )

    assert "delete_note" in chiamati
    assert chiamati.index("list_notes") < chiamati.index("delete_note")
    assert note(client) == []


def test_reale_nota_inesistente(config, tmp_path, client):
    client.chiama("add_note", {"text": MEETING})

    chiamati, risposta = chiedi(config, tmp_path, client, "Elimina la nota 99")

    assert "delete_note" in chiamati
    assert note(client) == [MEETING]
    assert "esito=errore_strumento" in (tmp_path / "assistente.log").read_text(encoding="utf-8")
    assert "99" in risposta
