import threading
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool, ToolException

from assistente.grafo import MESSAGGIO_ANNULLATA, MESSAGGIO_LIMITE, costruisci_grafo, instrada
from assistente.registro import configura_registro
from assistente.strumenti import ErroreCollegamento, crea_orologio
from tests.finti import ModelloFinto, RouterFinto

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
        router=RouterFinto(),
    )


def avvia_fino_al_limite(tmp_path):
    richieste = [AIMessage("", tool_calls=[chiamata(str(i))]) for i in range(1, 7)]
    grafo = grafo_con_orologio(ModelloFinto(richieste), tmp_path, limite=5)
    return grafo.invoke({"messaggi": [HumanMessage("che ore sono?")], "chiamate_strumento": 0})


def test_grafo_risponde_con_il_modello():
    modello = ModelloFinto([AIMessage("ciao")])

    esito = costruisci_grafo(modello, router=RouterFinto()).invoke(
        {"messaggi": [HumanMessage("salve")], "chiamate_strumento": 0}
    )

    assert [m.content for m in esito["messaggi"]] == ["salve", "ciao"]


def test_istruzioni_inviate_ma_non_salvate():
    modello = ModelloFinto([AIMessage("ciao")])

    esito = costruisci_grafo(modello, istruzioni="ISTR", router=RouterFinto()).invoke(
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
    assert "passaggio=1 id=1 strumento=orologio" in log
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


def test_chiamata_malformata_riceve_risposta(tmp_path):
    # Argomenti non JSON: LangChain mette la chiamata in invalid_tool_calls.
    malformata = {"name": "orologio", "args": "{fuso", "id": "1", "error": None, "type": "invalid_tool_call"}
    modello = ModelloFinto([AIMessage("", invalid_tool_calls=[malformata]), AIMessage("ok")])

    esito = grafo_con_orologio(modello, tmp_path).invoke(
        {"messaggi": [HumanMessage("che ore sono?")], "chiamate_strumento": 0}
    )

    risultato = next(m for m in esito["messaggi"] if isinstance(m, ToolMessage))
    assert risultato.tool_call_id == "1"
    assert risultato.content.startswith("Errore: argomenti non validi")
    assert esito["messaggi"][-1].content == "ok"


# --- Strumenti esterni: errori distinti, conferma, log correlato -----------------


def finto_delete_note(esito=None):
    """`delete_note` finto: registra gli argomenti ricevuti; `esito` può essere un'eccezione."""
    ricevuti = []

    def delete_note(note_id: int) -> str:
        ricevuti.append({"note_id": note_id})
        if isinstance(esito, BaseException):
            raise esito
        return f"eliminata {note_id}"

    strumento = StructuredTool.from_function(delete_note, description="Elimina una nota.")
    return strumento, ricevuti


def elimina(id, note_id=3):
    return chiamata(id, args={"note_id": note_id}, nome="delete_note")


def grafo_con_note(modello, tmp_path, strumento, conferme={}):
    return costruisci_grafo(
        modello,
        strumenti=[crea_orologio("Europe/Rome", adesso=lambda: ISTANTE), strumento],
        conferme=conferme,
        registro=configura_registro(tmp_path / "a.log"),
        router=RouterFinto(),
    )


def esegui(grafo, domanda="cancella la nota"):
    return grafo.invoke({"messaggi": [HumanMessage(domanda)], "chiamate_strumento": 0})


def risultati(esito):
    return {m.tool_call_id: m.content for m in esito["messaggi"] if isinstance(m, ToolMessage)}


def log(tmp_path):
    return (tmp_path / "a.log").read_text(encoding="utf-8")


def test_errore_strumento_distinto(tmp_path):
    strumento, _ = finto_delete_note(ToolException("Nessuna nota con ID 99."))
    modello = ModelloFinto([AIMessage("", tool_calls=[elimina("1", 99)]), AIMessage("non esiste")])

    esito = esegui(grafo_con_note(modello, tmp_path, strumento))

    assert risultati(esito) == {"1": "Errore dello strumento: Nessuna nota con ID 99."}
    assert "esito=errore_strumento" in log(tmp_path)


def test_errore_collegamento_distinto(tmp_path):
    strumento, _ = finto_delete_note(ErroreCollegamento("server chiuso"))
    modello = ModelloFinto([AIMessage("", tool_calls=[elimina("1")]), AIMessage("non riesco")])

    esito = esegui(grafo_con_note(modello, tmp_path, strumento))

    assert risultati(esito) == {"1": "Errore di collegamento: server chiuso"}
    assert "esito=errore_collegamento" in log(tmp_path)


def test_conferma_si_esegue(tmp_path):
    strumento, ricevuti = finto_delete_note()
    modello = ModelloFinto([AIMessage("", tool_calls=[elimina("1")]), AIMessage("fatto")])
    chieste = []

    def conferma(argomenti):
        chieste.append(argomenti)
        return True

    esito = esegui(grafo_con_note(modello, tmp_path, strumento, {"delete_note": conferma}))

    assert chieste == [{"note_id": 3}]
    assert ricevuti == [{"note_id": 3}]
    assert risultati(esito) == {"1": "eliminata 3"}
    assert "conferma=si" in log(tmp_path) and "esito=ok" in log(tmp_path)


def test_conferma_no_non_esegue(tmp_path):
    strumento, ricevuti = finto_delete_note()
    modello = ModelloFinto([AIMessage("", tool_calls=[elimina("1")]), AIMessage("annullata")])

    esito = esegui(grafo_con_note(modello, tmp_path, strumento, {"delete_note": lambda a: False}))

    assert ricevuti == []
    assert risultati(esito) == {"1": MESSAGGIO_ANNULLATA}
    assert "esito=annullata" in log(tmp_path) and "conferma=no" in log(tmp_path)
    assert esito["messaggi"][-1].content == "annullata"


def test_due_eliminazioni_due_conferme(tmp_path):
    strumento, ricevuti = finto_delete_note()
    modello = ModelloFinto(
        [AIMessage("", tool_calls=[elimina("a", 1), elimina("b", 2)]), AIMessage("ok")]
    )
    risposte = iter([True, False])

    esito = esegui(
        grafo_con_note(modello, tmp_path, strumento, {"delete_note": lambda a: next(risposte)})
    )

    assert ricevuti == [{"note_id": 1}]
    assert risultati(esito) == {"a": "eliminata 1", "b": MESSAGGIO_ANNULLATA}


def test_log_contiene_tool_call_id(tmp_path):
    modello = ModelloFinto([AIMessage("", tool_calls=[chiamata("1")]), AIMessage("ok")])

    esegui(grafo_con_orologio(modello, tmp_path), "che ore sono a Tokyo?")

    assert "id=1 strumento=orologio" in log(tmp_path)
    assert "esito=ok" in log(tmp_path)


def test_orologio_funziona_con_note_scollegate(tmp_path):
    strumento, _ = finto_delete_note(ErroreCollegamento("server chiuso"))
    modello = ModelloFinto(
        [AIMessage("", tool_calls=[elimina("1"), chiamata("2")]), AIMessage("ok")]
    )

    esito = esegui(grafo_con_note(modello, tmp_path, strumento))

    assert risultati(esito)["1"] == "Errore di collegamento: server chiuso"
    assert risultati(esito)["2"].startswith("2026-10-26 23:00:00 Asia/Tokyo")


def test_nodo_modello_scrive_testo_a_pezzi():
    grafo = costruisci_grafo(ModelloFinto([AIMessage("uno due tre")]), router=RouterFinto())

    eventi = list(
        grafo.stream(
            {"messaggi": [HumanMessage("ciao")], "chiamate_strumento": 0}, stream_mode="custom"
        )
    )

    assert len(eventi) > 1
    assert all(e["tipo"] == "testo" for e in eventi)
    assert "".join(e["testo"] for e in eventi) == "uno due tre"


def test_stream_conserva_chiamate_a_strumenti(tmp_path):
    modello = ModelloFinto(
        [AIMessage("Ora calcolo", tool_calls=[chiamata("1")]), AIMessage("ok")]
    )

    esito = grafo_con_orologio(modello, tmp_path).invoke(
        {"messaggi": [HumanMessage("che ore sono?")], "chiamate_strumento": 0}
    )

    risposta = esito["messaggi"][1]
    assert risposta.content == "Ora calcolo"
    assert risposta.tool_calls == [chiamata("1")]


def test_stream_conserva_chiamate_non_leggibili(tmp_path):
    malformata = {"name": "orologio", "args": "{non json", "id": "1", "error": "x"}
    modello = ModelloFinto([AIMessage("", invalid_tool_calls=[malformata]), AIMessage("ok")])

    esito = grafo_con_orologio(modello, tmp_path).invoke(
        {"messaggi": [HumanMessage("che ore sono?")], "chiamate_strumento": 0}
    )

    assert isinstance(esito["messaggi"][2], ToolMessage)
    assert esito["messaggi"][2].tool_call_id == "1"
    assert esito["messaggi"][-1].content == "ok"


def test_stream_risposta_vuota():
    grafo = costruisci_grafo(ModelloFinto([AIMessage(""), AIMessage("")]), router=RouterFinto())
    stato = {"messaggi": [HumanMessage("ciao")], "chiamate_strumento": 0}

    assert list(grafo.stream(stato, stream_mode="custom")) == []
    assert grafo.invoke(stato)["messaggi"][-1].content == ""


def eventi_di(grafo, domanda="ciao"):
    """Gli eventi custom del grafo per una domanda, nell'ordine in cui arrivano."""
    stato = {"messaggi": [HumanMessage(domanda)], "chiamate_strumento": 0}
    return list(grafo.stream(stato, stream_mode="custom"))


def test_evento_strumento_prima_del_risultato(tmp_path):
    modello = ModelloFinto([AIMessage("", tool_calls=[chiamata("1")]), AIMessage("fatto")])

    eventi = eventi_di(grafo_con_orologio(modello, tmp_path), "che ore sono?")

    assert eventi[0] == {"tipo": "strumento", "nome": "orologio"}
    assert [e["tipo"] for e in eventi[1:]] == ["testo"] * (len(eventi) - 1)
    assert len(eventi) > 1


def test_due_strumenti_due_eventi(tmp_path):
    strumento, _ = finto_delete_note()
    richieste = [chiamata("1"), elimina("2")]
    modello = ModelloFinto([AIMessage("", tool_calls=richieste), AIMessage("ok")])

    eventi = eventi_di(grafo_con_note(modello, tmp_path, strumento))

    nomi = [e["nome"] for e in eventi if e["tipo"] == "strumento"]
    assert nomi == ["orologio", "delete_note"]


def test_evento_per_chiamata_non_leggibile(tmp_path):
    malformata = {"name": "orologio", "args": "{fuso", "id": "1", "error": None}
    modello = ModelloFinto([AIMessage("", invalid_tool_calls=[malformata]), AIMessage("ok")])

    eventi = eventi_di(grafo_con_orologio(modello, tmp_path))

    assert {"tipo": "strumento", "nome": "orologio"} in eventi


def test_evento_strumento_arriva_mentre_la_conferma_e_in_attesa(tmp_path):
    # La conferma blocca il nodo (nel terminale è un input()): l'evento dello strumento
    # deve già essere arrivato a chi legge il flusso, non restare indietro fino alla fine.
    strumento, ricevuti = finto_delete_note()
    modello = ModelloFinto([AIMessage("", tool_calls=[elimina("1")]), AIMessage("annullata")])
    arrivato = threading.Event()
    visto_durante_la_conferma = []

    def conferma(argomenti):
        visto_durante_la_conferma.append(arrivato.wait(timeout=5))
        return False

    grafo = grafo_con_note(modello, tmp_path, strumento, {"delete_note": conferma})
    stato = {"messaggi": [HumanMessage("cancella")], "chiamate_strumento": 0}
    for evento in grafo.stream(stato, stream_mode="custom"):
        if evento == {"tipo": "strumento", "nome": "delete_note"}:
            arrivato.set()

    assert visto_durante_la_conferma == [True]
    assert ricevuti == []


def test_limite_scrive_testo_e_nessuno_strumento(tmp_path):
    richieste = [AIMessage("", tool_calls=[chiamata(str(i))]) for i in range(1, 7)]
    grafo = grafo_con_orologio(ModelloFinto(richieste), tmp_path, limite=5)

    eventi = eventi_di(grafo, "che ore sono?")

    assert eventi[-1] == {"tipo": "testo", "testo": MESSAGGIO_LIMITE, "nuovo_tratto": True}
    assert len([e for e in eventi if e["tipo"] == "strumento"]) == 5
