from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.grafo import MESSAGGIO_LIMITE, costruisci_grafo, instrada
from assistente.registro import configura_registro
from assistente.strumenti import crea_orologio
from tests.finti import ModelloFinto

ISTANTE = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)


def chiamata(id, args={"fuso_orario": "Asia/Tokyo"}, nome="orologio"):
    return {"name": nome, "args": args, "id": id, "type": "tool_call"}


def grafo_con_orologio(modello, tmp_path, limite=5):
    """Grafo con orologio a istante fisso e log in tmp_path/a.log."""
    return costruisci_grafo(
        modello,
        strumenti=[crea_orologio("Europe/Rome", adesso=lambda: ISTANTE)],
        limite=limite,
        registro=configura_registro(tmp_path / "a.log"),
    )


def avvia_fino_al_limite(tmp_path):
    richieste = [AIMessage("", tool_calls=[chiamata(str(i))]) for i in range(1, 7)]
    grafo = grafo_con_orologio(ModelloFinto(richieste), tmp_path, limite=5)
    return grafo.invoke({"messaggi": [HumanMessage("che ore sono?")], "chiamate_strumento": 0})


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


def test_instrada_fine():
    stato = {"messaggi": [HumanMessage("ciao"), AIMessage("salve")], "chiamate_strumento": 0}
    assert instrada(stato, 5) == "fine"


def test_instrada_strumenti():
    stato = {"messaggi": [AIMessage("", tool_calls=[chiamata("1")])], "chiamate_strumento": 0}
    assert instrada(stato, 5) == "strumenti"


def test_instrada_limite():
    stato = {
        "messaggi": [AIMessage("", tool_calls=[chiamata("1"), chiamata("2")])],
        "chiamate_strumento": 4,
    }
    assert instrada(stato, 5) == "limite"


def test_ciclo_completo(tmp_path):
    modello = ModelloFinto(
        [AIMessage("", tool_calls=[chiamata("1")]), AIMessage("A Tokyo sono le 23:00")]
    )

    esito = grafo_con_orologio(modello, tmp_path).invoke(
        {"messaggi": [HumanMessage("che ore sono a Tokyo?")], "chiamate_strumento": 0}
    )

    messaggi = esito["messaggi"]
    assert [type(m) for m in messaggi] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    assert messaggi[2].tool_call_id == "1"
    assert messaggi[2].content.startswith("2026-10-26 23:00:00 Asia/Tokyo")
    assert esito["chiamate_strumento"] == 1
    assert modello.ricevuti[1][-1] == messaggi[2]
    log = (tmp_path / "a.log").read_text(encoding="utf-8")
    assert "passaggio=1 strumento=orologio" in log
    assert "Asia/Tokyo" in log


def test_limite_raggiunto(tmp_path):
    esito = avvia_fino_al_limite(tmp_path)

    messaggi = esito["messaggi"]
    assert messaggi[-1].content == MESSAGGIO_LIMITE
    assert esito["chiamate_strumento"] == 5
    risultati = {m.tool_call_id: m.content for m in messaggi if isinstance(m, ToolMessage)}
    richieste = [c["id"] for m in messaggi if isinstance(m, AIMessage) for c in m.tool_calls]
    assert sorted(richieste) == sorted(risultati)
    assert risultati["6"] == "non eseguita: limite raggiunto"
    assert "limite raggiunto" in (tmp_path / "a.log").read_text(encoding="utf-8")


def test_domanda_dopo_il_limite(tmp_path):
    cronologia = avvia_fino_al_limite(tmp_path)["messaggi"]
    modello = ModelloFinto([AIMessage("ok")])

    esito = grafo_con_orologio(modello, tmp_path).invoke(
        {"messaggi": cronologia + [HumanMessage("ciao")], "chiamate_strumento": 0}
    )

    assert esito["messaggi"][-1].content == "ok"


def test_strumento_sconosciuto(tmp_path):
    modello = ModelloFinto(
        [AIMessage("", tool_calls=[chiamata("1", args={}, nome="meteo")]), AIMessage("niente")]
    )

    esito = grafo_con_orologio(modello, tmp_path).invoke(
        {"messaggi": [HumanMessage("che tempo fa?")], "chiamate_strumento": 0}
    )

    risultato = next(m for m in esito["messaggi"] if isinstance(m, ToolMessage))
    assert risultato.content == "Errore: strumento sconosciuto 'meteo'."
