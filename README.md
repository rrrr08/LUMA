# ⚡ Page-to-API Platform

A high-performance monorepo platform that dynamically turns any public structured website page into a live, cached REST API using Playwright crawling, GPT-4o Vision visual analysis, and safe sandboxed code execution.

---

## 🚀 Key Features

* **Visual & Markup Crawler (Playwright)**: Renders JS-heavy sites, filters out tracking scripts/ads, extracts titles/screenshot snapshots, and compiles clean DOM structures.
* **Multimodal Schema Analysis (GPT-4o)**: Visual inspection of layout nodes and structure maps to propose a JSON schema with confidence indicators.
* **Resilient Parsing Generator (Codex/GPT-4o)**: Instantly writes custom BeautifulSoup and lxml parser code dynamically based on the verified schema.
* **Restricted Subprocess Sandbox**: Validates custom parser scripts using static AST rules (banning dangerous modules/cmd operations) and executes them in isolated process environments with custom namespace restrictions.
* **Dynamic API Gateway**: Intercepts requests, validates X-API-KEY parameters, enforces rate limit filters, reads/writes Redis caches, and serves custom JSON outputs.
* **Advanced Features Integrated (New)**:
  * **Proxy Rotation & Geo-Bypassing**: Route crawler requests through simulated residential proxies to bypass geographical content restrictions.
  * **Dynamic Gateway Parameters**: Automatically compiles parameterized scrapers dynamically based on incoming API query string arguments, segregating Redis cache keys by parameter hash to avoid collisions.
  * **Webhooks for Data Drift**: Background cache refresh schedules automatically identify content drift and trigger async webhook payloads with retry backoffs.
  * **Interactive Point-and-Click Selector**: Overlay visual bounding boxes scaled against screenshots to map target elements directly to schema configurations.
  * **Direct CSV & Google Sheets Integrations**: Appends updates directly into mock Google Sheets worksheets and yields instantly downloadable CSV formatted reports.
  * **Dynamic Usage & Billing Console**:
    * **Plan Recommender**: Interactive slider-based cost estimation mapping expected monthly load to ideal tiers.
    * **Per-Endpoint Consumption Charts**: Visual breakdowns of request workload distribution across generated scrapers.
    * **Persistent Invoice Logs**: Automatic database invoice logs on upgrades with simulated PDF-receipt downloads and promo code discounts.
    * **Usage Alerting**: Customizable email and Slack webhook alerts for quota thresholds.

---

## 📁 Folder Structure

Follows standard Next.js App Router and FastAPI production guidelines:

```
root/
├── apps/
│   ├── web/               # Next.js App Router Frontend (Typescript, CSS variables)
│   └── api/               # FastAPI Backend Service (SQLAlchemy, Pydantic V2, pytest)
├── packages/              # Shared configurations
└── infra/                 # Docker, Kubernetes configurations
```

---

## 🛠️ Quick Start

### 1. Prerequisites
Ensure you have the following installed on your system:
* Node.js (version 18 or above)
* Python (version 3.10 or above)
* `uv` Package Manager (recommended for speed)
* Docker (for PostgreSQL & Redis container hosting)

### 2. Infrastructure Setup (PostgreSQL + Redis)
Start the Postgres and Redis storage services in the background:
```bash
docker-compose up -d
```

### 3. Backend Setup (FastAPI)
1. Navigate to the api directory:
   ```bash
   cd apps/api
   ```
2. Setup virtual environment:
   ```bash
   uv venv
   ```
3. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```
4. Run the development server:
   ```bash
   .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
   ```
   * *Swagger documentation will be available at:* `http://localhost:8000/docs`

### 4. Running Backend Tests
Execute the unit and integration test suite:
```bash
uv run --python .venv python -m pytest
```

### 5. Frontend Setup (Next.js)
1. Navigate to the web directory:
   ```bash
   cd apps/web
   ```
2. Install packages:
   ```bash
   npm install
   ```
3. Launch development server:
   ```bash
   npm run dev
   ```
   * *Dashboard console will be available at:* `http://localhost:3000`

---

## 🔒 Security & Sandboxing Guards

1. **AST Check Validation**:
   Bans calls to `eval()`, `exec()`, `open()`, and blocks imports targeting `os`, `sys`, `subprocess`, `socket`, `shutil`, `importlib`.
2. **SSRF Blocking Middleware**:
   DNS lookup pre-validation blocks requests navigating to loopback networks or internal VPC ranges.
3. **Subprocess Isolation**:
   Scraper parsing execution runs inside a Process Pool Executor bounded by timeout limits (max 5.0 seconds) and memory parameters (max 256MB).
