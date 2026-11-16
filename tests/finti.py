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
