from datetime import datetime, timezone

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from assistente.grafo import MESSAGGIO_LIMITE, costruisci_grafo
from assistente.strumenti import crea_orologio
from assistente.terminale import PENSANDO, PREFISSO_RISPOSTA, SALUTO, esegui_sessione
from tests.finti import ModelloFinto

ISTANTE = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)
CHIAMATA = {
    "name": "orologio",
    "args": {"fuso_orario": "Asia/Tokyo"},
    "id": "1",
    "type": "tool_call",
}


class ModelloACopione:
    """Ogni risposta è una lista di pezzi di testo, o di eccezioni da sollevare a quel punto."""

    def __init__(self, copioni):
        self.copioni = list(copioni)
        self.ricevuti = []

    def stream(self, messaggi):
        self.ricevuti.append(list(messaggi))
        for voce in self.copioni.pop(0):
            if isinstance(voce, BaseException):
                raise voce
            yield AIMessageChunk(voce)


def avvia(righe, risposte=(), modello=None, **grafo):
    """Esegue una sessione con input simulato; restituisce (righe di uscita, modello).

    L'uscita di `scrivi` (con a capo) e quella di `scrivi_pezzo` (senza) viene
    ricomposta nell'ordine in cui è comparsa, poi divisa in righe.
    """
    modello = modello or ModelloFinto(list(risposte))
    da_leggere = list(righe)
    uscita: list[str] = []

    def leggi(_prompt: str) -> str:
        riga = da_leggere.pop(0)
        if isinstance(riga, BaseException):
            raise riga
        return riga

    esegui_sessione(
        costruisci_grafo(modello, **grafo),
        leggi=leggi,
        scrivi=lambda testo: uscita.append(testo + "\n"),
        scrivi_pezzo=uscita.append,
    )
    return "".join(uscita).rstrip("\n").split("\n"), modello


def con_orologio():
    return {"strumenti": [crea_orologio("Europe/Rome", adesso=lambda: ISTANTE)]}


def test_righe_vuote_ignorate():
    _, modello = avvia(["", "   ", "esci"])
    assert modello.ricevuti == []


def test_esci_senza_distinzione_maiuscole():
    uscite, _ = avvia([" ESCI "])
    assert uscite[-1] == SALUTO


def test_ctrl_c_esce_con_saluto():
    uscite, _ = avvia([KeyboardInterrupt()])
    assert uscite[-1] == SALUTO


def test_fine_input_esce_con_saluto():
    uscite, _ = avvia([EOFError()])
    assert uscite[-1] == SALUTO


def test_ctrl_c_durante_attesa():
    uscite, _ = avvia(["ciao"], [KeyboardInterrupt()])
    assert uscite[-1] == SALUTO


def test_mostra_pensando_e_risposta():
    uscite, _ = avvia(["ciao", "esci"], [AIMessage("salve")])
    assert uscite.index(PENSANDO) < uscite.index(PREFISSO_RISPOSTA + "salve")


def test_cronologia_conservata():
    _, modello = avvia(
        ["mi chiamo Ada", "come mi chiamo?", "esci"],
        [AIMessage("piacere, Ada"), AIMessage("ti chiami Ada")],
    )
    assert [m.content for m in modello.ricevuti[1]] == [
        "mi chiamo Ada",
        "piacere, Ada",
        "come mi chiamo?",
    ]


def test_errore_modello_non_interrompe():
    uscite, modello = avvia(["a", "b", "esci"], [ConnectionError(), AIMessage("ok")])
    errore = next(u for u in uscite if u.startswith("Errore:"))
    assert (
        "Errore: impossibile ottenere una risposta dal modello (ConnectionError)" in errore
    )
    assert uscite.index(errore) < uscite.index(PREFISSO_RISPOSTA + "ok")
    assert [m.content for m in modello.ricevuti[1]] == ["b"]


def test_testo_a_pezzi_con_prefisso_una_volta():
    pezzi = []
    righe = iter(["ciao", "esci"])
    esegui_sessione(
        costruisci_grafo(ModelloFinto([AIMessage("uno due tre")])),
        leggi=lambda _prompt: next(righe),
        scrivi=lambda testo: None,
        scrivi_pezzo=pezzi.append,
    )

    assert len(pezzi) > 2
    assert pezzi.count(PREFISSO_RISPOSTA) == 1
    assert "".join(pezzi) == PREFISSO_RISPOSTA + "uno due tre\n"


def test_riga_strumento_su_riga_sua():
    uscite, _ = avvia(
        ["che ore sono?", "esci"],
        [AIMessage("", tool_calls=[CHIAMATA]), AIMessage("sono le 23")],
        **con_orologio(),
    )

    assert uscite[1:4] == [
        "Interrogando lo strumento orologio…",
        PREFISSO_RISPOSTA + "sono le 23",
        SALUTO,
    ]


def test_testo_prima_dello_strumento_e_dopo():
    uscite, _ = avvia(
        ["che ore sono?", "esci"],
        [AIMessage("Ora guardo", tool_calls=[CHIAMATA]), AIMessage("sono le 23")],
        **con_orologio(),
    )

    assert uscite == [
        PENSANDO,
        PREFISSO_RISPOSTA + "Ora guardo",
        "Interrogando lo strumento orologio…",
        PREFISSO_RISPOSTA + "sono le 23",
        SALUTO,
    ]


def test_risposta_vuota_nessun_prefisso():
    uscite, _ = avvia(["ciao", "esci"], [AIMessage("")])

    assert uscite == [PENSANDO, SALUTO]


def test_errore_a_meta_risposta():
    modello = ModelloACopione([["uno ", "due ", ConnectionError()], ["ok"]])

    uscite, _ = avvia(["a", "b", "esci"], modello=modello)

    errore = (
        "Errore: impossibile ottenere una risposta dal modello (ConnectionError). "
        "Controlla che LM Studio sia avviato."
    )
    assert uscite[:3] == [PENSANDO, PREFISSO_RISPOSTA + "uno due ", errore]
    assert [m.content for m in modello.ricevuti[1]] == ["b"]


def test_errore_dopo_uno_strumento_non_cambia_la_cronologia():
    modello = ModelloFinto(
        [AIMessage("", tool_calls=[CHIAMATA]), ConnectionError(), AIMessage("ok")]
    )

    uscite, _ = avvia(["a", "b", "esci"], modello=modello, **con_orologio())

    assert "Interrogando lo strumento orologio…" in uscite
    assert [m.content for m in modello.ricevuti[2]] == ["b"]


def test_messaggio_del_limite_come_risposta_normale():
    risposte = [AIMessage("", tool_calls=[CHIAMATA]), AIMessage("", tool_calls=[CHIAMATA])]

    uscite, _ = avvia(["che ore sono?", "esci"], risposte, limite=1, **con_orologio())

    assert uscite[-2:] == [PREFISSO_RISPOSTA + MESSAGGIO_LIMITE, SALUTO]
