from datetime import datetime, timezone

from assistente.strumenti import crea_orologio, ora_corrente

ISTANTE = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)


def test_fuso_predefinito():
    assert ora_corrente(None, ISTANTE, "Europe/Rome") == "2026-10-26 15:00:00 Europe/Rome (UTC+01:00)"


def test_fuso_esplicito():
    assert (
        ora_corrente("Asia/Tokyo", ISTANTE, "Europe/Rome")
        == "2026-10-26 23:00:00 Asia/Tokyo (UTC+09:00)"
    )


def test_stringa_vuota_usa_predefinito():
    assert ora_corrente("  ", ISTANTE, "Europe/Rome").endswith("Europe/Rome (UTC+01:00)")


def test_fuso_inesistente():
    assert ora_corrente("Asia/Milano", ISTANTE, "Europe/Rome").startswith(
        "Errore: fuso orario sconosciuto 'Asia/Milano'"
    )


def test_scarto_negativo():
    assert ora_corrente("America/New_York", ISTANTE, "Europe/Rome").endswith("(UTC-04:00)")


def test_strumento_langchain():
    t = crea_orologio("Europe/Rome", adesso=lambda: ISTANTE)
    assert t.name == "orologio"
    assert t.invoke({"fuso_orario": "Asia/Tokyo"}).startswith("2026-10-26 23:00:00")
    assert t.invoke({}).startswith("2026-10-26 15:00:00")
