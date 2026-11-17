from datetime import datetime, timezone

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from assistente import flusso
from assistente.grafo import costruisci_grafo
from assistente.registro import configura_registro
from assistente.router import (
    MESSAGGIO_RIFIUTO,
    MESSAGGIO_RIFORMULA,
    istruzioni_router,
    messaggi_per_router,
)
from assistente.strumenti import crea_orologio
from tests.finti import ModelloFinto, RouterFinto, decisione, illeggibile

ISTANTE = datetime(2026, 11, 17, 14, 0, tzinfo=timezone.utc)


def grafo(agente, router, tmp_path):
    return costruisci_grafo(
        agente,
        strumenti=[crea_orologio("Europe/Rome", adesso=lambda: ISTANTE)],
        registro=configura_registro(tmp_path / "a.log"),
        router=router,
    )


def chiedi(agente, router, tmp_path, domanda="domanda", cronologia=()):
    return grafo(agente, router, tmp_path).invoke(
        {"messaggi": [*cronologia, HumanMessage(domanda)], "chiamate_strumento": 0}
    )


def log(tmp_path):
    return (tmp_path / "a.log").read_text(encoding="utf-8")


def test_in_ambito_passa_all_agente(tmp_path):
    router = RouterFinto([decisione("conversazione", "mail di lavoro")])

    esito = chiedi(ModelloFinto([AIMessage("Ecco la mail.")]), router, tmp_path)

    assert esito["messaggi"][-1].content == "Ecco la mail."
    testo = log(tmp_path)
    assert "router categoria=conversazione motivo=mail di lavoro prossimo=agente" in testo
    assert "nodo=agente" in testo


def test_fuori_ambito_rifiuta_senza_agente(tmp_path):
    agente = ModelloFinto([])
    router = RouterFinto([decisione("fuori_ambito", "parla di sport")])

    esito = chiedi(agente, router, tmp_path)

    assert esito["messaggi"][-1].content == MESSAGGIO_RIFIUTO
    assert agente.ricevuti == []
    testo = log(tmp_path)
    assert "router categoria=fuori_ambito motivo=parla di sport prossimo=rifiuto" in testo
    assert "nodo=agente" not in testo


def test_illeggibile_chiede_di_riformulare(tmp_path):
    agente = ModelloFinto([])

    esito = chiedi(agente, RouterFinto([illeggibile("boh")]), tmp_path)

    assert esito["messaggi"][-1].content == MESSAGGIO_RIFORMULA
    assert agente.ricevuti == []
    testo = log(tmp_path)
    assert "WARNING" in testo and "risposta=boh prossimo=riformula" in testo
    assert "nodo=agente" not in testo


def test_warning_accorcia_la_risposta(tmp_path):
    chiedi(ModelloFinto([]), RouterFinto([illeggibile("x" * 500)]), tmp_path)

    testo = log(tmp_path)
    assert "x" * 200 in testo and "x" * 201 not in testo


def test_rifiuto_in_cronologia(tmp_path):
    router = RouterFinto([decisione("fuori_ambito")])

    esito = chiedi(ModelloFinto([]), router, tmp_path, "chi ha vinto ieri?")

    assert [type(m) for m in esito["messaggi"]] == [HumanMessage, AIMessage]
    assert [m.content for m in esito["messaggi"]] == ["chi ha vinto ieri?", MESSAGGIO_RIFIUTO]


def test_dopo_il_rifiuto_l_agente_vede_la_cronologia(tmp_path):
    primo = chiedi(ModelloFinto([]), RouterFinto([decisione("fuori_ambito")]), tmp_path, "gossip?")
    agente = ModelloFinto([AIMessage("Ecco la mail.")])

    chiedi(agente, RouterFinto(), tmp_path, "scrivi una mail", primo["messaggi"])

    contenuti = [m.content for m in agente.ricevuti[0]]
    assert contenuti == ["gossip?", MESSAGGIO_RIFIUTO, "scrivi una mail"]


def test_router_una_volta_per_domanda(tmp_path):
    router = RouterFinto()
    agente = ModelloFinto(
        [
            AIMessage(
                "",
                tool_calls=[
                    {"name": "orologio", "args": {"fuso_orario": "Europe/Rome"}, "id": "1", "type": "tool_call"}
                ],
            ),
            AIMessage("Sono le 15."),
        ]
    )

    chiedi(agente, router, tmp_path, "che ore sono?")

    assert len(router.ricevuti) == 1
    assert log(tmp_path).count("nodo=agente") == 2


def test_router_vede_la_cronologia(tmp_path):
    router = RouterFinto()
    cronologia = [HumanMessage("che ore sono?"), AIMessage("Sono le 15.")]

    chiedi(ModelloFinto([AIMessage("Sono le 23.")]), router, tmp_path, "e a Tokyo?", cronologia)

    ricevuti = router.ricevuti[0]
    assert ricevuti[0] == SystemMessage(istruzioni_router())
    attesi = messaggi_per_router([*cronologia, HumanMessage("e a Tokyo?")])
    assert [m.content for m in ricevuti[1:]] == [m.content for m in attesi]


def test_errore_del_router_si_propaga(tmp_path):
    with pytest.raises(ConnectionError):
        chiedi(ModelloFinto([]), RouterFinto([ConnectionError("giù")]), tmp_path)


def test_rifiuto_esce_in_streaming(tmp_path):
    g = grafo(ModelloFinto([]), RouterFinto([decisione("fuori_ambito")]), tmp_path)

    eventi = list(flusso.risposta_in_streaming(g, [HumanMessage("chi ha vinto ieri?")]))

    assert eventi[0] == flusso.Testo(MESSAGGIO_RIFIUTO)
    assert isinstance(eventi[-1], flusso.Fine) and len(eventi) == 2
