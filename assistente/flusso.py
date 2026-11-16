"""Gli eventi di una risposta: testo, strumento in uso, fine.

Il grafo scrive eventi «custom» (vedi `grafo.py`); qui diventano tre tipi semplici,
indipendenti da chi li mostra: oggi il terminale, domani un frontend.
"""

from dataclasses import dataclass
from typing import Iterator

from langchain_core.messages import BaseMessage


@dataclass(frozen=True)
class Testo:
    """Un pezzo di testo della risposta.

    `nuovo_tratto` è vero quando il testo non continua quello precedente (per esempio il
    messaggio del limite di passaggi): chi lo mostra deve staccarlo da ciò che è già a schermo.
    """

    testo: str
    nuovo_tratto: bool = False


@dataclass(frozen=True)
class Strumento:
    """Il programma sta per eseguire lo strumento `nome`."""

    nome: str


@dataclass(frozen=True)
class Fine:
    """La risposta è conclusa: `messaggi` è la cronologia aggiornata."""

    messaggi: list[BaseMessage]


Evento = Testo | Strumento | Fine


def risposta_in_streaming(grafo, messaggi: list[BaseMessage]) -> Iterator[Evento]:
    """Interroga il grafo e produce gli eventi man mano che arrivano.

    Le eccezioni del grafo si propagano senza produrre `Fine`.
    """
    stato = None
    flusso = grafo.stream(
        {"messaggi": messaggi, "chiamate_strumento": 0}, stream_mode=["custom", "values"]
    )
    for modo, dato in flusso:
        if modo == "values":
            stato = dato
        elif dato["tipo"] == "testo":
            yield Testo(dato["testo"], dato.get("nuovo_tratto", False))
        elif dato["tipo"] == "strumento":
            yield Strumento(dato["nome"])
    yield Fine(stato["messaggi"])
