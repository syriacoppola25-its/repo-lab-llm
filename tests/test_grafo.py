from langchain_core.messages import AIMessage, HumanMessage

from assistente.grafo import costruisci_grafo
from tests.finti import ModelloFinto


def test_grafo_risponde_con_il_modello():
    modello = ModelloFinto([AIMessage("ciao")])

    esito = costruisci_grafo(modello).invoke(
        {"messaggi": [HumanMessage("salve")], "chiamate_strumento": 0}
    )

    assert [m.content for m in esito["messaggi"]] == ["salve", "ciao"]
