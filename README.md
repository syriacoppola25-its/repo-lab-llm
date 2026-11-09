# Assistente del laboratorio

Chatbot da terminale in Python per il corso «Deep Learning e LLM: costruire chatbot e agenti».
Il flusso della conversazione è un grafo LangGraph scritto a mano.

Stato attuale: l'assistente conversa con un modello servito da LM Studio e ricorda la
conversazione per la durata della sessione. Quando serve l'ora chiede lo strumento `orologio`,
che il programma esegue davvero. Può salvare, elencare ed eliminare **note persistenti** tramite
un server MCP separato (`server_note/`); prima di ogni eliminazione chiede conferma nel
terminale. Si avvia sia in locale sia con Docker Compose.

## Preparare l'ambiente (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip check
python -c "import langgraph, langchain_openai, tzdata, fastmcp, mcp, langchain_mcp_adapters; print('ok')"
```

`pip check` deve rispondere `No broken requirements found.` e l'ultimo comando stampare `ok`.

Versioni MCP: `fastmcp==3.4.11`, `mcp==1.30.0`, `langchain-mcp-adapters==0.3.2`. fastmcp 4.x
non è utilizzabile insieme all'adattatore LangChain, perché richiede `mcp` 2.x mentre
`langchain-mcp-adapters` richiede `mcp` 1.x.

## Configurazione

L'assistente legge la configurazione solo da variabili d'ambiente:

| Variabile | Obbligatoria | Significato |
|---|---|---|
| `LMSTUDIO_URL` | sì | indirizzo dell'API di LM Studio, per esempio `http://localhost:1234/v1` |
| `LMSTUDIO_MODELLO` | sì | identificativo del modello, come restituito da `GET /v1/models` |
| `FUSO_PREDEFINITO` | no | fuso orario IANA predefinito (`Europe/Rome`) |
| `LIMITE_CHIAMATE_STRUMENTO` | no | chiamate allo strumento per domanda (`5`) |
| `PERCORSO_LOG` | no | file di log (`logs/assistente.log`) |
| `PERCORSO_NOTE` | no | archivio SQLite delle note (`dati/note.db`) |

`.env.example` contiene solo segnaposto (`URL_SERVER_LMSTUDIO`, `ID_NOME_MODELLO`): non va usato
così com'è. Se l'app trova una variabile obbligatoria mancante o con il segnaposto, non parte e
spiega quale variabile correggere.

L'identificativo del modello non va inventato: si legge dal server di LM Studio (avviato, con il
modello caricato):

```powershell
Invoke-RestMethod http://localhost:1234/v1/models | Select-Object -ExpandProperty data | Select-Object id
```

## Avvio

Con LM Studio avviato, in PowerShell (l'identificativo è quello usato nelle prove, letto dal
comando precedente):

```powershell
$env:LMSTUDIO_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODELLO = "google/gemma-4-e2b"
python -m assistente
```

- scrivi una domanda e premi Invio: compare `sto pensando…` e poi la risposta;
- le righe vuote vengono ignorate;
- per uscire scrivi `esci` (anche in maiuscolo) oppure premi Ctrl+C.

La cronologia della conversazione resta in memoria solo finché la sessione è aperta.

## Avvio con Docker Compose

LM Studio resta sull'host (non va in un container); nel container gira solo l'assistente.
Serve Docker Desktop avviato.

1. Crea `.env` copiando `.env.example` e sostituisci i segnaposto con i valori reali (il file
   non va in Git):

   ```
   LMSTUDIO_URL=http://localhost:1234/v1
   LMSTUDIO_MODELLO=google/gemma-4-e2b
   ```

2. Controlla la configurazione e costruisci l'immagine:

   ```powershell
   docker compose config
   docker compose build
   ```

3. Avvia la conversazione (per uscire: `esci` o Ctrl+C; il container viene rimosso):

   ```powershell
   docker compose run --rm assistente
   ```

