# Calcolatrice sicura tramite MCP — specifica

Data: 2026-11-09
Stato: approvata (2026-11-09)

Riferimenti: presentazione della lezione 5 (`../LLM_Lez_5.pdf`, Blocco 5 «Proposte di strumenti»,
scheda «Calcolatrice sicura»: *espressioni aritmetiche senza eval, solo operazioni consentite;
allena il rifiuto esplicito di input non validi*); specifiche precedenti
`2026-10-26-assistente-laboratorio-design.md` e `2026-11-09-note-mcp-design.md`, che restano
valide in tutto ciò che qui non cambia.

## 1. Intento

Il prof chiede almeno tre strumenti. L'assistente ha già l'orologio (locale) e le note (server
MCP); la terza capacità è una **calcolatrice sicura**, offerta da un **secondo server MCP**,
separato da quello delle note. È un tool MCP perché l'esercizio della lezione 5 riguarda i tool
MCP (decisione dell'utente).

Il punto dell'esercizio è il **rifiuto esplicito**: l'espressione non viene mai eseguita con
`eval`. Viene analizzata e si accetta solo un insieme chiuso di operazioni; tutto il resto viene
rifiutato con un errore che dice che cosa non va. Il modello deve riferire l'errore vero, non
inventare un risultato.

Successo significa:
- «quanto fa (12,5 + 7) * 3?» → una chiamata al tool della calcolatrice con un'espressione
  equivalente, l'assistente risponde con il risultato restituito dal tool;
- «calcola 10 / 0» → il tool risponde con un errore (divisione per zero), l'assistente lo
  riferisce senza dare un numero;
- un'espressione con funzioni, nomi, attributi, stringhe o altro non ammesso → errore esplicito
  che nomina ciò che non è ammesso;
- `9 ** 9 ** 9` o un'espressione enorme → rifiutata subito, il server non si blocca;
- nome, descrizione e schema del tool arrivano dal server con la discovery, non sono riscritti
  nell'assistente;
- orologio e note continuano a funzionare come prima;
- il log permette di seguire la chiamata (passaggio, nome, argomenti, esito, `tool_call_id`).

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Server MCP `server_calcolatrice/` (FastMCP, stdio) con un solo tool.
- Valutatore aritmetico basato su `ast` con una lista chiusa di nodi e operatori ammessi.
- L'assistente avvia **due** server MCP (note e calcolatrice) e ne scopre i tool; il client MCP
  esistente viene generalizzato invece di essere duplicato.
- Errori distinguibili come per le note: errore dello strumento (espressione non valida),
  errore di collegamento (server non disponibile).
- Funzionamento con Python locale e con Docker Compose.
- Test senza modello; prova reale con LM Studio separata.
- `CLAUDE.md` aggiornato: i server MCP ammessi diventano due (note e calcolatrice), entrambi
  stdio; struttura e comandi aggiornati.

**Non obiettivi (per ora)**
- Funzioni matematiche (`sqrt`, `sin`, `log`…), costanti (`pi`, `e`), variabili, confronti,
  operatori logici e sui bit, numeri complessi.
- Percentuali come operatore («15% di 240»): `%` è il resto della divisione, come in Python
  (vedi 6). Le percentuali le traduce il modello in moltiplicazioni.
- Notazione con virgola decimale nell'espressione: il tool accetta il punto (vedi 4.1).
- Risposte in streaming: sono un lavoro separato, con la sua specifica, dopo questo.
- Streamable HTTP, resources e prompts MCP, altri server.

**Anti-obiettivi**
- Usare `eval`, `exec`, `compile` in modalità esecuzione o librerie che valutano codice.
- Un input non valido che produce comunque un numero (errore mascherato da successo).
- Un'espressione che blocca il server o consuma memoria senza limite.
- Nome, descrizione o schema del tool scritti a mano nel client.
- Il modello che fa il conto «a mente» invece di chiamare il tool, dichiarato come riuscito
  senza prova dal log.

## 3. Vincoli

- Tutti i vincoli delle specifiche precedenti: Python sincrono e moduli piccoli, LM Studio
  sull'host, configurazione da variabili d'ambiente, Conventional Commits in italiano, comandi
  per PowerShell, incrementi piccoli e verificati, una risposta simulata non dimostra l'uso del
  tool.
- Il grafo resta quello attuale: stessi nodi, stessa `instrada`, **un solo limite di passaggi
  condiviso** da tutti gli strumenti (orologio, note, calcolatrice).
- Nessuna dipendenza nuova: bastano la libreria standard (`ast`, `operator`) e `fastmcp`,
  già presente.
- Modello delle prove reali: `google/gemma-4-e2b`.
- Un test esistente verifica che i nomi dei tool delle note non compaiano nel sorgente del
  client: la stessa regola vale per il tool della calcolatrice.

## 4. Comportamento concordato

### 4.1 Contratto del tool (lato server)

| Tool | Argomenti | Risultato | Errori |
|---|---|---|---|
| `calculate` | `expression`: espressione aritmetica come testo | l'espressione e il risultato | espressione vuota; troppo lunga; sintassi non valida; elemento non ammesso; divisione (o resto) per zero; esponente o risultato fuori dai limiti |

**Ammesso** (decisione dell'utente):
- numeri interi e decimali con il punto (`12.5`);
- `+`, `-`, `*`, `/` (divisione vera), `//` (divisione intera), `%` (resto), `**` (potenza);
- parentesi tonde;
- `+` e `-` unari (`-3`, `-(2+1)`).

**Rifiutato**, con un messaggio che nomina l'elemento: tutto il resto, per esempio nomi
(`x`, `pi`), chiamate di funzione (`sqrt(4)`, `__import__(...)`), attributi, indici, stringhe,
liste, confronti, operatori logici e sui bit, `True`/`False`/`None`, numeri complessi.

- La descrizione del tool (scritta nel server) dice quali operazioni sono ammesse, che il
  decimale si scrive con il punto e che `%` è il resto, non la percentuale.
- Gli errori arrivano al client come errori di tool MCP (`ToolError`), mai come risultato
  normale.
- Il valutatore è una funzione pura, testabile senza MCP.

### 4.2 Limiti di sicurezza

- Lunghezza massima dell'espressione (vedi 6).
- Esponente della potenza limitato in valore assoluto (vedi 6): `2 ** 10000` e `9 ** 9 ** 9`
  sono rifiutati **prima** di calcolare.
- Risultato non finito (infinito, NaN) o troppo grande: rifiutato con errore.
- Profondità di annidamento limitata indirettamente dalla lunghezza; un `RecursionError` o
  `MemoryError` dal parser diventa comunque un errore dello strumento, non un crash del server.

### 4.3 Collegamento MCP (lato assistente)

- Trasporto **stdio**: l'assistente avvia il server della calcolatrice come sottoprocesso,
  insieme a quello delle note; l'utente non avvia nulla a parte.
- Il client MCP oggi è `ClientNote`, legato al server delle note. Va reso generico (modulo da
  avviare, variabili d'ambiente, file di log come parametri), con un'istanza per server.
  La conferma dell'eliminazione continua a usare il client delle note.
- All'avvio si leggono i cataloghi di entrambi i server; i tool scoperti, insieme all'orologio,
  vanno a `bind_tools` e al nodo `strumenti`.
- Se uno dei due server non parte: messaggio chiaro che dice **quale** server, e uscita (come
  oggi per le note). Il server già avviato viene chiuso.
- Se un server si interrompe a metà sessione: errore di collegamento solo per i suoi tool; gli
  altri strumenti continuano a funzionare. Nessun riavvio automatico.
- Lo stderr del server della calcolatrice va in `logs/server_calcolatrice.log`.

### 4.4 Istruzioni di sistema

Si aggiunge: per ogni calcolo usare il tool della calcolatrice invece di calcolare a mente;
scrivere i decimali con il punto; tradurre le percentuali in moltiplicazioni (il 15% di 240 →
`240 * 15 / 100`); se il tool restituisce un errore, riferirlo all'utente senza inventare un
risultato.

### 4.5 Log

Nessun cambiamento di formato: la chiamata alla calcolatrice si registra come ogni altro
strumento (passaggio, nome, argomenti, esito, `tool_call_id`). Un'espressione rifiutata è un
«errore dello strumento».

### 4.6 Docker

Il server della calcolatrice gira nello stesso container dell'assistente (va copiato
nell'immagine come `server_note/`). Nessun volume nuovo: la calcolatrice non ha stato.

## 5. Verifiche richieste

**Test automatici (senza modello)**
- valutatore: ogni operazione ammessa, precedenza e parentesi, unari, decimali, potenza;
  rifiuto di ciascuna categoria non ammessa con messaggio che la nomina; divisione e resto per
  zero; espressione vuota, troppo lunga, sintassi errata; esponente oltre il limite rifiutato
  senza calcolare (il test termina subito); risultato infinito;
- un test che verifica che il sorgente del valutatore non usi `eval`/`exec`;
- server: tool chiamato in memoria, successo ed errore come `isError`;
- discovery: avviando davvero il server via stdio, il catalogo contiene il tool con nome,
  descrizione e schema dal server; il nome del tool non compare nel sorgente del client;
- assistente con due server: i tool di entrambi sono disponibili; server della calcolatrice
  che non parte → messaggio che lo nomina e uscita; server terminato a metà sessione → errore
  di collegamento solo per la calcolatrice;
- grafo con modello finto: chiamata alla calcolatrice, `ToolMessage` correlato, risposta finale;
- tutti i test esistenti continuano a passare.

**Prova reale con LM Studio (separata, attivata esplicitamente)**
- In `tests/test_reale_lmstudio.py`: un calcolo semplice con una chiamata a `calculate` e il
  risultato corretto nella risposta; «10 / 0» con errore riferito e nessun numero inventato;
  una percentuale tradotta in moltiplicazione; un controllo che orologio e note funzionino
  ancora.
- Parte manuale: lettura del log; ripetizione con Docker Compose.
- Se `gemma-4-e2b` calcola a mente invece di chiamare il tool: si migliorano istruzioni e
  descrizione; il modello non si cambia; se resta, lo si documenta con gli esempi osservati.

## 6. Scelte fatte da me (da controllare)

- Nome del tool `calculate`, argomento `expression`, in inglese come i tool delle note.
- `%` è il resto della divisione (semantica Python), non la percentuale: un'espressione resta
  aritmetica pura e il modello traduce le percentuali.
- Decimali solo con il punto: `12,5` nell'espressione è un errore di sintassi (in Python sarebbe
  una tupla, che comunque viene rifiutata). Le istruzioni dicono al modello di convertire.
- Lunghezza massima dell'espressione: 200 caratteri.
- Forme dei numeri: solo cifre con punto decimale facoltativo (`12`, `12.5`, `.5`, `5.`).
  Notazione scientifica (`1e5`), separatori (`1_000`), basi diverse (`0x10`, `0b1`) sono
  rifiutate con «notazione numerica non ammessa». Il controllo si fa sul testo originale del
  numero (le informazioni di posizione di `ast` permettono di recuperarlo), perché dopo il parsing
  queste forme sono costanti identiche alle altre.
- Esponente: in valore assoluto al massimo 100. Gli esponenti decimali sono ammessi
  (`2 ** 0.5`); un risultato complesso (`(-8) ** 0.5`) è rifiutato con «risultato non reale».
- Limiti di grandezza su **ogni risultato intermedio**, non solo sul finale: un intero con più
  di 50 cifre, o un decimale non finito o con valore assoluto oltre `1e50`, è rifiutato subito
  («risultato troppo grande»). Vale anche per i numeri scritti nell'espressione. Così con 200
  caratteri non si può costruire un valore enorme moltiplicando potenze.
- Formato del risultato: oggetto JSON come per le note, per esempio
  `{"espressione": "(12.5 + 7) * 3", "risultato": 58.5}`.
- Formato del risultato: intero se il valore è intero (`7 / 7` → `1`), altrimenti decimale
  arrotondato a 12 cifre significative per evitare `0.30000000000000004`.
- Divisione e resto con numeri negativi seguono Python (`-7 // 2` → `-4`).
- Il client generalizzato può chiamarsi `ClientMCP` in `assistente/client_mcp.py` (o restare in
  `note_mcp.py`): nome e collocazione al costruttore, con test e import aggiornati.
- Nuova variabile d'ambiente: nessuna. Il log del server segue `PERCORSO_LOG` come quello delle
  note.
