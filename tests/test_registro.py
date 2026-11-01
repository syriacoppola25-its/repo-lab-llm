from assistente.registro import configura_registro


def test_scrive_su_file(tmp_path):
    percorso = tmp_path / "sub" / "a.log"

    registro = configura_registro(percorso)
    registro.info("x")
    for gestore in registro.handlers:
        gestore.flush()

    assert percorso.exists()
    assert "INFO x" in percorso.read_text(encoding="utf-8")
