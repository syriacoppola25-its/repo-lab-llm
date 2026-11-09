"""Valutatore aritmetico della calcolatrice: solo operazioni ammesse, rifiuti espliciti."""

import ast
import re
import time
from pathlib import Path

import pytest

import server_calcolatrice.valutatore as modulo
from server_calcolatrice.valutatore import ErroreEspressione, formatta, valuta


@pytest.mark.parametrize(
    "espressione, atteso",
    [
        ("2 + 3", 5),
        ("10 - 4", 6),
        ("6 * 7", 42),
        ("7 / 2", 3.5),
        ("7 // 2", 3),
        ("7 % 3", 1),
        ("2 ** 10", 1024),
        ("2 + 3 * 4", 14),
        ("(2 + 3) * 4", 20),
        ("-3 + 1", -2),
        ("-(2 + 1)", -3),
        ("+5", 5),
        ("12.5 * 2", 25.0),
        (".5 + 5.", 5.5),
        ("-7 // 2", -4),
        ("2 ** -1", 0.5),
        ("2 ** 0.5", 2**0.5),
        ("  2+2  ", 4),
    ],
)
def test_operazioni_ammesse(espressione, atteso):
    assert valuta(espressione) == atteso


@pytest.mark.parametrize(
    "espressione, frammento",
    [
        ("", "espressione vuota"),
        ("   ", "espressione vuota"),
        ("1+" * 100 + "1", "troppo lunga"),
        ("2 +", "sintassi non valida"),
        ("12,5", "virgola non ammessa"),
        ("x + 1", "nome 'x'"),
        ("pi", "nome 'pi'"),
        ("sqrt(4)", "chiamata di funzione"),
        ("__import__('os')", "chiamata di funzione"),
        ("(1).real", "attributo"),
        ("[1][0]", "indice"),
        ("2 < 3", "confronto"),
        ("1 and 2", "operatore logico"),
        ("not 1", "operatore logico"),
        ("1 << 2", "operatore '<<'"),
        ("~1", "operatore '~'"),
        ("[1, 2]", "elenco"),
        ("'ab'", "testo"),
        ("True", "valore 'True'"),
        ("None", "valore 'None'"),
        ("1e5", "notazione numerica non ammessa: '1e5'"),
        ("1_000", "notazione numerica"),
        ("0x10", "notazione numerica"),
        ("0b1", "notazione numerica"),
        ("1j", "notazione numerica"),
        ("10 / 0", "divisione per zero"),
        ("10 // 0", "divisione per zero"),
        ("10 % 0", "divisione per zero"),
        ("0 ** -1", "divisione per zero"),
        ("0.0 ** -1", "divisione per zero"),
        ("2 ** 101", "esponente troppo grande"),
        ("9 ** 9 ** 9", "esponente troppo grande"),
        ("(10 ** 49) ** 100", "risultato troppo grande"),
        ("10 ** 50", "risultato troppo grande"),
        ("1" + "0" * 50, "risultato troppo grande"),
        ("10.0 ** 30 * 10.0 ** 30", "risultato troppo grande"),
        ("(-8) ** 0.5", "risultato non reale"),
    ],
)
def test_rifiuti_espliciti(espressione, frammento):
    with pytest.raises(ErroreEspressione, match=re.escape(frammento)):
        valuta(espressione)


def test_limite_esponente_rifiuta_prima_di_calcolare():
    inizio = time.perf_counter()
    with pytest.raises(ErroreEspressione):
        valuta("9 ** 9 ** 9")
    assert time.perf_counter() - inizio < 1


def test_espressione_esattamente_200_caratteri_ammessa():
    espressione = "1+" * 99 + "11"
    assert len(espressione) == 200
    assert valuta(espressione) == 110


def test_niente_eval():
    # Cerca le chiamate dirette alle funzioni predefinite (re.compile è ammesso).
    albero = ast.parse(Path(modulo.__file__).read_text(encoding="utf-8"))
    chiamate = {
        n.func.id for n in ast.walk(albero) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert not chiamate & {"eval", "exec", "compile", "__import__"}


def test_formatta():
    assert formatta(1.0) == 1 and type(formatta(1.0)) is int
    assert formatta(0.1 + 0.2) == 0.3
    assert formatta(7) == 7
    assert formatta(2 / 3) == 0.666666666667
