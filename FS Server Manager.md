# Specifica Tecnica: Tool di Server Management Semiautomatico (Server Guardian) - v1.0

## 1. Panoramica del Progetto
Il progetto consiste nello sviluppo di un tool di system management per ambienti Server Linux Ubuntu, strutturato con un'architettura **Client-Daemon**. Il sistema unisce un demone in background (per il monitoraggio continuo, l'esecuzione di task schedulati notturni e la gestione della sicurezza) a una dashboard interattiva a terminale (TUI) in stile `htop` per il controllo, la configurazione e la gestione manuale.

## 2. Architettura di Sistema
* **Demone di Background (`systemd service`):** 
  * Avvio automatico al boot del sistema e permanenza continua in esecuzione.
  * Gestione dei task schedulati programmati per le ore 02:00 di ogni notte.
  * Raccolta e buffering delle metriche di sistema (CPU, RAM, rete, processi) e stato dei container.
* **Dashboard TUI (`CLI Client`):**
  * Interfaccia grafica testuale interattiva richiamabile da terminale tramite comando rapido.
  * Visualizzazione in tempo reale dello stato del server e dei container.
  * Sezioni dedicate alla configurazione (email, API LLM) e alla gestione/conferma manuale degli aggiornamenti in sospeso.

## 3. Stack Tecnologico & Requisiti Ambientali
* **Linguaggio di Programmazione:** Python.
* **Sistema Operativo Target:** Ubuntu Linux.
* **Runtime Container:** Docker (gestione tramite SDK ufficiale).
* **Interfaccia TUI:** Framework Python moderno per terminali (es. Textual o Rich).

## 4. Gestione Task Schedulati (Ore 02:00 di ogni notte)
Alle ore 02:00 il demone esegue automaticamente la seguente sequenza di operazioni:
1. **Aggiornamento di Sistema:**
   * Esecuzione automatica dei comandi di aggiornamento dei pacchetti di sistema Ubuntu (`apt`).
   * *Gestione Errori:* Se l'aggiornamento di sistema fallisce, viene immediatamente generata e inviata una notifica di errore via email a tutti i destinatari configurati.
2. **Controllo e Aggiornamento Container Docker:**
   * Interrogazione del registro per verificare la disponibilità di nuove versioni dei container attivi.
   * **Politica di aggiornamento automatico:**
     * Se viene rilevata una nuova versione **Major o Minor stabile**, il demone procede autonomamente all'aggiornamento (pull, stop, ricreazione del container con le medesime configurazioni). *Se il processo fallisce, viene inviata una mail di errore.*
     * Se viene rilevata una **Release Incrementale** (es. patch minori), l'aggiornamento automatico viene **bloccato** e viene avviata una procedura di notifica di versione in attesa.

## 5. Sistema di Notifiche Email & Destinatari Multipli
* **Canale:** Invio diretto tramite protocollo SMTP utilizzando le librerie standard di Python.
* **Gestione Indirizzi:** 
  * Configurazione gestita tramite UI/configurazione con supporto a **due indirizzi email** (uno principale e uno di backup).
  * Le notifiche (versioni incrementali in attesa, avvisi di fallimento aggiornamenti) vengono inviate **simultaneamente a entrambi gli indirizzi** nello stesso momento.
* **Configurazione:** Parametri server SMTP, credenziali e indirizzi email salvati in modo protetto.
* **Contenuto del Messaggio:** 
  * Scritto in lingua inglese (us) linguaggio naturale, chiaro e umano (non un log tecnico freddo).
  * Informazioni incluse: nome del container, release attualmente in uso, versione incrementale rilevata o dettagli sull'errore riscontrato.

## 6. Sicurezza e Credenziali di Sistema
* **Salvataggio Password di Sistema:** 
  * La password di sistema necessaria per l'esecuzione automatica dei comandi amministrativi (richiesti dai task schedulati) viene memorizzata in modo **criptato** (tramite moduli di cifratura simmetrica locale in Python).
  * Il demone decifra la password in modo sicuro solo durante l'esecuzione dei comandi protetti pianificati.

## 7. Funzionalità Future & Estensioni (Agentic LLM)
* **Integrazione API LLM:**
  * Predisposizione per l'inserimento e la gestione delle API key di modelli linguistici (LLM) direttamente tramite la TUI.
  * L'integrazione consentirà in futuro di abilitare capacità agentiche per il tool (es. analisi avanzata dei log, diagnosi autonoma dei problemi di sistema o suggerimenti testuali interattivi).

## 8. Dashboard TUI e Menu di Controllo
La dashboard interattiva a terminale offre:
* **Sezione Monitoraggio:** Panoramica in stile `htop` di CPU, RAM, utilizzo della rete e processi attivi.
* **Sezione Container Docker:** Stato di salute, ID immagine e versione corrente dei container.
* **Menu di Conferma Aggiornamenti:** 
  * Elenco dei container per i quali è arrivata la notifica di versione incrementale.
  * Comando/pulsante rapido per **confermare e forzare l'aggiornamento manuale** direttamente dalla TUI.
* **Pannello di Configurazione:** Interfaccia per la gestione dei destinatari email (principale e backup) e l'inserimento/aggiornamento delle chiavi API LLM.