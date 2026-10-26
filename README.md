# Assistente del laboratorio

Chatbot da terminale in Python per il corso «Deep Learning e LLM: costruire chatbot e agenti».
Il flusso della conversazione è un grafo LangGraph scritto a mano.

Stato attuale: il grafo risponde con una frase fissa; il collegamento a LM Studio arriverà
nell'incremento successivo.

## Preparare l'ambiente (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -c "import langgraph, langchain_openai, tzdata; print('ok')"
```

L'ultimo comando deve stampare `ok`.

## Avvio

```powershell
python -m assistente
```

- scrivi una domanda e premi Invio: compare `sto pensando…` e poi la risposta;
- le righe vuote vengono ignorate;
- per uscire scrivi `esci` (anche in maiuscolo) oppure premi Ctrl+C.

La cronologia della conversazione resta in memoria solo finché la sessione è aperta.

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

Per ora il grafo è il più semplice possibile:

```
START → modello → END
```