**Indirizzo di LM Studio: locale e container.** Nel container `localhost` è il container stesso,
non il computer. Per questo `docker-compose.yml` sostituisce `LMSTUDIO_URL` del `.env` con
`http://host.docker.internal:1234/v1`, che dal container porta all'host. Lo stesso `.env` vale
quindi per entrambi i modi di avvio. Anche `PERCORSO_LOG` è impostato da Compose: il log del
container finisce nella cartella `logs\` dell'host. Allo stesso modo `PERCORSO_NOTE` punta a
`/app/dati/note.db`, cioè alla cartella `dati\` dell'host: le note restano anche dopo
`docker compose run --rm`, e sono le stesse dell'avvio locale.

Nel log le righe scritte dal container hanno l'orario in UTC, quelle dell'avvio locale l'orario
del computer.

## Strumento orologio

Il modello non conosce l'ora: quando gli serve, chiede (tool calling) lo strumento `orologio`,
che il programma esegue e il cui risultato torna al modello. L'argomento facoltativo
`fuso_orario` è un nome IANA (per esempio `Asia/Tokyo`); senza argomento si usa
`FUSO_PREDEFINITO`. Il risultato ha la forma `2026-11-02 04:55:00 Asia/Tokyo (UTC+09:00)`;
un fuso inesistente produce un messaggio d'errore per il modello, non un crash.

Per ogni domanda lo strumento può essere eseguito al massimo `LIMITE_CHIAMATE_STRUMENTO` volte
(predefinito 5); oltre, l'assistente risponde
`Non sono riuscito a completare la risposta (limite di passaggi raggiunto). Riprova o riformula la domanda.`

Esempio di domande: «che ore sono?», «e a Tokyo?».

### File di log

Ogni chiamata allo strumento viene scritta in `logs/assistente.log` (o in `PERCORSO_LOG`), mai
nel terminale. Per vedere le ultime righe:

```powershell
Get-Content logs\assistente.log -Encoding utf8 -Tail 6
```

Esempio di riga:
`INFO passaggio=1 id=<tool_call_id> strumento=orologio argomenti={'fuso_orario': 'Asia/Tokyo'} esito=ok risultato=...`.
`id` collega la riga alla richiesta del modello; `esito` vale `ok`, `annullata`,
`errore_strumento`, `errore_collegamento`, `argomenti_non_validi` o `strumento_sconosciuto`.
Per `delete_note` compare anche `conferma=si` o `conferma=no`. Quando si raggiunge il limite
compare una riga `WARNING limite raggiunto: ...`.

## Note persistenti (MCP)

Le note sono gestite da un **server MCP** separato, scritto con FastMCP (`server_note/`), che
le salva in SQLite (`dati/note.db`, fuori da Git). L'assistente lo avvia da solo come
sottoprocesso e ci parla via stdio: non serve avviarlo a mano. All'avvio ne legge il catalogo
(`tools/list`): nome, descrizione e schema dei tool vengono dal server, non sono riscritti
nell'assistente. L'orologio invece resta una funzione locale.

| Tool | Argomenti | Effetto |
|---|---|---|
| `add_note` | `text` (max 500 caratteri) | salva una nota; risponde con ID, data e testo |
| `list_notes` | `limit` (1–100, predefinito 20) | elenca le note in ordine di creazione |
| `delete_note` | `note_id` (preso da `list_notes`) | elimina definitivamente la nota |

Esempi: «ricordami che ho un meeting giovedì 4 alle 10», «fammi vedere le note», «cancella la
nota dell'appuntamento di giovedì 4».

**Conferma.** Prima di eseguire `delete_note` il programma (non il modello) chiede nel terminale:

```
Eliminare la nota 1: «meeting giovedì 4 alle 10»? (s/n)
```

Elimina solo con `s`, `si` o `sì`; qualsiasi altra risposta annulla e il modello riceve
`Eliminazione annullata dall'utente: nessuna nota è stata eliminata.`. Gli ID non vengono mai
riutilizzati, quindi un numero vecchio non può cancellare una nota nuova.

**Errori.** Il modello riceve testi diversi: `Errore dello strumento: Nessuna nota con ID 99.`
(errore restituito dal server, nessun effetto) oppure `Errore di collegamento: ...` (server non
raggiungibile). Gli avvisi del server vanno in `logs/server_note.log`, non nel terminale.

## Diagnosi

- `Variabile d'ambiente LMSTUDIO_URL mancante. Vedi .env.example.`: le variabili non sono
  impostate in questa finestra di PowerShell (valgono solo per la finestra in cui le imposti).
- `... contiene ancora il segnaposto ...`: sostituisci il segnaposto con il valore reale.
- `Errore: impossibile ottenere una risposta dal modello (OpenAIConnectionError)`: il server di
  LM Studio non è raggiungibile all'indirizzo indicato. Avvialo (o correggi `LMSTUDIO_URL`) e
  riprova: la sessione resta aperta e la domanda fallita non entra nella cronologia.
- `Errore: impossibile ottenere una risposta dal modello (OpenAIInvalidRequestError)`: il server
  risponde ma rifiuta la richiesta; controlla con il comando di `/v1/models` che il modello sia
  disponibile e che l'identificativo coincida, poi riprova.

- `Impossibile avviare il server delle note (...)`: il sottoprocesso `python -m server_note`
  non è partito. Controlla `logs\server_note.log` e che le dipendenze siano installate
  (`python -m pip check`).
