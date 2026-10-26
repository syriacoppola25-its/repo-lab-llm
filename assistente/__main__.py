"""Avvio: python -m assistente"""

from assistente.grafo import RispostaFissa, costruisci_grafo
from assistente.terminale import esegui_sessione


def main() -> None:
    esegui_sessione(costruisci_grafo(RispostaFissa()))


if __name__ == "__main__":
    main()
