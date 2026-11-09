"""Avvio da `python -m assistente` (senza modello e senza server veri)."""

import assistente.__main__ as avvio
from assistente.strumenti import ErroreCollegamento
from assistente.terminale import SALUTO


class ClientInterrotto:
    """Client finto: Ctrl+C arriva mentre si avvia il server delle note."""

    chiusure = 0

    def __init__(self, *argomenti, **opzioni):
        pass

    def apri(self):
        raise KeyboardInterrupt

    def chiudi(self):
        ClientInterrotto.chiusure += 1


class ClientAperto:
    """Client finto che si apre senza problemi e non offre strumenti."""

    chiusure = 0

    def __init__(self, *argomenti, **opzioni):
        pass

    def apri(self):
        pass

    def strumenti(self):
        return []

    def chiudi(self):
        ClientAperto.chiusure += 1


class CalcolatriceGuasta(ClientAperto):
    """Client finto: il server della calcolatrice non parte."""

    chiusure = 0

    def apri(self):
        raise ErroreCollegamento("server della calcolatrice non avviato (x)")

    def chiudi(self):
        CalcolatriceGuasta.chiusure += 1


def configura(monkeypatch, tmp_path):
    monkeypatch.setenv("LMSTUDIO_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("LMSTUDIO_MODELLO", "modello-di-prova")
    monkeypatch.setenv("PERCORSO_LOG", str(tmp_path / "logs" / "assistente.log"))
    monkeypatch.setenv("PERCORSO_NOTE", str(tmp_path / "note.db"))


def test_ctrl_c_durante_avvio_server(monkeypatch, tmp_path, capsys):
    configura(monkeypatch, tmp_path)
    monkeypatch.setattr(avvio, "ClientNote", ClientInterrotto)
    monkeypatch.setattr(avvio, "ClientCalcolatrice", ClientAperto)
    ClientInterrotto.chiusure = 0

    codice = avvio.main()  # non deve sollevare KeyboardInterrupt

    assert codice == 0
    assert ClientInterrotto.chiusure == 1
    assert SALUTO in capsys.readouterr().out


def test_calcolatrice_non_parte(monkeypatch, tmp_path, capsys):
    # Le note partono, la calcolatrice no: messaggio che la nomina, uscita, entrambi chiusi.
    configura(monkeypatch, tmp_path)
    monkeypatch.setattr(avvio, "ClientNote", ClientAperto)
    monkeypatch.setattr(avvio, "ClientCalcolatrice", CalcolatriceGuasta)
    ClientAperto.chiusure = CalcolatriceGuasta.chiusure = 0

    codice = avvio.main()

    uscita = capsys.readouterr().out
    assert codice == 1
    assert "Impossibile avviare il server della calcolatrice" in uscita
    assert "server_calcolatrice.log" in uscita
    assert ClientAperto.chiusure == 1 and CalcolatriceGuasta.chiusure == 1
