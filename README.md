# repo-lab-llm

Client Python minimo che invia una domanda a un modello eseguito in locale con LM Studio e stampa la risposta. Materiale della Lezione 3 del corso Deep Learning e LLM (ITS Alto Adriatico).

## Contenuto della repository

| File | Funzione |
|---|---|
| `client.py` | Scheletro del client da completare con Claude Code |
| `requirements.txt` | Dipendenze con versioni fissate |
| `.env.example` | Modello della configurazione locale, senza segreti |
| `CLAUDE.md` | Istruzioni di sviluppo lette da Claude Code |
| `.gitignore` | File esclusi da Git: configurazione locale, ambiente virtuale, pesi, log |

## Prerequisiti

- Windows con PowerShell, Git e VS Code (estensioni Python e Git Graph).
- Python con il launcher `py`.
- LM Studio con il modello `google/gemma-4-e2b`, quantizzazione a 4 bit (`Q4_K_M`).
- Claude Code CLI: guida ufficiale <https://code.claude.com/docs/en/setup>. In PowerShell: `irm https://claude.ai/install.ps1 | iex`, poi riaprire il terminale e verificare con `claude --version`.

## Preparazione

Dalla radice della repository:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

In VS Code selezionare l'interprete `.venv` con **Python: Select Interpreter**.

## Configurazione

1. In LM Studio scaricare e caricare `google/gemma-4-e2b` (4 bit), poi avviare il server dalla sezione Developer.
2. Leggere l'identificativo del modello esposto dal server:

   ```powershell
   $base = "http://localhost:1234/v1"
   (Invoke-RestMethod "$base/models").data | Select-Object id
   ```

3. Creare la configurazione locale, solo se `.env` non esiste già, e inserire l'indirizzo del server (quello usato al punto 2, con `/v1`) al posto di `URL_SERVER_REALE` e l'identificativo letto al punto 2 al posto di `ID_MODELLO_REALE`:

   ```powershell
   Copy-Item .env.example .env
   notepad .env
   ```

`.env` resta sul proprio computer ed è escluso da Git.

## Avvio

Con il server di LM Studio acceso e `.env` configurato:

```powershell
.\.venv\Scripts\python.exe client.py
```

Il client chiede una domanda da terminale, la invia a `{LM_BASE_URL}/chat/completions` e stampa il testo della risposta a frammenti, man mano che il modello lo genera (streaming), poi chiede la domanda successiva. Per uscire scrivere `esci` oppure premere `Ctrl+C`. Le righe vuote vengono ignorate. La conversazione resta in memoria durante la sessione: a ogni richiesta viene inviata l'intera cronologia, quindi il modello ricorda le domande e le risposte precedenti (per esempio il nome dell'utente). La cronologia si perde alla chiusura e non viene limitata: in sessioni molto lunghe può superare il contesto del modello e il server risponde con un errore, e in quel caso conviene riavviare il programma. Una richiesta fallita non entra nella cronologia. Se il server dà errore, il messaggio compare e il programma chiede ancora. Non ha interfaccia grafica e non salva nulla su disco.

## Verifica

1. Dipendenze installate:

   ```powershell
   .\.venv\Scripts\python.exe -c "import requests, dotenv; print('import ok')"
   ```

2. Server raggiungibile e modello esposto (deve comparire lo stesso id scritto in `LM_MODEL`):

   ```powershell
   (Invoke-RestMethod "http://localhost:1234/v1/models").data | Select-Object id
   ```

3. Risposta del modello: eseguire `client.py` come nella sezione Avvio e scrivere una domanda. Deve comparire un testo in italiano, con le lettere accentate corrette, che si compone progressivamente e non tutto insieme. Il testo può risultare troncato perché `max_tokens` è 500: è normale.
4. Ciclo: premere Invio senza testo (non deve succedere nulla, compare di nuovo la richiesta), poi scrivere `esci` (il programma termina). Rieseguire e premere `Ctrl+C`: deve comparire `Interrotto. Arrivederci.` senza traceback.
5. Memoria: scrivere `Mi chiamo Anna`, poi `Come mi chiamo?`: il modello deve rispondere con il nome. Uscire con `esci`, rieseguire e rifare la seconda domanda: il modello non deve più conoscere il nome.
6. Messaggio di errore: fermare il server in LM Studio, rieseguire `client.py` e scrivere una domanda. Deve comparire `Connessione fallita: controllare server, URL e porta.` e il programma deve chiedere ancora una domanda.

## Diagnosi rapida

| Messaggio | Primo controllo |
|---|---|
| `Connessione fallita` | LM Studio acceso, server avviato, URL e porta in `.env` |
| `Errore HTTP` con messaggio sul modello | Identificativo in `.env`, modello caricato |
| `Attesa scaduta` | Carico del computer, tempi del modello |
| Risposta vuota | `"reasoning_effort": "none"` nel payload: senza, il modello ragiona e consuma i token prima di rispondere |
| `KeyError: 'LM_BASE_URL'` o `'LM_MODEL'` | `.env` mancante o variabile non definita |

Una risposta arrivata non è necessariamente corretta: va letta e valutata.
