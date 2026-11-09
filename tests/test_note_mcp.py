"""Client MCP sincrono: avvia davvero il server delle note via stdio (nessun modello)."""

import json
from pathlib import Path

import pytest
from langchain_core.tools import ToolException

import assistente.note_mcp
from assistente.note_mcp import ClientNote
from assistente.strumenti import ErroreCollegamento
from server_note.archivio import ArchivioNote
from server_note.server import crea_server
from tests.test_server_note import catalogo


def nuovo_client(tmp_path, **opzioni):
    return ClientNote(tmp_path / "note.db", "Europe/Rome", tmp_path / "server_note.log", **opzioni)


@pytest.fixture
def client(tmp_path):
    with nuovo_client(tmp_path) as client:
        yield client


def per_nome(client):
    return {s.name: s for s in client.strumenti()}


def test_discovery_dal_server(client, tmp_path):
    strumenti = per_nome(client)
    atteso = catalogo(crea_server(ArchivioNote(tmp_path / "altro.db")))

    assert set(strumenti) == {"add_note", "list_notes", "delete_note"}
    for nome, tool in atteso.items():
        assert strumenti[nome].description == tool.description
        assert strumenti[nome].args_schema == tool.inputSchema
    assert "note_id" in strumenti["delete_note"].args_schema["required"]
    sorgente = Path(assistente.note_mcp.__file__).read_text(encoding="utf-8")
    for nome in ("add_note", "list_notes", "delete_note"):
        assert nome not in sorgente


def test_invocazione_diretta(client):
    strumenti = per_nome(client)

    creata = json.loads(strumenti["add_note"].invoke({"text": "ciao"}))
    elenco = json.loads(strumenti["list_notes"].invoke({}))

    assert creata["id"] == 1
    assert [n["testo"] for n in elenco["note"]] == ["ciao"]


def test_chiama_per_nome(client):
    client.chiama("add_note", {"text": "report venerdì"})
    assert json.loads(client.chiama("list_notes", {"limit": 100}))["totale"] == 1


def test_errore_strumento_e_toolexception(client):
    with pytest.raises(ToolException, match="99"):
        per_nome(client)["delete_note"].invoke({"note_id": 99})


def test_persistenza_tra_due_avvii(tmp_path):
    with nuovo_client(tmp_path) as primo:
        primo.chiama("add_note", {"text": "da ricordare"})
    with nuovo_client(tmp_path) as secondo:
        elenco = json.loads(secondo.chiama("list_notes", {}))
    assert [n["testo"] for n in elenco["note"]] == ["da ricordare"]


def test_dopo_chiusura_errore_di_collegamento(tmp_path):
    client = nuovo_client(tmp_path)
    client.apri()
    add = per_nome(client)["add_note"]
    client.chiudi()
    client.chiudi()  # idempotente

    with pytest.raises(ErroreCollegamento):
        add.invoke({"text": "ciao"})


def test_avvio_fallito(tmp_path):
    client = nuovo_client(tmp_path, python=str(tmp_path / "manca.exe"))
    with pytest.raises(ErroreCollegamento):
        client.apri()
    client.chiudi()


def test_banner_assente(client, tmp_path):
    client.chiama("list_notes", {})
    log = tmp_path / "server_note.log"
    assert "FastMCP" not in (log.read_text(encoding="utf-8") if log.exists() else "")
