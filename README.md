# Server Guardian (Server Management Semiautomatico) - v1.0

[![Target OS](https://img.shields.io/badge/OS-Ubuntu%20Linux-orange?logo=ubuntu)](https://ubuntu.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-SDK-2496ED?logo=docker)](https://docker.com)
[![TUI](https://img.shields.io/badge/TUI-Textual-green)](https://textual.textualize.io)

**Server Guardian** è un sistema di server management per ambienti Linux Ubuntu basato su un'architettura **Client-Daemon**. Il sistema combina un demone di background residente in `systemd` (per il monitoraggio continuo, la sicurezza e l'esecuzione di task notturni schedulati) e una dashboard interattiva a terminale (TUI) in stile `htop` per la supervisione in tempo reale e la gestione manuale degli aggiornamenti.

---

## 🚀 Funzionalità Principali

* **Architettura Client-Daemon:** Comunicazione bidirezionale ad alte prestazioni tramite Unix Domain Socket (`IPC`).
* **Task Schedulati Notturni (ore 02:00):**
  * **Aggiornamento di Sistema Ubuntu (`apt`):** Esecuzione autonoma di `update` e `upgrade`. In caso di errori, notifica immediata via email.
  * **Verifica & Aggiornamento Container Docker:**
    * *Nuove Major o Minor stabili:* Aggiornamento automatico (pull, stop, ricreazione conservando porte, volumi, reti ed environment). Notifica immediata in caso di fallimento.
    * *Release Incrementali (Patch):* Aggiornamento automatico bloccato, notifica via email e aggiunta alla lista *"In attesa"* per approvazione manuale.
    * *Tag `:latest`:* Nessun aggiornamento automatico, notifica email e richiesta di conferma via dashboard.
* **Sistema Notifiche Email:**
  * Invio simultaneo a due destinatari (principale e backup) via SMTP.
  * Messaggi formulati in lingua inglese (US) con linguaggio naturale chiaro e descrittivo.
* **Dashboard Interattiva TUI (Textual):**
  * Monitoraggio real-time di CPU, RAM, utilizzo rete e processi (`psutil`).
  * Vista container Docker: stato di salute, ID, tag e versioni.
  * Pannello approvazione aggiornamenti: elenco patch in sospeso e pulsante di forzatura manuale.
  * Schermata impostazioni: configurazione SMTP e salvataggio chiavi API LLM.
* **Sicurezza & Cifratura:**
  * Gestione credenziali e password con cifratura simmetrica locale e file chiave a permessi ristretti (`chmod 600`).
  * Gestione dei privilegi con l'utente corrente: test non-interattivo e fallback su elevazione tramite password protetta.
* **Predisposizione Agentic LLM:** Supporto per il salvataggio di API key (OpenAI, Anthropic, Gemini, ecc.) per future funzionalità di analisi autonoma dei log e diagnostica.

---

## 🏛️ Architettura del Progetto

```text
ServerManager/
├── FS Server Manager.md        # Specifica tecnica originale
├── README.md                   # Documentazione di progetto e installazione
├── .gitignore                  # File e segreti esclusi dal versioning
├── pyproject.toml              # Definizione progetto e dipendenze
├── systemd/
│   └── server-guardian.service # File unità di servizio systemd
└── server_guardian/
    ├── config.py               # Gestione configurazione persistente
    ├── security.py             # Crittografia simmetrica locale credenziali
    ├── mailer.py               # Servizio SMTP a doppio destinatario
    ├── daemon.py               # Demone di background
    ├── cli.py                  # Entrypoint CLI rapido
    ├── core/
    │   ├── metrics.py          # Rilevamento metriche di sistema
    │   ├── system_updater.py   # Aggiornamento pacchetti apt ed elevazione sudo
    │   ├── docker_manager.py   # Ispezione SemVer e lifecycle container
    │   └── scheduler.py        # Schedulatore task notturni (02:00)
    ├── ipc/
    │   ├── server.py           # Unix Domain Socket Server (Demone)
    │   └── client.py           # Unix Domain Socket Client (TUI)
    └── tui/
        ├── app.py              # Applicazione Textual
        ├── styles.tcss         # Stili grafici della dashboard
        └── views/              # Viste (Monitor, Docker, Updates, Settings)
```

---

## 📋 Prerequisiti

* **Sistema Operativo:** Ubuntu Linux (20.04 LTS, 22.04 LTS o superiore)
* **Python:** Versione 3.10 o superiore
* **Docker:** Docker Engine installato e attivo
* Utente di sistema con accesso al gruppo `docker` o permessi `sudo`

---

## 🛠️ Guida all'Installazione

### 1. Clonazione del Repository

```bash
git clone https://github.com/GonnyTech/ServerManager.git
cd ServerManager
```

### 2. Creazione dell'Ambiente Virtuale Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### 3. Configurazione Iniziale delle Credenziali

Avvia la CLI in modalità configurazione per generare la chiave di cifratura simmetrica protetta e salvare i parametri iniziali:

```bash
server-guardian configure
```

Ti verrà richiesto di inserire:
* Password di sistema (verrà criptata e memorizzata con permessi `600`)
* Parametri server SMTP (Host, Porta, Username, Password/App-Token)
* Indirizzo email principale e indirizzo email di backup
* (Opzionale) Chiave API LLM

### 4. Installazione e Avvio del Demone come Servizio `systemd`

Copia il file di servizio in `systemd` e abilitalo per l'utente desiderato:

```bash
sudo cp systemd/server-guardian.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now server-guardian
```

Per verificare lo stato del demone:

```bash
sudo systemctl status server-guardian
```

---

## 🖥️ Utilizzo della Dashboard TUI

Per avviare la console di gestione interattiva a terminale:

```bash
server-guardian
```

### Scorciatoie da Tastiera nella TUI:
* `1` - Tab **Monitoraggio** (Metriche CPU/RAM/Rete/Processi stile `htop`)
* `2` - Tab **Docker** (Panoramica container attivi e versioni)
* `3` - Tab **Aggiornamenti** (Revisione patch e rilascio forzato manuale)
* `4` - Tab **Impostazioni** (Configurazione SMTP, destinatari email e API LLM)
* `q` o `Ctrl+C` - Uscita dalla dashboard (il demone continuerà a girare in background)

---

## 📄 Licenza

Distribuito sotto licenza MIT. Consulta il file `LICENSE` per ulteriori dettagli.
