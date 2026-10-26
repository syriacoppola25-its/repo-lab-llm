# Assistente del laboratorio — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** chatbot da terminale in Python che conversa con il modello di LM Studio tramite un grafo
LangGraph scritto a mano, ricorda la sessione, usa uno strumento orologio con limite di chiamate e
si avvia anche con Docker Compose.

**Architecture:** un pacchetto `assistente/` con moduli piccoli: configurazione, collegamento al
modello, strumento orologio, registro (log), grafo, terminale. Il terminale conserva la cronologia
in una lista e a ogni domanda invoca il grafo con l'intera cronologia; il grafo ha i nodi
`modello`, `strumenti`, `limite` e una funzione di instradamento propria. I test sostituiscono il
modello con un modello finto e l'orologio con un istante fisso.

**Tech Stack:** Python 3.13, `langgraph==1.2.17`, `langchain-openai==1.7.2`, `tzdata==2026.5`,
`pytest==9.1.1` (solo sviluppo), Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-26-assistente-laboratorio-design.md`

## Regola del piano

Ogni passo indica un **Risultato** (che cosa deve esistere o accadere, osservabile da chiunque) e
una **Verifica** (comando o controllo esplicito, con l'esito atteso). Un passo è completato solo
quando la verifica dà l'esito atteso; se non lo dà, ci si ferma e si riferisce. Le verifiche
marcate **[LM Studio]** o **[Docker]** richiedono quei servizi attivi e si eseguono esplicitamente;
tutte le altre girano senza modello.

## Global Constraints

- Si lavora nella radice di `repo-lab-llm/`, branch `main`. Non leggere né modificare `lezione3/`.
- Codice sincrono, moduli piccoli, nomi in italiano.
- Grafo scritto a mano: vietati `create_react_agent`, `ToolNode`, `tools_condition`.
- Configurazione solo da variabili d'ambiente. Nessun identificativo di modello o indirizzo nel codice.
- `.env.example` contiene solo segnaposto: `URL_SERVER_LMSTUDIO`, `ID_NOME_MODELLO`; le
  variabili facoltative sono commentate.
- Predefiniti: fuso `Europe/Rome`, limite `5` chiamate allo strumento per domanda, log
  `logs/assistente.log`.
- Messaggio di limite, testo esatto: `Non sono riuscito a completare la risposta (limite di passaggi raggiunto). Riprova o riformula la domanda.`
- Modello delle prove reali: `google/gemma-4-e2b`.
- Nessuna dipendenza oltre a quelle elencate; versioni fissate.
- Ogni commit: `git status`, controllo del diff, `git add` dei soli file pertinenti, Conventional
  Commits in italiano, riga finale `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  Mai versionare `.env`, `.venv/`, `logs/`, cache. Nessun push.
- Esecuzione Native: al termine di ogni Task (incremento) fermarsi, riferire gli esiti e chiedere
  all'utente prima di iniziare il successivo.
- README: solo comandi effettivamente eseguiti e verificati, con varianti PowerShell.
- Test automatici: `python -m pytest` dalla radice, senza LM Studio né Docker.

**Verifica standard di commit** (richiamata come «VC» nei passi di commit):
`git show --stat HEAD` elenca esattamente i file indicati nel passo; `git status --short` è
vuoto (i file ignorati non compaiono); `git ls-files` non contiene
`.env`, `.venv`, `logs`, `__pycache__`.

## Review Focus

1. `.env` copiato senza sostituire i segnaposto (`ID_NOME_MODELLO`): l'avvio deve fermarsi con un
   messaggio chiaro, non con un errore 404 alla prima domanda. → test in Task 2.
2. LM Studio spento o che cade a metà sessione: messaggio chiaro, cronologia invariata, la sessione
   continua. → test in Task 2.
3. Il modello passa `fuso_orario: ""`, un fuso inesistente o il nome di uno strumento che non esiste:
   nessun crash, risultato d'errore leggibile al modello. → test in Task 3.
4. Dopo aver raggiunto il limite la domanda successiva deve funzionare: ogni `tool_call` in
   cronologia ha il suo `ToolMessage`. → test in Task 3.
5. `Esci`, ` ESCI `, Ctrl+C mentre compare «sto pensando…», fine input (Ctrl+Z/Ctrl+D): uscita pulita
   senza traceback. → test in Task 1.

## Struttura dei file

