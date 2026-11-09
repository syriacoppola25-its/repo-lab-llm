"""Grafo con il server delle note vero (via stdio) e un modello finto."""

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente import conferma as modulo_conferma
from assistente.conferma import crea_conferma_eliminazione
from assistente.grafo import MESSAGGIO_ANNULLATA, costruisci_grafo
from assistente.modello import istruzioni_sistema
from assistente.note_mcp import ClientNote
from assistente.registro import configura_registro
from tests.finti import ModelloFinto


@pytest.fixture
def client(tmp_path):
    with ClientNote(tmp_path / "note.db", "Europe/Rome", tmp_path / "server_note.log") as client:
        client.chiama("add_note", {"text": "meeting giovedì 4 alle 10"})
        yield client


def richiesta(id, nome, argomenti):
    return {"name": nome, "args": argomenti, "id": id, "type": "tool_call"}


def elimina_descrivendo(client, tmp_path, risposta, note_id=1):
    """Il modello cerca con list_notes, poi chiede delete_note; l'utente risponde `risposta`."""
    modello = ModelloFinto(
        [
            AIMessage("", tool_calls=[richiesta("1", "list_notes", {})]),
            AIMessage("", tool_calls=[richiesta("2", "delete_note", {"note_id": note_id})]),
            AIMessage("fatto"),
        ]
    )
    domande = []

    def leggi(domanda):
        domande.append(domanda)
        return risposta

    conferma = crea_conferma_eliminazione(lambda i: modulo_conferma.testo_nota(client, i), leggi=leggi)
    grafo = costruisci_grafo(
        modello,
        strumenti=client.strumenti(),
        conferme={"delete_note": conferma},
        registro=configura_registro(tmp_path / "a.log"),
    )
    esito = grafo.invoke(
        {"messaggi": [HumanMessage("cancella la nota del meeting")], "chiamate_strumento": 0}
    )
    risultati = {m.tool_call_id: m.content for m in esito["messaggi"] if isinstance(m, ToolMessage)}
    return risultati, domande


def note_salvate(client):
    return [n["testo"] for n in json.loads(client.chiama("list_notes", {}))["note"]]


def test_conferma_si_elimina(client, tmp_path):
    risultati, domande = elimina_descrivendo(client, tmp_path, "s")

    assert domande == ["Eliminare la nota 1: «meeting giovedì 4 alle 10»? (s/n) "]
    assert json.loads(risultati["2"])["eliminata"]["id"] == 1
    assert note_salvate(client) == []


def test_conferma_no_mantiene(client, tmp_path):
    risultati, _ = elimina_descrivendo(client, tmp_path, "n")

    assert risultati["2"] == MESSAGGIO_ANNULLATA
    assert note_salvate(client) == ["meeting giovedì 4 alle 10"]


def test_id_inesistente_errore_senza_effetti(client, tmp_path):
    risultati, domande = elimina_descrivendo(client, tmp_path, "s", note_id=99)

    assert domande == ["Eliminare la nota 99? (s/n) "]
    assert risultati["2"] == "Errore dello strumento: Nessuna nota con ID 99."
    assert note_salvate(client) == ["meeting giovedì 4 alle 10"]


def test_testo_nota_con_client_chiuso(tmp_path):
    client = ClientNote(tmp_path / "note.db", "Europe/Rome", tmp_path / "server_note.log")
    assert modulo_conferma.testo_nota(client, 1) is None


def test_istruzioni_citano_gli_strumenti_delle_note():
    istruzioni = istruzioni_sistema("Europe/Rome")
    for nome in ("add_note", "list_notes", "delete_note"):
        assert nome in istruzioni
