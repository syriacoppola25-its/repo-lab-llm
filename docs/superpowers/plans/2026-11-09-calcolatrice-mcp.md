# Calcolatrice sicura tramite MCP — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** aggiungere all'assistente una calcolatrice sicura (senza `eval`) offerta da un secondo server MCP stdio, scoperta con la discovery come il server delle note.

**Architecture:** un valutatore puro basato su `ast` (`server_calcolatrice/valutatore.py`) esposto da un server FastMCP con un solo tool `calculate`. Nell'assistente il client MCP di `note_mcp.py` diventa generico (`client_mcp.py`, classe `ClientMCP`); `ClientNote` e `ClientCalcolatrice` sono sottoclassi sottili. `__main__.py` avvia entrambi i server; grafo, limite di passaggi e log restano invariati.

**Tech Stack:** Python 3.13, `ast`/`operator`/`math` (libreria standard), `fastmcp==3.4.11`, `mcp==1.30.0`, `langchain-mcp-adapters==0.3.2`, LangGraph, pytest. Nessuna dipendenza nuova.

**Spec:** `docs/superpowers/specs/2026-11-09-calcolatrice-mcp-design.md`

## Global Constraints

- Branch `dev`; push e passaggio su `main` solo su richiesta dell'utente.
- **Fermarsi dopo ogni task** e attendere l'utente (regola dell'utente), con resoconto: cosa eseguito, esito, cosa resta da provare.
- Mai `eval`, `exec`, `compile` per valutare l'espressione.
- Nome, descrizione e schema del tool solo nel server; i nomi dei tool (`calculate`, `add_note`, `list_notes`, `delete_note`) non compaiono nel sorgente di `assistente/client_mcp.py`, `assistente/note_mcp.py`, `assistente/calcolatrice_mcp.py` (nemmeno nei commenti).
- Limiti: espressione max **200** caratteri; esponente max **100** in valore assoluto; ogni valore (letterale, intermedio, finale) intero `< 10**50` in valore assoluto, decimale finito e `<= 1e50` in valore assoluto.
- Ammessi: numeri con sole cifre e punto facoltativo (`12`, `12.5`, `.5`, `5.`); `+ - * / // % **`; parentesi; `+`/`-` unari. Tutto il resto rifiutato.
- Risultato del tool: dict `{"espressione": <testo ripulito dagli spazi esterni>, "risultato": <int|float>}`; intero se il valore è intero, altrimenti arrotondato a 12 cifre significative.
- Un solo limite di passaggi condiviso (`LIMITE_CHIAMATE_STRUMENTO`); nessuna nuova variabile d'ambiente.
- Conventional Commits in italiano, chiusi da `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; prima di ogni commit `git status`, controllo del diff, staging selettivo.
- PowerShell 5.1: per riscrivere file usare lo strumento Edit (niente `Set-Content`, aggiunge il BOM).

## Review Focus

- Spazi all'inizio dell'espressione (`" 2+2"`): `ast.parse` in modalità `eval` dà `IndentationError`; l'utente si aspetta 4 → ripulire con `strip()` prima (test in Task 1).
- Virgola decimale (`12,5`): diventa una tupla; l'utente si aspetta un errore che spieghi di usare il punto, non un generico «elemento non ammesso» (test in Task 1).
- Intero enorme da potenza (`(10**49)**100`): la conversione a stringa di interi oltre 4300 cifre solleva `ValueError`; il controllo di grandezza va fatto per confronto numerico, mai con `len(str(n))` (test in Task 1).
- `0 ** -1` e `0.0 ** -1`: sollevano `ZeroDivisionError`; l'utente si aspetta «divisione per zero», non un crash del server (test in Task 1).
- Server della calcolatrice che non parte all'avvio dopo che quello delle note è partito: il server delle note va chiuso comunque e il messaggio deve nominare la calcolatrice (test in Task 4).

---

### Task 1: Valutatore aritmetico sicuro

**Files:**
- Create: `server_calcolatrice/__init__.py` (vuoto), `server_calcolatrice/valutatore.py`
- Test: `tests/test_valutatore.py`

**Interfaces:**
- Produces: in `server_calcolatrice/valutatore.py`
  - costanti `LUNGHEZZA_MASSIMA = 200`, `ESPONENTE_MASSIMO = 100`, `CIFRE_MASSIME = 50`, `VALORE_MASSIMO = 1e50`;
  - `class ErroreEspressione(ValueError)` — il messaggio è il testo mostrato al modello;
  - `def valuta(espressione: str) -> int | float` — valore grezzo, già controllato nei limiti;
  - `def formatta(valore: int | float) -> int | float` — intero se intero, altrimenti 12 cifre significative (`float(f"{v:.12g}")`).

**Messaggi esatti** (frammenti da cui dipendono i test; il resto del testo è libero):

| Caso | Messaggio |
|---|---|
| vuota / solo spazi | `espressione vuota` |
| oltre 200 caratteri | `espressione troppo lunga: massimo 200 caratteri` |
| `SyntaxError` | `sintassi non valida` |
| tupla (`12,5`) | `virgola non ammessa: i decimali si scrivono con il punto` |
| nome (`x`, `pi`) | `elemento non ammesso: nome 'x'` |
| chiamata | `elemento non ammesso: chiamata di funzione` |
| attributo | `elemento non ammesso: attributo` |
| indice | `elemento non ammesso: indice` |
| confronto | `elemento non ammesso: confronto` |
| `and`/`or`/`not` | `elemento non ammesso: operatore logico` |
| operatori sui bit (`<< >> & \| ^ ~`), `@` | `elemento non ammesso: operatore '<<'` (simbolo dell'operatore) |
| lista/dict/set | `elemento non ammesso: elenco` |
| stringhe, byte | `elemento non ammesso: testo` |
| `True`/`False`/`None`/`...` | `elemento non ammesso: valore 'True'` |
| altri nodi | `elemento non ammesso: <NomeClasseNodo>` |
| letterale numerico con forma non ammessa (`1e5`, `1_000`, `0x10`, `0b1`, `1j`) | `notazione numerica non ammessa: '1e5'` |
| `/`, `//`, `%` per zero, `0 ** -1` | `divisione per zero` |
| esponente `> 100` in valore assoluto | `esponente troppo grande: massimo 100 in valore assoluto` |
| valore oltre i limiti, `OverflowError` | `risultato troppo grande` |
| risultato complesso | `risultato non reale` |
| `RecursionError`, `MemoryError` | `espressione troppo complessa` |

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_valutatore.py`

```python
import re

