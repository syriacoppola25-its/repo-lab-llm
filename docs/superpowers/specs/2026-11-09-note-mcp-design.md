# Note persistenti tramite MCP — specifica

Data: 2026-11-09
Stato: approvata (2026-11-09)

Riferimenti: presentazione della lezione 5 «MCP: dalle funzioni agli strumenti condivisi»
(`../LLM_Lez_5.pdf`, in particolare slide 20–24, 26, 30–31); specifica di base
`2026-10-26-assistente-laboratorio-design.md`, che resta valida in tutto ciò che qui non cambia.

## 1. Intento

L'assistente del laboratorio impara a gestire **note che sopravvivono alla sessione**: aggiungerle,
rileggerle, eliminarle, parlando in italiano. La capacità non è una funzione interna ma un
**server MCP separato**: l'assistente ne scopre gli strumenti (discovery) e li invoca tramite
un client MCP. È l'esercizio di laboratorio della lezione 5: dimostrare con evidenze che una
domanda attiva un tool MCP, il risultato torna al modello e viene usato nella risposta.

A differenza dell'orologio, questo strumento **produce effetti**: l'eliminazione è irreversibile,
per questo è protetta da una conferma chiesta dal programma.

Successo significa:
- «ricordami che ho un meeting giovedì 4 alle 10» → una sola chiamata `add_note`, l'assistente
  conferma la nota creata con il suo numero;
- «fammi vedere le note» → chiamata `list_notes`, elenco numerato;
- «cancella la nota dell'appuntamento di giovedì 4» → il modello trova il numero con
  `list_notes`, chiede `delete_note`; il programma mostra la nota nel terminale e cancella solo
  dopo un `s` dell'utente;
- «elimina la nota 99» (inesistente) → errore chiaro, nessuna eliminazione;
- chiudendo e riaprendo l'assistente le note ci sono ancora (anche con Docker);
- nome, descrizione e schema degli strumenti arrivano dal server, non sono riscritti nell'agente;
- il log permette di seguire ogni chiamata: richiesta del modello, argomenti, esito, correlazione
  con il `tool_call_id`.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Server MCP delle note con tre tool: `add_note(text)`, `list_notes(limit)`, `delete_note(note_id)`.
- Archivio SQLite su file, escluso da Git.
- Client MCP nell'assistente: discovery dal server, conversione in strumenti LangChain,
  invocazione dal nodo `strumenti` del grafo esistente.
- Conferma dell'eliminazione chiesta dal programma (non dal modello).
- Errori distinguibili: errore dello strumento (es. ID inesistente), errore di collegamento
  (server non disponibile), argomenti non validi.
- Funzionamento con Python locale e con Docker Compose.
- Test senza modello; prova reale con LM Studio separata.

**Non obiettivi (per ora)**
- Spostare l'orologio su MCP: resta una funzione locale (slide 3: una funzione interna semplice
  può restare locale anche quando altri strumenti usano MCP).
- Streamable HTTP, più server MCP, resources e prompts MCP, modifica di una nota esistente,
  scadenze/promemoria con date vere, ricerca nelle note: sono estensioni facoltative.
- Persistenza della cronologia della conversazione: resta solo per la sessione.
- Interpretare le date scritte nella nota («giovedì 4»): il testo si salva così com'è.

**Anti-obiettivi**
- Nome, descrizione o schema dei tool scritti a mano nel client: annullerebbe la discovery.
- Un'eliminazione eseguita senza il `s` dell'utente, o una nota sbagliata eliminata perché il
  modello ha indovinato un numero.
