# Risposte in streaming — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** far uscire la risposta dell'assistente a pezzi, con una riga `Interrogando lo strumento <nome>…` per ogni strumento eseguito, attraverso eventi indipendenti dal terminale.

**Architecture:** il nodo `modello` del grafo legge il modello con `.stream(...)`, scrive ogni pezzo di testo con `get_stream_writer()` (evento «custom» di LangGraph) e ricompone il messaggio intero per lo stato; il nodo `strumenti` scrive un evento prima di eseguire ciascuna richiesta; il nodo `limite` scrive il suo messaggio come testo. Un modulo nuovo `assistente/flusso.py` traduce `grafo.stream(...)` in tre eventi (`Testo`, `Strumento`, `Fine`); il terminale li stampa. `grafo.invoke` resta valido.

**Tech Stack:** Python 3.13, LangGraph 1.2.17 (`stream_mode=["custom", "values"]`, `langgraph.config.get_stream_writer`), `langchain-openai` 1.7.2, pytest. Nessuna dipendenza nuova.

**Spec:** `docs/superpowers/specs/2026-11-09-streaming-design.md`

## Global Constraints

- Branch `dev`; push e passaggio su `main` solo su richiesta dell'utente (prima `dev`, poi `main`).
- **Fermarsi dopo ogni task** e attendere l'utente, con resoconto: cosa eseguito, esito, cosa resta da provare.
- Streaming vero: nessun testo trattenuto in attesa di sapere se arriva uno strumento; niente risposta ottenuta intera e poi spezzata.
- Il grafo non stampa nulla: gli eventi non dipendono dal terminale.
- Riga strumento: `Interrogando lo strumento <nome>…` (carattere `…` come in `sto pensando…`), nome originale del tool; nessuna traduzione, nessun nome di tool nel sorgente nuovo.
- Il testo scritto dal modello nello stesso turno di una chiamata a strumento si mostra.
- Messaggi di errore del terminale identici a oggi: `Errore: impossibile ottenere una risposta dal modello (<Tipo>). Controlla che LM Studio sia avviato.`
- Righe di log, formato e istruzioni di sistema invariati; codice sincrono; nessuna nuova dipendenza né variabile d'ambiente.
- `grafo.invoke` deve continuare a funzionare (test esistenti).
- Conventional Commits in italiano, chiusi da `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`; prima di ogni commit `git status`, controllo del diff, staging selettivo.
- PowerShell 5.1: per riscrivere file usare Edit/Write (niente `Set-Content`, aggiunge il BOM).

## Review Focus

- Modello che risponde con testo vuoto: nessun `Assistente: ` vuoto (test in Task 4).
- Errore del modello a metà risposta: testo già stampato resta, a capo, messaggio d'errore, domanda fuori dalla cronologia (test in Task 4).
- Errore dopo che uno strumento è già stato eseguito nella stessa domanda: la cronologia non cambia (test in Task 4).
- Richiesta con argomenti non leggibili (`invalid_tool_calls`): ha comunque un nome e genera la riga strumento (test in Task 2).
- Conferma `n` su `delete_note`: la riga strumento precede la domanda `s/n` (test in Task 2).

---

### Task 1: Il nodo `modello` legge a pezzi e scrive eventi di testo

**Files:**
- Modify: `tests/finti.py` (aggiungere `ModelloFinto.stream`), `assistente/grafo.py` (`nodo_modello`)
- Test: `tests/test_grafo.py`

**Interfaces:**
- Produces: `ModelloFinto.stream(messaggi) -> Iterator[AIMessageChunk]`: registra `messaggi` in `ricevuti` come `invoke`, solleva se la risposta preparata è un'eccezione, altrimenti produce il contenuto spezzato in più chunk (per parole, mantenendo gli spazi) e, in un ultimo chunk, le chiamate a strumenti come `tool_call_chunks` (anche le `invalid_tool_calls`, con `args` testuale grezzo). Le risposte con contenuto vuoto producono solo l'ultimo chunk (o nessun chunk se non hanno chiamate). `invoke` resta.
- Produces: evento custom `{"tipo": "testo", "testo": str}`, scritto dal nodo `modello` per ogni chunk con contenuto non vuoto.
- Produces: il nodo restituisce comunque un `AIMessage` completo (`message_chunk_to_message`); se il modello non produce alcun chunk, `AIMessage("")`.