import pytest
from pathlib import Path
import server_calcolatrice.valutatore as modulo
from server_calcolatrice.valutatore import ErroreEspressione, formatta, valuta

@pytest.mark.parametrize("espressione, atteso", [
    ("2 + 3", 5), ("10 - 4", 6), ("6 * 7", 42), ("7 / 2", 3.5), ("7 // 2", 3),
    ("7 % 3", 1), ("2 ** 10", 1024), ("2 + 3 * 4", 14), ("(2 + 3) * 4", 20),
    ("-3 + 1", -2), ("-(2 + 1)", -3), ("+5", 5), ("12.5 * 2", 25.0), (".5 + 5.", 5.5),
    ("-7 // 2", -4), ("2 ** -1", 0.5), ("2 ** 0.5", 2 ** 0.5), ("  2+2  ", 4),
])
def test_operazioni_ammesse(espressione, atteso):
    assert valuta(espressione) == atteso

@pytest.mark.parametrize("espressione, frammento", [
    ("", "espressione vuota"), ("   ", "espressione vuota"),
    ("1+" * 100 + "1", "troppo lunga"),
    ("2 +", "sintassi non valida"), ("12,5", "virgola non ammessa"),
    ("x + 1", "nome 'x'"), ("pi", "nome 'pi'"),
    ("sqrt(4)", "chiamata di funzione"), ("__import__('os')", "chiamata di funzione"),
    ("(1).real", "attributo"), ("[1][0]", "indice"), ("2 < 3", "confronto"),
    ("1 and 2", "operatore logico"), ("not 1", "operatore logico"),
    ("1 << 2", "operatore '<<'"), ("~1", "operatore '~'"), ("[1, 2]", "elenco"),
    ("'ab'", "testo"), ("True", "valore 'True'"), ("None", "valore 'None'"),
    ("1e5", "notazione numerica non ammessa: '1e5'"), ("1_000", "notazione numerica"),
    ("0x10", "notazione numerica"), ("0b1", "notazione numerica"), ("1j", "notazione numerica"),
    ("10 / 0", "divisione per zero"), ("10 // 0", "divisione per zero"),
    ("10 % 0", "divisione per zero"), ("0 ** -1", "divisione per zero"),
    ("0.0 ** -1", "divisione per zero"),
    ("2 ** 101", "esponente troppo grande"), ("9 ** 9 ** 9", "esponente troppo grande"),
    ("(10 ** 49) ** 100", "risultato troppo grande"),
    ("10 ** 50", "risultato troppo grande"), ("1" + "0" * 50, "risultato troppo grande"),
    ("10.0 ** 30 * 10.0 ** 30", "risultato troppo grande"),
    ("(-8) ** 0.5", "risultato non reale"),
])
def test_rifiuti_espliciti(espressione, frammento):
    with pytest.raises(ErroreEspressione, match=re.escape(frammento)):
        valuta(espressione)
