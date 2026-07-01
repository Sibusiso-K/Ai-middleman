# AI Middleman — Complete Setup Guide

## Prerequisites

- Windows 11 with Docker Desktop installed
- Python 3.11+ installed
- Git installed
- ngrok auth token (free account at https://ngrok.com)
- Meta Developer account with WhatsApp Business App configured

---

## Step 1: Clone and Configure

Open **VS Code** and open a terminal (`Ctrl+` `):

```cmd
cd "C:\Users\lovilocal.adm\Desktop\AI Middleman"
git clone https://github.com/Sibusiso-K/Ai-middleman.git
cd ai-middleman
```

### Configure `.env` file

Copy the example and fill in your credentials:

```cmd
copy .env.example .env
```

Edit `.env` with your actual values:

```env
# Database
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/aimiddleman

# WhatsApp Cloud API
WHATSAPP_APP_SECRET=your_app_secret_from_meta_dashboard
WHATSAPP_VERIFY_TOKEN=ai_middleman_verify_2026
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_BUSINESS_ACCOUNT_ID=your_business_account_id
WHATSAPP_ACCESS_TOKEN=your_permanent_access_token
WHATSAPP_VERIFY_SSL=false

# LLM (Featherless.ai)
FEATHERLESS_API_KEY=your_featherless_api_key
FEATHERLESS_MODEL=meta-llama/Meta-Llama-3.1-8B-Instruct
```

---

## Step 2: Start Docker (PostgreSQL)

Make sure **Docker Desktop** is running (check system tray), then:

```cmd
docker-compose up -d
```

Verify the database is running:

```cmd
docker ps
```

You should see `ai-middleman-db-1` with status "Up".

### Run migrations (first time only):

```cmd
docker exec -i ai-middleman-db-1 psql -U postgres -d aimiddleman < migrations/001_create_tables.sql
docker exec -i ai-middleman-db-1 psql -U postgres -d aimiddleman < migrations/002_privacy_tables.sql
```

### Import contacts (first time only):

```cmd
pip install asyncpg python-dotenv
python data/import_contacts.py
```

---

## Step 3: Start the FastAPI Server

Open a **new terminal** in VS Code (`Ctrl+Shift+` `):

```cmd
cd "C:\Users\lovilocal.adm\Desktop\AI Middleman\ai-middleman"
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

Verify it's working:
```cmd
curl http://localhost:8000/health
```

---

## Step 4: Start ngrok Tunnel

Open a **new terminal** in VS Code:

```cmd
cd "C:\Users\lovilocal.adm\Desktop\AI Middleman\ai-middleman"
pip install pyngrok
python dev_tunnel.py
```

You'll see output like:
```
Public webhook URL: https://plating-marmalade-outthink.ngrok-free.dev
Use this in Meta dashboard as Callback URL:
https://plating-marmalade-outthink.ngrok-free.dev/webhook/whatsapp
```

**Copy this URL** and paste it into your Meta App Dashboard:
- Go to **WhatsApp > Configuration > Callback URL**
- Paste: `https://YOUR-NGROK-URL.ngrok-free.dev/webhook/whatsapp`
- Verify token: `ai_middleman_verify_2026`
- Click **Verify and Save**

---

## Step 5: Start the Streamlit Dashboard

Open a **new terminal** in VS Code:

```cmd
cd "C:\Users\lovilocal.adm\Desktop\AI Middleman\ai-middleman"
pip install streamlit plotly pandas asyncpg requests python-dotenv
streamlit run dashboard/app.py --server.port 8501
```

The dashboard opens at: **http://localhost:8501**

---

## Step 6: Test the Full Flow

### Test 1: API health check
```cmd
curl http://localhost:8000/health
```

### Test 2: Match query
```cmd
curl -X POST http://localhost:8000/match -H "Content-Type: application/json" -d "{\"query\": \"I need a credit finance specialist in London\"}"
```

### Test 3: Send a WhatsApp message
Send a message from your personal WhatsApp to the business number (e.g., `+27 65 074 6242`).

You should receive a reply within 2-3 seconds with matched contacts.

### Test 4: Request an introduction
Reply with a number (1-5) to request an introduction. The request appears in the dashboard under **Pending Approvals**.

### Test 5: Approve in dashboard
Go to http://localhost:8501 → **Pending Approvals** → Click ✅ Approve.

The requester receives a WhatsApp message with the full contact details.

---

## Quick Restart (All Services)

If you need to restart everything after a reboot:

### Terminal 1 — Docker:
```cmd
cd "C:\Users\lovilocal.adm\Desktop\AI Middleman\ai-middleman"
docker-compose up -d
```

### Terminal 2 — FastAPI:
```cmd
cd "C:\Users\lovilocal.adm\Desktop\AI Middleman\ai-middleman"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 3 — ngrok:
```cmd
cd "C:\Users\lovilocal.adm\Desktop\AI Middleman\ai-middleman"
python dev_tunnel.py
```

### Terminal 4 — Dashboard:
```cmd
cd "C:\Users\lovilocal.adm\Desktop\AI Middleman\ai-middleman"
streamlit run dashboard/app.py --server.port 8501
```

---

## Running Services Summary

| Service | URL | Terminal |
|---------|-----|----------|
| PostgreSQL | `localhost:5432` | Docker (background) |
| FastAPI | `http://localhost:8000` | Terminal 2 |
| ngrok | `https://xxx.ngrok-free.dev` | Terminal 3 |
| Dashboard | `http://localhost:8501` | Terminal 4 |

---

## Troubleshooting

### "Connection refused" on port 5432
→ Docker Desktop is not running. Start it from the Start Menu.

### "Connection refused" on port 8000
→ FastAPI server is not running. Check Terminal 2.

### WhatsApp messages not being received
→ Check ngrok tunnel is running (Terminal 3). Update the Callback URL in Meta dashboard if the ngrok URL changed.

### "Invalid webhook signature" in logs
→ Check `WHATSAPP_APP_SECRET` in `.env` matches the Meta App Dashboard.

### "Recipient is not a valid test number"
→ You're using the test phone number. Switch to the registered business number or add the recipient to the test number's allowlist.

### Dashboard shows "Database Offline"
→ Docker container is not running. Run `docker-compose up -d`.