import pytest

from assistente.conferma import crea_conferma_eliminazione


def conferma_con(risposta, testo="meeting giovedì 4 alle 10"):
    """Conferma con input simulato; restituisce (funzione, domande poste, ID cercati)."""
    domande, cercati = [], []

    def leggi(domanda):
        domande.append(domanda)
        if isinstance(risposta, BaseException):
            raise risposta
        return risposta

    def trova_testo(note_id):
        cercati.append(note_id)
        return testo

    return crea_conferma_eliminazione(trova_testo, leggi=leggi), domande, cercati


@pytest.mark.parametrize("risposta", ["s", " Sì ", "SI", "si"])
def test_risposte_affermative(risposta):
    conferma, _, _ = conferma_con(risposta)
    assert conferma({"note_id": 3}) is True


@pytest.mark.parametrize("risposta", ["n", "", "no", "forse"])
def test_altre_risposte_annullano(risposta):
    conferma, _, _ = conferma_con(risposta)
    assert conferma({"note_id": 3}) is False


def test_domanda_mostra_il_testo():
    conferma, domande, _ = conferma_con("n")
    conferma({"note_id": 3})
    assert domande == ["Eliminare la nota 3: «meeting giovedì 4 alle 10»? (s/n) "]


def test_domanda_senza_testo_se_non_trovato():
    conferma, domande, _ = conferma_con("n", testo=None)
    conferma({"note_id": 99})
    assert domande == ["Eliminare la nota 99? (s/n) "]


def test_id_come_stringa():
    conferma, domande, cercati = conferma_con("s")
    assert conferma({"note_id": "3"}) is True
    assert cercati == [3]
    assert domande[0].startswith("Eliminare la nota 3:")


def test_fine_input_vale_no():
    conferma, _, _ = conferma_con(EOFError())
    assert conferma({"note_id": 3}) is False


def test_ctrl_c_non_intercettato():
    conferma, _, _ = conferma_con(KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        conferma({"note_id": 3})


@pytest.mark.parametrize("note_id", ["tre", "1.0", 1.0, True, " 3", "", None, "٣"])
def test_id_non_intero_annulla_senza_chiedere(note_id):
    # Mai True senza domanda: un ID che non è un intero non elimina nulla.
    conferma, domande, cercati = conferma_con("s")
    assert conferma({"note_id": note_id}) is False
    assert domande == [] and cercati == []


def test_id_mancante_annulla():
    conferma, domande, _ = conferma_con("s")
    assert conferma({}) is False
    assert domande == []