- Un errore mascherato da successo (es. «nota eliminata» quando l'ID non esiste).
- Dimostrare l'uso del tool solo con risposte simulate.
- Rendere asincrono tutto il progetto per far posto al client MCP: grafo e terminale restano
  sincroni.
- Versionare il file delle note.

## 3. Vincoli

- Tutti i vincoli della specifica di base (Python sincrono e moduli piccoli, LM Studio sull'host,
  configurazione da variabili d'ambiente, Conventional Commits in italiano, comandi per
  PowerShell, incrementi piccoli e verificati).
- Il grafo resta scritto a mano: stessi nodi `modello`, `strumenti`, `limite`, stessa funzione
  `instrada`, stesso limite di passaggi per domanda (le chiamate MCP contano come le altre).
- Modello delle prove reali: `google/gemma-4-e2b` (quello del corso).
- `CLAUDE.md` oggi dice di non anticipare MCP: va aggiornato (struttura, confini, comandi) quando
  il lavoro parte.

## 4. Comportamento concordato

### 4.1 Contratto dei tool (lato server)

| Tool | Argomenti | Risultato | Errori |
|---|---|---|---|
| `add_note` | `text`: testo della nota | nota creata con numero (ID) e data di creazione | testo vuoto/solo spazi; più lungo di 500 caratteri; archivio non accessibile |
| `list_notes` | `limit`: numero massimo di note (facoltativo) | elenco ordinato con ID, data e testo; lista vuota dichiarata come tale | `limit` fuori intervallo; archivio non accessibile |
| `delete_note` | `note_id`: numero della nota | conferma dell'eliminazione con il testo eliminato | ID inesistente; archivio non accessibile |

- Le descrizioni dei tool (scritte nel server) devono dire chiaramente che `add_note` e
  `delete_note` modificano l'archivio e che `delete_note` vuole il numero preso da `list_notes`.
- Il server valida gli argomenti da sé: lo schema controlla la forma, il server controlla il
  contenuto (testo vuoto, ID esistente).
- Gli errori arrivano al client come errori di tool MCP, non come risultati normali.

### 4.2 Conferma dell'eliminazione (lato host)

- Quando il modello chiede `delete_note`, il nodo `strumenti` **prima** di invocare il server
  chiama una funzione di conferma passata al grafo.
- Nel terminale la conferma mostra la nota e chiede, per esempio:
  `Eliminare la nota 3: «meeting giovedì 4 alle 10»? (s/n)`.
- Solo `s` (o `si`/`sì`, senza distinzione di maiuscole) esegue l'eliminazione. Qualsiasi altra
  risposta la annulla: il modello riceve come risultato «eliminazione annullata dall'utente» e lo
  riferisce.
- Nei test la funzione di conferma si sostituisce con una risposta fissa.

### 4.3 Collegamento MCP

- Trasporto **stdio**: l'assistente avvia il server delle note come sottoprocesso; l'utente non
  deve avviarlo a parte.
- All'avvio l'assistente chiede il catalogo al server (`tools/list`) e lo converte in strumenti
  LangChain; questi, insieme all'orologio locale, vanno a `bind_tools` e al nodo `strumenti`.
- Il collegamento resta aperto per tutta la sessione e si chiude all'uscita (`esci`, Ctrl+C,
  fine input) senza traceback.
- Con stdio, `stdout` del server è riservato al protocollo: eventuali log del server vanno su
  `stderr` o su file.

### 4.4 Istruzioni di sistema

Si aggiungono indicazioni sulle note: usare `add_note` quando l'utente chiede di ricordare
qualcosa; per eliminare una nota descritta a parole, cercarne il numero con `list_notes` e poi
chiamare `delete_note`, senza inventare numeri; non chiedere conferma nel testo, perché la chiede
il programma.

### 4.5 Log

- Ogni chiamata a uno strumento (locale o MCP) registra anche il `tool_call_id`, oltre a ciò che
  già registra (passaggio, nome, argomenti, risultato o errore).
- Il tipo di esito è riconoscibile: successo, errore dello strumento, errore di collegamento,
  argomenti non validi, eliminazione confermata, eliminazione annullata.
- Il log continua a non contenere il testo della conversazione (gli argomenti dei tool, quindi
  anche il testo delle note, sì: servono come evidenza).

### 4.6 Archivio e Docker

- File SQLite predefinito `dati/note.db`, percorso configurabile da variabile d'ambiente;
  cartella `dati/` esclusa da Git; la cartella si crea se manca.
- In Docker il server delle note gira nello stesso container dell'assistente; `./dati` è montata
  come volume, così le note restano dopo `docker compose run --rm`.

### 4.7 Dipendenze nuove

