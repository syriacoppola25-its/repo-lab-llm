from langchain_core.messages import AIMessage

from assistente.grafo import costruisci_grafo
from assistente.terminale import PENSANDO, SALUTO, esegui_sessione
from tests.finti import ModelloFinto


def avvia(righe, risposte=()):
    """Esegue una sessione con input simulato; restituisce (uscite, modello)."""
    modello = ModelloFinto(list(risposte))
    da_leggere = list(righe)
    uscite: list[str] = []

    def leggi(_prompt: str) -> str:
        riga = da_leggere.pop(0)
        if isinstance(riga, BaseException):
            raise riga
        return riga

    esegui_sessione(costruisci_grafo(modello), leggi=leggi, scrivi=uscite.append)
    return uscite, modello


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
    assert uscite.index(PENSANDO) < uscite.index("Assistente: salve")
