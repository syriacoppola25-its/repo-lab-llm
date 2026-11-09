"""Configurazione letta dalle variabili d'ambiente."""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from zoneinfo import ZoneInfo

# Valori di .env.example: se arrivano fin qui, il file non è stato compilato.
SEGNAPOSTO = {"LMSTUDIO_URL": "URL_SERVER_LMSTUDIO", "LMSTUDIO_MODELLO": "ID_NOME_MODELLO"}


class ConfigErrata(ValueError):
    """Configurazione mancante o non valida; il messaggio nomina la variabile."""


@dataclass(frozen=True)
class Config:
    url_server: str
    modello: str
    fuso_predefinito: str = "Europe/Rome"
    limite_chiamate: int = 5
    percorso_log: Path = Path("logs/assistente.log")
    percorso_note: Path = Path("dati/note.db")


def _obbligatoria(env: Mapping[str, str], nome: str) -> str:
    valore = env.get(nome, "").strip()
    if not valore:
        raise ConfigErrata(f"Variabile d'ambiente {nome} mancante.")
    if valore == SEGNAPOSTO[nome]:
        raise ConfigErrata(
            f"La variabile {nome} contiene ancora il segnaposto '{valore}': sostituiscilo con il valore reale."
        )
    return valore


def _facoltativa(env: Mapping[str, str], nome: str) -> str | None:
    valore = env.get(nome, "").strip()
    return valore or None


def carica_config(env: Mapping[str, str]) -> Config:
    """Costruisce la configurazione da `env` (di solito `os.environ`)."""
    predefinita = Config(url_server="", modello="")
    url_server = _obbligatoria(env, "LMSTUDIO_URL")
    modello = _obbligatoria(env, "LMSTUDIO_MODELLO")

    fuso = _facoltativa(env, "FUSO_PREDEFINITO") or predefinita.fuso_predefinito
    try:
        ZoneInfo(fuso)
    except (ValueError, KeyError):
        raise ConfigErrata(
            f"FUSO_PREDEFINITO non valido: '{fuso}'. Usa un nome IANA, per esempio Europe/Rome."
        ) from None

    testo_limite = _facoltativa(env, "LIMITE_CHIAMATE_STRUMENTO")
    limite = predefinita.limite_chiamate
    if testo_limite is not None:
        try:
            limite = int(testo_limite)
        except ValueError:
            limite = 0
        if limite < 1:
            raise ConfigErrata(
                f"LIMITE_CHIAMATE_STRUMENTO non valido: '{testo_limite}'. Serve un numero intero maggiore di zero."
            )

    percorso = _facoltativa(env, "PERCORSO_LOG")
    note = _facoltativa(env, "PERCORSO_NOTE")
    return Config(
        url_server=url_server,
        modello=modello,
        fuso_predefinito=fuso,
        limite_chiamate=limite,
        percorso_log=Path(percorso) if percorso else predefinita.percorso_log,
        percorso_note=Path(note) if note else predefinita.percorso_note,
    )