- [ ] **Step 1: Scrivere i test falliti** in `tests/test_grafo.py`:
  - `test_nodo_modello_scrive_testo_a_pezzi`: `ModelloFinto([AIMessage("uno due tre")])`, `grafo.stream({"messaggi": [HumanMessage("ciao")], "chiamate_strumento": 0}, stream_mode="custom")` → lista con più di un evento, tutti `{"tipo": "testo", ...}`, e la concatenazione dei `testo` è `"uno due tre"`.
  - `test_stream_conserva_chiamate_a_strumenti`: una risposta `AIMessage("Ora calcolo", tool_calls=[chiamata("1")])` seguita da `AIMessage("ok")`; con `grafo.invoke` il messaggio dopo la domanda ha `content == "Ora calcolo"` e `tool_calls` uguali a `[chiamata("1")]`.
  - `test_stream_conserva_chiamate_non_leggibili`: la risposta con `invalid_tool_calls=[malformata]` (come a `tests/test_grafo.py:131`) viene ancora chiusa da un `ToolMessage` di errore e il grafo termina con `ok`.
  - `test_stream_risposta_vuota`: `ModelloFinto([AIMessage("")])` → `invoke` termina, ultimo messaggio `content == ""`, nessun evento di testo.
- [ ] **Step 2: Eseguire** `python -m pytest tests/test_grafo.py -q` → i nuovi test falliscono (`stream` assente o nessun evento); gli esistenti passano.
- [ ] **Step 3: Implementare** `ModelloFinto.stream` in `tests/finti.py` come descritto sopra.
- [ ] **Step 4: Implementare** in `assistente/grafo.py` il nuovo `nodo_modello`: `for pezzo in modello.stream(messaggi)`, accumulando con `+`; per ogni pezzo con `content` non vuoto (stringa) chiamare `get_stream_writer()({"tipo": "testo", "testo": pezzo.content})`; alla fine `message_chunk_to_message(totale)` oppure `AIMessage("")`. Aggiornare il diagramma in testa al modulo solo se serve (la forma del grafo non cambia).
- [ ] **Step 5: Eseguire** `python -m pytest -q` → tutta la suite passa (nessun test esistente cambia: il modello finto ora ha `stream`).
- [ ] **Step 6: Commit** `feat(grafo): il nodo modello legge la risposta a pezzi` (file: `tests/finti.py`, `assistente/grafo.py`, `tests/test_grafo.py`).

### Task 2: Eventi strumento e messaggio del limite

**Files:**
- Modify: `assistente/grafo.py` (`nodo_strumenti`, `nodo_limite`)
- Test: `tests/test_grafo.py`

**Interfaces:**
- Consumes: Task 1 (`get_stream_writer`, formato degli eventi custom).
- Produces: evento custom `{"tipo": "strumento", "nome": str}`, scritto da `nodo_strumenti` **prima** di `esegui(richiesta)` per ogni richiesta (anche con argomenti non leggibili o strumento sconosciuto), usando `richiesta["name"]`.
- Produces: `nodo_limite` scrive `{"tipo": "testo", "testo": MESSAGGIO_LIMITE}`; non scrive eventi strumento.

- [ ] **Step 1: Scrivere i test falliti** in `tests/test_grafo.py` (tutti con `stream_mode="custom"`, eventi filtrati per `tipo`):
  - `test_evento_strumento_prima_del_risultato`: una chiamata a `orologio` poi risposta finale → sequenza di tipi `["strumento", "testo", ...]` con il primo evento `{"tipo": "strumento", "nome": "orologio"}`.
  - `test_due_strumenti_due_eventi`: due richieste nella stessa risposta → due eventi strumento, nell'ordine delle richieste.
  - `test_evento_per_chiamata_non_leggibile`: con `invalid_tool_calls=[malformata]` compare un evento strumento con il nome della chiamata.
  - `test_evento_strumento_precede_la_conferma`: con una funzione di conferma che, quando chiamata, aggiunge `"conferma"` a una lista condivisa con gli eventi raccolti nel ciclo, l'ordine osservato è `strumento` (per `delete_note`) poi `conferma`; con risposta `False` la riga resta (evento presente).
  - `test_limite_scrive_testo_e_nessuno_strumento`: oltre il limite (come a `tests/test_grafo.py:29`) → l'ultimo evento è `{"tipo": "testo", "testo": MESSAGGIO_LIMITE}` e il numero di eventi strumento è pari alle richieste eseguite, non a quelle bloccate.
- [ ] **Step 2: Eseguire** `python -m pytest tests/test_grafo.py -q` → i nuovi test falliscono.
- [ ] **Step 3: Implementare** le due scritture in `assistente/grafo.py` (stesso `get_stream_writer()` del Task 1, recuperato nel corpo del nodo).
- [ ] **Step 4: Eseguire** `python -m pytest -q` → suite verde.
- [ ] **Step 5: Commit** `feat(grafo): eventi per strumenti e messaggio del limite`.

