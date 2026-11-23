# Router: precedenza degli strumenti e temperature=0 — piano

Data: 2026-11-23. Specifica: `docs/superpowers/specs/2026-11-17-router-design.md`
(aggiornamento del 2026-11-23: §3 «Precedenza degli strumenti», §5 `temperature=0`, §9 nuovo caso
reale). Origine: problema Important della revisione finale del router, confermato con
`gemma-4-e4b` («Ricordami di comprare il guanciale» → `fuori_ambito` 2 volte su 2).

Un solo incremento, un commit di codice e uno di documentazione. Nessuna nuova dipendenza,
nessuna variabile d'ambiente nuova. Grafo, nodi, log e messaggi restano come sono.

## Task 1 — istruzioni e temperatura del router (TDD)

File: `assistente/router.py`, `tests/test_router.py`.

1. Test che falliscono, in `tests/test_router.py`:
   - `test_istruzioni_danno_precedenza_agli_strumenti`: il testo di `istruzioni_router()`
     contiene la regola «qualunque sia l'argomento» e l'esempio del guanciale come
     `conversazione`.
   - `test_router_a_temperatura_zero`: `modello_router(config).temperature == 0`, con una
     `Config` di prova (nessuna chiamata al server: costruire `ChatOpenAI` non apre connessioni).
2. Eseguire `python -m pytest tests/test_router.py -q`: i due test falliscono.
3. Codice in `assistente/router.py`:
   - nelle istruzioni, dopo l'elenco delle categorie, la regola: «Se l'utente chiede di
     salvare, elencare o eliminare note, di fare un calcolo o di sapere data e ora, la
     categoria è conversazione qualunque sia l'argomento (anche sport o cucina).»;
   - due esempi in più: «Ricordami di comprare il guanciale» → conversazione, «Salva una
     nota: vedere la partita sabato» → conversazione;
   - nuova funzione `modello_router(config) -> ChatOpenAI` con `temperature=0`;
     `crea_router` la usa (comportamento invariato per il resto).
4. `python -m pytest -q`: tutto verde (atteso 226 passed, 13 skipped).

## Task 2 — caso nella prova reale

File: `tests/test_reale_lmstudio.py`.

- `test_reale_router_nota_fuori_tema`: «Ricordami di comprare il guanciale» → nel log
  `categoria=conversazione` e `prossimo=agente`, `add_note` chiamato, una nota salvata che
  contiene «guanciale».
- Senza `PROVA_LMSTUDIO` il test resta saltato (atteso 226 passed, 14 skipped).

Verifica reale (utente, oppure io con LM Studio acceso): solo i test del router,
`python -m pytest tests/test_reale_lmstudio.py -v -k router` (4 prove), più la sonda delle
6 frasi della revisione (guanciale, partita, calcetto, pizza, ciao, «che cosa sai fare?»)
due volte ciascuna: atteso `conversazione` in tutti i 12 giri.

Commit: `fix(router): note e calcoli in ambito qualunque sia l'argomento`.

## Task 3 — documentazione

- README: regola di precedenza nella sezione dell'ambito, `temperature=0`, conteggi dei test
  aggiornati, nuova prova reale nell'elenco.
- CLAUDE.md: nessun cambio (struttura e comandi invariati).

Commit: `docs: precedenza degli strumenti nel router`.

## Fuori da questo piano

Gli altri Minor della revisione (WARNING su una riga, log degli errori del router, frase su
`gemma-4-e2b` nel README, atteso scritto a mano in `test_router_vede_la_cronologia`, tipo
`Decisione`, saluti nella prova reale): restano annotati nell'handoff, solo su richiesta.
