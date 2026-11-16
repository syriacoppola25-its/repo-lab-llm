# Risposte in streaming — specifica

Data: 2026-11-09
Stato: approvata (2026-11-16)

Riferimenti: specifiche precedenti `2026-10-26-assistente-laboratorio-design.md`,
`2026-11-09-note-mcp-design.md` e `2026-11-09-calcolatrice-mcp-design.md`, che restano valide in
tutto ciò che qui non cambia.

## 1. Intento

La consegna del prof chiede di usare lo streaming. In futuro l'assistente verrà collegato a
un'interfaccia frontend, quindi conta non solo l'effetto nel terminale ma il modo in cui la
risposta esce dal programma: a pezzi, attraverso un'interfaccia pulita che oggi usa il terminale e
domani potrà usare un frontend, senza riscrivere il grafo.

Successo significa:
- il testo dell'assistente compare nel terminale man mano che il modello lo genera;
- quando il programma esegue uno strumento compare una riga
  `Interrogando lo strumento <nome>…` (decisione dell'utente), dove `<nome>` è il nome originale
  del tool (`orologio`, `add_note`, `calculate`…), una riga per ogni strumento eseguito;
- dopo lo strumento la risposta riprende in streaming;
- la conferma `s/n` per `delete_note` funziona come oggi;
- cronologia, errori, limite di passaggi, log e strumenti si comportano come prima;
- la prova reale con LM Studio (`google/gemma-4-e4b`) mostra lo streaming vero, anche con
  chiamate a strumenti.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Una funzione che, data la cronologia e la nuova domanda, produce una **sequenza di eventi**
  invece di una risposta unica. Tre tipi di evento:
  - **testo**: un pezzo di testo della risposta;
  - **strumento**: il programma sta per eseguire lo strumento `<nome>`;
  - **fine**: la risposta è conclusa; porta la cronologia aggiornata (tutti i messaggi, come
    oggi `esito["messaggi"]`).
- Il terminale consuma gli eventi e li stampa.
- Test senza modello per eventi e terminale; prova reale con LM Studio separata.

**Non obiettivi (per ora)**
- Frontend, server HTTP, websocket, SSE o qualunque interfaccia grafica.
- Mostrare i token di «ragionamento» del modello, gli argomenti degli strumenti o il loro
  risultato.
- Nomi degli strumenti tradotti in italiano (decisione dell'utente: si usa il nome originale).
- Interrompere una risposta a metà con un comando (Ctrl+C resta com'è oggi: chiude la sessione).
- Codice asincrono: resta tutto sincrono.

**Anti-obiettivi** (sarebbe un fallimento anche se funzionasse)
- Uno streaming «finto»: risposta ottenuta intera e poi stampata a pezzi.
- Il grafo che stampa direttamente nel terminale: gli eventi devono restare indipendenti da chi li
  mostra, altrimenti il frontend futuro richiede di rifare il lavoro.
- Nomi, descrizioni o schemi dei tool MCP riscritti nell'assistente.
- Nuove dipendenze: LangGraph e `langchain-openai` bastano.

## 3. Comportamento nel terminale

Esempio con uno strumento (il testo dopo `Assistente:` compare a pezzi):

```
Tu: quanto fa 12 * 7?
sto pensando…
Interrogando lo strumento calculate…
Assistente: 12 * 7 fa 84.
Tu:
```

Regole:
- `sto pensando…` si stampa come oggi, su una riga, appena inviata la domanda (scelta mia: non si
  cancella, il terminale non lo permette in modo semplice e portabile).
- Il prefisso `Assistente: ` si stampa una volta, prima del primo pezzo di testo di quel tratto di
  risposta; i pezzi seguono sulla stessa riga senza a capo, mostrati subito (flush).
- La riga dello strumento va sempre su una riga sua: se c'era testo in corso, prima si va a capo.
  Se dopo lo strumento il modello scrive altro testo, si ristampa `Assistente: ` (scelta mia).
- La riga dello strumento compare **prima** dell'esecuzione, quindi per `delete_note` compare
  prima della domanda `Eliminare la nota …? (s/n)`. Con risposta `n` la riga resta comunque: lo
  strumento è stato richiesto ma non eseguito, e l'assistente lo riferisce come oggi.
- Alla fine della risposta si va a capo.
- **Testo prima di uno strumento** (decisione dell'utente): se il modello scrive del testo nello
  stesso turno in cui chiede uno strumento (per esempio «Ora calcolo…»), quel testo si mostra in
  streaming come ogni altro. Oggi non compare mai (si stampa solo l'ultimo messaggio): è un
  cambiamento voluto, da indicare nel README. Esempio:
  ```
  Assistente: Ora calcolo…
  Interrogando lo strumento calculate…
  Assistente: 12 * 7 fa 84.
  ```
  Niente trattenuto in attesa di sapere se arriva uno strumento: sarebbe streaming finto.
- Il messaggio del limite di passaggi compare come una risposta normale (`Assistente: …`), anche se
  non viene dal modello; se prima il modello aveva scritto testo, quel testo resta e il messaggio
  del limite compare dopo, con il suo prefisso.
- Se il modello genera una risposta vuota, non si stampa un `Assistente: ` vuoto (scelta mia).

## 4. Errori

- Errore del modello prima di qualunque testo: identico a oggi
  (`Errore: impossibile ottenere una risposta dal modello (<Tipo>). Controlla che LM Studio sia
  avviato.`).
- Errore a metà risposta: il testo già stampato resta, si va a capo, poi lo stesso messaggio
  d'errore. In entrambi i casi la domanda **non** entra nella cronologia e la sessione continua,
  come oggi.
- Ctrl+C durante lo streaming chiude la sessione con il saluto, come oggi durante l'attesa.
- Gli errori degli strumenti restano testo per il modello (nessun cambiamento).

## 5. Che cosa resta com'è

- Struttura del grafo (nodi `modello`, `strumenti`, `limite`; funzione `instrada`), stato,
  conferme, limite di passaggi, log su file (stesse righe, stesso formato).
- I due server MCP e i loro client.
- Le istruzioni di sistema.
- Avvio locale e con Docker Compose (con `docker compose run` il terminale è interattivo, quindi
  lo streaming deve vedersi anche lì).

## 6. Scelte tecniche

Decise in conversazione:
- Interfaccia a eventi indipendente dal terminale, pensata per il frontend futuro.
- Il testo scritto dal modello prima di una chiamata a strumento viene mostrato (vedi 3).
- Testo della riga strumento: `Interrogando lo strumento <nome>…`, nome originale del tool.

Mie scelte (correggibili in revisione):
- Lo streaming usa quello che LangGraph offre già (`grafo.stream` con le sue modalità di
  streaming, per esempio i messaggi del modello per i pezzi di testo e una scrittura personalizzata
  dal nodo `strumenti` per l'evento strumento), non un meccanismo inventato da noi.
- L'evento «strumento» nasce nel nodo `strumenti`, subito prima di eseguire ciascuna richiesta
  (anche quelle con argomenti non validi o strumento sconosciuto, che hanno comunque un nome),
  così l'evento precede la conferma. L'ordine di *stampa* rispetto alla domanda `s/n` non è
  garantito (revisione del 2026-11-16): con lo streaming il nodo gira in un thread di lavoro mentre
  il ciclo principale stampa la riga, e LangGraph non offre un punto di sincronizzazione; in
  pratica la riga esce prima, perché la conferma legge prima la nota dal server. La soluzione
  strutturale (conferma con `interrupt()` di LangGraph) è rimandata a quando ci sarà il frontend.
  Le richieste chiuse dal nodo `limite` non generano l'evento: non vengono eseguite.
- Il messaggio del limite è un «nuovo tratto» di testo (`Testo.nuovo_tratto`): il terminale lo
  stacca da ciò che è già a schermo e lo mostra con il suo prefisso.
- La funzione che produce gli eventi e i tipi di evento stanno in un modulo piccolo e nuovo
  (nome a scelta del costruttore), separato da `grafo.py` e da `terminale.py`.
- `grafo.invoke` deve continuare a funzionare (i test esistenti del grafo lo usano).

## 7. Test e verifiche

Senza modello (nella suite normale):
- sequenza di eventi per: risposta semplice in più pezzi; risposta con uno strumento; due
  strumenti in una domanda; testo prima di uno strumento; limite raggiunto; conferma `n` su `delete_note` (la riga strumento
  precede la domanda di conferma);
- l'evento fine porta la cronologia corretta (stessa di oggi);
- terminale: prefisso una sola volta, pezzi sulla stessa riga, riga strumento su riga sua, errore a
  metà risposta, cronologia invariata dopo un errore, test esistenti di `test_terminale.py`
  adattati senza perdere ciò che verificano;
- il modello finto dei test deve produrre davvero più pezzi, così si verifica lo streaming e non
  una risposta unica.

Prova reale (separata, `PROVA_LMSTUDIO=1`): con `google/gemma-4-e4b`, una domanda senza strumenti
arriva in più di un pezzo di testo; una domanda che richiede `calculate` produce l'evento strumento
e poi testo. Una risposta simulata non dimostra lo streaming di LM Studio.

Prova manuale dell'utente, nel terminale e con Docker Compose: vedere il testo comparire a pezzi e
la riga `Interrogando lo strumento …`.

## 8. Documentazione

- README: una riga sullo streaming e sulla riga strumento; nessun nuovo comando.
- `CLAUDE.md`: aggiornare la struttura se nasce un nuovo modulo.

## 9. Lasciato al costruttore

- Nome del modulo, dei tipi di evento e della funzione.
- Come combinare le modalità di `grafo.stream` e come ottenere la cronologia finale.
- Come il terminale riceve la funzione di scrittura senza a capo (parametro aggiuntivo o altro),
  purché resti testabile senza terminale vero.
- Come far produrre più pezzi al modello finto.
