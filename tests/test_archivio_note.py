from datetime import datetime, timezone

import pytest

from server_note.archivio import ArchivioNote, ErroreNote

ISTANTE = datetime(2026, 11, 9, 9, 30, tzinfo=timezone.utc)  # 10:30 a Roma


def archivio(percorso):
    return ArchivioNote(percorso, "Europe/Rome", adesso=lambda: ISTANTE)


@pytest.fixture
def note(tmp_path):
    return archivio(tmp_path / "note.db")


def test_aggiungi_restituisce_id_data_e_testo(note):
    assert note.aggiungi("meeting giovedì 4 alle 10") == {
        "id": 1,
        "creata": "2026-11-09 10:30",
        "testo": "meeting giovedì 4 alle 10",
    }


def test_testo_ripulito_dagli_spazi_ai_lati(note):
    assert note.aggiungi("  ciao  ")["testo"] == "ciao"


def test_testo_vuoto_rifiutato(note):
    with pytest.raises(ErroreNote, match="vuoto"):
        note.aggiungi("   ")
    assert note.elenca()["totale"] == 0


def test_testo_troppo_lungo_rifiutato(note):
    with pytest.raises(ErroreNote, match="500"):
        note.aggiungi("x" * 501)
    assert note.aggiungi("x" * 500)["id"] == 1


def test_testo_speciale_identico(note):
    testo = "l'esame d'inglese; DROP TABLE note \"ok\" — è"
    note.aggiungi(testo)
    assert note.elenca()["note"][0]["testo"] == testo


def test_elenca_ordine_e_limite(note):
    for testo in ("uno", "due", "tre"):
        note.aggiungi(testo)
    elenco = note.elenca(2)
    assert [n["id"] for n in elenco["note"]] == [1, 2]
    assert elenco["totale"] == 3


def test_elenca_vuoto(note):
    assert note.elenca() == {"note": [], "totale": 0}


@pytest.mark.parametrize("limite", [0, 101])
def test_limite_fuori_intervallo(note, limite):
    with pytest.raises(ErroreNote, match=r"1 e 100"):
        note.elenca(limite)


def test_elimina_restituisce_la_nota(note):
    nota = note.aggiungi("report venerdì")
    assert note.elimina(1) == {"eliminata": nota}
    assert note.elenca()["totale"] == 0


def test_elimina_id_inesistente_senza_effetti(note):
    note.aggiungi("resta")
    with pytest.raises(ErroreNote, match="99"):
        note.elimina(99)
    assert note.elenca()["totale"] == 1


def test_id_non_riutilizzato(note):
    note.aggiungi("prima")
    note.elimina(1)
    assert note.aggiungi("seconda")["id"] == 2


def test_note_persistono_riaprendo(tmp_path):
    archivio(tmp_path / "note.db").aggiungi("da ricordare")
    riaperto = archivio(tmp_path / "note.db")
    assert [n["testo"] for n in riaperto.elenca()["note"]] == ["da ricordare"]


def test_cartella_creata_se_manca(tmp_path):
    note = archivio(tmp_path / "a" / "b" / "note.db")
    assert note.aggiungi("ciao")["id"] == 1


def test_archivio_non_accessibile(tmp_path):
    cartella = tmp_path / "sono_una_cartella"
    cartella.mkdir()
    with pytest.raises(ErroreNote, match="non accessibile"):
        archivio(cartella).elenca()
