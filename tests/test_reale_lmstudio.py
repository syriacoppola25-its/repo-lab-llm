"""Prova reale con LM Studio: si esegue solo con PROVA_LMSTUDIO=1.

Richiede LM Studio avviato e le variabili LMSTUDIO_URL e LMSTUDIO_MODELLO.
"""

import os

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.config import carica_config
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello, istruzioni_sistema
from assistente.registro import configura_registro
from assistente.strumenti import crea_orologio

pytestmark = pytest.mark.skipif(
    os.environ.get("PROVA_LMSTUDIO") != "1",
    reason="prova reale: impostare PROVA_LMSTUDIO=1 con LM Studio avviato",
)


def test_modello_reale_usa_orologio(tmp_path):
    config = carica_config(os.environ)
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
