from pathlib import Path

import pytest

from assistente.config import ConfigErrata, carica_config

VALIDA = {"LMSTUDIO_URL": "http://localhost:1234/v1", "LMSTUDIO_MODELLO": "google/gemma-4-e2b"}


def test_valori_obbligatori_e_predefiniti():
    c = carica_config(VALIDA)
    assert (c.url_server, c.modello) == ("http://localhost:1234/v1", "google/gemma-4-e2b")
    assert (c.fuso_predefinito, c.limite_chiamate, c.percorso_log) == (
        "Europe/Rome",
        5,
        Path("logs/assistente.log"),
    )


def test_percorso_note_predefinito():
    assert carica_config(VALIDA).percorso_note == Path("dati/note.db")


def test_percorso_note_da_variabile():
    assert carica_config({**VALIDA, "PERCORSO_NOTE": "x/n.db"}).percorso_note == Path("x/n.db")


def test_variabile_mancante():
    with pytest.raises(ConfigErrata, match="LMSTUDIO_URL"):
        carica_config({})


def test_segnaposto_non_sostituito():
    for variabile, segnaposto in [
        ("LMSTUDIO_MODELLO", "ID_NOME_MODELLO"),
        ("LMSTUDIO_URL", "URL_SERVER_LMSTUDIO"),
    ]:
        with pytest.raises(ConfigErrata, match=variabile):
            carica_config({**VALIDA, variabile: segnaposto})


def test_limite_non_valido():
    for valore in ["zero", "0", "-1"]:
        with pytest.raises(ConfigErrata, match="LIMITE_CHIAMATE_STRUMENTO"):
            carica_config({**VALIDA, "LIMITE_CHIAMATE_STRUMENTO": valore})


def test_fuso_predefinito_inesistente():
    with pytest.raises(ConfigErrata, match="FUSO_PREDEFINITO"):
        carica_config({**VALIDA, "FUSO_PREDEFINITO": "Europa/Roma"})