```

Più:
- `test_limite_esponente_rifiuta_prima_di_calcolare`: `valuta("9 ** 9 ** 9")` solleva entro 1 secondo (misura con `time.perf_counter`).
- `test_niente_eval`: il sorgente di `modulo.__file__` non contiene `eval(`, `exec(`, `compile(`.
- `test_formatta`: `formatta(1.0) == 1 and type(...) is int`; `formatta(0.1 + 0.2) == 0.3`; `formatta(7) == 7`; `formatta(2 / 3) == 0.666666666667`.
- `test_espressione_esattamente_200_caratteri_ammessa`: `"1+" * 99 + "11"` (200 caratteri) → `valuta` restituisce 110.

- [ ] **Step 2: Eseguire i test e vederli fallire**

Run: `python -m pytest tests/test_valutatore.py -q`
Expected: errore di import (`server_calcolatrice` non esiste).

- [ ] **Step 3: Implementare `valuta` e `formatta`**

Approccio: `testo = espressione.strip()`; controlli su vuota e lunghezza; `ast.parse(testo, mode="eval")` dentro `try` (`SyntaxError` → sintassi non valida); visita ricorsiva che valuta solo `Expression`, `BinOp`, `UnaryOp`, `Constant`; ogni altro nodo → messaggio della tabella. Per `Constant`: prima il tipo (`bool`, `None`, `Ellipsis` → valore; `str`/`bytes` → testo), poi per `int`/`float`/`complex` il testo originale (`ast.get_source_segment(testo, nodo)`) deve combaciare con `re.fullmatch(r"\d+(\.\d*)?|\.\d+", ...)`. Operatori ammessi in una mappa chiusa verso `operator.add`, `sub`, `mul`, `truediv`, `floordiv`, `mod`, `pow`, `pos`, `neg`. Per `Pow` controllare l'esponente **prima** di calcolare. Dopo ogni valore (letterale e risultato di ogni operazione): complesso → non reale; intero con `abs(v) >= 10 ** CIFRE_MASSIME` → troppo grande (confronto numerico, mai `str`); float non finito o `abs(v) > VALORE_MASSIMO` → troppo grande. Catturare `ZeroDivisionError`, `OverflowError` attorno al calcolo e `RecursionError`, `MemoryError` attorno a parse e visita.

- [ ] **Step 4: Eseguire i test e vederli passare**

Run: `python -m pytest tests/test_valutatore.py -q` → tutti passati. Poi `python -m pytest -q` → nessuna regressione.

- [ ] **Step 5: Commit**

```bash
git add server_calcolatrice/__init__.py server_calcolatrice/valutatore.py tests/test_valutatore.py
git commit -m "feat(calcolatrice): valutatore aritmetico sicuro senza eval"
```

---

### Task 2: Server MCP della calcolatrice

**Files:**
- Create: `server_calcolatrice/server.py`, `server_calcolatrice/__main__.py`
- Test: `tests/test_server_calcolatrice.py`

**Interfaces:**
- Consumes: `valuta`, `formatta`, `ErroreEspressione` (Task 1).
- Produces: `def crea_server() -> FastMCP` in `server_calcolatrice/server.py` (nome server `"Calcolatrice del laboratorio"`), tool `calculate(expression: str) -> dict`; avvio con `python -m server_calcolatrice`.

- [ ] **Step 1: Scrivere i test che falliscono**, con gli helper `con_client`/`catalogo` di `tests/test_server_note.py` (importarli, non riscriverli: sono generici sul server).

- `test_catalogo_un_tool`: `set(catalogo(crea_server())) == {"calculate"}`; `inputSchema["required"] == ["expression"]`, tipo `string`.
- `test_descrizione_dichiara_le_regole`: la descrizione contiene `"+ - * / // % **"`, `"punto"`, `"resto"` e `"percentual"` (dice che `%` non è la percentuale).
- `test_calcolo`: `call_tool("calculate", {"expression": " (12.5 + 7) * 3 "})` → `structured_content == {"espressione": "(12.5 + 7) * 3", "risultato": 58.5}`.
- `test_risultato_arrotondato`: `"0.1 + 0.2"` → `risultato == 0.3`; `"7 / 7"` → `risultato == 1`.
- `test_errore_diventa_errore_mcp`: `"10 / 0"` con `raise_on_error=False` → `is_error` e `content[0].text == "divisione per zero"`.
- `test_input_ostile_rifiutato`: `"__import__('os').system('echo x')"` → `is_error`, testo contiene `"chiamata di funzione"`.

- [ ] **Step 2: Eseguire e vedere fallire** — `python -m pytest tests/test_server_calcolatrice.py -q` → import error.

- [ ] **Step 3: Implementare** `crea_server()` come `server_note/server.py`: `ErroreEspressione` → `ToolError(str(errore))`. Docstring del tool (copia fissata):

```
Calcola un'espressione aritmetica e restituisce espressione e risultato.
Operazioni ammesse: + - * / // % ** e parentesi tonde, con numeri interi o decimali.
I decimali si scrivono con il punto (12.5). % è il resto della divisione, non la percentuale:
per una percentuale moltiplica (il 15% di 240 è 240 * 15 / 100).
Funzioni, nomi e altri simboli non sono ammessi: in quel caso restituisce un errore.
```

`server_calcolatrice/__main__.py`: `crea_server().run(show_banner=False, log_level="WARNING")`.

- [ ] **Step 4: Eseguire e vedere passare** — file nuovo e suite intera.

- [ ] **Step 5: Commit** — `feat(calcolatrice): server MCP con il tool della calcolatrice`

---

### Task 3: Client MCP generico e client della calcolatrice

**Files:**
- Create: `assistente/client_mcp.py`, `assistente/calcolatrice_mcp.py`
- Modify: `assistente/note_mcp.py` (resta solo `ClientNote`)
- Test: `tests/test_calcolatrice_mcp.py`; `tests/test_note_mcp.py` invariato e verde

**Interfaces:**
- Produces:
  - `assistente/client_mcp.py`: `class ClientMCP` con `__init__(self, modulo: str, descrizione: str, percorso_log_server: Path, ambiente: dict[str, str] | None = None, timeout: float = 20.0, python: str = sys.executable)`, metodi invariati rispetto a oggi (`apri`, `strumenti`, `chiama`, `chiudi`, context manager). Avvia `[python, "-m", modulo]` con `env={**os.environ, **ambiente}`. Messaggi: `f"server {descrizione} non avviato (...)"`, `f"server {descrizione} non collegato"`. Contiene anche `_testo` e `RADICE_PROGETTO`.
  - `assistente/note_mcp.py`: `class ClientNote(ClientMCP)` con la **stessa firma di oggi** `(percorso_note, fuso, percorso_log_server, timeout=20.0, python=sys.executable)` → `modulo="server_note"`, `descrizione="delle note"`, ambiente `PERCORSO_NOTE` (assoluto) e `FUSO_PREDEFINITO`.
  - `assistente/calcolatrice_mcp.py`: `class ClientCalcolatrice(ClientMCP)` con `(percorso_log_server, timeout=20.0, python=sys.executable)` → `modulo="server_calcolatrice"`, `descrizione="della calcolatrice"`.

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_calcolatrice_mcp.py` (server vero via stdio, fixture con `ClientCalcolatrice(tmp_path / "server_calcolatrice.log")`):

- `test_discovery_dal_server`: nomi `== {"calculate"}`; descrizione e `args_schema` uguali a `catalogo(crea_server())`; i sorgenti di `client_mcp.py`, `note_mcp.py`, `calcolatrice_mcp.py` non contengono nessuno dei quattro nomi dei tool.
- `test_invocazione`: `json.loads(strumento.invoke({"expression": "6 * 7"}))["risultato"] == 42`.
- `test_espressione_rifiutata_e_toolexception`: `"sqrt(4)"` → `pytest.raises(ToolException, match="chiamata di funzione")`.
- `test_avvio_fallito_nomina_la_calcolatrice`: con `python=str(tmp_path / "manca.exe")` → `ErroreCollegamento` con `"calcolatrice"` nel messaggio.
- `test_dopo_chiusura_errore_di_collegamento`: dopo `chiudi()`, invocare → `ErroreCollegamento`.

- [ ] **Step 2: Eseguire e vedere fallire** — import error su `assistente.calcolatrice_mcp`.

- [ ] **Step 3: Spostare il codice** di `ClientNote` in `ClientMCP` (parametrizzando modulo, descrizione, ambiente) e creare le due sottoclassi. Aggiornare `test_discovery_dal_server` di `tests/test_note_mcp.py` solo se necessario per includere `client_mcp.py` tra i sorgenti controllati.

- [ ] **Step 4: Eseguire** `python -m pytest tests/test_calcolatrice_mcp.py tests/test_note_mcp.py tests/test_note_grafo.py -q`, poi la suite intera: tutto verde.

- [ ] **Step 5: Commit** — `refactor(mcp): client MCP generico per più server` e `feat(calcolatrice): client MCP della calcolatrice` (due commit se il refactor passa da solo i test esistenti prima di aggiungere `ClientCalcolatrice`).

---

### Task 4: Assistente con due server e istruzioni

**Files:**
- Modify: `assistente/__main__.py`, `assistente/modello.py`
- Test: `tests/test_avvio.py`, `tests/test_calcolatrice_grafo.py` (nuovo)

**Interfaces:**
- Consumes: `ClientNote`, `ClientCalcolatrice` (Task 3).
- Produces: `main()` che apre nell'ordine note → calcolatrice; strumenti = `[orologio, *note.strumenti(), *calcolatrice.strumenti()]`; `finally` chiude entrambi. In caso di `ErroreCollegamento`: stampa `f"Impossibile avviare il server {descrizione} ({errore}). Vedi {log}."` (descrizione `"delle note"` / `"della calcolatrice"`, log `logs/server_note.log` / `logs/server_calcolatrice.log` nella cartella di `PERCORSO_LOG`) e restituisce 1.

- [ ] **Step 1: Scrivere i test che falliscono**

In `tests/test_avvio.py`:
- `test_calcolatrice_non_parte`: `ClientNote` sostituito da un finto che si apre e conta le chiusure, `ClientCalcolatrice` da un finto il cui `apri` solleva `ErroreCollegamento("server della calcolatrice non avviato (x)")` → `main() == 1`, stdout contiene `"Impossibile avviare il server della calcolatrice"` e `"server_calcolatrice.log"`, entrambi i finti chiusi una volta.
- `test_ctrl_c_durante_avvio_server` esistente: monkeypatch anche `ClientCalcolatrice` con lo stesso finto; deve restare verde.

In `tests/test_calcolatrice_grafo.py` (server veri, `ModelloFinto` da `tests/finti.py`, come `tests/test_note_grafo.py`):
- `test_chiamata_alla_calcolatrice`: il modello finto chiede `calculate` con `{"expression": "2 + 3"}`, poi risponde «Fa 5.» → `ToolMessage` con lo stesso `tool_call_id` e contenuto con `"risultato": 5`; log con `strumento=calculate` e `esito=successo`.
- `test_errore_della_calcolatrice_arriva_al_modello`: `"10 / 0"` → `ToolMessage` contiene `divisione per zero`; log `esito=errore_strumento`.
- `test_calcolatrice_chiusa_gli_altri_funzionano`: client note e calcolatrice aperti, poi `calcolatrice.chiudi()`; il modello chiede nello stesso turno `calculate` e `list_notes` → log con `esito=errore_collegamento` per `calculate` e `esito=successo` per `list_notes`.
- `test_istruzioni_citano_la_calcolatrice`: `istruzioni_sistema("Europe/Rome")` contiene `calculate`, `punto`, `240 * 15 / 100`.

(Verificare nel test esistente di `tests/test_note_grafo.py` il formato reale delle righe di log e adattare le stringhe cercate.)

- [ ] **Step 2: Eseguire e vedere fallire.**

- [ ] **Step 3: Implementare.** In `istruzioni_sistema` aggiungere (copia fissata):

```
Calcoli: per ogni calcolo usa sempre lo strumento `calculate`, non fare i conti a mente.
Scrivi i decimali con il punto. Il simbolo % è il resto della divisione: traduci le
percentuali in moltiplicazioni (il 15% di 240 è 240 * 15 / 100). Se `calculate`
restituisce un errore, riferiscilo all'utente senza inventare un risultato.
```

- [ ] **Step 4: Suite intera verde.** Poi prova manuale rapida: `python -m assistente` parte e `esci` saluta senza traceback (con `.env` compilato).

- [ ] **Step 5: Commit** — `feat(assistente): calcolatrice MCP accanto a orologio e note`

---

### Task 5: Prova reale con LM Studio

**Files:**
- Modify: `tests/test_reale_lmstudio.py`

- [ ] **Step 1: Scrivere i test reali.** Aggiungere la fixture `calcolatrice` (`ClientCalcolatrice(tmp_path / "server_calcolatrice.log")`) e far legare a `chiedi` **tutti e tre** gli strumenti (orologio, note, calcolatrice), così i test esistenti delle note verificano anche che funzionino con la calcolatrice presente. Nuovi test:
- `test_reale_calcolo`: «Quanto fa (12,5 + 7) * 3?» → `"calculate" in chiamati`; `"58,5"` o `"58.5"` nella risposta.
- `test_reale_divisione_per_zero`: «Quanto fa 10 diviso 0?» → `"calculate" in chiamati`; log con `esito=errore_strumento`; risposta contiene `"zero"`.
- `test_reale_percentuale`: «Quanto è il 15% di 240?» → `"calculate" in chiamati`; `"36"` nella risposta.

- [ ] **Step 2: Suite senza modello** — `python -m pytest -q`: i reali risultano `skipped`.

- [ ] **Step 3: Prova reale** (PowerShell):

```powershell
$env:PROVA_LMSTUDIO = "1"
python -m pytest tests/test_reale_lmstudio.py -q
```

Expected: tutti passati con `google/gemma-4-e2b`. Se il modello calcola a mente o sbaglia: migliorare istruzioni o descrizione del tool (non il modello), ripetere, e se il problema resta documentarlo con gli esempi senza dichiarare il task completato.

- [ ] **Step 4: Commit** — `test(calcolatrice): prova reale con LM Studio`

---

### Task 6: Docker, README e CLAUDE.md

**Files:**
- Modify: `Dockerfile` (`COPY server_calcolatrice/ server_calcolatrice/`), `README.md`, `CLAUDE.md`

- [ ] **Step 1: Docker.** Da PowerShell:

```powershell
docker compose build
docker compose run --rm -T assistente python -c "import server_calcolatrice.server, assistente.calcolatrice_mcp; print('ok')"
```

Expected: `ok`. Poi `docker compose run --rm assistente` e una domanda di calcolo dal vero; controllare in `logs/assistente.log` la riga di `calculate`.

- [ ] **Step 2: README.** Aggiungere: la calcolatrice (operazioni ammesse, `%` = resto, decimali con il punto, limiti), il secondo server e il suo log `logs/server_calcolatrice.log`, il messaggio `Impossibile avviare il server della calcolatrice (...)` nella diagnosi, i nuovi file di test. Solo comandi verificati in questo piano.

- [ ] **Step 3: CLAUDE.md.** Struttura (`server_calcolatrice/`, `client_mcp.py`, `calcolatrice_mcp.py`, nuovi test); Confini: «MCP è ammesso per le note e per la calcolatrice (due server, entrambi stdio)»; Obiettivo: riga sulla calcolatrice sicura.

- [ ] **Step 4: Verifica finale** — `python -m pytest -q` verde; `git status` pulito dopo il commit.

- [ ] **Step 5: Commit** — `docs: calcolatrice MCP in README e CLAUDE.md` (con `build(docker): ...` separato per il Dockerfile).