```
.gitignore                 .env, .venv/, logs/, __pycache__/, .pytest_cache/
.dockerignore              come sopra + tests/, docs/, lezione3/, .git/
.env.example               segnaposto
requirements.txt           dipendenze dell'app, versioni fissate
requirements-dev.txt       -r requirements.txt + pytest
Dockerfile
docker-compose.yml
README.md
assistente/
  __init__.py
  __main__.py              avvio: python -m assistente
  config.py                Config, carica_config
  modello.py               istruzioni di sistema, crea_modello
  strumenti.py             ora_corrente, crea_orologio
  registro.py              configura_registro (log su file)
  grafo.py                 Stato, instrada, costruisci_grafo
  terminale.py             esegui_sessione (ciclo domanda/risposta, cronologia)
tests/
  finti.py                 ModelloFinto
  test_terminale.py
  test_grafo.py
  test_config.py
  test_strumenti.py
  test_registro.py
  test_reale_lmstudio.py   prova reale, saltata se PROVA_LMSTUDIO non vale 1
```

---

### Task 1: grafo con risposta fissa e terminale

**Risultato dell'incremento:** `python -m assistente` apre la conversazione, risponde sempre con una
frase fissa attraverso il grafo, ignora le righe vuote, esce con `esci`/Ctrl+C. Nessun modello coinvolto.

**Files:**
- Create: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `README.md`,
  `assistente/__init__.py`, `assistente/__main__.py`, `assistente/grafo.py`,
  `assistente/terminale.py`, `tests/finti.py`, `tests/test_grafo.py`, `tests/test_terminale.py`

**Interfaces:**
- Produces:
  - `assistente.grafo.Stato(TypedDict)`: `messaggi: Annotated[list[AnyMessage], add_messages]`,
    `chiamate_strumento: int`.
  - `assistente.grafo.costruisci_grafo(modello) -> CompiledStateGraph` — in questo task solo
    `START → modello → END`. `modello` è qualunque oggetto con `invoke(list[BaseMessage]) -> AIMessage`.
  - `assistente.grafo.RispostaFissa` — `invoke(messaggi) -> AIMessage("Risposta fissa: il modello non è ancora collegato.")`.
  - `assistente.terminale.esegui_sessione(grafo, leggi: Callable[[str], str] = input, scrivi: Callable[[str], None] = print) -> None`.
  - `assistente.terminale.SALUTO = "Arrivederci!"`, `PENSANDO = "sto pensando…"`, prompt `"Tu: "`,
    risposta stampata come `"Assistente: <testo>"`.
  - `tests.finti.ModelloFinto(risposte: list[AIMessage | BaseException])` — `invoke(messaggi)` salva
    una copia di `messaggi` in `self.ricevuti` e restituisce (o solleva) la risposta successiva.

- [ ] **Step 1: Preparare l'ambiente**

`requirements.txt`: `langgraph==1.2.17`, `langchain-openai==1.7.2`, `tzdata==2026.5`.
`requirements-dev.txt`: `-r requirements.txt` e `pytest==9.1.1`. `.gitignore` come in «Struttura».
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```
**Risultato:** ambiente virtuale `.venv` con le dipendenze installate.
**Verifica:** `python -c "import langgraph, langchain_openai, tzdata; print('ok')"` stampa `ok`;
`python -m pip check` stampa `No broken requirements found.`; `git status --short` non mostra `.venv/`.
Se `pip` segnala conflitti, fermarsi e riferire (non cambiare versioni da soli).

- [ ] **Step 2: Scrivere i test**

`tests/test_grafo.py`:
```python
def test_grafo_risponde_con_il_modello():
    modello = ModelloFinto([AIMessage("ciao")])
    esito = costruisci_grafo(modello).invoke({"messaggi": [HumanMessage("salve")], "chiamate_strumento": 0})
    assert [m.content for m in esito["messaggi"]] == ["salve", "ciao"]
