"""Oggetti finti usati nei test al posto del modello vero."""

from langchain_core.messages import AIMessage, BaseMessage


class ModelloFinto:
    """Restituisce (o solleva) le risposte preparate, una per ogni invocazione.

    Ogni lista di messaggi ricevuta viene salvata in `ricevuti`, così i test
    possono controllare che cosa è stato mandato al modello.
    """

    def __init__(self, risposte: list[AIMessage | BaseException]):
        self.risposte = list(risposte)
        self.ricevuti: list[list[BaseMessage]] = []

    def invoke(self, messaggi: list[BaseMessage]) -> AIMessage:
        self.ricevuti.append(list(messaggi))
        risposta = self.risposte.pop(0)
        if isinstance(risposta, BaseException):
            raise risposta
        return risposta
