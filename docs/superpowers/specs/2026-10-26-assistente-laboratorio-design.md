# Assistente del laboratorio — specifica

Data: 2026-10-26
Stato: approvata (2026-10-26)

## 1. Intento

Un chatbot da terminale, scritto in Python, che conversa con un modello locale servito da
LM Studio e può chiedere l'ora attraverso uno strumento orologio. È il progetto di base del corso
«Deep Learning e LLM: costruire chatbot e agenti»: nelle lezioni successive verranno aggiunti
altri strumenti, MCP, workflow e RAG. Per questo il flusso è organizzato in un grafo LangGraph
**scritto a mano e leggibile**, pensato anche per chi usa LangGraph per la prima volta.

Successo significa:
- si conversa in italiano e il modello ricorda ciò che è stato detto nella sessione;
- alle domande sull'ora il modello chiama davvero lo strumento, il programma lo esegue e il
  modello risponde usando il risultato;
- le chiamate allo strumento si vedono in un file di log, separato dalla conversazione;
- tutto funziona sia con Python locale sia con Docker Compose, con LM Studio sull'host;
- i test automatici passano senza un modello attivo.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Ciclo di conversazione da terminale con cronologia in memoria per la sola sessione.
- Strumento orologio con fuso orario, chiamato dal modello tramite tool calling.
- Grafo esplicito: stato, nodi `modello` e `strumenti`, funzione di instradamento.
- Limite alle chiamate dello strumento per ogni domanda.
- Log delle chiamate allo strumento su file.
- Avvio con Docker Compose.
- Test automatici indipendenti dal modello; istruzioni per le prove reali.

**Non obiettivi (per ora)**
- Altri strumenti, MCP, workflow, RAG.
- Persistenza della cronologia tra sessioni.
- Streaming della risposta.
- Interfacce grafiche, servizi cloud, containerizzazione di LM Studio.

**Anti-obiettivi** (renderebbero il lavoro un fallimento anche se "funziona")
- Usare l'agente prefabbricato (`create_react_agent`) o `ToolNode`/`tools_condition` nascondendo
  il funzionamento del grafo.
- Dimostrare l'uso dello strumento solo con risposte simulate.
- Identificativo del modello o indirizzo del server scritti nel codice.
- Credenziali, `.env`, ambienti virtuali, cache o log versionati in Git.

## 3. Vincoli

- Si lavora nella radice della repository `repo-lab-llm/`, nel branch corrente. La cartella
  `lezione3/` contiene un progetto precedente: va ignorata.
- Python, codice sincrono, moduli piccoli. Separazione tra grafo, collegamento al modello,
  strumenti e interfaccia da terminale.