```
`tests/test_terminale.py` (input simulato da una lista; le eccezioni nella lista vengono sollevate da `leggi`):
```python
def test_righe_vuote_ignorate():        # input ["", "   ", "esci"] -> modello.ricevuti == []
def test_esci_senza_distinzione_maiuscole():  # input [" ESCI "] -> ultima uscita == SALUTO
def test_ctrl_c_esce_con_saluto():      # input [KeyboardInterrupt()] -> nessuna eccezione, ultima uscita == SALUTO
def test_fine_input_esce_con_saluto():  # input [EOFError()] -> come sopra
def test_ctrl_c_durante_attesa():       # ModelloFinto([KeyboardInterrupt()]), input ["ciao"] -> ultima uscita == SALUTO
def test_mostra_pensando_e_risposta():  # input ["ciao","esci"], risposta "salve" -> uscite contengono PENSANDO e "Assistente: salve" in quest'ordine
```
**Risultato:** 7 test scritti, il codice dell'app non esiste ancora.
**Verifica:** `python -m pytest -v` termina con errore di raccolta `ModuleNotFoundError: No module named 'assistente'`.

- [ ] **Step 3: Implementare `grafo.py`, `terminale.py`, `__main__.py`, `__init__.py`**

Nodo `modello`: `{"messaggi": [modello.invoke(stato["messaggi"])]}`. Il terminale tiene
`cronologia: list[BaseMessage]` e a ogni domanda invoca il grafo con
`{"messaggi": cronologia + [HumanMessage(domanda)], "chiamate_strumento": 0}`; poi
`cronologia = esito["messaggi"]` e stampa `esito["messaggi"][-1].content`. `KeyboardInterrupt` ed
`EOFError` (in lettura o durante l'invocazione) → `scrivi(SALUTO)` e ritorno.
`__main__.py`: `esegui_sessione(costruisci_grafo(RispostaFissa()))`.
**Risultato:** i 7 test passano.
**Verifica:** `python -m pytest -v` → `7 passed`.

- [ ] **Step 4: Prova manuale dell'app senza modello**

**Risultato:** l'app si comporta come richiesto in un terminale vero.
**Verifica:** `python -m assistente`, poi:
`ciao` → compaiono `sto pensando…` e `Assistente: Risposta fissa: il modello non è ancora collegato.`;
riga vuota → nessuna risposta, ricompare `Tu: `; `Esci` → `Arrivederci!` e ritorno al prompt di
PowerShell; nuovo avvio e Ctrl+C → `Arrivederci!` senza traceback; `$LASTEXITCODE` → `0`.

- [ ] **Step 5: README**

Sezioni: scopo, creazione dell'ambiente (comandi dello Step 1), `python -m pytest`,
`python -m assistente`, breve spiegazione di stato, nodo e arco in LangGraph.
**Risultato:** README con solo i comandi già eseguiti negli Step 1–4.
**Verifica:** ogni blocco di comandi del README corrisponde a un comando eseguito in questo task
(confronto riga per riga); nessun comando relativo a LM Studio o Docker.

- [ ] **Step 6: Commit**
```powershell
git status; git diff
git add .gitignore requirements.txt requirements-dev.txt README.md assistente tests
git commit -m "feat(grafo): grafo minimo con risposta fissa e ciclo da terminale"
```
**Risultato:** un commit con i file del Task 1.
**Verifica:** VC.

---

### Task 2: collegamento a LM Studio e cronologia

**Risultato dell'incremento:** l'app parla con il modello di LM Studio indicato dalle variabili
d'ambiente e ricorda la conversazione; configurazione errata o server spento producono messaggi chiari.

**Files:**
- Create: `assistente/config.py`, `assistente/modello.py`, `.env.example`, `tests/test_config.py`
- Modify: `assistente/terminale.py`, `assistente/__main__.py`, `assistente/grafo.py` (rimuovere
  `RispostaFissa`), `tests/test_grafo.py`, `tests/test_terminale.py`, `README.md`

**Interfaces:**
- Consumes: `costruisci_grafo`, `esegui_sessione`, `ModelloFinto` (Task 1).
- Produces:
  - `assistente.config.Config` (dataclass frozen): `url_server: str`, `modello: str`,
    `fuso_predefinito: str = "Europe/Rome"`, `limite_chiamate: int = 5`,
    `percorso_log: Path = Path("logs/assistente.log")`.
  - `assistente.config.carica_config(env: Mapping[str, str]) -> Config`; solleva
    `ConfigErrata(ValueError)` con messaggio in italiano che nomina la variabile.
  - Variabili: `LMSTUDIO_URL`, `LMSTUDIO_MODELLO` (obbligatorie), `FUSO_PREDEFINITO`,
    `LIMITE_CHIAMATE_STRUMENTO`, `PERCORSO_LOG` (facoltative).
  - `assistente.modello.istruzioni_sistema(fuso_predefinito: str) -> str`.
  - `assistente.modello.crea_modello(config: Config, strumenti: list[BaseTool]) -> Runnable` —
    `ChatOpenAI(base_url=config.url_server, model=config.modello, api_key="lm-studio")`, con
    `bind_tools(strumenti)` solo se la lista non è vuota.
  - `costruisci_grafo(modello, istruzioni: str = "")` — il nodo `modello` antepone
    `SystemMessage(istruzioni)` ai messaggi passati al modello (solo se `istruzioni` non è vuoto),
    senza salvarlo nella cronologia.
  - Terminale: eccezione durante l'invocazione (diversa da `KeyboardInterrupt`/`EOFError`) →
    `scrivi("Errore: impossibile ottenere una risposta dal modello (<NomeEccezione>). Controlla che LM Studio sia avviato.")`,
    cronologia invariata.

- [ ] **Step 1: Scrivere i test**

`tests/test_config.py`:
```python
def test_valori_obbligatori_e_predefiniti():
    c = carica_config({"LMSTUDIO_URL": "http://localhost:1234/v1", "LMSTUDIO_MODELLO": "google/gemma-4-e2b"})
    assert (c.fuso_predefinito, c.limite_chiamate, c.percorso_log) == ("Europe/Rome", 5, Path("logs/assistente.log"))
