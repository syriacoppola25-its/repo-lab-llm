# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti».
La cartella del progetto è `repo-lab-llm/`.

## Struttura
- `assistente/`: `config.py` (variabili d'ambiente), `modello.py` (LM Studio, istruzioni di
  sistema), `strumenti.py` (orologio, `ErroreCollegamento`), `registro.py` (log su file),
  `grafo.py` (stato, nodi, `instrada`, conferme), `note_mcp.py` (client MCP sincrono con
  discovery), `conferma.py` (conferma `s/n` prima di `delete_note`), `terminale.py` (ciclo e
  cronologia), `__main__.py` (avvio, insieme al server delle note).
- `server_note/`: server MCP delle note (FastMCP, stdio): `archivio.py` (SQLite),
  `server.py` (tool `add_note`, `list_notes`, `delete_note`), `__main__.py`.
- `tests/`: test senza modello (il server delle note si avvia davvero via stdio);
  `test_reale_lmstudio.py` è la prova reale.
- `Dockerfile`, `docker-compose.yml`; `.env` locale (non versionato) da `.env.example`;
  `dati/` (archivio delle note) e `logs/` non versionati.

## Comandi
- Ambiente: `python -m venv .venv`, `.\.venv\Scripts\Activate.ps1`,
  `python -m pip install -r requirements-dev.txt`.
- Test senza modello: `python -m pytest -v`.
- Prova reale: `$env:PROVA_LMSTUDIO = "1"` più `LMSTUDIO_URL`/`LMSTUDIO_MODELLO`, poi
  `python -m pytest tests/test_reale_lmstudio.py -q`.
- Avvio: `python -m assistente`; con Docker: `docker compose run --rm assistente`.

## Obiettivo
Un'applicazione da terminale in Python che conversa con un modello locale e:
- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);
- usa un modello servito da LM Studio, che resta sul computer host;
- conserva la cronologia della conversazione per la durata della sessione (nessuna persistenza);
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling
  ed eseguito davvero dal programma;
- gestisce note persistenti tramite un server MCP separato (lezione 5), con conferma
  dell'eliminazione chiesta dal programma;
- si avvia anche con Docker Compose.

## Confini
- Implementare solo i requisiti concordati. MCP è ammesso per le note (un solo server, stdio);
  altri strumenti o server MCP, workflow e RAG arriveranno nelle lezioni successive: non
  anticiparli.
- Nome, descrizione e schema dei tool MCP stanno solo nel server: il client li ottiene con la
  discovery, non li riscrive.
- Niente interfacce grafiche, servizi cloud o framework non concordati.
- Lavorare solo dentro `repo-lab-llm/`. La repository contiene altre lezioni:
  non leggerle per copiarne il codice e non modificarle.
- Lavorare nel branch `dev`; `main` riceve il lavoro solo alla fine, su mia richiesta.
  Nessun altro branch o worktree se non richiesto.

## Scelte tecniche
- Python, codice sincrono e moduli piccoli, con una separazione semplice tra
  grafo, collegamento al modello, strumenti e interfaccia da terminale.
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente.
  L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.
- Un file di configurazione di esempio senza credenziali; il file reale resta fuori da Git.
- Docker Compose per l'applicazione; LM Studio non va containerizzato.
- Dipendenze motivate, concordate e con versioni fissate.
- Comandi documentati anche per PowerShell (Windows).

## Metodo: Superpowers
- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano.
- Salvare specifica e piano in `repo-lab-llm/docs/superpowers/`.
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.

## Test e verifiche
- Test automatici ripetibili che non richiedono un modello attivo (grafo, cronologia,
  instradamento, strumento con istante controllato).
- Prove reali con LM Studio e con Docker tenute separate e attivate esplicitamente.
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare.

## Git
- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`,
  `docs: ...`.
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.
- Mai versionare credenziali, `.env`, ambienti virtuali, cache o pesi dei modelli.
- Push soltanto su mia richiesta.

## Documentazione
- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo
  comandi verificati.
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test,
  regole di lavoro), non per annotare l'avanzamento.
