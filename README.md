# Personal Node

A Windows background service that runs a local HTTP server, exposes it through an `ngrok` tunnel, and optionally emails you the public link when the server starts.

Protected file routes (`/files`, `/view`, `/upload`) use a login page and a **5-day session cookie** so random visitors cannot browse or upload to your machine.

---

## Requirements

- Windows 10 or later
- Python 3.10+
- [ngrok](https://ngrok.com/) installed and authenticated
- Python packages:

```bash
pip install python-dotenv requests
```

---

## Quick Start

### 1. Create `.env`

Create a `.env` file in the project root:

```env
# Email notification (optional)
SENDER_EMAIL=your@gmail.com
RECEIVER_EMAIL=you@gmail.com
APP_PASSWORD=your_gmail_app_password

# ngrok custom domain (optional)
NGROK_DOMAIN=your-subdomain.ngrok-free.app

# Required for file access
FILE_AUTH_USERNAME=your_username
FILE_AUTH_PASSWORD=your_strong_password
FILE_AUTH_SESSION_DAYS=5
```

If `FILE_AUTH_USERNAME` or `FILE_AUTH_PASSWORD` is missing, file browsing, viewing, and uploads are disabled.

### 2. Run setup once

From the project root:

```bash
python bin/setup.py
```

This will:

- Generate `bin/start-personal-node.vbs`
- Copy that script into your Windows Startup folder so it runs on boot
- Create the global `handle-personal-node` command in `bin/`
- Add `bin/` to your user `PATH`

Close and reopen your terminal after setup so the `PATH` change takes effect.

### 3. Start the service

```bash
handle-personal-node prod
```

Or run in test mode with live terminal output:

```bash
handle-personal-node test
```

In test mode, start ngrok separately in another terminal:

```bash
ngrok http 8080
```

---

## Command Line Usage

```bash
handle-personal-node <command>
```

| Command | Description |
| :--- | :--- |
| `prod` | Start production service in the background |
| `test` | Start test server in the foreground with live logs |
| `stop` | Stop running `ngrok` and Personal Node Python processes |
| `restart` | Stop everything, then start production mode again |
| `status` | Show active `ngrok` and Python processes |
| `logs` | Stream production logs from `logs/server.log` |

---

## HTTP Routes

| Route | Auth required | Description |
| :--- | :---: | :--- |
| `/` | No | Public home page |
| `/login` | No | Sign in to access files |
| `/logout` | No | End the current session |
| `/files` | Yes | Browse folders under `ROOT_FOLDER` |
| `/view/...` | Yes | View a file inline |
| `/upload/...` | Yes | Upload a file into a folder |

When you open a protected route, you are redirected to `/login`. After signing in, the server sets a cookie that lasts **5 days** (configurable). Use **Log out** in the file browser to end the session early.

---

## Configuration

Settings live in `config.py` and `.env`.

| Variable | Required | Description |
| :--- | :---: | :--- |
| `FILE_AUTH_USERNAME` | Yes | Username for file routes |
| `FILE_AUTH_PASSWORD` | Yes | Password for file routes |
| `FILE_AUTH_SESSION_DAYS` | No | Cookie lifetime in days (default: `5`) |
| `SENDER_EMAIL` | No | Gmail address used to send live-link emails |
| `RECEIVER_EMAIL` | No | Email address that receives live-link emails |
| `APP_PASSWORD` | No | Gmail app password for SMTP |
| `NGROK_DOMAIN` | No | Reserved ngrok domain from the [ngrok dashboard](https://dashboard.ngrok.com/domains) |

Ports:

- Production: `8000`
- Test: `8080`

The file root defaults to `C:\` in `config.py`. Change `ROOT_FOLDER` there if you want to expose a different directory.

---

## Directory Structure

```text
Personal Node/
├── bin/
│   ├── handle-personal-node.py   # CLI manager
│   ├── handle-personal-node.cmd  # Global command wrapper (generated)
│   ├── setup.py                  # One-time setup script
│   └── start-personal-node.vbs   # Background launcher (generated)
├── email_service/
│   └── sender.py                 # Live-link email notification
├── logs/
│   └── server.log                # Production server log
├── server/
│   ├── auth.py                   # Session cookie auth
│   ├── handler.py                # HTTP request handler
│   ├── html/                     # HTML page templates
│   ├── templates.py              # Template loader
│   └── urls.py                   # URL helpers
├── config.py                     # App configuration
├── main.py                       # Entry point
└── README.md
```

---

## Security Notes

- File routes are protected with a login page and a session cookie.
- Sessions expire after `FILE_AUTH_SESSION_DAYS` (default 5 days).
- Keep `.env` out of version control. It is already listed in `.gitignore`.
- Use a strong, unique password for `FILE_AUTH_PASSWORD`.
- Always use HTTPS through ngrok in production.
- Restrict `ROOT_FOLDER` to only the directories you actually need to share.
