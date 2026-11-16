"""Il ciclo domanda/risposta da terminale, con la cronologia della sessione."""

from typing import Callable

from langchain_core.messages import BaseMessage, HumanMessage

from assistente.flusso import Fine, Strumento, Testo, risposta_in_streaming

SALUTO = "Arrivederci!"
PENSANDO = "sto pensando…"
PROMPT = "Tu: "
PREFISSO_RISPOSTA = "Assistente: "
COMANDO_USCITA = "esci"


def riga_strumento(nome: str) -> str:
    """La riga mostrata quando il programma sta per eseguire uno strumento."""
    return f"Interrogando lo strumento {nome}…"


def _scrivi_senza_a_capo(testo: str) -> None:
    print(testo, end="", flush=True)


def esegui_sessione(
    grafo,
    leggi: Callable[[str], str] = input,
    scrivi: Callable[[str], None] = print,
    scrivi_pezzo: Callable[[str], None] = _scrivi_senza_a_capo,
) -> None:
    """Conversa finché l'utente scrive `esci`, preme Ctrl+C o chiude l'input.

    `scrivi` stampa una riga intera; `scrivi_pezzo` stampa senza andare a capo, per il
    testo che arriva a pezzi. La cronologia vive solo in questa funzione: alla fine
    della sessione va persa.
    """
    cronologia: list[BaseMessage] = []
    riga_aperta = False  # c'è testo della risposta non ancora chiuso da un a capo
    try:
        while True:
            domanda = leggi(PROMPT).strip()
            if not domanda:
                continue
            if domanda.lower() == COMANDO_USCITA:
                break
            scrivi(PENSANDO)
            try:
                for evento in risposta_in_streaming(grafo, cronologia + [HumanMessage(domanda)]):
                    if isinstance(evento, Testo):
                        if not evento.testo:
                            continue
                        if evento.nuovo_tratto and riga_aperta:
                            scrivi_pezzo("\n")
                            riga_aperta = False
                        if not riga_aperta:
                            scrivi_pezzo(PREFISSO_RISPOSTA)
                            riga_aperta = True
                        scrivi_pezzo(evento.testo)
                    elif isinstance(evento, Strumento):
                        if riga_aperta:
                            scrivi_pezzo("\n")
                            riga_aperta = False
                        scrivi(riga_strumento(evento.nome))
                    elif isinstance(evento, Fine):
                        if riga_aperta:
                            scrivi_pezzo("\n")
                            riga_aperta = False
                        cronologia = evento.messaggi
            except Exception as errore:
                # La domanda fallita non entra nella cronologia; la sessione continua.
                # Il testo già stampato resta: si chiude la sua riga prima del messaggio.
                if riga_aperta:
                    scrivi_pezzo("\n")
                scrivi(
                    "Errore: impossibile ottenere una risposta dal modello "
                    f"({type(errore).__name__}). Controlla che LM Studio sia avviato."
                )
                continue
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C a metà risposta: si chiude la riga aperta prima del saluto.
        if riga_aperta:
            scrivi_pezzo("\n")
    scrivi(SALUTO)
