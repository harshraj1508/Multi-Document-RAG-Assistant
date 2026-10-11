# Setup Guide (New Machine)

How to set up, run, view, and push this project from another system.

---

## ⭐ Easiest path: Docker (one command, runs everything)

Docker Compose starts the three services — API, PostgreSQL + pgvector, and UI —
on a private network. This is the recommended way to run the project.

```bash
cd project-sp

# (optional) set your Groq key so answers use the LLM
export GROQ_API_KEY=your_key_here    # Windows PowerShell: $env:GROQ_API_KEY="your_key_here"

docker compose up --build
```

Then open:
- **UI:** http://localhost:8501
- **API docs:** http://localhost:8000/docs

Then: register → login → upload a `.txt`/`.md` file → ask a question.

> **LLM note:** the app selects a provider automatically — **Groq** if
> `GROQ_API_KEY` is set, otherwise a local **Ollama** if one is running, and as
> a last resort a built-in **extractive** answerer, so generation never
> hard-fails.

---

## 0. Prerequisites on the other machine

Install these first (all free):

- **Git** — https://git-scm.com/downloads
- **Docker Desktop** (includes Docker Compose) — https://www.docker.com/products/docker-desktop
  - This is the easiest path: it runs the API, database, and UI for you.
- *(Only if you want to run WITHOUT Docker)* **Python 3.11+** — https://www.python.org/downloads

Check they're installed:
```bash
git --version
docker --version
docker compose version
```

---

## 1. Get the code onto the other machine

Pick ONE of these.

### Option A — You already pushed to GitHub/GitLab
```bash
git clone <your-repo-url>
cd project-sp
```

### Option B — Copy the folder manually (USB / zip / scp)
Copy the whole `project-sp` folder over, then:
```bash
cd project-sp
```
> Don't copy the `.venv/` folder — it's machine-specific. You'll recreate it.

---

## 2. Run it (recommended: Docker — one command)

From inside the `project-sp` folder:

```bash
docker compose up --build
```

Wait until you see logs saying the API started. Then open:

- **UI:**  http://localhost:8501
- **API docs (Swagger):** http://localhost:8000/docs

To stop it: press `Ctrl+C`, then (to remove containers):
```bash
docker compose down
```

To wipe the database too (start totally fresh):
```bash
docker compose down -v
```

---

## 3. Run it WITHOUT Docker (alternative)

Terminal 1 — start a Postgres with pgvector:
```bash
docker run -d --name rag-db -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=ragdb \
  pgvector/pgvector:pg16
```

Terminal 1 — install deps and run the API:
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Terminal 2 — run the UI:
```bash
source .venv/bin/activate        # Windows: .venv\Scripts\activate
streamlit run ui/streamlit_app.py
```

---

## 4. See it working (quick smoke test)

### Via the UI (easiest)
1. Open http://localhost:8501
2. In the sidebar: enter an email + password, click **Register**, then **Login**.
3. Upload a `.txt` or `.md` file, click **Ingest**.
4. Type a question in the chat box → you get an answer + citations.

### Via the API with curl (proves the backend works)
```bash
# health check
curl http://localhost:8000/health

# register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@test.com","password":"secret1"}'

# login -> grab the token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=demo@test.com&password=secret1" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# upload a document
echo "The sun is a star at the center of the solar system." > sample.txt
curl -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample.txt" -F "namespace=default"

# ask a question
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the sun?","namespace":"default"}'

# metrics
curl http://localhost:8000/metrics
```

---

## 5. Run the tests (prove code quality)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest -v
```
You should see **14 passed**.

---

## 6. Push to a git repository

### Option A — via a Git UI (GitHub Desktop / VS Code / web upload)
1. Create a new empty repository on GitHub (do **not** add a README/.gitignore,
   to avoid conflicts).
2. In your Git UI, add this `project-sp` folder as a local repository and
   publish it to the new remote.
3. Confirm the ignored files are **not** staged (see the list below). The
   `.gitignore` handles this automatically, but double-check `.env` and `.venv/`
   are not in the commit.

### Option B — via the command line
```bash
# from inside project-sp
git init
git add .
git commit -m "feat: initial RAG assistant"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```

### What gets committed vs. ignored
The `.gitignore` excludes secrets and local/generated files automatically.

| Commit ✅ | Ignore ❌ (never upload) |
|---|---|
| `app/`, `ui/`, `tests/`, `docs/` | `.env` (contains your Groq key) |
| `demo_docs/`, `demo.html` | `.venv/` (recreated with pip) |
| `Dockerfile`, `docker-compose.yml`, `requirements.txt` | `rag.db` / `*.db` (local runtime database) |
| `README.md`, `SETUP.md`, `.gitignore`, `.dockerignore` | `__pycache__/`, `.pytest_cache/` |
| `.env.example` (blank template) | `.DS_Store` |

> **Security:** never upload `.env` — it holds your real `GROQ_API_KEY`. Share
> `.env.example` (blank) instead. If a key is ever committed, rotate it.
