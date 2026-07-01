# Setup Guide — AI Middleman

This guide walks you through setting up the AI Middleman system from scratch on a new machine.

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | python.org |
| Docker Desktop | Latest | docker.com |
| Git | Latest | git-scm.com |
| ngrok account | Free | ngrok.com |
| Featherless.ai account | Free | featherless.ai |
| Meta Developer account | Free | developers.facebook.com |

## Step-by-Step Setup

### 1. Clone the repository
```bash
git clone https://github.com/Sibusiso-K/Ai-middleman.git
cd Ai-middleman
```

### 2. Create and activate virtual environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
```
Open `.env` and fill in all required values. See the README for descriptions of each variable.

### 5. Start PostgreSQL with Docker
```bash
docker compose up -d
```
Wait 10 seconds, then verify it's running:
```bash
docker ps
```
You should see a container named `ai-middleman-db-1` with status `Up`.

### 6. Generate contact data
```bash
python generate_contacts.py
```
This creates `contacts.csv` (50,000 synthetic professional contacts) and `contacts_sample.xlsx` (first 200 rows for inspection).

### 7. Import contacts to database
```bash
python data/import_contacts.py
```
Expected output:
```
Found 50000 rows. Importing...
Progress: 1000/50000
...
Done! Inserted: 50000, Skipped: 0
```

### 8. Verify the database
```bash
docker exec -it ai-middleman-db-1 psql -U postgres -d aimiddleman -c "SELECT COUNT(*) FROM contacts;"
```
Expected: `50000`

### 9. Start the API server
```bash
uvicorn app.main:app --reload
```
Expected output:
```
Database connected successfully!
Application startup complete.
Uvicorn running on http://127.0.0.1:8000
```

### 10. Test the matching engine
```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"query": "I need a credit finance specialist in London"}'
```
You should receive a JSON response with ranked contacts and confidence scores.

### 11. Start the Streamlit dashboard (optional)
```bash
cd dashboard
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

### 12. Set up WhatsApp webhook
Follow the WhatsApp Setup section in README.md.

## Troubleshooting

**`Application startup failed` — PostgreSQL connection error**
```bash
docker compose up -d
# Wait 10 seconds, then restart uvicorn
```

**`ModuleNotFoundError`**
```bash
pip install -r requirements.txt
```

**`source` not recognized (Windows)**
```bash
venv\Scripts\activate  # Use this instead
```

**ngrok URL case sensitivity error**
Always copy the ngrok URL directly from the terminal output. Never retype it manually — case matters.

**WhatsApp 401 Unauthorized**
Your access token has expired. Generate a new permanent token from Meta dashboard → Step 2 → Test your registered number.

**WhatsApp #131030 Recipient not in allowed list**
Your app may be unpublished. Go to Meta dashboard → Publish and complete the publishing process.