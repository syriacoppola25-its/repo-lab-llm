"""Valutatore aritmetico sicuro: l'espressione non viene mai eseguita come codice.

Il testo viene analizzato con `ast` e si calcolano solo i nodi di un elenco
chiuso (numeri, operatori ammessi, parentesi). Ogni altro elemento è rifiutato
con un `ErroreEspressione` che dice che cosa non è ammesso.
"""

import ast
import math
import operator
import re

LUNGHEZZA_MASSIMA = 200
ESPONENTE_MASSIMO = 100
CIFRE_MASSIME = 50
VALORE_MASSIMO = 1e50

# Solo cifre con punto decimale facoltativo: 12, 12.5, .5, 5.
_NUMERO = re.compile(r"\d+(\.\d*)?|\.\d+")

_BINARI = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARI = {ast.UAdd: operator.pos, ast.USub: operator.neg}

# Operatori riconosciuti ma non ammessi: il messaggio mostra il simbolo.
_SIMBOLI = {
    ast.LShift: "<<",
    ast.RShift: ">>",
    ast.BitAnd: "&",
    ast.BitOr: "|",
    ast.BitXor: "^",
    ast.MatMult: "@",
    ast.Invert: "~",
}

_NON_AMMESSI = {
    ast.Call: "chiamata di funzione",
    ast.Attribute: "attributo",
    ast.Subscript: "indice",
    ast.Compare: "confronto",
    ast.BoolOp: "operatore logico",
    ast.List: "elenco",
    ast.Dict: "elenco",
    ast.Set: "elenco",
    ast.JoinedStr: "testo",
}


class ErroreEspressione(ValueError):
    """Espressione rifiutata; il messaggio è il testo mostrato al modello."""


def _non_ammesso(cosa: str) -> ErroreEspressione:
    return ErroreEspressione(f"elemento non ammesso: {cosa}")


def _controlla(valore):
    """Rifiuta valori complessi o oltre i limiti di grandezza."""
    if isinstance(valore, complex):
        raise ErroreEspressione("risultato non reale")
    if isinstance(valore, int):
        # Confronto numerico: str() di un intero enorme solleverebbe ValueError.
        if abs(valore) >= 10**CIFRE_MASSIME:
            raise ErroreEspressione("risultato troppo grande")
    elif not math.isfinite(valore) or abs(valore) > VALORE_MASSIMO:
        raise ErroreEspressione("risultato troppo grande")
    return valore


def _numero(nodo: ast.Constant, testo: str):
    valore = nodo.value
    if isinstance(valore, (str, bytes)):
        raise _non_ammesso("testo")
    if valore is None or valore is Ellipsis or isinstance(valore, bool):
        raise _non_ammesso(f"valore '{valore}'")
    scritto = ast.get_source_segment(testo, nodo) or ""
    if not _NUMERO.fullmatch(scritto):
        raise ErroreEspressione(f"notazione numerica non ammessa: '{scritto}'")
    return _controlla(valore)


def _calcola(funzione, *operandi):
    try:
        return _controlla(funzione(*operandi))
    except ZeroDivisionError:
        raise ErroreEspressione("divisione per zero") from None
    except OverflowError:
        raise ErroreEspressione("risultato troppo grande") from None


def _visita(nodo: ast.AST, testo: str):
    if isinstance(nodo, ast.Constant):
        return _numero(nodo, testo)
    if isinstance(nodo, ast.BinOp):
        tipo = type(nodo.op)
        if tipo not in _BINARI:
            raise _non_ammesso(f"operatore '{_SIMBOLI.get(tipo, tipo.__name__)}'")
        sinistra = _visita(nodo.left, testo)
        destra = _visita(nodo.right, testo)
        if tipo is ast.Pow and abs(destra) > ESPONENTE_MASSIMO:
            # Controllato prima di calcolare: 9 ** 9 ** 9 non deve bloccare il server.
            raise ErroreEspressione(
                f"esponente troppo grande: massimo {ESPONENTE_MASSIMO} in valore assoluto"
            )
        return _calcola(_BINARI[tipo], sinistra, destra)
    if isinstance(nodo, ast.UnaryOp):
        tipo = type(nodo.op)
        if tipo is ast.Not:
            raise _non_ammesso("operatore logico")
        if tipo not in _UNARI:
            raise _non_ammesso(f"operatore '{_SIMBOLI.get(tipo, tipo.__name__)}'")
        return _calcola(_UNARI[tipo], _visita(nodo.operand, testo))
    if isinstance(nodo, ast.Tuple):
        raise ErroreEspressione("virgola non ammessa: i decimali si scrivono con il punto")
    if isinstance(nodo, ast.Name):
        raise _non_ammesso(f"nome '{nodo.id}'")
    raise _non_ammesso(_NON_AMMESSI.get(type(nodo), type(nodo).__name__))


def valuta(espressione: str) -> int | float:
    """Calcola `espressione` se contiene solo elementi ammessi, altrimenti la rifiuta."""
    testo = (espressione or "").strip()
    if not testo:
        raise ErroreEspressione("espressione vuota")
    if len(testo) > LUNGHEZZA_MASSIMA:
        raise ErroreEspressione(
            f"espressione troppo lunga: massimo {LUNGHEZZA_MASSIMA} caratteri"
        )
    try:
        albero = ast.parse(testo, mode="eval")
        return _visita(albero.body, testo)
    except SyntaxError:
        raise ErroreEspressione("sintassi non valida") from None
    except (RecursionError, MemoryError):
        raise ErroreEspressione("espressione troppo complessa") from None


def formatta(valore: int | float) -> int | float:
    """Intero se il valore è intero, altrimenti 12 cifre significative (0.1 + 0.2 → 0.3)."""
    if isinstance(valore, float):
        # Oltre 2**53 ogni decimale "è intero": come int mostrerebbe cifre false.
        if valore.is_integer() and abs(valore) < 2**53:
            return int(valore)
        return float(f"{valore:.12g}")
    return valore
