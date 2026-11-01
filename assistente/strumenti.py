"""Strumenti che il modello può chiedere di eseguire: per ora solo l'orologio."""

from datetime import datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

from langchain_core.tools import BaseTool, StructuredTool


def ora_corrente(fuso_orario: str | None, adesso: datetime, fuso_predefinito: str) -> str:
    """Data e ora di `adesso` nel fuso richiesto, come testo leggibile dal modello.

    Un fuso inesistente non solleva eccezioni: il modello riceve un messaggio d'errore.
    """
    nome = (fuso_orario or "").strip() or fuso_predefinito
    try:
        fuso = ZoneInfo(nome)
    except (ValueError, KeyError):
        return (
            f"Errore: fuso orario sconosciuto '{fuso_orario}'. "
            "Usa un nome IANA, per esempio Europe/Rome o Asia/Tokyo."
        )
    locale = adesso.astimezone(fuso)
    minuti = int(locale.utcoffset().total_seconds()) // 60
    segno = "+" if minuti >= 0 else "-"
    ore, resto = divmod(abs(minuti), 60)
    return f"{locale:%Y-%m-%d %H:%M:%S} {nome} (UTC{segno}{ore:02d}:{resto:02d})"


def crea_orologio(
    fuso_predefinito: str,
    adesso: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> BaseTool:
    """Strumento `orologio` per LangChain; `adesso` si sostituisce nei test."""

    def orologio(fuso_orario: str | None = None) -> str:
        return ora_corrente(fuso_orario, adesso(), fuso_predefinito)

    return StructuredTool.from_function(
        orologio,
        name="orologio",
        description=(
            "Restituisce la data e l'ora attuali. Usalo ogni volta che servono data o ora. "
            "Argomento facoltativo fuso_orario: nome IANA del fuso (per esempio Asia/Tokyo); "
            "per una città passa il fuso IANA della città. Senza argomento usa il fuso predefinito."
        ),
    )
