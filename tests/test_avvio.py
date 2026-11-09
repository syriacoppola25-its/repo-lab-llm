"""Avvio da `python -m assistente` (senza modello e senza server delle note)."""

import assistente.__main__ as avvio
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


def test_ctrl_c_durante_avvio_server(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("LMSTUDIO_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("LMSTUDIO_MODELLO", "modello-di-prova")
    monkeypatch.setenv("PERCORSO_LOG", str(tmp_path / "logs" / "assistente.log"))
    monkeypatch.setenv("PERCORSO_NOTE", str(tmp_path / "note.db"))
    monkeypatch.setattr(avvio, "ClientNote", ClientInterrotto)
    ClientInterrotto.chiusure = 0

    codice = avvio.main()  # non deve sollevare KeyboardInterrupt

    assert codice == 0
    assert ClientInterrotto.chiusure == 1
    assert SALUTO in capsys.readouterr().out
