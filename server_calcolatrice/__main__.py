"""Avvio del server della calcolatrice in stdio: python -m server_calcolatrice

Con stdio, stdout è riservato ai messaggi del protocollo: niente banner e
solo avvisi nei log (che vanno su stderr).
"""

from server_calcolatrice.server import crea_server


def main() -> None:
    crea_server().run(show_banner=False, log_level="WARNING")


if __name__ == "__main__":
    main()
