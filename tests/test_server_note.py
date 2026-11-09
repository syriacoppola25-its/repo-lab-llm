"""Server MCP delle note, interrogato con il client in memoria di FastMCP."""

import asyncio

import pytest
from fastmcp import Client

from server_note.archivio import ArchivioNote
from server_note.server import crea_server


@pytest.fixture
def server(tmp_path):
    return crea_server(ArchivioNote(tmp_path / "note.db"))


def con_client(server, operazione):
    """Esegue `operazione(client)` in una sessione MCP in memoria e ne restituisce l'esito."""

    async def esegui():
        async with Client(server) as client:
            return await operazione(client)

    return asyncio.run(esegui())


def catalogo(server):
    async def elenca(client):
        return {t.name: t for t in await client.list_tools()}

    return con_client(server, elenca)


def test_catalogo_tre_tool(server):
    tool = catalogo(server)

    assert set(tool) == {"add_note", "list_notes", "delete_note"}
    add = tool["add_note"].inputSchema
    assert add["required"] == ["text"] and add["properties"]["text"]["type"] == "string"
    delete = tool["delete_note"].inputSchema
    assert delete["required"] == ["note_id"]
    assert delete["properties"]["note_id"]["type"] == "integer"
    assert tool["list_notes"].inputSchema["properties"]["limit"]["default"] == 20


def test_descrizioni_dichiarano_gli_effetti(server):
    tool = catalogo(server)

    assert "modifica l'archivio" in tool["add_note"].description
    assert "modifica l'archivio" in tool["delete_note"].description
    assert "list_notes" in tool["delete_note"].description


def test_add_poi_list(server):
    async def aggiungi_ed_elenca(client):
        await client.call_tool("add_note", {"text": "report venerdì"})
        return await client.call_tool("list_notes", {})

    esito = con_client(server, aggiungi_ed_elenca)

    note = esito.structured_content["note"]
    assert [(n["id"], n["testo"]) for n in note] == [(1, "report venerdì")]


def test_errore_diventa_errore_mcp(server):
    async def elimina(client):
        return await client.call_tool("delete_note", {"note_id": 99}, raise_on_error=False)

    esito = con_client(server, elimina)

    assert esito.is_error
    assert esito.content[0].text == "Nessuna nota con ID 99."
