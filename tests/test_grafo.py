from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from assistente.grafo import costruisci_grafo
from tests.finti import ModelloFinto


def test_grafo_risponde_con_il_modello():
    modello = ModelloFinto([AIMessage("ciao")])

    esito = costruisci_grafo(modello).invoke(
        {"messaggi": [HumanMessage("salve")], "chiamate_strumento": 0}
    )

    assert [m.content for m in esito["messaggi"]] == ["salve", "ciao"]


def test_istruzioni_inviate_ma_non_salvate():
    modello = ModelloFinto([AIMessage("ciao")])

    esito = costruisci_grafo(modello, istruzioni="ISTR").invoke(
        {"messaggi": [HumanMessage("salve")], "chiamate_strumento": 0}
    )

    assert modello.ricevuti[0][0] == SystemMessage("ISTR")
    assert not any(isinstance(m, SystemMessage) for m in esito["messaggi"])
