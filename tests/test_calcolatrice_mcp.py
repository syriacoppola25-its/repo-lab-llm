"""Client MCP della calcolatrice: avvia davvero il server via stdio (nessun modello)."""

import json
from pathlib import Path

import pytest
from langchain_core.tools import ToolException

import assistente.calcolatrice_mcp
import assistente.client_mcp
import assistente.note_mcp
from assistente.calcolatrice_mcp import ClientCalcolatrice
from assistente.strumenti import ErroreCollegamento
from server_calcolatrice.server import crea_server
from tests.test_server_note import catalogo

NOMI_DEI_TOOL = ("calculate", "add_note", "list_notes", "delete_note")


@pytest.fixture
def client(tmp_path):
    with ClientCalcolatrice(tmp_path / "server_calcolatrice.log") as client:
        yield client


def per_nome(client):
    return {s.name: s for s in client.strumenti()}


def test_discovery_dal_server(client):
    strumenti = per_nome(client)
    atteso = catalogo(crea_server())

    assert set(strumenti) == {"calculate"}
    assert strumenti["calculate"].description == atteso["calculate"].description
    assert strumenti["calculate"].args_schema == atteso["calculate"].inputSchema
    for modulo in (assistente.client_mcp, assistente.note_mcp, assistente.calcolatrice_mcp):
        sorgente = Path(modulo.__file__).read_text(encoding="utf-8")
        for nome in NOMI_DEI_TOOL:
            assert nome not in sorgente, f"{nome} in {modulo.__name__}"


def test_invocazione(client):
    esito = json.loads(per_nome(client)["calculate"].invoke({"expression": "6 * 7"}))

    assert esito["risultato"] == 42


def test_espressione_rifiutata_e_toolexception(client):
    with pytest.raises(ToolException, match="chiamata di funzione"):
        per_nome(client)["calculate"].invoke({"expression": "sqrt(4)"})


def test_avvio_fallito_nomina_la_calcolatrice(tmp_path):
    client = ClientCalcolatrice(tmp_path / "log.log", python=str(tmp_path / "manca.exe"))
    with pytest.raises(ErroreCollegamento, match="calcolatrice"):
        client.apri()
    client.chiudi()


def test_dopo_chiusura_errore_di_collegamento(tmp_path):
    client = ClientCalcolatrice(tmp_path / "server_calcolatrice.log")
    client.apri()
    calcola = per_nome(client)["calculate"]
    client.chiudi()

    with pytest.raises(ErroreCollegamento, match="calcolatrice"):
        calcola.invoke({"expression": "1 + 1"})
