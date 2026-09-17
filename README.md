# CodeSentinel - AI-Powered Automated PR Review Agent

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)

**CodeSentinel** is a production-ready Minimum Viable Product (MVP) automated Pull Request review agent. It integrates with GitHub webhooks and uses a **3-Pass Multi-Agent LLM Engine** paired with **AST Code Chunking** to deliver deep security, performance, and code style reviews.

---

## 🌟 Key Features

1. **FastAPI Webhook Listener (`/webhook`)**
   - Ingests GitHub `pull_request` events (`opened`, `synchronize`, `reopened`).
   - Secure HMAC `X-Hub-Signature-256` payload verification.
   - Dispatches review tasks to background queues.

2. **Custom AST Code Chunker**
   - Splits code diffs into semantic chunks along **Function, Class, Method, and Async boundaries** using Python's `ast` module.
   - Preserves logical context for LLMs rather than splitting arbitrarily by line count.
   - Resilient sliding block fallback for multi-language diffs or syntax-incomplete patches.

3. **3-Pass Multi-Agent Review Pipeline**
   - 🔒 **SecurityAgent**: Scans for hardcoded secrets/passwords, SQL injection, command injection, path traversal, `eval()`/`exec()`, unsafe deserialization, and weak cryptography.
   - ⚡ **PerformanceAgent**: Flags $O(N^2)$ nested loops, N+1 query patterns, unclosed file descriptors/sockets, redundant API calls, and blocking I/O inside async code.
   - 🎨 **StyleAgent**: Enforces PEP8 naming standards, type hints, docstrings, low cyclomatic complexity, and readability.

4. **GitHub Review API Integration**
   - Posts inline comments directly onto the active PR diff via GitHub Review API (`POST /repos/{owner}/{repo}/pulls/{number}/reviews`).
   - Dynamically decides review state (`COMMENT` vs `REQUEST_CHANGES`) based on severity threshold.

5. **PostgreSQL & SQLAlchemy Persistence**
   - Logs review history, file line findings, agent classifications, and severity risk indices (0-100 score).

6. **Interactive Dark-Mode Dashboard & PR Simulator**
   - Serves an interactive visual UI at `/` allowing developers to paste custom diffs, run real-time multi-agent reviews, view instant inline suggestions, and inspect review metrics.

---

## 🏗️ Architecture Overview

```
                        +----------------------------+
                        |  GitHub PR Event / Webhook |
                        +--------------+-------------+
                                       |
                                       v
                        +----------------------------+
                        |  FastAPI Server (/webhook) |
                        +--------------+-------------+
                                       |
                                       v
                        +----------------------------+
                        |   AST Code Chunker (py)   |
                        +--------------+-------------+
                                       |
           +---------------------------+---------------------------+
           |                           |                           |
           v                           v                           v
+--------------------+      +--------------------+      +--------------------+
|   SecurityAgent    |      |  PerformanceAgent  |      |     StyleAgent     |
| (Secrets, Inj, Ops)|      | (O(N^2), Leaks)    |      | (PEP8, Structure)  |
+----------+---------+      +----------+---------+      +----------+---------+
           |                           |                           |
           +---------------------------+---------------------------+
                                       |
                                       v
                        +----------------------------+
                        |   Severity Score Engine    |
                        +--------------+-------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
    +-----------------------------+         +-----------------------------+
    | GitHub Review API (Comments)|         | PostgreSQL (Review History) |
    +-----------------------------+         +-----------------------------+
```

---

## 🚀 Quick Start with Docker Compose

Run the entire stack (FastAPI, Redis, PostgreSQL) with a single command:

```bash
docker-compose up --build
```

Access the services:
- 🌐 **Web Dashboard & PR Simulator**: [http://localhost:8000](http://localhost:8000)
- 📚 **Swagger API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 💚 **Healthcheck Endpoint**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🛠️ Local Development Setup

### 1. Clone & Setup Virtual Environment

```bash
git clone https://github.com/your-org/CodeSentinel.git
cd CodeSentinel

python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create `.env` file (or copy `.env.example`):

```env
APP_NAME=CodeSentinel
DEBUG=True
PORT=8000

DATABASE_URL=sqlite:///./codesentinel.db
REDIS_URL=redis://localhost:6379/0

GITHUB_WEBHOOK_SECRET=your_secret_here
GITHUB_TOKEN=your_github_pat_here

AI_PROVIDER=gemini  # "gemini" or "openai" or "mock"
GEMINI_API_KEY=your_gemini_api_key
```

### 3. Run FastAPI Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

---

## 🧪 Running Automated Tests

Run the test suite covering AST chunking, multi-agent parsing, webhook HMAC signatures, and PR simulation:

```bash
pytest -v
```

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/webhook` | GitHub webhook handler for `pull_request` events |
| `POST` | `/api/simulate` | Interactive PR simulation endpoint for manual diff testing |
| `GET` | `/api/reviews` | List all past PR review sessions and findings |
| `GET` | `/api/reviews/{id}`| Fetch specific review session details |
| `GET` | `/api/stats` | Dashboard statistics & vulnerability trends |
| `GET` | `/health` | Application health check |

---

## 📄 License

MIT License. Designed & Built for production-grade automated PR code reviews.
