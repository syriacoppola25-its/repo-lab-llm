import threading
from datetime import datetime, timezone

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from assistente import flusso
from assistente.grafo import costruisci_grafo
from assistente.strumenti import crea_orologio
from tests.finti import ModelloFinto

ISTANTE = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)
CHIAMATA = {
    "name": "orologio",
    "args": {"fuso_orario": "Asia/Tokyo"},
    "id": "1",
    "type": "tool_call",
}


def grafo_con(modello):
    return costruisci_grafo(
        modello, strumenti=[crea_orologio("Europe/Rome", adesso=lambda: ISTANTE)]
    )


def test_risposta_semplice():
    domanda = [HumanMessage("ciao")]

    eventi = list(flusso.risposta_in_streaming(grafo_con(ModelloFinto([AIMessage("uno due tre")])), domanda))

    *pezzi, fine = eventi
    assert len(pezzi) > 1 and all(isinstance(e, flusso.Testo) for e in pezzi)
    assert "".join(e.testo for e in pezzi) == "uno due tre"
    assert isinstance(fine, flusso.Fine)
    assert fine.messaggi[0] == domanda[0]
    assert fine.messaggi[-1].content == "uno due tre"
    assert sum(isinstance(e, flusso.Fine) for e in eventi) == 1


def test_con_strumento():
    modello = ModelloFinto(
        [AIMessage("Ora guardo", tool_calls=[CHIAMATA]), AIMessage("A Tokyo sono le 23")]
    )

    eventi = list(flusso.risposta_in_streaming(grafo_con(modello), [HumanMessage("che ore sono?")]))

    tipi = [type(e).__name__ for e in eventi]
    assert tipi[0] == "Testo" and tipi[-1] == "Fine"
    posizione = tipi.index("Strumento")
    assert eventi[posizione] == flusso.Strumento("orologio")
    assert "".join(e.testo for e in eventi[:posizione]) == "Ora guardo"
    assert "".join(e.testo for e in eventi[posizione + 1 : -1]) == "A Tokyo sono le 23"


def test_fine_porta_la_cronologia_come_invoke():
    def scenario():
        return ModelloFinto([AIMessage("", tool_calls=[CHIAMATA]), AIMessage("fatto")])

    domanda = [HumanMessage("che ore sono?")]
    fine = list(flusso.risposta_in_streaming(grafo_con(scenario()), domanda))[-1]

    atteso = grafo_con(scenario()).invoke({"messaggi": domanda, "chiamate_strumento": 0})
    assert [(type(m), m.content) for m in fine.messaggi] == [
        (type(m), m.content) for m in atteso["messaggi"]
    ]


def test_streaming_vero():
    # Il modello produce il secondo pezzo solo dopo che chi legge ha ricevuto il primo:
    # con un flusso trattenuto fino alla fine l'attesa scadrebbe.
    primo_ricevuto = threading.Event()
    sbloccato = []

    class ModelloLento:
        def stream(self, messaggi):
            yield AIMessageChunk("uno ")
            sbloccato.append(primo_ricevuto.wait(timeout=5))
            yield AIMessageChunk("due")

    eventi = []
    for evento in flusso.risposta_in_streaming(costruisci_grafo(ModelloLento()), [HumanMessage("ciao")]):
        eventi.append(evento)
        primo_ricevuto.set()

    assert sbloccato == [True]
    assert eventi[0] == flusso.Testo("uno ")


def test_errore_si_propaga_senza_fine():
    risposta = flusso.risposta_in_streaming(
        grafo_con(ModelloFinto([ConnectionError()])), [HumanMessage("ciao")]
    )
    ricevuti = []

    with pytest.raises(ConnectionError):
        for evento in risposta:
            ricevuti.append(evento)

    assert not any(isinstance(e, flusso.Fine) for e in ricevuti)


def test_limite_e_un_nuovo_tratto_di_testo():
    richieste = [AIMessage("", tool_calls=[CHIAMATA]), AIMessage("Provo", tool_calls=[CHIAMATA])]
    grafo = costruisci_grafo(
        ModelloFinto(richieste),
        strumenti=[crea_orologio("Europe/Rome", adesso=lambda: ISTANTE)],
        limite=1,
    )

    eventi = list(flusso.risposta_in_streaming(grafo, [HumanMessage("che ore sono?")]))

    testi = [e for e in eventi if isinstance(e, flusso.Testo)]
    assert testi[-1].nuovo_tratto is True
    assert all(not t.nuovo_tratto for t in testi[:-1])
