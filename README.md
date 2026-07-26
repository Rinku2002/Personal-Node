# Personal Node

A background service manager that runs a Python server alongside an `ngrok` tunnel on Windows.

---

## 🚀 Quick Start

### 1. Initial Setup
Run the setup script **once** from the project root. This will:
* Generate `start-personal-node.vbs` dynamically.
* Register `start-personal-node.vbs` in the Windows Startup folder (runs on boot).
* Add the project's `bin/` folder to your User `PATH` environment variable.

```bash
python setup.py
```

> ⚠️ **Important:** After running `setup.py`, close and reopen your terminal or PowerShell session for the `PATH` changes to take effect.

---

## 🛠️ Command Line Usage

Once setup is complete, you can run `handle-personal-node` from **any directory** in your terminal.

```bash
handle-personal-node <command>
```

### Available Commands

| Command | Description |
| :--- | :--- |
| `handle-personal-node prod` | Start production service in background using `start.vbs` |
| `handle-personal-node test` | Start test service in foreground with live terminal logs |
| `handle-personal-node stop` | Forcefully kill all running `ngrok` and Python instances |
| `handle-personal-node restart` | Stop all services and restart in production mode |
| `handle-personal-node status` | Display active `ngrok` and Python processes |
| `handle-personal-node logs` | Stream live server logs (`logs/server.log`) |

---

## 📁 Directory Structure

```text
Personal Node/
├── bin/
│   ├── handle-personal-node.py   # CLI logic
│   └── handle-personal-node.bat  # Global execution wrapper
├── logs/
│   └── server.log                # Production output log
├── main.py                       # Core Python application
├── setup.py                      # One-click environment setup
├── start.vbs                     # Background launcher script
└── README.md
```

ngrok config
 - Set ngrok domain in `.env`. Check available domains: https://dashboard.ngrok.com/domains