def test_variabile_mancante():          # {} -> ConfigErrata, messaggio contiene "LMSTUDIO_URL"
def test_segnaposto_non_sostituito():   # LMSTUDIO_MODELLO="ID_NOME_MODELLO" -> ConfigErrata; idem LMSTUDIO_URL="URL_SERVER_LMSTUDIO"
def test_limite_non_valido():           # LIMITE_CHIAMATE_STRUMENTO in ("zero", "0", "-1") -> ConfigErrata
def test_fuso_predefinito_inesistente(): # FUSO_PREDEFINITO="Europa/Roma" -> ConfigErrata
```
`tests/test_grafo.py`:
```python
def test_istruzioni_inviate_ma_non_salvate():
    # costruisci_grafo(modello, istruzioni="ISTR"): modello.ricevuti[0][0] == SystemMessage("ISTR");
    # nessun SystemMessage in esito["messaggi"]
```
`tests/test_terminale.py`:
```python
def test_cronologia_conservata():
    # input ["mi chiamo Ada", "come mi chiamo?", "esci"]; modello.ricevuti[1] contenuti ==
    # ["mi chiamo Ada", <risposta 1>, "come mi chiamo?"]
def test_errore_modello_non_interrompe():
    # ModelloFinto([ConnectionError(), AIMessage("ok")]), input ["a", "b", "esci"]:
    # uscite contengono "Errore: impossibile ottenere una risposta dal modello (ConnectionError)" e poi "Assistente: ok";
    # contenuti di modello.ricevuti[1] == ["b"] (cronologia invariata dopo l'errore)
