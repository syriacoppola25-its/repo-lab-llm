"""Oggetti finti usati nei test al posto del modello vero."""

import json
import re
from typing import Iterator

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage


class ModelloFinto:
    """Restituisce (o solleva) le risposte preparate, una per ogni invocazione.

    Ogni lista di messaggi ricevuta viene salvata in `ricevuti`, così i test
    possono controllare che cosa è stato mandato al modello.
    """

    def __init__(self, risposte: list[AIMessage | BaseException]):
        self.risposte = list(risposte)
        self.ricevuti: list[list[BaseMessage]] = []

    def _prossima(self, messaggi: list[BaseMessage]) -> AIMessage:
        self.ricevuti.append(list(messaggi))
        risposta = self.risposte.pop(0)
        if isinstance(risposta, BaseException):
            raise risposta
        return risposta

    def invoke(self, messaggi: list[BaseMessage]) -> AIMessage:
        return self._prossima(messaggi)

    def stream(self, messaggi: list[BaseMessage]) -> Iterator[AIMessageChunk]:
        """Come `invoke`, ma la risposta arriva a pezzi: una parola per volta.

        Le chiamate a strumenti (anche quelle non leggibili) arrivano in un ultimo
        pezzo, come `tool_call_chunks` con gli argomenti in forma di testo.
        """
        risposta = self._prossima(messaggi)
        for parola in re.findall(r"\S+\s*", risposta.content):
            yield AIMessageChunk(parola)
        pezzi = [
            {"name": c["name"], "args": json.dumps(c["args"]), "id": c["id"], "index": i}
            for i, c in enumerate(risposta.tool_calls)
        ]
        pezzi += [
            {"name": c["name"], "args": c["args"], "id": c["id"], "index": len(pezzi) + i}
            for i, c in enumerate(risposta.invalid_tool_calls)
        ]
        if pezzi:
            yield AIMessageChunk("", tool_call_chunks=pezzi)


def decisione(categoria: str, motivo: str = "motivo di prova") -> dict:
    """Uscita del router come quella reale (`include_raw=True`) con una decisione leggibile."""
    dati = {"categoria": categoria, "motivo": motivo}
    return {"raw": AIMessage(json.dumps(dati)), "parsed": dati, "parsing_error": None}


def illeggibile(testo: str = "non è json") -> dict:
    """Uscita del router quando la risposta del modello non si legge come JSON."""
    return {"raw": AIMessage(testo), "parsed": None, "parsing_error": ValueError("JSON non valido")}


class RouterFinto:
    """Router che restituisce (o solleva) le uscite preparate, una per invocazione.

    Senza risposte preparate classifica sempre come `conversazione`.
    Ogni lista di messaggi ricevuta viene salvata in `ricevuti`.
    """

    def __init__(self, risposte: list[dict | BaseException] | None = None):
        self.risposte = None if risposte is None else list(risposte)
        self.ricevuti: list[list[BaseMessage]] = []

    def invoke(self, messaggi: list[BaseMessage]) -> dict:
        self.ricevuti.append(list(messaggi))
        if self.risposte is None:
            return decisione("conversazione")
        risposta = self.risposte.pop(0)
        if isinstance(risposta, BaseException):
            raise risposta
        return risposta