### Task 3: Modulo degli eventi (`assistente/flusso.py`)

**Files:**
- Create: `assistente/flusso.py`
- Test: `tests/test_flusso.py`

**Interfaces:**
- Consumes: eventi custom dei Task 1-2; `grafo.stream(..., stream_mode=["custom", "values"])` produce tuple `(modo, dato)`.
- Produces (dataclass congelate): `Testo(testo: str)`, `Strumento(nome: str)`, `Fine(messaggi: list[BaseMessage])`; alias `Evento = Testo | Strumento | Fine`.
- Produces: `def risposta_in_streaming(grafo, messaggi: list[BaseMessage]) -> Iterator[Evento]`: parte con stato `{"messaggi": messaggi, "chiamate_strumento": 0}`; traduce ogni evento custom in `Testo`/`Strumento` appena arriva; tiene l'ultimo stato `values` e, alla fine, produce un solo `Fine(stato["messaggi"])`. Le eccezioni del grafo si propagano senza `Fine`.

- [ ] **Step 1: Scrivere i test falliti** in `tests/test_flusso.py` (grafo vero con `ModelloFinto`, senza terminale):
  - `test_risposta_semplice`: eventi `Testo` (più di uno) e un solo `Fine` finale; la concatenazione dei testi è la risposta; `Fine.messaggi[-1].content` uguale; `Fine.messaggi` inizia con i messaggi passati.
  - `test_con_strumento`: ordine `Testo*` (preambolo), `Strumento("orologio")`, `Testo*`, `Fine`.
  - `test_fine_porta_la_cronologia_come_invoke`: `Fine.messaggi` uguale (per contenuto e tipo) a `grafo.invoke(...)["messaggi"]` sullo stesso scenario.
  - `test_streaming_vero`: con un modello il cui `stream` è un generatore che annota in una lista quando produce ogni pezzo, il primo `Testo` arriva prima che il modello abbia prodotto l'ultimo pezzo (interleaving osservabile nella lista condivisa).
  - `test_errore_si_propaga_senza_fine`: modello che solleva `ConnectionError` → `pytest.raises(ConnectionError)` consumando il generatore, nessun `Fine` prodotto.
- [ ] **Step 2: Eseguire** `python -m pytest tests/test_flusso.py -q` → falliscono (modulo assente).
- [ ] **Step 3: Implementare** `assistente/flusso.py` con i tipi e `risposta_in_streaming` come sopra.
- [ ] **Step 4: Eseguire** `python -m pytest -q` → suite verde.
- [ ] **Step 5: Commit** `feat(flusso): eventi di testo, strumento e fine`.

### Task 4: Il terminale stampa gli eventi

**Files:**
- Modify: `assistente/terminale.py` (`esegui_sessione`), `tests/test_terminale.py`
- Test: `tests/test_terminale.py`

**Interfaces:**
- Consumes: `risposta_in_streaming`, `Testo`, `Strumento`, `Fine` (Task 3).
- Produces: `esegui_sessione(grafo, leggi=input, scrivi=print, scrivi_pezzo=...)` dove `scrivi_pezzo: Callable[[str], None]` stampa senza a capo e con flush (default: `print(testo, end="", flush=True)`). Costanti nuove: `PREFISSO_RISPOSTA = "Assistente: "` e `def riga_strumento(nome: str) -> str` che restituisce `f"Interrogando lo strumento {nome}…"`.
- Regole (dallo spec §3-4): `sto pensando…` come oggi; `PREFISSO_RISPOSTA` una volta prima del primo pezzo di ciascun tratto di testo; i pezzi sulla stessa riga; prima della riga strumento, se c'era testo in corso, si va a capo (i test ricompongono l'uscita e fissano la sequenza di caratteri dello spec §3; come ottenerla con `scrivi` e `scrivi_pezzo` è del costruttore); la riga strumento su riga sua; dopo lo strumento il prefisso si ristampa al nuovo testo; testo vuoto non stampa nulla; a fine risposta a capo se c'era testo in corso. Errore: si chiude l'eventuale riga in corso, poi il messaggio d'errore invariato; la cronologia resta quella di prima della domanda. La cronologia nuova è `Fine.messaggi`.