```
**Risultato:** 8 nuovi test, falliscono perché il codice manca.
**Verifica:** `python -m pytest -v` → errore di raccolta su `assistente.config` e fallimenti nei
nuovi test di grafo e terminale; i 7 test del Task 1 non toccati passano ancora (escludendo i file che non si importano: `python -m pytest tests/test_terminale.py -v` mostra solo i 2 nuovi test falliti).

- [ ] **Step 2: Implementare `config.py`, `modello.py` e le modifiche**

Fuso valido = `zoneinfo.ZoneInfo(valore)` non solleva. `__main__.main() -> int`:
`carica_config(os.environ)`; su `ConfigErrata` stampa il messaggio più `Vedi .env.example.` e
restituisce 1; altrimenti `crea_modello(config, [])`, grafo con `istruzioni_sistema(...)`, sessione,
restituisce 0. Istruzioni di sistema: rispondi in italiano e in modo conciso.
`.env.example`:
```
LMSTUDIO_URL=URL_SERVER_LMSTUDIO
LMSTUDIO_MODELLO=ID_NOME_MODELLO
# FUSO_PREDEFINITO=
# LIMITE_CHIAMATE_STRUMENTO=
# PERCORSO_LOG=
```
**Risultato:** tutti i test passano; `.env.example` contiene solo segnaposto.
**Verifica:** `python -m pytest -v` → `15 passed`;
`Select-String -Path .env.example -Pattern "localhost|gemma|1234"` non restituisce nulla.

- [ ] **Step 3: Verifica dell'avvio con configurazione errata (senza modello)**

**Risultato:** senza configurazione valida l'app non parte e spiega perché.
**Verifica:** in un PowerShell nuovo, senza variabili: `python -m assistente` stampa un messaggio
che nomina `LMSTUDIO_URL` e `Vedi .env.example.`; `$LASTEXITCODE` → `1`. Con
`$env:LMSTUDIO_URL="URL_SERVER_LMSTUDIO"` e `$env:LMSTUDIO_MODELLO="ID_NOME_MODELLO"`: stesso
comportamento, messaggio sul segnaposto.

- [ ] **Step 4: Prova reale con LM Studio [LM Studio]**
```powershell
Invoke-RestMethod http://localhost:1234/v1/models | Select-Object -ExpandProperty data | Select-Object id
$env:LMSTUDIO_URL = "http://localhost:1234/v1"
$env:LMSTUDIO_MODELLO = "google/gemma-4-e2b"
python -m assistente
```
**Risultato:** conversazione reale con memoria.
**Verifica:** l'elenco dei modelli contiene `google/gemma-4-e2b`; a una domanda normale arriva
una risposta in italiano; «mi chiamo Ada» poi «come mi chiamo?» → la risposta contiene «Ada».
Poi, con il server di LM Studio fermato: una domanda produce il messaggio `Errore: impossibile
ottenere una risposta dal modello (...)` e ricompare `Tu: `. Annotare gli esiti per il resoconto.

- [ ] **Step 5: README**

Sezioni: configurazione (`.env.example`, variabili, ID ricavato da `/v1/models`), avvio locale
(comandi dello Step 4), diagnosi (server spento, segnaposto non sostituiti).
**Risultato:** README aggiornato con i soli comandi eseguiti negli Step 3–4.
**Verifica:** confronto riga per riga tra i comandi del README e quelli eseguiti; nessun valore
reale di modello presentato come predefinito (solo come esempio della prova).

- [ ] **Step 6: Commit**
```powershell
git status; git diff
git add assistente tests .env.example README.md
git commit -m "feat(modello): collegamento a LM Studio e cronologia di sessione"
```
**Risultato:** un commit con i file del Task 2.
**Verifica:** VC; in più `git show HEAD:.env.example` contiene `ID_NOME_MODELLO`.

---

### Task 3: strumento orologio, instradamento e limite

**Risultato dell'incremento:** il modello può chiedere l'ora; il grafo esegue lo strumento, registra
la chiamata nel log e torna al modello; dopo 5 chiamate per domanda si ferma col messaggio fisso.

**Files:**
- Create: `assistente/strumenti.py`, `assistente/registro.py`, `tests/test_strumenti.py`,
  `tests/test_registro.py`, `tests/test_reale_lmstudio.py`
- Modify: `assistente/grafo.py`, `assistente/modello.py`, `assistente/__main__.py`,
  `tests/test_grafo.py`, `README.md`

**Interfaces:**
- Consumes: `Config`, `carica_config`, `crea_modello`, `istruzioni_sistema`, `costruisci_grafo` (Task 2).
- Produces:
  - `assistente.strumenti.ora_corrente(fuso_orario: str | None, adesso: datetime, fuso_predefinito: str) -> str`
    — `adesso` è un datetime con fuso. Formato: `AAAA-MM-GG HH:MM:SS <fuso> (UTC±HH:MM)`.
    `None` o stringa vuota/spazi → `fuso_predefinito`. Fuso inesistente →
    `Errore: fuso orario sconosciuto '<valore>'. Usa un nome IANA, per esempio Europe/Rome o Asia/Tokyo.`
  - `assistente.strumenti.crea_orologio(fuso_predefinito: str, adesso: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> BaseTool`
    — `StructuredTool` con nome `orologio`, unico argomento facoltativo `fuso_orario: str | None`,
    descrizione: da usare per data e ora; per una città passare il suo nome IANA.
  - `assistente.registro.configura_registro(percorso: Path) -> logging.Logger` — logger
    `"assistente.strumenti"`, `FileHandler` UTF-8 (crea la cartella), formato
    `%(asctime)s %(levelname)s %(message)s`, `propagate = False`.
  - `assistente.grafo.MESSAGGIO_LIMITE` (testo esatto in Global Constraints).
  - `assistente.grafo.instrada(stato: Stato, limite: int) -> Literal["strumenti", "limite", "fine"]`.
  - `costruisci_grafo(modello, istruzioni: str = "", strumenti: Sequence[BaseTool] = (), limite: int = 5, registro: logging.Logger | None = None)`.
  - Righe di log: `passaggio=<n> strumento=<nome> argomenti=<dict> risultato=<testo>` (INFO);
    `limite raggiunto: chiamate=<n> richieste=<k> limite=<limite>` (WARNING).

- [ ] **Step 1: Test dello strumento e del registro**

`tests/test_strumenti.py`, con `ISTANTE = datetime(2026, 10, 26, 14, 0, tzinfo=timezone.utc)`:
```python
def test_fuso_predefinito():  assert ora_corrente(None, ISTANTE, "Europe/Rome") == "2026-10-26 15:00:00 Europe/Rome (UTC+01:00)"
def test_fuso_esplicito():    assert ora_corrente("Asia/Tokyo", ISTANTE, "Europe/Rome") == "2026-10-26 23:00:00 Asia/Tokyo (UTC+09:00)"
def test_stringa_vuota_usa_predefinito(): assert ora_corrente("  ", ISTANTE, "Europe/Rome").endswith("Europe/Rome (UTC+01:00)")
def test_fuso_inesistente():  assert ora_corrente("Asia/Milano", ISTANTE, "Europe/Rome").startswith("Errore: fuso orario sconosciuto 'Asia/Milano'")
def test_scarto_negativo():   assert ora_corrente("America/New_York", ISTANTE, "Europe/Rome").endswith("(UTC-04:00)")
def test_strumento_langchain():
    t = crea_orologio("Europe/Rome", adesso=lambda: ISTANTE)
    assert t.name == "orologio"
    assert t.invoke({"fuso_orario": "Asia/Tokyo"}).startswith("2026-10-26 23:00:00")
    assert t.invoke({}).startswith("2026-10-26 15:00:00")
```
`tests/test_registro.py`:
```python
def test_scrive_su_file(tmp_path):  # configura_registro(tmp_path/"sub"/"a.log").info("x") -> file esiste e contiene "INFO x"
```
**Risultato:** 7 test nuovi che falliscono.
**Verifica:** `python -m pytest tests/test_strumenti.py tests/test_registro.py -v` → errore
`ModuleNotFoundError` su `assistente.strumenti` / `assistente.registro`.

- [ ] **Step 2: Implementare `strumenti.py` e `registro.py`**

**Risultato:** strumento e registro funzionanti in isolamento.
**Verifica:** `python -m pytest tests/test_strumenti.py tests/test_registro.py -v` → `7 passed`;
`python -m pytest -v` → `22 passed` (nessuna regressione).

- [ ] **Step 3: Commit dello strumento**
```powershell
git status; git diff
git add assistente/strumenti.py assistente/registro.py tests/test_strumenti.py tests/test_registro.py
git commit -m "feat(strumenti): orologio con fuso orario e registro su file"
```
**Risultato:** commit con i 4 file.
**Verifica:** VC.

- [ ] **Step 4: Test di instradamento e grafo**

Helper nei test: `chiamata(id, args={"fuso_orario": "Asia/Tokyo"}, nome="orologio")` → dict
`tool_call`; orologio con `ISTANTE` fisso; registro su `tmp_path`.
```python
def test_instrada_fine():        # ultimo AIMessage senza tool_calls -> "fine"
def test_instrada_strumenti():   # 1 tool_call, chiamate_strumento=0, limite 5 -> "strumenti"
def test_instrada_limite():      # 2 tool_call, chiamate_strumento=4, limite 5 -> "limite"
def test_ciclo_completo(tmp_path):
    # ModelloFinto([AIMessage("", tool_calls=[chiamata("1")]), AIMessage("A Tokyo sono le 23:00")])
    # tipi in esito["messaggi"] == [HumanMessage, AIMessage, ToolMessage, AIMessage];
    # ToolMessage.tool_call_id == "1"; ToolMessage.content inizia con "2026-10-26 23:00:00 Asia/Tokyo";
    # esito["chiamate_strumento"] == 1; modello.ricevuti[1][-1] è il ToolMessage;
    # il file di log contiene "passaggio=1 strumento=orologio" e "Asia/Tokyo"
def test_limite_raggiunto(tmp_path):
    # ModelloFinto con 6 AIMessage che chiedono sempre lo strumento (id "1".."6"), limite=5
    # -> esito["messaggi"][-1].content == MESSAGGIO_LIMITE; esito["chiamate_strumento"] == 5;
    # ogni tool_call in cronologia ha un ToolMessage con lo stesso id; quello di "6" ha contenuto
    # "non eseguita: limite raggiunto"; il log contiene "limite raggiunto"
def test_domanda_dopo_il_limite(tmp_path):
    # cronologia di test_limite_raggiunto + HumanMessage("ciao"), chiamate_strumento=0,
    # modello risponde AIMessage("ok") -> esito["messaggi"][-1].content == "ok"
def test_strumento_sconosciuto(tmp_path):
    # tool_call con nome "meteo" -> ToolMessage "Errore: strumento sconosciuto 'meteo'.", nessuna eccezione
```
**Risultato:** 7 nuovi test che falliscono.
**Verifica:** `python -m pytest tests/test_grafo.py -v` → i 7 nuovi falliscono (`ImportError` su
`instrada`/`MESSAGGIO_LIMITE` o asserzioni), i 2 precedenti passano.

- [ ] **Step 5: Implementare il grafo completo e il collegamento in `__main__`**

Nodi: `modello`; `strumenti` (esegue ogni `tool_call` dell'ultimo `AIMessage`, aggiunge un
`ToolMessage(content, tool_call_id=...)` per ciascuna, incrementa `chiamate_strumento`, scrive la
riga INFO); `limite` (un `ToolMessage("non eseguita: limite raggiunto")` per ogni chiamata pendente
+ `AIMessage(MESSAGGIO_LIMITE)`, riga WARNING). Archi: `START → modello`;
`add_conditional_edges("modello", instrada, {"strumenti": "strumenti", "limite": "limite", "fine": END})`;
`strumenti → modello`; `limite → END`. Un commento breve per nodo.
`istruzioni_sistema(fuso)` aggiunge: per data/ora usa sempre lo strumento `orologio`; per una città
passa il suo fuso IANA; se il fuso è quello predefinito (`<fuso>`) non nominarlo, altrimenti
indicalo nella risposta. `__main__`: `configura_registro(config.percorso_log)`,
`crea_orologio(config.fuso_predefinito)`, `crea_modello(config, [orologio])`, grafo con
`limite=config.limite_chiamate`.
**Risultato:** tutti i test automatici passano; il grafo ha i tre nodi previsti.
**Verifica:** `python -m pytest -v` → `29 passed`;
`python -c "from assistente.grafo import costruisci_grafo; from tests.finti import ModelloFinto; print(costruisci_grafo(ModelloFinto([])).get_graph().draw_ascii())"`
mostra i nodi `modello`, `strumenti`, `limite` e gli archi descritti. (Se `draw_ascii` richiede
una dipendenza non installata, usare `.get_graph().nodes` e `.edges` e confrontare con gli archi;
non installare altro.)

- [ ] **Step 6: Prova reale automatizzata, attivata esplicitamente [LM Studio]**

`tests/test_reale_lmstudio.py`: `pytestmark = pytest.mark.skipif(os.environ.get("PROVA_LMSTUDIO") != "1", reason=...)`,
configurazione da `carica_config(os.environ)`, registro su `tmp_path`.
```python
def test_modello_reale_usa_orologio():
    # invoca il grafo reale con "Che ore sono a Tokyo?":
    # almeno un ToolMessage presente; il primo ToolMessage contiene "Asia/Tokyo";
    # l'ultimo messaggio è un AIMessage senza tool_calls e con testo non vuoto
```
**Risultato:** prova reale disponibile ma esclusa dai test normali.
**Verifica:** senza variabile, `python -m pytest -v` → `29 passed, 1 skipped`. Con
`$env:PROVA_LMSTUDIO = "1"` (più le variabili del Task 2):
`python -m pytest tests/test_reale_lmstudio.py -v` → `1 passed`; ripetere 3 volte e annotare gli
esiti (il modello non è deterministico). Se fallisce: migliorare istruzioni e descrizione dello
strumento, rieseguire; se resta instabile, annotarlo per il resoconto. Il modello non si cambia.

- [ ] **Step 7: Prova reale interattiva [LM Studio]**

**Risultato:** comportamento dello strumento osservato nella conversazione e nel log.
**Verifica:** `python -m assistente`; in un secondo PowerShell `Get-Content logs\assistente.log -Wait`.
«che ore sono?» → ora italiana corretta (confronto con l'orologio di Windows), fuso non nominato;
«e a Tokyo?» → ora di Tokyo corretta, `Asia/Tokyo` nominato; «di che cosa abbiamo parlato?» → cita
le domande sull'ora. Nel log compaiono una riga `passaggio=1 strumento=orologio` con
`Europe/Rome` (o argomenti vuoti e risultato `Europe/Rome`) e una con `Asia/Tokyo`. Nel terminale
non compaiono righe di log. Annotare gli esiti.

- [ ] **Step 8: README**

Sezioni: strumento orologio, file di log e come seguirlo, prova reale con `PROVA_LMSTUDIO`,
diagramma testuale del grafo.
**Risultato:** README aggiornato con i soli comandi eseguiti negli Step 5–7.
**Verifica:** confronto riga per riga tra i comandi del README e quelli eseguiti.

- [ ] **Step 9: Commit**
```powershell
git status; git diff
git add assistente tests README.md
git commit -m "feat(grafo): instradamento verso lo strumento orologio con limite di chiamate"
```
**Risultato:** commit con grafo, modifiche collegate, test e README.
**Verifica:** VC; `logs/` non compare in `git show --stat HEAD`.

---

### Task 4: Docker Compose

**Risultato dell'incremento:** `docker compose run --rm assistente` avvia la stessa app nel
container, collegata a LM Studio sull'host, con il log visibile nella cartella `logs/` dell'host.

**Files:**
- Create: `Dockerfile`, `.dockerignore`, `docker-compose.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `python -m assistente` e le variabili del Task 2.
- Produces: servizio Compose `assistente`.

- [ ] **Step 1: Scrivere i file Docker**

`Dockerfile`: `FROM python:3.13-slim`, `WORKDIR /app`, `ENV PYTHONUNBUFFERED=1`, copia e installa
`requirements.txt` (`--no-cache-dir`), copia `assistente/`, `CMD ["python", "-m", "assistente"]`.
`docker-compose.yml`, servizio `assistente`: `build: .`, `env_file: .env`,
`environment: {LMSTUDIO_URL: "http://host.docker.internal:1234/v1", PERCORSO_LOG: "/app/logs/assistente.log"}`,
`stdin_open: true`, `tty: true`, `volumes: ["./logs:/app/logs"]`,
`extra_hosts: ["host.docker.internal:host-gateway"]`. Creare un `.env` locale da `.env.example`
con valori reali (non versionato).
**Risultato:** configurazione Compose valida, che sostituisce l'indirizzo per il container.
**Verifica [Docker]:** `docker compose config` termina senza errori e mostra
`LMSTUDIO_URL: http://host.docker.internal:1234/v1` e il volume `logs`; `git status --short` non
mostra `.env`.

- [ ] **Step 2: Build e controlli nel container senza modello [Docker]**
```powershell
docker compose build
docker compose run --rm assistente python -c "from zoneinfo import ZoneInfo; ZoneInfo('Asia/Tokyo'); import assistente.grafo; print('ok')"
docker compose run --rm assistente ls /app
```
**Risultato:** immagine costruita con app e fusi orari, senza file estranei.
**Verifica:** build riuscita; il secondo comando stampa `ok`; il terzo elenca solo `assistente` e
`requirements.txt` (niente `tests`, `docs`, `lezione3`, `.env`).

- [ ] **Step 3: Prova reale Docker + LM Studio [Docker] [LM Studio]**

**Risultato:** conversazione nel container con lo strumento funzionante.
**Verifica:** `docker compose run --rm assistente`: domanda normale → risposta; «che ore sono a
Tokyo?» → ora di Tokyo corretta; `esci` → `Arrivederci!` e il container termina; nuovo avvio e
Ctrl+C → uscita pulita; `Get-Content logs\assistente.log -Tail 5` sull'host mostra la chiamata
con `Asia/Tokyo`. Se il container non raggiunge LM Studio: attivare in LM Studio il servizio sulla
rete locale, ripetere e annotare la soluzione verificata.

- [ ] **Step 4: README**

Sezioni: avvio con Docker (comandi degli Step 1–3), differenza di indirizzo locale/container,
diagnosi della connessione.
**Risultato:** README aggiornato con i soli comandi eseguiti in questo task.
**Verifica:** confronto riga per riga tra i comandi del README e quelli eseguiti.

- [ ] **Step 5: Commit**
```powershell
git status; git diff
git add Dockerfile .dockerignore docker-compose.yml README.md
git commit -m "feat(docker): avvio dell'assistente con Docker Compose"
```
**Risultato:** commit con i file Docker e il README.
**Verifica:** VC; `.env` assente da `git show --stat HEAD`.

---

### Task 5: verifica completa e documentazione finale

**Risultato dell'incremento:** tutte le verifiche rieseguite da zero, README coerente con ciò che è
stato provato, `CLAUDE.md` aggiornato con struttura e comandi stabili, resoconto finale.

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: Test senza modello da ambiente pulito**
```powershell
deactivate; Remove-Item -Recurse -Force .venv
python -m venv .venv; .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -v
```
**Risultato:** i test passano partendo solo dai file versionati.
**Verifica:** `29 passed, 1 skipped`.

- [ ] **Step 2: Prove reali complete [LM Studio] [Docker]**

**Risultato:** tabella degli esiti delle prove reali con `google/gemma-4-e2b`.
**Verifica:** rieseguiti Task 3 Step 6–7 e Task 4 Step 2–3; per ciascuna prova annotati comando,
esito atteso, esito ottenuto, eventuali risposte errate del modello.

- [ ] **Step 3: Controllo Git**

**Risultato:** nessun file sensibile o generato in Git.
**Verifica:** `git ls-files` non contiene `.env`, `.venv`, `logs`, `__pycache__`, `.pytest_cache`;
`git status --short` è vuoto.

- [ ] **Step 4: Documentazione finale**

README: rilettura di ogni comando, rimozione di quelli non eseguiti, sezione «Verifica completa»
con l'ordine delle prove. `CLAUDE.md`: proporre all'utente il testo aggiornato (frase sulla
cartella iniziale, struttura del pacchetto, `python -m pytest`, prova reale con `PROVA_LMSTUDIO=1`)
e committarlo solo dopo il suo consenso.
```powershell
git status; git diff
git add README.md
git commit -m "docs: istruzioni di verifica completa"
```
**Risultato:** README finale committato; `CLAUDE.md` proposto all'utente.
**Verifica:** VC; ogni comando del README compare nella tabella dello Step 2 o in un passo
precedente già verificato; risposta dell'utente sul `CLAUDE.md` ricevuta prima di committarlo.

- [ ] **Step 5: Resoconto all'utente**

**Risultato:** resoconto con che cosa è stato eseguito, con quale esito e che cosa resta da provare
o è risultato instabile.
**Verifica:** il resoconto contiene la tabella dello Step 2, il risultato di `python -m pytest -v`
e l'elenco dei commit (`git log --oneline` dall'inizio del lavoro).
