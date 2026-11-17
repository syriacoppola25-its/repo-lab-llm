# Router dell'ambito — specifica

Data: 2026-11-17
Stato: approvata (2026-11-17)

Riferimenti: specifiche precedenti `2026-10-26-assistente-laboratorio-design.md`,
`2026-11-09-note-mcp-design.md`, `2026-11-09-calcolatrice-mcp-design.md` e
`2026-11-09-streaming-design.md`, che restano valide in tutto ciò che qui non cambia.

## 1. Intento

La consegna chiede di far crescere il grafo con altri nodi. Il primo passo è un nodo **router**
che lavora prima dell'agente (modello + strumenti) e decide se la domanda rientra nell'ambito
dell'assistente. Le domande fuori ambito ricevono un rifiuto senza che l'agente parta.

Ambito scelto (decisione dell'utente): **assistente d'ufficio**, e solo quello. Quando arriverà
il RAG l'ambito potrà essere allargato; per ora non si anticipa nulla.

Successo significa (evidenze chieste dalla consegna):
- per una domanda **in ambito**, il log riporta la categoria, il motivo e il passaggio all'agente;
- per una domanda **fuori ambito**, l'utente riceve un rifiuto e il log non mostra nessuna
  esecuzione del nodo agente;
- ci sono test con risposte del router simulate per entrambi i percorsi.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Un nodo `router` all'inizio del grafo, con **output strutturato** fatto di due campi:
  - `categoria`: `conversazione` oppure `fuori_ambito`;
  - `motivo`: una frase breve in italiano.
- Un arco condizionale dopo il router:
  - `conversazione` → agente (come oggi);
  - `fuori_ambito` → nodo `rifiuto` → fine;
  - risposta del router non leggibile → nodo `riformula` → fine (decisione dell'utente: in
    questo caso si chiede di riformulare, non si rifiuta).
- La decisione sugli strumenti resta all'agente, come prima (indicazione della consegna):
  il router non sa nulla degli strumenti e non li sceglie.
- Righe di log per ogni decisione del router e per ogni esecuzione del nodo agente.
- Test senza modello con risposte del router simulate; prova reale con LM Studio separata.

**Non obiettivi (per ora)**
- RAG, nuovi strumenti o server MCP: arriveranno nelle prossime lezioni.
- Altre categorie oltre alle due.
- Variabili d'ambiente nuove o un modello diverso per il router.
- Mostrare categoria e motivo all'utente nel terminale: stanno solo nel log.

**Anti-obiettivi** (sarebbe un fallimento anche se funzionasse)
- Un router che decide gli strumenti o che risponde lui alla domanda.
- Un router basato su parole chiave o regole scritte a mano invece che sul modello.
- Il nodo agente eseguito (anche solo avviato) per una domanda fuori ambito.
- Un'eccezione che chiude la sessione quando il modello risponde al router con un JSON storto.
- Nuove dipendenze.

## 3. L'ambito

Il router classifica come **`conversazione`**:
- le richieste che usano gli strumenti già presenti: data e ora (anche di altre città), note
  (salvare, elencare, eliminare), calcoli;
- il lavoro d'ufficio: scrivere o rivedere mail, riassumere o riformulare testi, organizzare la
  giornata, riunioni e scadenze, chiarire termini di lavoro;
- saluti, ringraziamenti, «che cosa sai fare?» e i seguiti di una conversazione già in ambito
  («e a Tokyo?», «ok grazie») (scelta mia).

Il router classifica come **`fuori_ambito`** (decisione dell'utente): sport, gossip, storie o
contenuti di fantasia, consigli medici, e in generale tutto ciò che non riguarda il lavoro
d'ufficio. Anche ricette e cucina sono fuori ambito (decisione dell'utente).

Le istruzioni del router riportano questo elenco, con qualche esempio per categoria (gli esempi
precisi li sceglie il costruttore). Devono chiedere al modello di classificare **l'ultima
domanda dell'utente**, usando i messaggi precedenti solo come contesto per capire i seguiti.

## 4. Il grafo

```
START → router ──conversazione──→ agente ──fine──────→ END
           │                        ↑  │ ──limite──→ limite → END
           │                        │  └─strumenti─→ strumenti
           │                        └───────────────────┘
           ├──fuori_ambito──→ rifiuto ──→ END
           └──non_leggibile─→ riformula ─→ END
```

- Il nodo oggi chiamato `modello` si chiama `agente` (scelta mia: rende riconoscibile nel grafo
  e nel log il nodo che la consegna chiama «agente»). Il suo comportamento non cambia.
- Il ciclo agente/strumenti/limite resta identico.
- Il router gira **una volta per domanda**, all'inizio. Dopo un giro di strumenti si torna
  all'agente, non al router.
- Lo stato riceve un campo in più con la decisione del router (categoria e motivo, oppure
  l'indicazione che non era leggibile), usato dall'arco condizionale. Il nome e la forma esatta
  li sceglie il costruttore.
- `costruisci_grafo` riceve il router come parametro **obbligatorio** (decisione dell'utente):
  il grafo parte sempre dal router. I test esistenti vanno adattati passando un router finto
  che classifica come `conversazione`.

## 5. Il router

- Usa lo **stesso modello di LM Studio** già configurato (decisione dell'utente), con una
  propria istanza **senza strumenti collegati** e con le proprie istruzioni di sistema.
- L'output strutturato si ottiene con `with_structured_output` di LangChain e uno **schema JSON
  scritto come dizionario** (`categoria` con i due valori ammessi, `motivo` stringa, entrambi
  obbligatori). Scelta mia: lo schema a dizionario evita di importare direttamente `pydantic`,
  che oggi non è tra le dipendenze dichiarate. Il metodo (per esempio `json_schema`, che LM
  Studio supporta) lo verifica il costruttore con la prova reale. Se `json_schema` non funziona
  con il modello, il ripiego è far scrivere il JSON al modello tramite le istruzioni e leggerlo e
  controllarlo con il nostro codice. **Non** si usa `function_calling`, che collegherebbe al
  router uno strumento nascosto (scelta mia).
- Il router **non va in streaming**: la sua risposta non compare nel terminale.
- Il router riceve le istruzioni di sistema e la conversazione della sessione **ridotta ai
  messaggi di testo dell'utente e dell'assistente** (senza chiamate a strumenti né risultati),
  con l'ultima domanda in fondo (scelta mia: servono i seguiti ma non i dettagli degli
  strumenti, che possono confondere un modello piccolo).

**Quando la risposta del router è «non leggibile»**: il JSON non si legge, manca un campo,
`categoria` non è uno dei due valori, oppure `motivo` è vuoto. In tutti questi casi si va al
nodo `riformula`. Il controllo dei valori lo fa il nostro codice, non solo lo schema.

**Altri errori** (LM Studio spento, timeout, errori HTTP come un 400): non sono «non leggibile».
L'eccezione risale come oggi per l'agente e il terminale mostra il messaggio d'errore già
esistente; la domanda non entra nella cronologia (scelta mia). Solo i fallimenti di lettura e di
controllo della risposta vanno a `riformula`.

## 6. Rifiuto e riformula

- Entrambi i nodi rispondono con un **messaggio fisso** (scelta mia, il testo esatto lo può
  ritoccare il costruttore):
  - rifiuto: «Mi dispiace, posso aiutarti solo con il lavoro d'ufficio (mail, testi,
    organizzazione, note, orari, calcoli).»
  - riformula: «Non ho capito bene la richiesta: puoi riformularla?»
- Il messaggio esce come evento di testo, quindi il terminale lo stampa come una normale
  risposta (`Assistente: …`). Il terminale non cambia.
- La domanda e il messaggio di risposta **entrano nella cronologia** (decisione dell'utente per
  il rifiuto; scelta mia anche per riformula, per coerenza).

## 7. Log

Nello stesso file di oggi (`logs/assistente.log`), con lo stesso logger. Il formato esatto lo
sceglie il costruttore, ma devono comparire:
- una riga del router con `categoria`, `motivo` e il nodo successivo, per esempio
  `router categoria=conversazione motivo=... prossimo=agente` oppure
  `router categoria=fuori_ambito motivo=... prossimo=rifiuto`;
- per la risposta non leggibile, una riga di livello `WARNING` con il testo grezzo ricevuto
  (accorciato se lungo) e `prossimo=riformula`;
- una riga `nodo=agente` (o simile) **a ogni esecuzione** del nodo agente.

Così per una domanda fuori ambito il log mostra la riga del router con `prossimo=rifiuto` e
nessuna riga dell'agente. Le righe degli strumenti restano come oggi.

## 8. Che cosa resta com'è

Strumenti, server MCP, conferma di `delete_note`, limite di passaggi, streaming, eventi
(`Testo`, `Strumento`, `Fine`), terminale, configurazione, Docker. Le istruzioni di sistema
dell'agente non cambiano.

## 9. Test e verifiche

**Senza modello** (con un router finto che restituisce risposte preparate):
- `conversazione` → l'agente risponde; nel log compaiono la riga del router (categoria, motivo,
  `prossimo=agente`) e la riga dell'agente.
- `fuori_ambito` → la risposta è il messaggio di rifiuto; il modello dell'agente **non riceve
  nessuna chiamata**; il log non contiene righe dell'agente.
- risposta non leggibile (JSON storto, categoria sconosciuta, motivo vuoto) → messaggio
  riformula, agente non chiamato, riga `WARNING` nel log.
- il rifiuto entra nella cronologia; una domanda successiva in ambito arriva all'agente con la
  cronologia completa.
- dopo un giro di strumenti il router non viene richiamato.
- il router riceve solo messaggi di testo utente/assistente, senza chiamate a strumenti.
- l'errore di collegamento del router si propaga come eccezione.
- i test esistenti continuano a passare (adattati con un router finto `conversazione`).

**Prova reale con LM Studio** (separata, `PROVA_LMSTUDIO=1`, `google/gemma-4-e4b`):
- una domanda in ambito (per esempio una mail o un'ora) → log con `categoria=conversazione`,
  motivo e passaggio all'agente;
- una domanda fuori ambito (per esempio il risultato di una partita) → rifiuto e nessuna riga
  dell'agente nel log;
- una ricetta → fuori ambito.

La prova reale **verifica** la classificazione (decisione dell'utente): se il modello classifica
male uno dei casi, il test fallisce e l'incremento non si chiude finché le istruzioni del router
non vengono sistemate. Una risposta simulata non dimostra che il modello classifichi bene: lo
dice solo la prova reale, e il resoconto riporta l'esito osservato.

## 10. Documentazione

README (ambito, grafo, log del router, prova reale) e CLAUDE.md (struttura del grafo, se
cambiano moduli).

## 11. Lasciato al costruttore

- In quale modulo stanno il router e le sue istruzioni (per esempio un nuovo `router.py`, oppure
  `modello.py` e `grafo.py`).
- Gli esempi nelle istruzioni del router e il testo esatto dei messaggi fissi.
- Il formato preciso delle righe di log, nel rispetto della sezione 7.
- Il nome e la forma del campo di stato con la decisione del router.
- Come finge il router nei test (un oggetto nuovo in `tests/finti.py` o un adattamento di
  `ModelloFinto`).