- [ ] **Step 1: Adattare e scrivere i test falliti** in `tests/test_terminale.py`: `avvia(...)` raccoglie in un'unica lista l'uscita nell'ordine, sia da `scrivi` sia da `scrivi_pezzo`, per poterne verificare la sequenza; i test esistenti (`test_righe_vuote_ignorate`, `test_esci_...`, `test_ctrl_c_...`, `test_fine_input_...`, `test_ctrl_c_durante_attesa`, `test_cronologia_conservata`, `test_errore_modello_non_interrompe`) restano con lo stesso significato; `test_mostra_pensando_e_risposta` diventa la verifica che `PENSANDO` precede il testo della risposta. Nuovi:
  - `test_testo_a_pezzi_con_prefisso_una_volta`: `"uno due tre"` produce più pezzi, `PREFISSO_RISPOSTA` compare una sola volta e il testo ricomposto è `"uno due tre"`.
  - `test_riga_strumento_su_riga_sua`: uscita ricomposta (con a capo) contiene `"Interrogando lo strumento orologio…"` come riga intera.
  - `test_testo_prima_dello_strumento_e_dopo`: preambolo, riga strumento, nuovo prefisso e testo finale nell'ordine dello spec §3.
  - `test_risposta_vuota_nessun_prefisso`: `AIMessage("")` non stampa `PREFISSO_RISPOSTA`.
  - `test_errore_a_meta_risposta`: modello il cui `stream` produce due pezzi e poi solleva `ConnectionError`; il testo già stampato resta, poi a capo e il messaggio `Errore: impossibile ottenere una risposta dal modello (ConnectionError)...`; alla domanda successiva il modello riceve la cronologia senza la domanda fallita.
  - `test_errore_dopo_uno_strumento_non_cambia_la_cronologia`: strumento eseguito, poi errore nel secondo passaggio del modello; la domanda successiva riceve la cronologia di prima.
  - `test_messaggio_del_limite_come_risposta_normale`: oltre il limite compare `PREFISSO_RISPOSTA` + `MESSAGGIO_LIMITE`.
- [ ] **Step 2: Eseguire** `python -m pytest tests/test_terminale.py -q` → falliscono.
- [ ] **Step 3: Implementare** in `assistente/terminale.py` come sopra, rimuovendo `grafo.invoke`.
- [ ] **Step 4: Eseguire** `python -m pytest -q` → suite verde (compreso `tests/test_avvio.py`: `__main__.py` non cambia e usa i default).
- [ ] **Step 5: Commit** `feat(terminale): risposta in streaming e riga dello strumento`.

### Task 5: Prova reale, documentazione e verifica finale

**Files:**
- Modify: `tests/test_reale_lmstudio.py`, `README.md`, `CLAUDE.md`
- Test: `tests/test_reale_lmstudio.py`

**Interfaces:**
- Consumes: `risposta_in_streaming`, `Testo`, `Strumento`, `Fine` (Task 3); fixture e helper già presenti nel file della prova reale (`grafo_reale`, `config`, `calcolatrice`, ...).

- [ ] **Step 1: Aggiungere due prove reali** (stesso `skipif` su `PROVA_LMSTUDIO` degli altri):
  - `test_reale_streaming_in_piu_pezzi`: domanda senza strumenti (per esempio «Rispondi in due frasi: che cos'è un grafo?») → almeno due eventi `Testo` e un `Fine`.
  - `test_reale_streaming_con_calcolatrice`: «quanto fa 12 * 7?» → un `Strumento("calculate")` seguito da almeno un `Testo`, e `Fine`.
- [ ] **Step 2: Eseguire la prova reale** (LM Studio acceso con `google/gemma-4-e4b`): `$env:PROVA_LMSTUDIO = "1"` più `LMSTUDIO_URL`/`LMSTUDIO_MODELLO`, poi `python -m pytest tests/test_reale_lmstudio.py -q`. Riportare l'esito reale; se qualche prova preesistente fallisce per variabilità del modello, dirlo senza nasconderlo.
- [ ] **Step 3: Aggiornare** `README.md` (una riga sullo streaming, la riga `Interrogando lo strumento …`, e che il testo scritto prima di uno strumento ora si vede; nessun nuovo comando) e `CLAUDE.md` (struttura: `flusso.py`; obiettivo: risposte in streaming; i comandi non cambiano).
- [ ] **Step 4: Eseguire** `python -m pytest -v` → suite completa verde con le prove reali saltate.
- [ ] **Step 5: Commit** `test(streaming): prova reale con LM Studio` e `docs: streaming in README e CLAUDE.md` (due commit, file pertinenti).
- [ ] **Step 6: Resoconto** con ciò che resta da provare dall'utente: uso a mano nel terminale (`python -m assistente`: testo che compare a pezzi, riga strumento, conferma `n`) e con `docker compose run --rm assistente`.
