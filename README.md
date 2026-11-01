# Assistente del laboratorio

Chatbot da terminale in Python per il corso «Deep Learning e LLM: costruire chatbot e agenti».
Il flusso della conversazione è un grafo LangGraph scritto a mano.

Stato attuale: l'assistente conversa con un modello servito da LM Studio e ricorda la
conversazione per la durata della sessione. Lo strumento orologio arriverà nell'incremento
successivo.

## Preparare l'ambiente (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -c "import langgraph, langchain_openai, tzdata; print('ok')"
```

L'ultimo comando deve stampare `ok`.

## Configurazione

L'assistente legge la configurazione solo da variabili d'ambiente:

| Variabile | Obbligatoria | Significato |
|---|---|---|
| `LMSTUDIO_URL` | sì | indirizzo dell'API di LM Studio, per esempio `http://localhost:1234/v1` |
| `LMSTUDIO_MODELLO` | sì | identificativo del modello, come restituito da `GET /v1/models` |
| `FUSO_PREDEFINITO` | no | fuso orario IANA predefinito (`Europe/Rome`) |
| `LIMITE_CHIAMATE_STRUMENTO` | no | chiamate allo strumento per domanda (`5`) |
| `PERCORSO_LOG` | no | file di log (`logs/assistente.log`) |

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

## Test automatici

Non richiedono un modello attivo:

```powershell
python -m pytest -v
```

## Come è fatto il grafo

LangGraph descrive il programma come un grafo:

- **stato** (`Stato` in `assistente/grafo.py`): i dati che passano da un nodo all'altro, cioè la
  lista dei messaggi della conversazione e il numero di chiamate allo strumento;
- **nodo**: una funzione che riceve lo stato e restituisce le modifiche da applicare (per esempio
  il nodo `modello` aggiunge la risposta del modello ai messaggi);
- **arco**: il collegamento che dice quale nodo viene eseguito dopo. Un **arco condizionale**
  sceglie il nodo successivo in base allo stato.

Il nodo `modello` antepone le istruzioni di sistema ai messaggi che manda al modello, senza
salvarle nella cronologia. Per ora il grafo è il più semplice possibile:

```
START → modello → END
```
