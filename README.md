# ServerManager (Semi-Automated Server Management) - v1.1

[![Target OS](https://img.shields.io/badge/OS-Ubuntu%20Linux-orange?logo=ubuntu)](https://ubuntu.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-SDK-2496ED?logo=docker)](https://docker.com)
[![TUI](https://img.shields.io/badge/TUI-Textual-green)](https://textual.textualize.io)

**Server Guardian** is a Linux Ubuntu server management system built on a **Client-Daemon** architecture. The system combines a background daemon residing in `systemd` (for continuous monitoring, security, and scheduled nightly tasks) and an interactive terminal dashboard (TUI) styled like `htop` for real-time supervision and manual update management.

---

## 🚀 Key Features

- **Client-Daemon Architecture:** High-performance bidirectional communication via Unix Domain Socket (`IPC`).
- **Scheduled Nightly Tasks (02:00 AM CEST):**
  * **Ubuntu System Update (`apt`):** Autonomous execution of `update` and `upgrade`. In case of errors, immediate email notification.
  * **Docker Container Check & Update:**
    * *New Major or Stable Minor versions:* Automatic update (pull, stop, recreation preserving ports, volumes, networks, and environment). Immediate notification upon failure.
    * *Incremental Releases (Patches):* Automatic update blocked, email notification sent, and added to the *"Pending"* list for manual approval.
    * *`:latest` tag:* No automatic update, email notification, and confirmation request via dashboard.
- **Email Notification System:**
  * Simultaneous sending to two recipients (primary and backup) via SMTP.
  * Messages formulated in US English with clear, descriptive natural language.
- **Interactive TUI Dashboard (Textual):**
  * Real-time monitoring of CPU, RAM, GPU (with hardware transcoding detection NVENC / Intel QuickSync for apps like Jellyfin/Plex), network usage, and processes (`psutil`).
  * Docker container view: health status, ID, tag, and versions.
  * Update approval panel: list of pending patches and manual force-update button.
  * Settings screen: SMTP configuration and LLM API key storage.
- **Security & Encryption:**
  * Management of credentials and passwords with local symmetric encryption and restricted permission key files (`chmod 600`).
  * Privilege management with the current user: non-interactive testing and fallback to elevation via protected password.
- **Agentic LLM Readiness:** Support for saving API keys (OpenAI, Anthropic, Gemini, etc.) for future autonomous log analysis and diagnostic features.

---

## 🏛️ Project Architecture

```text
ServerManager/
├── FS Server Manager.md        # Original technical specification
├── README.md                   # Project documentation and installation
├── .gitignore                  # Files and secrets excluded from versioning
├── pyproject.toml              # Project definition and dependencies
├── systemd/
│   └── server-guardian.service # systemd service unit file
└── server_guardian/
    ├── config.py               # Persistent configuration management
    ├── security.py             # Local symmetric credential encryption
    ├── mailer.py               # Dual-recipient SMTP service
    ├── daemon.py               # Background daemon
    ├── cli.py                  # Quick CLI entrypoint
    ├── core/
    │   ├── metrics.py          # System metrics detection
    │   ├── system_updater.py   # apt package update and sudo elevation
    │   ├── docker_manager.py   # SemVer inspection and container lifecycle
    │   └── scheduler.py        # Nightly task scheduler (02:00 AM)
    ├── ipc/
    │   ├── server.py           # Unix Domain Socket Server (Daemon)
    │   └── client.py           # Unix Domain Socket Client (TUI)
    └── tui/
        ├── app.py              # Textual application
        ├── styles.tcss         # Dashboard graphical styles
        └── views/              # Views (Monitor, Docker, Updates, Settings)

```

---

## 📋 Prerequisites

* **Operating System:** Ubuntu Linux (20.04 LTS, 22.04 LTS or higher)
* **Python:** Version 3.10 or higher
* **Docker:** Docker Engine installed and active
* System user with access to the `docker` group or `sudo` permissions

---

## 🛠️ Installation Guide

### 1. Cloning the Repository

```bash
git clone https://github.com/GonnyTech/ServerManager.git
cd ServerManager

```

### 2. Creating the Python Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

```

### 3. Initial Credential Configuration

Start the CLI in configuration mode to generate the protected symmetric encryption key and save the initial parameters:

```bash
server-guardian configure

```

You will be prompted to enter:

* System password (will be encrypted and stored with `600` permissions)
* SMTP server parameters (Host, Port, Username, Password/App-Token)
* Primary email address and backup email address
* (Optional) LLM API Key

### 4. Installing and Starting the Daemon as a `systemd` Service

Copy the service file to `systemd` and enable it for the desired user:

```bash
sudo cp systemd/server-guardian.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now server-guardian

```

To check the status of the daemon:

```bash
sudo systemctl status server-guardian

```

---

## 🖥️ Using the TUI Dashboard

To start the interactive terminal management console:

```bash
server-guardian

```

### Keyboard Shortcuts in the TUI:

* `1` - **Monitoring** Tab (CPU/GPU/RAM/Network/Process metrics styled like `htop`)
* `2` - **Docker** Tab (Overview of active containers and versions)
* `3` - **Updates** Tab (Patch review and manual force release)
* `4` - **Settings** Tab (SMTP configuration, email recipients, and LLM APIs)
* `q` or `Ctrl+C` - Exit the dashboard (the daemon will keep running in the background)

---

## 📄 License

Distributed under the MIT License. See the `LICENSE` file for more details.
