# Tower Deployment Guide

This guide covers deploying PrivyBot to a Windows tower (always-on server) using NSSM (Non-Sucking Service Manager).

## Prerequisites

- Windows Server or Windows 10/11 tower machine
- Python 3.12 installed
- Git installed
- SSH access or RDP access to the tower
- PrivyBot repository cloned on the tower

## Step 1: Install NSSM

NSSM (Non-Sucking Service Manager) allows running Python scripts as Windows services.

1. Download NSSM from https://nssm.cc/download
2. Extract the zip file
3. Copy `nssm.exe` to a directory in your PATH (e.g., `C:\Windows\System32` or a dedicated tools folder)
4. Verify installation: open Command Prompt and run `nssm version`

## Step 2: Prepare the Environment

On the tower machine:

```powershell
# Navigate to PrivyBot directory
cd C:\Github\PrivyBot

# Install uv if not already installed
pip install uv

# Install dependencies
uv sync

# Create .env file with your secrets
# Copy from your laptop or create manually
```

**Required .env variables:**
```
OPENROUTER_API_KEY=sk-or-v1-...
TELEGRAM_BOT_TOKEN=8275492461:AAFUh-...
TELEGRAM_CHAT_ID=2022758508
DEFAULT_MODEL=deepseek/deepseek-v4-flash:free
DEEP_MODEL=deepseek/deepseek-chat
CLAUDE_MODEL=anthropic/claude-sonnet-4
PRIVY_NAME=PrivyBot
```

## Step 3: Seed the Database

```powershell
cd C:\Github\PrivyBot
uv run python seed.py
```

This creates `privy.db` with the initial memory context.

## Step 4: Create the Service with NSSM

Open Command Prompt as Administrator and run:

```cmd
nssm install PrivyBot
```

NSSM will open a configuration window. Fill in:

**Path:**
```
C:\Users\YourUser\AppData\Local\Programs\Python\Python312\python.exe
```
(Or wherever Python 3.12 is installed on the tower)

**Startup directory:**
```
C:\Github\PrivyBot
```

**Arguments:**
```
-m uv run python privybot.py
```

**Service name:** `PrivyBot`

Click **Install service**.

## Step 5: Configure Service Details

Open the service configuration again:

```cmd
nssm edit PrivyBot
```

**Details tab:**
- Display name: `PrivyBot`
- Description: `Personal AI assistant`
- Startup type: `Automatic`

**Log on tab:**
- Log on as: `Local System account` (or a dedicated service account)
- Allow service to interact with desktop: **unchecked** (not needed for headless service)

**I/O Redirection tab (important for logs):**
- Output file: `C:\Github\PrivyBot\logs\service_stdout.log`
- Error file: `C:\Github\PrivyBot\logs\service_stderr.log`

**Environment tab:**
Add any environment variables if needed (NSSM will read .env from the startup directory, but you can also set them here).

Click **Apply** and **OK**.

## Step 6: Start the Service

```cmd
nssm start PrivyBot
```

Verify it's running:

```cmd
nssm status PrivyBot
```

## Step 7: Verify Bot is Alive

From your phone, send `/status` to the bot. You should see:
- Uptime
- Memory count
- Thread count
- Last model used
- Throttle status

If you get a response, the bot is running correctly.

## Step 8: Check Logs

Logs are written to two locations:

1. **Application logs:** `C:\Github\PrivyBot\logs\privy.log`
2. **Service logs:** `C:\Github\PrivyBot\logs\service_stdout.log` and `service_stderr.log`

Monitor these logs to debug startup issues or runtime errors.

## Remote Management

### Restart the Service

```cmd
nssm restart PrivyBot
```

### Stop the Service

```cmd
nssm stop PrivyBot
```

### View Service Status

```cmd
nssm status PrivyBot
```

### Edit Service Configuration

```cmd
nssm edit PrivyBot
```

### Remove the Service

```cmd
nssm stop PrivyBot
nssm remove PrivyBot confirm
```

## Updating the Bot

When you push changes to GitHub:

```powershell
# On the tower
cd C:\Github\PrivyBot
git pull
uv sync
nssm restart PrivyBot
```

## Development Workflow

Branches:
- `main` — Tower production, never commit directly
- `dev` — active development on laptop
- `experimental` — risky ideas, may never merge

**Tower pulls from main only.** The tower runs the main branch exclusively. All development happens on dev, then merges to main for deployment.

Standard workflow:
```bash
git checkout dev
# [make changes]
uv run python scripts/verify.py
git checkout main
git merge dev
git push origin main
# /deploy from Telegram
```

Hotfix workflow:
```bash
git checkout main
git checkout -b hotfix/description
# [fix the issue]
uv run python scripts/verify.py
git checkout main
git merge hotfix/description
git push origin main
# /deploy from Telegram
```

## Troubleshooting

### Service Won't Start

1. Check service logs: `C:\Github\PrivyBot\logs\service_stderr.log`
2. Verify Python path is correct in NSSM configuration
3. Verify .env file exists and has all required variables
4. Run manually to test: `uv run python privybot.py`

### Bot Not Responding

1. Check `/status` command on Telegram
2. Check `logs/privy.log` for errors
3. Verify TELEGRAM_CHAT_ID matches your Telegram user ID
4. Check OpenRouter API key is valid

### Database Issues

1. Verify `privy.db` exists in the PrivyBot directory
2. Reseed if needed: `uv run python seed.py`
3. Check file permissions on the database

### Network Issues

1. Verify tower has internet access
2. Check firewall allows outbound HTTPS (api.telegram.org, openrouter.ai)
3. Verify DNS resolution is working

## Alternative: Task Scheduler

If you prefer not to use NSSM, you can use Windows Task Scheduler:

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: "At startup"
4. Action: "Start a program"
   - Program: `python.exe` (full path)
   - Arguments: `-m uv run python privybot.py`
   - Start in: `C:\Github\PrivyBot`
5. Conditions: "Run whether user is logged on or not"
6. Settings: "Run task as soon as possible after a scheduled start is missed"

NSSM is preferred for better log management and service control.

## Security Notes

- Rotate your Telegram bot token via @BotFather before making the repo public
- Keep `.env` file secure (it's already in .gitignore)
- Consider using a dedicated service account with minimal permissions
- Restrict SSH/RDP access to the tower
- Keep Python and dependencies updated

## Log Rotation

Logs will grow over time. Set up a log rotation script or manually clean up:

```powershell
# Archive old logs
Compress-Archive -Path logs\privy.log -DestinationPath logs\privy_$(Get-Date -Format 'yyyyMMdd').zip
# Clear current log
Clear-Content logs\privy.log
```

Or use a log rotation tool like `logrotate` (Windows ports available).

## Backup Strategy

Back up these files regularly:

- `privy.db` (contains all memories and threads)
- `.env` (contains API keys)
- `context.yaml` (memory seed configuration)

Automated backup script example:

```powershell
# backup_privybot.ps1
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
Copy-Item privy.db "backups\privy_$timestamp.db"
Copy-Item .env "backups\env_$timestamp.txt"
Copy-Item context.yaml "backups\context_$timestamp.yaml"
```

Schedule this script to run daily via Task Scheduler.