- Le note non si comportano come previsto: diagnosi per livelli.
  1. Il server risponde? `python -m pytest tests/test_server_note.py tests/test_note_mcp.py -q`
     (catalogo, chiamata diretta ed errori, senza modello).
  2. Il modello chiama il tool? Nel log cerca le righe con `strumento=add_note`,
     `list_notes`, `delete_note`: se mancano, il modello ha risposto senza usare lo strumento.
  3. L'esito è giusto? `esito=errore_strumento` è un rifiuto del server (es. ID inesistente);
     `esito=errore_collegamento` indica che il server non risponde (riavvia l'assistente).
  4. Il risultato è giusto ma la risposta no: è un problema di interpretazione del modello.
- Docker: per controllare che il container raggiunga LM Studio sull'host:

  ```powershell
  docker compose run --rm -T assistente python -c "import urllib.request,json; print([m['id'] for m in json.load(urllib.request.urlopen('http://host.docker.internal:1234/v1/models', timeout=10))['data']])"
  ```

  Deve stampare l'elenco dei modelli. Se invece dà errore di connessione, in LM Studio verifica
  che il server sia avviato.
- Docker: per controllare l'immagine senza modello:

  ```powershell
  docker compose run --rm -T assistente python -c "from zoneinfo import ZoneInfo; ZoneInfo('Asia/Tokyo'); import assistente.grafo, assistente.note_mcp, server_note.server; print('ok')"
  docker compose run --rm -T assistente ls -a /app
  ```

  Il primo stampa `ok`; il secondo elenca solo `assistente`, `server_note`, `dati` e `logs` (le
  cartelle dei volumi) e `requirements.txt`.

## Test automatici

Non richiedono un modello attivo:

```powershell
python -m pytest -v
```

La prova reale con LM Studio (`tests/test_reale_lmstudio.py`) viene saltata, a meno di attivarla
esplicitamente. Con LM Studio avviato e le variabili di «Avvio» impostate:

```powershell
$env:PROVA_LMSTUDIO = "1"
python -m pytest tests/test_reale_lmstudio.py -q
Remove-Item Env:PROVA_LMSTUDIO
```

La prova usa il modello vero (circa 2 minuti):
- «Che ore sono a Tokyo?» → strumento `orologio` con `Asia/Tokyo`;
- «Ricordami che ho un meeting giovedì 4 alle 10» → una sola `add_note`;
- «Fammi vedere le note» → `list_notes` e la nota nella risposta;
- «Cancella la nota dell'appuntamento di giovedì 4» → `list_notes` prima di `delete_note`,
  archivio vuoto;
- «Elimina la nota 99» → `delete_note` con errore dello strumento, nessuna nota eliminata.

Le note usano un archivio temporaneo e la conferma è fissa (sì). Il modello non è
deterministico: conviene ripeterla più volte.

## Verifica completa

Ordine delle prove per ricontrollare tutto da zero (PowerShell, nella cartella del progetto):

1. Ambiente pulito e test automatici, senza modello né Docker:

   ```powershell
   Remove-Item -Recurse -Force .venv
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements-dev.txt
   python -m pip check
   python -m pytest -v
   ```

   Esito atteso: `No broken requirements found.` e `85 passed, 5 skipped`.
2. LM Studio: elenco dei modelli (sezione «Configurazione»), prova reale con
   `PROVA_LMSTUDIO` (sezione «Test automatici», ripetuta più volte) e conversazione con
   `python -m assistente`: «che ore sono?», «e a Tokyo?», «di che cosa abbiamo parlato?»,
   confrontando le ore con l'orologio di Windows e il file di log. Per le note, sempre con
   `python -m assistente`: aggiungi due note, elencale, eliminane una rispondendo `s` alla
   conferma e prova a eliminare l'altra rispondendo `n`; esci, riavvia e chiedi di nuovo le
   note (deve esserci solo la seconda). Nel log controlla `conferma=si`/`conferma=no` ed `esito`.
3. Docker: `docker compose build`, i due controlli dell'immagine (sezione «Diagnosi») e
   `docker compose run --rm assistente` con una domanda sull'ora di Tokyo, poi `esci`. Poi
   aggiungi una nota, esci, riavvia il container e chiedi le note: la nota deve esserci
   (è in `dati\note.db` sull'host).

Comportamento noto del modello `google/gemma-4-e2b`: usa correttamente lo strumento, ma spesso
nomina il fuso `Europe/Rome` anche quando non serve.

## Come è fatto il grafo

LangGraph descrive il programma come un grafo:

- **stato** (`Stato` in `assistente/grafo.py`): i dati che passano da un nodo all'altro, cioè la
  lista dei messaggi della conversazione e il numero di chiamate allo strumento;
- **nodo**: una funzione che riceve lo stato e restituisce le modifiche da applicare (per esempio
  il nodo `modello` aggiunge la risposta del modello ai messaggi);
- **arco**: il collegamento che dice quale nodo viene eseguito dopo. Un **arco condizionale**
  sceglie il nodo successivo in base allo stato.

Il grafo dell'assistente (`costruisci_grafo` in `assistente/grafo.py`):

```
START → modello ──fine──────→ END
          ↑  │ ──limite──→ limite → END
          │  └─strumenti─→ strumenti
          └───────────────────┘
```

- `modello`: manda al modello le istruzioni di sistema (non salvate nella cronologia) e la
  conversazione, e aggiunge la risposta;
- `instrada` (arco condizionale): se la risposta non chiede strumenti → `END`; se li chiede e il
  limite non è superato → `strumenti`; altrimenti → `limite`;
- `strumenti`: esegue ogni chiamata richiesta, aggiunge un risultato per ciascuna e torna a
  `modello`;
- `limite`: chiude le chiamate rimaste senza esito e risponde con il messaggio di limite.
