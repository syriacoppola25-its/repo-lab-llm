"""Server MCP della calcolatrice, interrogato con il client in memoria di FastMCP."""

from server_calcolatrice.server import crea_server
from tests.test_server_note import catalogo, con_client


def calcola(espressione):
    async def chiama(client):
        return await client.call_tool(
            "calculate", {"expression": espressione}, raise_on_error=False
        )

    return con_client(crea_server(), chiama)


def test_catalogo_un_tool():
    tool = catalogo(crea_server())

    assert set(tool) == {"calculate"}
    schema = tool["calculate"].inputSchema
    assert schema["required"] == ["expression"]
    assert schema["properties"]["expression"]["type"] == "string"


def test_descrizione_dichiara_le_regole():
    descrizione = catalogo(crea_server())["calculate"].description

    assert "+ - * / // % **" in descrizione
    assert "punto" in descrizione
    assert "resto" in descrizione
    assert "percentual" in descrizione


def test_calcolo():
    esito = calcola(" (12.5 + 7) * 3 ")

    assert not esito.is_error
    assert esito.structured_content == {"espressione": "(12.5 + 7) * 3", "risultato": 58.5}


def test_risultato_arrotondato():
    assert calcola("0.1 + 0.2").structured_content["risultato"] == 0.3
    assert calcola("7 / 7").structured_content["risultato"] == 1


def test_errore_diventa_errore_mcp():
    esito = calcola("10 / 0")

    assert esito.is_error
    assert esito.content[0].text == "divisione per zero"


def test_input_ostile_rifiutato():
    esito = calcola("__import__('os').system('echo x')")

    assert esito.is_error
    assert "chiamata di funzione" in esito.content[0].text
