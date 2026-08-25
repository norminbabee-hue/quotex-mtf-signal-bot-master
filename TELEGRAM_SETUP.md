# Telegram setup

## 1. Create the local `.env` file

In VS Code, inside the **project root** (the same folder that contains `pyproject.toml` and `.env.example`):

1. Create a new file named exactly `.env`.
2. Copy the contents of `.env.example` into `.env`.
3. Replace only these two values:

```env
TELEGRAM_BOT_TOKEN=PASTE_YOUR_BOT_TOKEN_HERE
TELEGRAM_CHAT_ID=PASTE_YOUR_CHAT_ID_HERE
```

For the requested prediction messages, keep:

```env
TELEGRAM_SEND_PREDICTIONS=true
```

Leave the MT5/QuoteX settings as they are unless you specifically need to change them.

## 2. Where the values go

- **Bot token:** after `TELEGRAM_BOT_TOKEN=`
- **Chat ID:** after `TELEGRAM_CHAT_ID=`

Do not add quotes unless your value actually contains them. Do not add spaces around `=`.

## 3. Security

`.env` is intentionally ignored by Git, so the real token and chat ID stay on the local PC and are not committed to GitHub.

**Never paste the real token into `.env.example`, GitHub, screenshots, or chat messages.**

## 4. Test locally

From the project root in PowerShell:

```powershell
python -c "from pathlib import Path; p=Path('.env'); print('ENV EXISTS:', p.exists()); print('TOKEN SET:', any(x.startswith('TELEGRAM_BOT_TOKEN=') and x.split('=',1)[1].strip() for x in p.read_text(encoding='utf-8').splitlines()) if p.exists() else False); print('CHAT ID SET:', any(x.startswith('TELEGRAM_CHAT_ID=') and x.split('=',1)[1].strip() for x in p.read_text(encoding='utf-8').splitlines()) if p.exists() else False)"
```

The command only reports True/False; it does not print the secret values.

Then start the live dashboard:

```powershell
py scripts/run_live_dashboard.py
```

A successful Telegram configuration should produce a log similar to:

```text
Telegram connected successfully: @your_bot | chat_id configured=YES
```

If the token or chat ID is missing or invalid, the bot will log the problem and continue the market scanner without Telegram.