- LM Studio sull'host, tramite l'API compatibile con OpenAI. Modelli disponibili al momento
  (da `GET /v1/models`): `google/gemma-4-e4b`, `google/gemma-4-e2b`.
  Sondaggio preliminare (2026-10-26, una sola richiesta diretta all'API, fuori dal progetto):
  a «Che ore sono a Tokyo?» `google/gemma-4-e4b` ha risposto con `finish_reason: tool_calls` e
  la chiamata `orologio({"fuso_orario": "Asia/Tokyo"})`. Il supporto al tool calling c'è; la sua
  affidabilità sull'intero ciclo resta da verificare nelle prove reali, che si fanno con
  `google/gemma-4-e2b`, il modello usato in classe (non ancora sondato).
- Configurazione solo da variabili d'ambiente; `.env.example` versionato, `.env` escluso.
- Dipendenze motivate e con versioni fissate.
- Comandi documentati anche per PowerShell. Ambiente verificato: Windows 11, Python 3.13,
  Docker 29.8, Docker Compose v5.6.
- Conventional Commits in italiano, incrementi piccoli e verificati prima del commit.

## 4. Comportamento concordato

### 4.1 Terminale
- L'utente scrive una domanda e riceve la risposta **intera** (niente streaming). Durante
  l'attesa compare un'indicazione «sto pensando…».
- Le righe vuote (o solo spazi) vengono ignorate: nessuna chiamata al modello.
- Si esce scrivendo `esci` oppure premendo Ctrl+C.
- Alla chiusura della sessione la cronologia va persa.

### 4.2 Cronologia
- La conversazione (domande, risposte, chiamate e risultati dello strumento) resta in memoria e
  viene passata al modello a ogni domanda, così il modello ricorda le risposte precedenti.
- Nessun salvataggio su disco della conversazione.

### 4.3 Strumento orologio
- Parametro facoltativo: fuso orario in formato IANA (`Europe/Rome`, `Asia/Tokyo`, …).
- Se il parametro manca si usa il fuso predefinito, `Europe/Rome`.
- Restituisce data, ora e fuso usato con lo scarto da UTC (es.
  `2026-10-26 15:42:10 Europe/Rome (UTC+01:00)`).
- È il modello a tradurre una città («Tokyo») nel fuso IANA. Lo strumento conosce solo i fusi.
- Nella risposta all'utente il fuso **non** viene nominato quando è quello predefinito italiano;
  viene indicato quando è diverso (es. «A Tokyo (Asia/Tokyo) sono le 23:42»). Questo si ottiene
  con le istruzioni di sistema; con un modello piccolo va verificato nelle prove reali.

### 4.4 Ciclo dello strumento e limite
- Il grafo: `START → modello`; dopo `modello` l'instradamento sceglie fra
  - risposta finale → `END`;
  - richiesta di strumento sotto il limite → `strumenti` → `modello`;
  - richiesta di strumento con limite raggiunto → `END` con messaggio fisso.
- Limite predefinito: **5 chiamate allo strumento per singola domanda**, configurabile. Il
  contatore si azzera a ogni nuova domanda.
- Al raggiungimento del limite l'utente vede: «Non sono riuscito a completare la risposta
  (limite di passaggi raggiunto). Riprova o riformula la domanda.» La sessione prosegue.

### 4.5 Log
- Le chiamate allo strumento vengono scritte in un file (`logs/assistente.log`), non nel
  terminale della conversazione.
- Ogni chiamata registra: data e ora, nome dello strumento, argomenti ricevuti dal modello,
  risultato o errore, numero di passaggio nella domanda corrente. Il fuso compare sempre, anche
  quello predefinito. Va registrato anche il raggiungimento del limite.
- Il log non contiene il testo della conversazione.
- `logs/` è esclusa da Git. In Docker la cartella è montata dall'host, così il file si legge
  anche dall'esterno del container.

### 4.6 Docker
- Docker Compose avvia solo l'applicazione; LM Studio resta sull'host, raggiunto con
  `host.docker.internal`.
- L'applicazione è interattiva: il servizio deve avere stdin e terminale.
- La configurazione arriva da `.env` tramite Compose.

## 5. Scelte tecniche decise

- **Grafo LangGraph scritto a mano**: nodi `modello` e `strumenti` e funzione di
  instradamento propri, niente agente o nodo strumenti prefabbricati. Scelta fatta insieme
  perché il grafo sia leggibile da un principiante e facile da estendere.
- **Dipendenze**: `langgraph` (grafo), `langchain-openai` (collegamento a LM Studio con
  l'API compatibile OpenAI e formato del tool calling), `tzdata` (database dei fusi, assente
  nell'immagine Docker di Python), `pytest` (solo sviluppo). Versioni fissate nel piano,
  verificate al momento dell'installazione. Nessuna altra dipendenza senza accordo.
- **Variabili d'ambiente** (nomi definitivi decisi nel piano): indirizzo del server LM Studio,
  identificativo del modello, fuso predefinito (`Europe/Rome`), limite di chiamate (`5`),
  percorso del file di log.
- **Test**: `pytest` con un modello finto e un orologio con istante fisso. Prove reali con
  LM Studio e con Docker separate e avviate esplicitamente.

## 6. Verifiche richieste

**Test automatici (senza modello)**
- strumento: fuso predefinito, fuso esplicito, conversione con istante fisso
  (es. 15:00 Roma = 23:00 Tokyo in ottobre/novembre), fuso inesistente;
- instradamento: risposta diretta, richiesta di strumento, limite raggiunto;
- grafo completo con modello finto: domanda → strumento → risposta finale;
- cronologia: il secondo turno riceve i messaggi del primo;
- terminale: righe vuote ignorate, `esci`, Ctrl+C;
- log: una chiamata allo strumento produce una riga con i campi richiesti.

**Prove reali (manuali, documentate nel README)**
- con Python locale e LM Studio; con Docker Compose e LM Studio sull'host;
- domande di controllo: una domanda normale; «che ore sono?» (nessun fuso nominato);
  «e a Tokyo?» (fuso nominato); «cosa ti ho chiesto prima?» (memoria); verifica del log;
  uscita con `esci` e con Ctrl+C.
- Il resoconto finale dice cosa è stato eseguito, con quale esito e cosa resta da provare.

## 7. Scelte lasciate al costruttore (mie proposte, da segnalare)

- `.env.example` contiene solo segnaposto, mai valori reali (decisione dell'utente): per esempio
  `ID_NOME_MODELLO` per il modello e `URL_SERVER_LMSTUDIO` per l'indirizzo. Le variabili
  facoltative (fuso predefinito, limite, percorso del log) compaiono commentate: se assenti, il
  codice usa i valori predefiniti (`Europe/Rome`, `5`, `logs/assistente.log`).
- Il modello usato in classe e nelle prove reali è `google/gemma-4-e2b` (decisione dell'utente).
- Se nelle prove reali il modello sbaglia spesso il ciclo dello strumento: si migliorano le
  istruzioni di sistema e la descrizione dello strumento; il modello non si cambia (è quello del
  corso). Se il problema resta, lo si documenta nel resoconto con gli esempi osservati.
- `esci` riconosciuto senza distinzione fra maiuscole e minuscole e ignorando gli spazi ai lati.
- Ctrl+C, `esci` e chiusura dell'input (Ctrl+Z/Ctrl+D) terminano con un breve saluto, senza
  traceback.
- Conteggio del limite: conta ogni singola chiamata allo strumento (il modello può chiederne più
  d'una in un messaggio). Il controllo avviene prima di eseguire un gruppo di chiamate: se
  eseguirle tutte supererebbe il limite, non se ne esegue nessuna e si termina col messaggio fisso.
- Cronologia dopo il limite: le chiamate rimaste senza esito ricevono un risultato segnaposto
  («non eseguita: limite raggiunto») e il messaggio fisso viene aggiunto come risposta, così la
  cronologia resta valida per l'API e la domanda successiva funziona.
- Indirizzo di LM Studio: `.env` contiene l'indirizzo per l'uso locale (`localhost:1234`);
  `docker-compose.yml` lo sostituisce con `host.docker.internal:1234` per il container. Un solo
  `.env` vale per entrambi i modi di avvio.
- Fuso inesistente: lo strumento non solleva eccezioni ma restituisce al modello un messaggio
  di errore leggibile, che conta come chiamata ai fini del limite.
- LM Studio non raggiungibile o errore del modello: messaggio chiaro all'utente, la sessione
  resta aperta.
- Istruzioni di sistema in italiano.
- Avvio in Docker con `docker compose run --rm <servizio>`.
- Struttura dei moduli, nomi dei file e delle variabili, formato esatto delle righe di log.
- Il README include una breve spiegazione di stato, nodo e arco condizionale in LangGraph.