- `fastmcp` — framework per il server MCP (come nella slide 20).
- `langchain-mcp-adapters` — client/adattatore che converte il catalogo MCP in strumenti
  LangChain.
- Versioni fissate nel piano, verificate al momento dell'installazione. Nessun'altra dipendenza
  senza accordo.

## 5. Verifiche richieste

**Test automatici (senza modello)**
- server: aggiunta, elenco (anche vuoto, con `limit`), eliminazione; testo vuoto e troppo lungo;
  ID inesistente senza effetti; persistenza riaprendo lo stesso file; archivio in cartella
  temporanea;
- discovery: avviando davvero il server via stdio, il catalogo contiene i tre tool con nome,
  descrizione e schema provenienti dal server;
- invocazione diretta tramite client MCP con input noto;
- grafo con modello finto e strumenti MCP: chiamata, `ToolMessage` correlato con lo stesso
  `tool_call_id`, risposta finale;
- conferma: `s` elimina, `n` annulla senza eliminare, e in entrambi i casi il modello riceve un
  esito;
- errore di collegamento distinto dall'errore dello strumento;
- i test esistenti (orologio, instradamento, limite, cronologia, terminale, log) continuano a
  passare.

**Prova reale con LM Studio (separata, attivata esplicitamente)**
- Parte automatica, nello stile dell'attuale `tests/test_reale_lmstudio.py` (attivata con
  `PROVA_LMSTUDIO=1`): server delle note vero su archivio temporaneo, modello vero, conferma
  sostituita da una risposta fissa. Casi: aggiunta con una sola `add_note`; elenco;
  eliminazione descritta a parole (`list_notes` poi `delete_note`); «elimina la nota 99»;
  una domanda sull'ora per verificare che l'orologio funzioni ancora.
- Parte manuale, con i passi scritti nel README e l'esito riportato nel resoconto: conferma
  interattiva `s` e `n` nel terminale; riavvio dell'assistente e rilettura delle note; lettura
  del log (chiamata, argomenti, esito, `tool_call_id`); ripetizione con Docker Compose.
- Se `gemma-4-e2b` sbaglia la sequenza (es. inventa il numero invece di usare `list_notes`): come
  nella specifica di base si migliorano istruzioni di sistema e descrizioni dei tool, il modello
  non si cambia; se il problema resta lo si documenta con gli esempi osservati, senza dichiarare
  completato il percorso.

## 6. Scelte fatte da me (da controllare)

- Limite di 500 caratteri per il testo di una nota.
- `list_notes`: ordine per ID crescente (ordine di creazione); `limit` predefinito 20, ammesso
  da 1 a 100.
- Data di creazione nel fuso predefinito dell'assistente (`Europe/Rome`), passato al server
  tramite variabile d'ambiente, così in Docker (dove il sistema è in UTC) l'ora resta quella
  italiana.
- Nome della cartella del server (es. `server_note/`) e del modulo client: al costruttore.
- La conferma viene chiesta **sempre** prima di ogni `delete_note`, senza eccezioni. Il testo da
  mostrare si ottiene dal server chiamando `list_notes` (con il `limit` massimo) tramite lo
  stesso client MCP: se la nota è nell'elenco la conferma mostra numero e testo, altrimenti solo
  il numero («Eliminare la nota 99? (s/n)»). Con `s` la chiamata va al server, che per un ID
  inesistente risponde con l'errore senza eliminare nulla. Così nessun caso porta a
  un'eliminazione senza `s`, non serve un quarto tool e l'assistente non legge il file SQLite.
- Se il server delle note non parte all'avvio: messaggio chiaro e uscita, come per una
  configurazione errata (niente modalità ridotta senza note).
- Se il server si interrompe a metà sessione: nessun riavvio automatico. La sessione continua;
  ogni chiamata ai tool delle note restituisce al modello un «errore di collegamento» (distinto
  dagli errori dello strumento), registrato nel log. L'orologio continua a funzionare.
- Ctrl+C durante la domanda di conferma chiude la sessione come altrove, senza eliminare.
- Come gestire l'asincronia del client MCP con un grafo sincrono: al costruttore, con il vincolo
  che grafo e terminale restino sincroni e che il collegamento resti aperto per la sessione.
