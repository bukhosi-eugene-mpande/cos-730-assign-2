# COS 730 – Assignment 2
## From Behavioural Models to Optimised Implementation

**Student:** Bukhosi Eugene Mpande (u21573558)  
**University:** University of Pretoria  

---

## Overview

This project implements, analyses, and optimises a subsystem of an **Intelligent Submission and Review System** — a peer review platform where researchers submit work, reviewers score it, and a final outcome (Accept / Revision / Reject) is determined.

The assignment progresses through six tasks:
1. Baseline implementation faithful to a provided sequence diagram
2. Design analysis identifying GRASP violations and coupling issues
3. Decision table modelling of all system decision logic
4. Optimised sequence diagram redesign
5. Refactored implementation aligned to the optimised diagram
6. Empirical benchmarking and comparison of both implementations

---

## Links

| Resource | URL |
|---|---|
| **Baseline** | https://initial-implementation-production.up.railway.app |
| **Optimised** | https://cos-730-assign-2-production.up.railway.app |
| **Source Code** | https://github.com/bukhosi-eugene-mpande/cos-730-assign-2 |

---

## Tech Stack

- **Python** — core language
- **NiceGUI** — reactive web UI (Researcher, Reviewer, Admin tabs)
- **SQLite** — embedded relational database
- **Cloudflare R2** — cloud object storage for submitted documents
- **Resend** — transactional email notifications
- **Railway** — cloud deployment platform

---

## Project Structure

```
cos-730-assign-2/
├── initial-implementation/     # Task 1 — baseline (matches sequence diagram exactly)
│   ├── main.py
│   ├── controllers.py
│   └── database.py
├── optimised-implementation/   # Task 5 — refactored, improved design
│   ├── main.py
│   ├── controllers.py
│   └── database.py
├── graphs/                     # Task 6 — benchmark graphs (8 figures)
├── baseline.mermaid            # Provided baseline sequence diagram
├── optimised.mermaid           # Redesigned optimised sequence diagram
├── benchmark.py                # Task 6 empirical benchmark script
├── report.md                   # Full assignment report
├── requirements.txt
└── Procfile                    # Railway deployment config
```

---

## Running Locally

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Set up environment variables** — copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

**Run the baseline (port 8080):**
```bash
cd initial-implementation
python3 database.py   # first run only
python3 main.py
```

**Run the optimised (port 8081):**
```bash
cd optimised-implementation
python3 database.py   # first run only
python3 main.py
```

Both can run simultaneously in separate terminals.

---

## Running the Benchmark

From the project root:
```bash
python3 benchmark.py
```

Generates 8 comparison graphs in `graphs/` and prints a full summary table to the console.

---

## Environment Variables

| Variable | Description |
|---|---|
| `R2_ACCOUNT_ID` | Cloudflare R2 account ID |
| `R2_ACCESS_KEY_ID` | R2 access key |
| `R2_SECRET_ACCESS_KEY` | R2 secret key |
| `R2_BUCKET_NAME` | R2 bucket name |
| `R2_ENDPOINT_URL` | R2 endpoint URL |
| `RESEND_API_KEY` | Resend API key for email notifications |
