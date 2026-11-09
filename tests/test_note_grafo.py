"""Grafo con il server delle note vero (via stdio) e un modello finto."""

import asyncio
import json
from datetime import datetime, timezone

import mcp.client.stdio as stdio_mcp
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente import conferma as modulo_conferma
from assistente.conferma import crea_conferma_eliminazione
from assistente.grafo import MESSAGGIO_ANNULLATA, costruisci_grafo
from assistente.modello import istruzioni_sistema
from assistente.note_mcp import ClientNote
from assistente.registro import configura_registro
from assistente.strumenti import crea_orologio
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


def test_id_decimale_non_elimina_senza_conferma(client, tmp_path):
    # Il server accetterebbe "1.0" come 1: la conferma non deve lasciarlo passare.
    risultati, domande = elimina_descrivendo(client, tmp_path, "n", note_id="1.0")

    assert risultati["2"] == MESSAGGIO_ANNULLATA
    assert note_salvate(client) == ["meeting giovedì 4 alle 10"]


def test_list_notes_con_argomento_nome_non_elimina(client, tmp_path):
    # Il modello chiede list_notes con un argomento "nome": la conferma non scatta
    # (non è delete_note), quindi nessuna nota deve sparire.
    modello = ModelloFinto(
        [
            AIMessage(
                "",
                tool_calls=[richiesta("1", "list_notes", {"nome": "delete_note", "note_id": 1})],
            ),
            AIMessage("fatto"),
        ]
    )
    domande = []
    conferma = crea_conferma_eliminazione(lambda i: None, leggi=lambda d: domande.append(d) or "n")
    grafo = costruisci_grafo(
        modello,
        strumenti=client.strumenti(),
        conferme={"delete_note": conferma},
        registro=configura_registro(tmp_path / "a.log"),
    )
    grafo.invoke({"messaggi": [HumanMessage("mostra le note")], "chiamate_strumento": 0})

    assert domande == []
    assert note_salvate(client) == ["meeting giovedì 4 alle 10"]


def test_server_terminato_a_meta_sessione(monkeypatch, tmp_path):
    # Si intercetta il processo del server (solo nel test) per poterlo terminare davvero.
    processi = []
    crea_processo = stdio_mcp._create_platform_compatible_process

    async def crea_e_ricorda(*argomenti, **opzioni):
        processo = await crea_processo(*argomenti, **opzioni)
        processi.append(processo)
        return processo

    monkeypatch.setattr(stdio_mcp, "_create_platform_compatible_process", crea_e_ricorda)
    adesso = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
    orologio = crea_orologio("Europe/Rome", adesso=lambda: adesso)

    with ClientNote(tmp_path / "note.db", "Europe/Rome", tmp_path / "server_note.log") as client:
        client.timeout = 5
        asyncio.run_coroutine_threadsafe(
            stdio_mcp._terminate_process_tree(processi[0], 1), client._loop
        ).result(10)

        modello = ModelloFinto(
            [
                AIMessage("", tool_calls=[richiesta("1", "list_notes", {})]),
                AIMessage("", tool_calls=[richiesta("2", "orologio", {})]),
                AIMessage("fatto"),
            ]
        )
        grafo = costruisci_grafo(
            modello,
            strumenti=[orologio, *client.strumenti()],
            registro=configura_registro(tmp_path / "a.log"),
        )
        esito = grafo.invoke({"messaggi": [HumanMessage("note e ora")], "chiamate_strumento": 0})

    risultati = {m.tool_call_id: m.content for m in esito["messaggi"] if isinstance(m, ToolMessage)}
    righe = (tmp_path / "a.log").read_text(encoding="utf-8").splitlines()

    assert risultati["1"].startswith("Errore di collegamento:")
    assert "2026-11-09 11:00" in risultati["2"]
    assert esito["messaggi"][-1].content == "fatto"
    assert "strumento=list_notes" in righe[0] and "esito=errore_collegamento" in righe[0]
    assert "strumento=orologio" in righe[1] and "esito=ok" in righe[1]


def test_testo_nota_con_client_chiuso(tmp_path):
    client = ClientNote(tmp_path / "note.db", "Europe/Rome", tmp_path / "server_note.log")
    assert modulo_conferma.testo_nota(client, 1) is None


def test_istruzioni_citano_gli_strumenti_delle_note():
    istruzioni = istruzioni_sistema("Europe/Rome")
    for nome in ("add_note", "list_notes", "delete_note"):
        assert nome in istruzioni
