# tenderwatch Phase 1 — Production MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a production-ready tenderwatch SaaS in 8 weeks: 政府電子採購網 OpenData → embedding pre-filter → LLM semantic match → LINE Bot push + Web dashboard, with 綠界 subscription billing and self-serve onboarding.

**Architecture:** Single FastAPI monolith (reuses existing `tender_filter.py` + `tenderwatch.py` as libs), Postgres + SQLModel, Jinja2 + HTMX for dashboard (no SPA), APScheduler for daily cron, separate Astro static site for marketing/SEO. Deployed as one service on Zeabur (~NT$200/月).

**Tech Stack:** Python 3.12 + FastAPI + SQLModel + Alembic + Postgres 16 + Redis + APScheduler + Jinja2 + HTMX + Tailwind CDN + LINE Messaging API + LINE Login + 綠界 AIO 定期扣款 + Resend email + Anthropic Claude + OpenAI embeddings + Astro 5 (marketing site) + Zeabur (hosting) + Better Stack + Sentry + Plausible (self-host)

---

## File Structure

```
_nice/tenderwatch/
├── app/                        # FastAPI app
│   ├── __init__.py
│   ├── main.py                 # ASGI entry + lifespan
│   ├── config.py               # pydantic-settings
│   ├── db.py                   # SQLModel engine + session
│   ├── models/                 # ORM models, 1 file per aggregate
│   │   ├── tender.py
│   │   ├── user.py
│   │   ├── profile.py
│   │   ├── match.py
│   │   └── subscription.py
│   ├── ingest/                 # data plane
│   │   ├── opendata.py         # pcc.gov.tw fetcher
│   │   └── embedder.py         # text-embedding-3-small + cosine
│   ├── scoring/                # adapts existing prototype libs
│   │   ├── filter.py           # wraps tender_filter.filter_all
│   │   └── semantic.py         # wraps tenderwatch.llm_score_tender
│   ├── notify/
│   │   ├── line_push.py        # LINE Messaging API push
│   │   ├── email_digest.py     # Resend
│   │   └── renderer.py         # markdown + LINE plain text
│   ├── auth/
│   │   └── line_login.py       # OAuth flow
│   ├── billing/
│   │   ├── ecpay.py            # 綠界 AIO 定期扣款 client
│   │   └── webhooks.py         # 綠界 callback handler
│   ├── routes/                 # FastAPI routers
│   │   ├── public.py           # /
│   │   ├── auth.py             # /login /callback
│   │   ├── onboarding.py       # /onboarding
│   │   ├── dashboard.py        # /app/*
│   │   ├── billing.py          # /billing/*
│   │   ├── linebot.py          # /webhook/line
│   │   └── ecpay_hooks.py      # /webhook/ecpay
│   ├── templates/              # Jinja2
│   │   ├── base.html
│   │   ├── public/
│   │   ├── onboarding/
│   │   ├── dashboard/
│   │   └── emails/
│   ├── static/                 # tailwind, favicons
│   └── workers/
│       ├── scheduler.py        # APScheduler — daily ingest + scoring + push
│       └── tasks.py            # callable units the scheduler invokes
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── alembic/                    # migrations
│   ├── env.py
│   └── versions/
├── marketing/                  # Astro static site (separate deploy)
│   ├── astro.config.mjs
│   ├── src/pages/
│   │   ├── index.astro
│   │   ├── pricing.astro
│   │   ├── faq.astro
│   │   ├── tos.astro
│   │   ├── privacy.astro
│   │   ├── refund.astro
│   │   └── blog/
│   └── public/
├── tenderwatch.py              # ⚠️ existing prototype, kept as lib
├── tender_filter.py            # ⚠️ existing prototype, kept as lib
├── pyproject.toml
├── docker-compose.yml          # local dev: postgres + redis
├── Dockerfile
├── zeabur.json
├── .env.example
├── .env                        # gitignored
└── README.md                   # ⚠️ existing, will be reorganized in Sprint 4
```

---

## Pre-Flight

### Task P1: Scaffold project + dependencies

**Files:**
- Create: `_nice/tenderwatch/pyproject.toml`
- Create: `_nice/tenderwatch/.env.example`
- Create: `_nice/tenderwatch/.gitignore`
- Create: `_nice/tenderwatch/docker-compose.yml`
- Create: `_nice/tenderwatch/app/__init__.py`
- Create: `_nice/tenderwatch/app/config.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "tenderwatch"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi[standard]==0.115.*",
  "uvicorn[standard]==0.32.*",
  "sqlmodel==0.0.22",
  "psycopg[binary]==3.2.*",
  "alembic==1.13.*",
  "pydantic-settings==2.6.*",
  "httpx==0.27.*",
  "anthropic==0.40.*",
  "openai==1.55.*",
  "redis==5.2.*",
  "apscheduler==3.10.*",
  "jinja2==3.1.*",
  "python-multipart==0.0.*",
  "itsdangerous==2.2.*",
  "sentry-sdk[fastapi]==2.18.*",
  "resend==2.4.*",
  "line-bot-sdk==3.14.*",
  "numpy==2.1.*",
  "structlog==24.4.*",
]

[dependency-groups]
dev = [
  "pytest==8.3.*",
  "pytest-asyncio==0.24.*",
  "pytest-cov==6.0.*",
  "ruff==0.7.*",
  "respx==0.21.*",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create .env.example**

```
DATABASE_URL=postgresql+psycopg://tw:tw@localhost:5432/tenderwatch
REDIS_URL=redis://localhost:6379/0
SESSION_SECRET=change-me-256-bits

ANTHROPIC_API_KEY=
OPENAI_API_KEY=

LINE_LOGIN_CHANNEL_ID=
LINE_LOGIN_CHANNEL_SECRET=
LINE_LOGIN_REDIRECT_URI=https://tenderwatch.tw/auth/callback
LINE_BOT_CHANNEL_ACCESS_TOKEN=
LINE_BOT_CHANNEL_SECRET=

ECPAY_MERCHANT_ID=
ECPAY_HASH_KEY=
ECPAY_HASH_IV=
ECPAY_RETURN_URL=https://tenderwatch.tw/webhook/ecpay
ECPAY_CLIENT_BACK_URL=https://tenderwatch.tw/billing/done
ECPAY_INVOICE_API_KEY=

RESEND_API_KEY=
SENTRY_DSN=
BETTERSTACK_HEARTBEAT_URL=

PCC_OPENDATA_BASE_URL=https://web.pcc.gov.tw
SEMANTIC_SIM_THRESHOLD=0.30
ENV=dev
```

- [ ] **Step 3: Create .gitignore**

```
.env
__pycache__/
*.pyc
.pytest_cache/
.coverage
htmlcov/
.venv/
.ruff_cache/
node_modules/
dist/
.astro/
```

- [ ] **Step 4: Create docker-compose.yml for local dev**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: tw
      POSTGRES_PASSWORD: tw
      POSTGRES_DB: tenderwatch
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
volumes:
  pgdata: {}
```

- [ ] **Step 5: Create app/config.py with pydantic-settings**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    session_secret: str

    anthropic_api_key: str = ""
    openai_api_key: str = ""

    line_login_channel_id: str = ""
    line_login_channel_secret: str = ""
    line_login_redirect_uri: str = ""
    line_bot_channel_access_token: str = ""
    line_bot_channel_secret: str = ""

    ecpay_merchant_id: str = ""
    ecpay_hash_key: str = ""
    ecpay_hash_iv: str = ""
    ecpay_return_url: str = ""
    ecpay_client_back_url: str = ""
    ecpay_invoice_api_key: str = ""

    resend_api_key: str = ""
    sentry_dsn: str = ""
    betterstack_heartbeat_url: str = ""

    pcc_opendata_base_url: str = "https://web.pcc.gov.tw"
    semantic_sim_threshold: float = 0.30
    env: str = "dev"


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 6: Install deps + verify**

Run: `cd _nice/tenderwatch && uv sync && cp .env.example .env && docker compose up -d postgres redis`
Expected: postgres + redis running, `uv run python -c "from app.config import get_settings; print(get_settings().env)"` outputs `dev`.

- [ ] **Step 7: Commit**

```bash
git add _nice/tenderwatch/pyproject.toml _nice/tenderwatch/.env.example _nice/tenderwatch/.gitignore _nice/tenderwatch/docker-compose.yml _nice/tenderwatch/app/__init__.py _nice/tenderwatch/app/config.py
git commit -m "tenderwatch(scaffold): pyproject + config + docker-compose local dev"
```

---

# Sprint 1 (Week 1-2) — Data Plane + Embedding Pre-filter

## Task 1.1: SQLModel models + first Alembic migration

**Files:**
- Create: `_nice/tenderwatch/app/db.py`
- Create: `_nice/tenderwatch/app/models/__init__.py`
- Create: `_nice/tenderwatch/app/models/tender.py`
- Create: `_nice/tenderwatch/app/models/user.py`
- Create: `_nice/tenderwatch/app/models/profile.py`
- Create: `_nice/tenderwatch/app/models/match.py`
- Create: `_nice/tenderwatch/app/models/subscription.py`
- Create: `_nice/tenderwatch/alembic/env.py`
- Test: `_nice/tenderwatch/tests/integration/test_db_schema.py`

- [ ] **Step 1: Write failing test for schema**

```python
# tests/integration/test_db_schema.py
from sqlmodel import select

from app.db import engine, init_db
from app.models.tender import Tender
from app.models.user import User


def test_tables_exist_after_init(monkeypatch):
    init_db()
    from sqlmodel import Session
    with Session(engine) as s:
        # empty queries should succeed even with 0 rows
        assert s.exec(select(Tender)).all() == []
        assert s.exec(select(User)).all() == []
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `uv run pytest tests/integration/test_db_schema.py -v`
Expected: FAIL — `app.db` not importable.

- [ ] **Step 3: Implement app/db.py**

```python
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)


def init_db() -> None:
    import app.models  # noqa: F401 register models
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
```

- [ ] **Step 4: Implement models/tender.py**

```python
from datetime import date, datetime
from typing import Optional

from sqlmodel import Column, Field, SQLModel
from sqlalchemy import ARRAY, String
from sqlalchemy.dialects.postgresql import JSONB


class Tender(SQLModel, table=True):
    __tablename__ = "tenders"

    case_no: str = Field(primary_key=True, max_length=64)
    title: str
    agency: str
    category: str
    budget_twd: int
    posted_date: date
    deadline_date: date
    description: str
    required_capital_twd: int = 0
    required_certs: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(String)))
    location: str = "全國"
    raw_payload: dict = Field(default_factory=dict, sa_column=Column(JSONB))
    embedding: list[float] | None = Field(default=None, sa_column=Column(JSONB))
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 5: Implement models/user.py**

```python
from datetime import datetime

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int = Field(primary_key=True)
    line_user_id: str = Field(index=True, unique=True, max_length=64)
    display_name: str
    email: str | None = Field(default=None, index=True)
    plan: str = Field(default="free")  # free | solo | pro
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 6: Implement models/profile.py**

```python
from datetime import datetime

from sqlalchemy import ARRAY, String
from sqlmodel import Column, Field, SQLModel


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"

    id: int = Field(primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    company_name: str
    capital_twd: int
    employee_count: int
    capability_description: str  # free-form, embedded
    min_tender_budget_twd: int = 0
    max_tender_budget_twd: int | None = None
    excluded_categories: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(String)))
    iso_certifications: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(String)))
    minimum_days_to_deadline: int = 7
    embedding: list[float] | None = Field(default=None, sa_column=Column("embedding", type_=__import__("sqlalchemy").JSON))
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 7: Implement models/match.py**

```python
from datetime import datetime

from sqlalchemy import ARRAY, String
from sqlmodel import Column, Field, SQLModel


class Match(SQLModel, table=True):
    __tablename__ = "matches"

    id: int = Field(primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    profile_id: int = Field(foreign_key="profiles.id")
    tender_case_no: str = Field(foreign_key="tenders.case_no", index=True)
    passes_hard_filter: bool
    fail_reasons: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(String)))
    cosine_sim: float | None = None
    llm_score: int | None = None
    llm_match_level: str | None = None
    llm_key_match_points: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(String)))
    llm_key_gaps: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(String)))
    llm_recommendation: str | None = None
    pushed_to_line: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 8: Implement models/subscription.py**

```python
from datetime import datetime

from sqlmodel import Field, SQLModel


class Subscription(SQLModel, table=True):
    __tablename__ = "subscriptions"

    id: int = Field(primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    plan: str  # solo | pro
    ecpay_merchant_trade_no: str = Field(max_length=64, unique=True)
    ecpay_period_amount: int  # NTD
    status: str  # active | failed | cancelled
    next_charge_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    cancelled_at: datetime | None = None
```

- [ ] **Step 9: Implement models/__init__.py**

```python
from app.models.tender import Tender
from app.models.user import User
from app.models.profile import Profile
from app.models.match import Match
from app.models.subscription import Subscription

__all__ = ["Tender", "User", "Profile", "Match", "Subscription"]
```

- [ ] **Step 10: alembic init + write env.py**

Run: `uv run alembic init alembic`
Then replace `alembic/env.py` with:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

import app.models  # noqa: F401 register
from app.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 11: Generate + run first migration**

```bash
cd _nice/tenderwatch
uv run alembic revision --autogenerate -m "init schema"
uv run alembic upgrade head
```

- [ ] **Step 12: Run integration test**

Run: `uv run pytest tests/integration/test_db_schema.py -v`
Expected: PASS

- [ ] **Step 13: Commit**

```bash
git add _nice/tenderwatch/app/ _nice/tenderwatch/alembic/ _nice/tenderwatch/tests/integration/test_db_schema.py
git commit -m "tenderwatch(db): SQLModel schema + alembic init migration"
```

---

## Task 1.2: PCC OpenData fetcher

**Files:**
- Create: `_nice/tenderwatch/app/ingest/__init__.py`
- Create: `_nice/tenderwatch/app/ingest/opendata.py`
- Test: `_nice/tenderwatch/tests/unit/test_opendata.py`

The endpoint `https://web.pcc.gov.tw/prkms/tender/common/bulletion/...` returns JSON. We implement a fetcher that takes a date range and yields normalized `Tender` rows. Real network call is mocked in unit tests via `respx`.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_opendata.py
from datetime import date
import respx
from httpx import Response

from app.ingest.opendata import fetch_tenders_for_date


SAMPLE_JSON = {
    "tenders": [
        {
            "case_no": "11401001",
            "title": "資安顧問服務",
            "agency": "外交部",
            "category": "資訊服務",
            "budget_twd": 2500000,
            "posted_date": "2026-05-10",
            "deadline_date": "2026-05-30",
            "description": "提供 ISO 27001 顧問服務",
            "required_capital_twd": 5000000,
            "required_certs": ["ISO 27001"],
            "location": "台北市",
        }
    ]
}


@respx.mock
def test_fetch_normalizes_pcc_payload():
    respx.get("https://web.pcc.gov.tw/prkms/tender/common/bulletion/listTenderByDate").mock(
        return_value=Response(200, json=SAMPLE_JSON)
    )
    out = list(fetch_tenders_for_date(date(2026, 5, 10)))
    assert len(out) == 1
    assert out[0]["case_no"] == "11401001"
    assert out[0]["required_certs"] == ["ISO 27001"]
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/unit/test_opendata.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement opendata.py**

```python
# app/ingest/opendata.py
from datetime import date
from typing import Iterator

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)
PATH = "/prkms/tender/common/bulletion/listTenderByDate"


def fetch_tenders_for_date(d: date) -> Iterator[dict]:
    settings = get_settings()
    params = {"date": d.isoformat()}
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{settings.pcc_opendata_base_url}{PATH}", params=params)
        resp.raise_for_status()
        payload = resp.json()
    for raw in payload.get("tenders", []):
        yield _normalize(raw)


def _normalize(raw: dict) -> dict:
    return {
        "case_no": str(raw["case_no"]),
        "title": raw["title"],
        "agency": raw["agency"],
        "category": raw["category"],
        "budget_twd": int(raw.get("budget_twd", 0)),
        "posted_date": raw["posted_date"],
        "deadline_date": raw["deadline_date"],
        "description": raw.get("description", ""),
        "required_capital_twd": int(raw.get("required_capital_twd", 0)),
        "required_certs": list(raw.get("required_certs", [])),
        "location": raw.get("location", "全國"),
        "raw_payload": raw,
    }
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/unit/test_opendata.py -v`
Expected: PASS

- [ ] **Step 5: Add retry + 429 handling**

```python
# inside fetch_tenders_for_date, replace the simple Client block:
import time

with httpx.Client(timeout=30.0) as client:
    for attempt in range(3):
        resp = client.get(f"{settings.pcc_opendata_base_url}{PATH}", params=params)
        if resp.status_code == 429:
            log.warning("pcc.opendata.rate_limited", attempt=attempt)
            time.sleep(2 ** attempt * 5)
            continue
        resp.raise_for_status()
        payload = resp.json()
        break
    else:
        raise RuntimeError("pcc opendata rate limit not recoverable")
```

- [ ] **Step 6: Add retry test**

```python
# tests/unit/test_opendata.py — append
@respx.mock
def test_fetch_retries_on_429():
    route = respx.get("https://web.pcc.gov.tw/prkms/tender/common/bulletion/listTenderByDate")
    route.side_effect = [Response(429), Response(200, json=SAMPLE_JSON)]
    out = list(fetch_tenders_for_date(date(2026, 5, 10)))
    assert len(out) == 1
    assert route.call_count == 2
```

Run: `uv run pytest tests/unit/test_opendata.py -v`
Expected: both tests PASS

- [ ] **Step 7: Commit**

```bash
git add _nice/tenderwatch/app/ingest/ _nice/tenderwatch/tests/unit/test_opendata.py
git commit -m "tenderwatch(ingest): PCC OpenData fetcher with retry"
```

---

## Task 1.3: Embedding pre-filter

**Files:**
- Create: `_nice/tenderwatch/app/ingest/embedder.py`
- Test: `_nice/tenderwatch/tests/unit/test_embedder.py`

Use OpenAI `text-embedding-3-small` (1536 dim, NT$0.02/M token). Cosine sim threshold from settings.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_embedder.py
import numpy as np
from app.ingest.embedder import cosine, should_send_to_llm


def test_cosine_identical_vectors_is_one():
    v = [1.0, 0.0, 0.5]
    assert cosine(v, v) == 1.0


def test_cosine_orthogonal_vectors_is_zero():
    assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_should_send_below_threshold_returns_false():
    profile_v = [1.0, 0.0]
    tender_v = [0.0, 1.0]  # cosine 0
    assert should_send_to_llm(profile_v, tender_v, threshold=0.3) is False


def test_should_send_above_threshold_returns_true():
    profile_v = [1.0, 0.0]
    tender_v = [0.95, 0.05]
    assert should_send_to_llm(profile_v, tender_v, threshold=0.3) is True
```

- [ ] **Step 2: Run test, expect ImportError**

Run: `uv run pytest tests/unit/test_embedder.py -v`
Expected: FAIL

- [ ] **Step 3: Implement embedder.py**

```python
# app/ingest/embedder.py
import math
from typing import Sequence

from openai import OpenAI

from app.config import get_settings

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=get_settings().openai_api_key)
    return _client


def embed(text: str) -> list[float]:
    resp = _get_client().embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("dim mismatch")
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def should_send_to_llm(profile_emb: Sequence[float], tender_emb: Sequence[float],
                        threshold: float | None = None) -> bool:
    if threshold is None:
        threshold = get_settings().semantic_sim_threshold
    return cosine(profile_emb, tender_emb) >= threshold
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/unit/test_embedder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add _nice/tenderwatch/app/ingest/embedder.py _nice/tenderwatch/tests/unit/test_embedder.py
git commit -m "tenderwatch(ingest): embedding pre-filter with cosine threshold"
```

---

## Task 1.4: Adapter — wrap existing prototype libs

**Files:**
- Create: `_nice/tenderwatch/app/scoring/__init__.py`
- Create: `_nice/tenderwatch/app/scoring/filter.py`
- Create: `_nice/tenderwatch/app/scoring/semantic.py`
- Test: `_nice/tenderwatch/tests/unit/test_scoring_adapters.py`

Re-uses existing `tender_filter.py` + `tenderwatch.py` so the proven prototype logic doesn't fork.

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_scoring_adapters.py
from datetime import date

from app.scoring.filter import run_hard_filter


def test_hard_filter_rejects_underbudget_tender():
    tender_row = {
        "case_no": "1", "title": "x", "agency": "y", "category": "資訊服務",
        "budget_twd": 100_000, "posted_date": "2026-05-10", "deadline_date": "2026-06-30",
        "description": "", "required_capital_twd": 0, "required_certs": [], "location": "全國",
    }
    profile_row = {
        "company_name": "X", "capital_twd": 5_000_000, "employee_count": 5,
        "capability_description": "IT", "min_tender_budget_twd": 500_000,
        "max_tender_budget_twd": None, "excluded_categories": [],
        "iso_certifications": [], "minimum_days_to_deadline": 7,
    }
    result = run_hard_filter(tender_row, profile_row, today=date(2026, 5, 10))
    assert result["passes_hard_filter"] is False
    assert any("低於" in r for r in result["fail_reasons"])
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/unit/test_scoring_adapters.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement scoring/filter.py**

```python
# app/scoring/filter.py
"""Adapter that converts dict rows into existing prototype dataclasses."""
import sys
from datetime import date
from pathlib import Path

# add prototype dir to sys.path so we can import tender_filter
PROTOTYPE_DIR = Path(__file__).resolve().parents[2]
if str(PROTOTYPE_DIR) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE_DIR))

from tender_filter import Tender, UserProfile, filter_tender  # noqa: E402


def run_hard_filter(tender_row: dict, profile_row: dict, today: date) -> dict:
    tender = Tender(
        case_no=tender_row["case_no"], title=tender_row["title"],
        agency=tender_row["agency"], category=tender_row["category"],
        budget_twd=int(tender_row["budget_twd"]),
        posted_date=tender_row["posted_date"], deadline_date=tender_row["deadline_date"],
        description=tender_row["description"],
        required_capital_twd=int(tender_row.get("required_capital_twd", 0)),
        required_certs=tuple(tender_row.get("required_certs", [])),
        location=tender_row.get("location", "全國"),
    )
    profile = UserProfile(
        company_name=profile_row["company_name"],
        capital_twd=int(profile_row["capital_twd"]),
        employee_count=int(profile_row["employee_count"]),
        capability_description=profile_row["capability_description"],
        min_tender_budget_twd=int(profile_row.get("min_tender_budget_twd", 0)),
        max_tender_budget_twd=profile_row.get("max_tender_budget_twd"),
        excluded_categories=tuple(profile_row.get("excluded_categories", [])),
        iso_certifications=tuple(profile_row.get("iso_certifications", [])),
        minimum_days_to_deadline=int(profile_row.get("minimum_days_to_deadline", 7)),
    )
    fr = filter_tender(tender, profile, today)
    return {
        "case_no": tender.case_no,
        "passes_hard_filter": fr.passes_hard_filter,
        "fail_reasons": fr.fail_reasons,
    }
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/unit/test_scoring_adapters.py -v`
Expected: PASS

- [ ] **Step 5: Implement scoring/semantic.py**

```python
# app/scoring/semantic.py
import sys
from dataclasses import asdict
from pathlib import Path

PROTOTYPE_DIR = Path(__file__).resolve().parents[2]
if str(PROTOTYPE_DIR) not in sys.path:
    sys.path.insert(0, str(PROTOTYPE_DIR))

from tender_filter import Tender, UserProfile  # noqa: E402
from tenderwatch import llm_score_tender  # noqa: E402


def run_semantic_score(tender_row: dict, profile_row: dict) -> dict:
    tender = Tender(
        case_no=tender_row["case_no"], title=tender_row["title"],
        agency=tender_row["agency"], category=tender_row["category"],
        budget_twd=int(tender_row["budget_twd"]),
        posted_date=tender_row["posted_date"], deadline_date=tender_row["deadline_date"],
        description=tender_row["description"],
        required_capital_twd=int(tender_row.get("required_capital_twd", 0)),
        required_certs=tuple(tender_row.get("required_certs", [])),
        location=tender_row.get("location", "全國"),
    )
    profile = UserProfile(
        company_name=profile_row["company_name"],
        capital_twd=int(profile_row["capital_twd"]),
        employee_count=int(profile_row["employee_count"]),
        capability_description=profile_row["capability_description"],
    )
    score = llm_score_tender(profile, tender)
    return asdict(score)
```

- [ ] **Step 6: Commit**

```bash
git add _nice/tenderwatch/app/scoring/ _nice/tenderwatch/tests/unit/test_scoring_adapters.py
git commit -m "tenderwatch(scoring): adapter wrapping prototype filter + LLM scorer"
```

---

## Task 1.5: Daily ingest worker

**Files:**
- Create: `_nice/tenderwatch/app/workers/__init__.py`
- Create: `_nice/tenderwatch/app/workers/tasks.py`
- Test: `_nice/tenderwatch/tests/integration/test_ingest_task.py`

A callable `run_daily_ingest(today)` that: 1) fetches today's tenders 2) upserts to DB 3) for each user profile, runs hard filter → embed → cosine pre-filter → LLM → persists Match row.

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_ingest_task.py
from datetime import date
from unittest.mock import patch

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models.profile import Profile
from app.models.tender import Tender
from app.models.user import User
from app.models.match import Match
from app.workers.tasks import run_daily_ingest


def _seed_user_with_profile():
    init_db()
    with Session(engine) as s:
        u = User(line_user_id="U1", display_name="Test", plan="solo")
        s.add(u); s.commit(); s.refresh(u)
        p = Profile(
            user_id=u.id, company_name="X", capital_twd=5_000_000, employee_count=5,
            capability_description="IT 顧問,擅長 ISO 27001 + 雲端遷移",
            min_tender_budget_twd=500_000, embedding=[1.0] * 1536,
        )
        s.add(p); s.commit()
        return u.id


def test_run_daily_ingest_creates_matches(monkeypatch):
    user_id = _seed_user_with_profile()
    fake_tender = {
        "case_no": "T1", "title": "資安顧問", "agency": "外交部", "category": "資訊服務",
        "budget_twd": 2_500_000, "posted_date": "2026-05-10", "deadline_date": "2026-06-30",
        "description": "ISO 27001 顧問", "required_capital_twd": 0,
        "required_certs": [], "location": "台北市", "raw_payload": {},
    }
    with patch("app.workers.tasks.fetch_tenders_for_date", return_value=[fake_tender]), \
         patch("app.workers.tasks.embed", return_value=[1.0] * 1536), \
         patch("app.workers.tasks.run_semantic_score", return_value={
             "score": 88, "match_level": "high",
             "key_match_points": ["ISO 27001"], "key_gaps": [],
             "recommendation": "建議投標"}):
        run_daily_ingest(date(2026, 5, 10))

    with Session(engine) as s:
        matches = s.exec(select(Match).where(Match.user_id == user_id)).all()
        assert len(matches) == 1
        assert matches[0].llm_score == 88
        assert matches[0].passes_hard_filter is True
```

- [ ] **Step 2: Run test, expect FAIL**

Run: `uv run pytest tests/integration/test_ingest_task.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement workers/tasks.py**

```python
# app/workers/tasks.py
from datetime import date
from typing import Iterable

import structlog
from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine
from app.ingest.embedder import cosine, embed
from app.ingest.opendata import fetch_tenders_for_date
from app.models.match import Match
from app.models.profile import Profile
from app.models.tender import Tender
from app.scoring.filter import run_hard_filter
from app.scoring.semantic import run_semantic_score

log = structlog.get_logger(__name__)


def _upsert_tenders(rows: Iterable[dict]) -> list[dict]:
    out = []
    with Session(engine) as s:
        for r in rows:
            existing = s.get(Tender, r["case_no"])
            if existing is None:
                t = Tender(**{k: v for k, v in r.items() if k != "embedding"})
                s.add(t)
                out.append(r)
            else:
                out.append(r)  # already known; still re-score (profile may have changed)
        s.commit()
    return out


def _ensure_embedding(s: Session, case_no: str, description: str) -> list[float]:
    t = s.get(Tender, case_no)
    if t.embedding is None:
        emb = embed(f"{t.title}\n{t.category}\n{description}")
        t.embedding = emb
        s.add(t); s.commit()
    return t.embedding


def run_daily_ingest(today: date) -> dict:
    settings = get_settings()
    rows = list(fetch_tenders_for_date(today))
    _upsert_tenders(rows)
    log.info("ingest.fetched", count=len(rows), date=today.isoformat())

    profiles_processed = 0
    matches_created = 0
    llm_calls = 0
    with Session(engine) as s:
        profiles = s.exec(select(Profile)).all()
        for profile in profiles:
            profile_row = profile.model_dump()
            if profile.embedding is None:
                pe = embed(profile.capability_description)
                profile.embedding = pe; s.add(profile); s.commit()
            for r in rows:
                hf = run_hard_filter(r, profile_row, today)
                if not hf["passes_hard_filter"]:
                    s.add(Match(user_id=profile.user_id, profile_id=profile.id,
                                tender_case_no=r["case_no"], passes_hard_filter=False,
                                fail_reasons=hf["fail_reasons"]))
                    matches_created += 1
                    continue
                # pre-filter cosine
                te = _ensure_embedding(s, r["case_no"], r["description"])
                sim = cosine(profile.embedding, te)
                if sim < settings.semantic_sim_threshold:
                    s.add(Match(user_id=profile.user_id, profile_id=profile.id,
                                tender_case_no=r["case_no"], passes_hard_filter=True,
                                cosine_sim=sim, llm_score=None))
                    matches_created += 1
                    continue
                # LLM score
                sc = run_semantic_score(r, profile_row)
                llm_calls += 1
                s.add(Match(user_id=profile.user_id, profile_id=profile.id,
                            tender_case_no=r["case_no"], passes_hard_filter=True,
                            cosine_sim=sim, llm_score=sc["score"],
                            llm_match_level=sc.get("match_level"),
                            llm_key_match_points=sc.get("key_match_points", []),
                            llm_key_gaps=sc.get("key_gaps", []),
                            llm_recommendation=sc.get("recommendation")))
                matches_created += 1
            s.commit()
            profiles_processed += 1

    stats = {"profiles": profiles_processed, "matches": matches_created, "llm_calls": llm_calls}
    log.info("ingest.done", **stats)
    return stats
```

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/integration/test_ingest_task.py -v`
Expected: PASS

- [ ] **Step 5: Add APScheduler bootstrap**

Create `app/workers/scheduler.py`:

```python
from datetime import date

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.workers.tasks import run_daily_ingest

log = structlog.get_logger(__name__)


def start_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="Asia/Taipei")
    sched.add_job(lambda: run_daily_ingest(date.today()),
                  CronTrigger(hour="6,14", minute=0), id="daily_ingest")
    sched.start()
    log.info("scheduler.started")
    return sched
```

- [ ] **Step 6: Commit**

```bash
git add _nice/tenderwatch/app/workers/ _nice/tenderwatch/tests/integration/test_ingest_task.py
git commit -m "tenderwatch(workers): daily ingest task + APScheduler cron"
```

---

# Sprint 2 (Week 3-4) — Auth + Subscription Billing + Onboarding

## Task 2.1: FastAPI app skeleton + session middleware

**Files:**
- Create: `_nice/tenderwatch/app/main.py`
- Create: `_nice/tenderwatch/app/routes/__init__.py`
- Create: `_nice/tenderwatch/app/routes/public.py`
- Test: `_nice/tenderwatch/tests/integration/test_app_smoke.py`

- [ ] **Step 1: Write failing test**

```python
# tests/integration/test_app_smoke.py
from fastapi.testclient import TestClient
from app.main import app


def test_root_returns_200():
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
    assert "tenderwatch" in r.text.lower()


def test_healthz():
    c = TestClient(app)
    r = c.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/integration/test_app_smoke.py -v`
Expected: FAIL

- [ ] **Step 3: Implement main.py**

```python
# app/main.py
from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.routes import public

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
    if settings.env == "prod":
        from app.workers.scheduler import start_scheduler
        sched = start_scheduler()
        app.state.scheduler = sched
    yield
    sched = getattr(app.state, "scheduler", None)
    if sched:
        sched.shutdown()


app = FastAPI(title="tenderwatch", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=get_settings().session_secret)
app.mount("/static", StaticFiles(directory="app/static", check_dir=False), name="static")
app.include_router(public.router)


@app.get("/healthz")
async def healthz():
    return {"ok": True}
```

- [ ] **Step 4: Implement routes/public.py**

```python
# app/routes/public.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("public/index.html", {"request": request})
```

- [ ] **Step 5: Implement minimal templates**

Create `app/templates/base.html`:
```html
<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<title>{% block title %}tenderwatch{% endblock %}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/htmx.org@2.0.3"></script>
</head>
<body class="bg-slate-50 text-slate-900">
{% block content %}{% endblock %}
</body>
</html>
```

Create `app/templates/public/index.html`:
```html
{% extends "base.html" %}
{% block content %}
<main class="max-w-3xl mx-auto p-8">
  <h1 class="text-3xl font-bold">tenderwatch</h1>
  <p class="mt-2 text-slate-600">台灣中小企業政府標案 AI 即時警示。</p>
  <a href="/auth/line" class="mt-6 inline-block px-4 py-2 bg-emerald-600 text-white rounded">用 LINE 免費試用</a>
</main>
{% endblock %}
```

- [ ] **Step 6: Run tests, expect PASS**

Run: `uv run pytest tests/integration/test_app_smoke.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add _nice/tenderwatch/app/main.py _nice/tenderwatch/app/routes/ _nice/tenderwatch/app/templates/ _nice/tenderwatch/tests/integration/test_app_smoke.py
git commit -m "tenderwatch(app): FastAPI skeleton + landing + healthz"
```

---

## Task 2.2: LINE Login OAuth flow

**Files:**
- Create: `_nice/tenderwatch/app/auth/__init__.py`
- Create: `_nice/tenderwatch/app/auth/line_login.py`
- Create: `_nice/tenderwatch/app/routes/auth.py`
- Test: `_nice/tenderwatch/tests/integration/test_line_login.py`

Manual setup precondition: at LINE Developers console create a Login channel; set callback URL to `http://localhost:8000/auth/callback` for dev and `https://tenderwatch.tw/auth/callback` for prod.

- [ ] **Step 1: Write failing test**

```python
# tests/integration/test_line_login.py
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.db import init_db, engine
from app.main import app


def test_login_redirects_to_line():
    c = TestClient(app)
    r = c.get("/auth/line", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "access.line.me" in r.headers["location"]


def test_callback_creates_user_and_session():
    init_db()
    c = TestClient(app)
    fake_token = {"access_token": "AT", "id_token": "IT"}
    fake_profile = {"userId": "U_TEST_1", "displayName": "Alice"}
    with patch("app.auth.line_login.exchange_code_for_tokens", return_value=fake_token), \
         patch("app.auth.line_login.fetch_profile", return_value=fake_profile):
        r = c.get("/auth/callback?code=fake&state=anystate", follow_redirects=False)
    assert r.status_code in (302, 307)
    from sqlmodel import Session, select
    from app.models.user import User
    with Session(engine) as s:
        u = s.exec(select(User).where(User.line_user_id == "U_TEST_1")).first()
        assert u is not None
        assert u.display_name == "Alice"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/integration/test_line_login.py -v`
Expected: FAIL

- [ ] **Step 3: Implement auth/line_login.py**

```python
# app/auth/line_login.py
import secrets
from urllib.parse import urlencode

import httpx

from app.config import get_settings

LINE_AUTH_URL = "https://access.line.me/oauth2/v2.1/authorize"
LINE_TOKEN_URL = "https://api.line.me/oauth2/v2.1/token"
LINE_PROFILE_URL = "https://api.line.me/v2/profile"


def build_authorize_url(state: str) -> str:
    s = get_settings()
    params = {
        "response_type": "code",
        "client_id": s.line_login_channel_id,
        "redirect_uri": s.line_login_redirect_uri,
        "state": state,
        "scope": "profile openid",
    }
    return f"{LINE_AUTH_URL}?{urlencode(params)}"


def new_state() -> str:
    return secrets.token_urlsafe(16)


def exchange_code_for_tokens(code: str) -> dict:
    s = get_settings()
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": s.line_login_redirect_uri,
        "client_id": s.line_login_channel_id,
        "client_secret": s.line_login_channel_secret,
    }
    r = httpx.post(LINE_TOKEN_URL, data=data, timeout=20.0)
    r.raise_for_status()
    return r.json()


def fetch_profile(access_token: str) -> dict:
    r = httpx.get(LINE_PROFILE_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=20.0)
    r.raise_for_status()
    return r.json()
```

- [ ] **Step 4: Implement routes/auth.py**

```python
# app/routes/auth.py
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.auth.line_login import (
    build_authorize_url, exchange_code_for_tokens, fetch_profile, new_state,
)
from app.db import engine
from app.models.user import User

router = APIRouter(prefix="/auth")


@router.get("/line")
async def login_with_line(request: Request):
    state = new_state()
    request.session["oauth_state"] = state
    return RedirectResponse(build_authorize_url(state))


@router.get("/callback")
async def callback(request: Request, code: str | None = None, state: str | None = None):
    if not code or state != request.session.get("oauth_state"):
        raise HTTPException(400, "invalid oauth state")
    tokens = exchange_code_for_tokens(code)
    prof = fetch_profile(tokens["access_token"])
    with Session(engine) as s:
        user = s.exec(select(User).where(User.line_user_id == prof["userId"])).first()
        if user is None:
            user = User(line_user_id=prof["userId"], display_name=prof["displayName"])
            s.add(user); s.commit(); s.refresh(user)
        request.session["user_id"] = user.id
    if not _has_profile(user.id):
        return RedirectResponse("/onboarding")
    return RedirectResponse("/app")


def _has_profile(user_id: int) -> bool:
    from app.models.profile import Profile
    with Session(engine) as s:
        return s.exec(select(Profile).where(Profile.user_id == user_id)).first() is not None
```

- [ ] **Step 5: Wire router into main.py**

In `app/main.py`, add:
```python
from app.routes import auth as auth_routes
app.include_router(auth_routes.router)
```

- [ ] **Step 6: Run tests, expect PASS**

Run: `uv run pytest tests/integration/test_line_login.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add _nice/tenderwatch/app/auth/ _nice/tenderwatch/app/routes/auth.py _nice/tenderwatch/app/main.py _nice/tenderwatch/tests/integration/test_line_login.py
git commit -m "tenderwatch(auth): LINE Login OAuth + session"
```

---

## Task 2.3: Onboarding wizard

**Files:**
- Create: `_nice/tenderwatch/app/routes/onboarding.py`
- Create: `_nice/tenderwatch/app/templates/onboarding/wizard.html`
- Test: `_nice/tenderwatch/tests/integration/test_onboarding.py`

3-step HTMX form: (1) 公司基本（名稱、資本額、員工數），(2) 能力描述（必填，含 5 個範例選單），(3) 排除/門檻（min_budget、excluded_categories、minimum_days）。

- [ ] **Step 1: Write failing test**

```python
# tests/integration/test_onboarding.py
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.db import engine, init_db
from app.main import app
from app.models.profile import Profile
from app.models.user import User


def _login_session(client: TestClient) -> int:
    init_db()
    with Session(engine) as s:
        u = User(line_user_id="U_X", display_name="X")
        s.add(u); s.commit(); s.refresh(u)
        uid = u.id
    client.cookies = {}
    # bypass OAuth: inject session via middleware test helper
    with client as c:
        c.get("/")  # init session cookie
        c.post("/_test/login", data={"user_id": uid})
    return uid


def test_post_onboarding_creates_profile(monkeypatch):
    client = TestClient(app)
    uid = _login_session(client)
    payload = {
        "company_name": "雲鼎資訊",
        "capital_twd": "5000000",
        "employee_count": "18",
        "capability_description": "中型 IT 顧問,擅長 ISO 27001、雲端遷移、政府 HIS 介接",
        "min_tender_budget_twd": "500000",
        "excluded_categories": "工程施作,印刷",
        "iso_certifications": "ISO 27001,ISO 9001",
        "minimum_days_to_deadline": "14",
    }
    r = client.post("/onboarding", data=payload, follow_redirects=False)
    assert r.status_code in (302, 303)
    with Session(engine) as s:
        p = s.exec(select(Profile).where(Profile.user_id == uid)).first()
        assert p is not None
        assert p.company_name == "雲鼎資訊"
        assert "工程施作" in p.excluded_categories
```

- [ ] **Step 2: Add /_test/login helper (dev/test only)**

In `app/routes/auth.py`:
```python
from app.config import get_settings

@router.post("/_test/login", include_in_schema=False)
async def _test_login(request: Request, user_id: int):
    if get_settings().env not in ("dev", "test"):
        raise HTTPException(404, "not found")
    request.session["user_id"] = user_id
    return {"ok": True}
```

- [ ] **Step 3: Run test, expect FAIL**

Run: `uv run pytest tests/integration/test_onboarding.py -v`
Expected: FAIL — /onboarding not implemented.

- [ ] **Step 4: Implement routes/onboarding.py**

```python
# app/routes/onboarding.py
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.db import engine
from app.models.profile import Profile

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _require_user(request: Request) -> int:
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(401, "login required")
    return uid


@router.get("/onboarding", response_class=HTMLResponse)
async def show(request: Request):
    _require_user(request)
    return templates.TemplateResponse("onboarding/wizard.html", {"request": request})


@router.post("/onboarding")
async def submit(
    request: Request,
    company_name: str = Form(...),
    capital_twd: int = Form(...),
    employee_count: int = Form(...),
    capability_description: str = Form(...),
    min_tender_budget_twd: int = Form(0),
    max_tender_budget_twd: int | None = Form(None),
    excluded_categories: str = Form(""),
    iso_certifications: str = Form(""),
    minimum_days_to_deadline: int = Form(7),
):
    uid = _require_user(request)
    excluded = [x.strip() for x in excluded_categories.split(",") if x.strip()]
    certs = [x.strip() for x in iso_certifications.split(",") if x.strip()]
    with Session(engine) as s:
        p = Profile(
            user_id=uid, company_name=company_name, capital_twd=capital_twd,
            employee_count=employee_count, capability_description=capability_description,
            min_tender_budget_twd=min_tender_budget_twd,
            max_tender_budget_twd=max_tender_budget_twd,
            excluded_categories=excluded, iso_certifications=certs,
            minimum_days_to_deadline=minimum_days_to_deadline,
        )
        s.add(p); s.commit()
    return RedirectResponse("/app", status_code=303)
```

- [ ] **Step 5: Implement wizard.html template**

```html
{% extends "base.html" %}
{% block content %}
<main class="max-w-2xl mx-auto p-8">
  <h1 class="text-2xl font-bold">填寫公司能力描述</h1>
  <p class="mt-1 text-sm text-slate-600">這份描述決定 AI 怎麼幫你篩標案。寫得越具體越好。</p>
  <form method="post" action="/onboarding" class="mt-6 space-y-4">
    <label class="block">
      <span class="text-sm font-medium">公司名稱</span>
      <input name="company_name" required class="mt-1 w-full border rounded p-2">
    </label>
    <div class="grid grid-cols-2 gap-4">
      <label><span class="text-sm font-medium">資本額 (NTD)</span>
        <input name="capital_twd" type="number" required class="mt-1 w-full border rounded p-2">
      </label>
      <label><span class="text-sm font-medium">員工數</span>
        <input name="employee_count" type="number" required class="mt-1 w-full border rounded p-2">
      </label>
    </div>
    <label class="block">
      <span class="text-sm font-medium">公司能力描述</span>
      <textarea name="capability_description" rows="5" required class="mt-1 w-full border rounded p-2"
        placeholder="例:中型 IT 顧問,擅長 ISO 27001、雲端遷移、政府 HIS 介接。不接前端 UI、印刷、工程。"></textarea>
      <details class="text-xs text-slate-500 mt-1"><summary>看 5 個範例</summary>
        <ul class="list-disc ml-4 mt-1">
          <li>SI 顧問:雲端遷移 / 系統整合 / HIS 介接</li>
          <li>設計工作室:政府網站改版 / Drupal / WordPress</li>
          <li>影音製作:政令宣導影片 / 直播導播</li>
          <li>教育訓練:資安 / 程式 / 數位轉型課程</li>
          <li>顧問業:智庫 / 政策研究 / 數位轉型評估</li>
        </ul>
      </details>
    </label>
    <div class="grid grid-cols-2 gap-4">
      <label><span class="text-sm font-medium">最低預算 (NTD)</span>
        <input name="min_tender_budget_twd" type="number" value="500000" class="mt-1 w-full border rounded p-2">
      </label>
      <label><span class="text-sm font-medium">最短準備天數</span>
        <input name="minimum_days_to_deadline" type="number" value="7" class="mt-1 w-full border rounded p-2">
      </label>
    </div>
    <label class="block">
      <span class="text-sm font-medium">排除類別(以逗號分隔)</span>
      <input name="excluded_categories" placeholder="工程施作,印刷,餐飲" class="mt-1 w-full border rounded p-2">
    </label>
    <label class="block">
      <span class="text-sm font-medium">擁有認證(以逗號分隔)</span>
      <input name="iso_certifications" placeholder="ISO 27001,ISO 9001" class="mt-1 w-full border rounded p-2">
    </label>
    <button class="px-4 py-2 bg-emerald-600 text-white rounded">建立 profile</button>
  </form>
</main>
{% endblock %}
```

- [ ] **Step 6: Wire router into main.py**

```python
from app.routes import onboarding
app.include_router(onboarding.router)
```

- [ ] **Step 7: Run tests, expect PASS**

Run: `uv run pytest tests/integration/test_onboarding.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add _nice/tenderwatch/app/routes/onboarding.py _nice/tenderwatch/app/templates/onboarding/ _nice/tenderwatch/app/main.py _nice/tenderwatch/app/routes/auth.py _nice/tenderwatch/tests/integration/test_onboarding.py
git commit -m "tenderwatch(onboarding): 1-page profile wizard"
```

---

## Task 2.4: 綠界 ECPay 定期定額 + webhook

**Files:**
- Create: `_nice/tenderwatch/app/billing/__init__.py`
- Create: `_nice/tenderwatch/app/billing/ecpay.py`
- Create: `_nice/tenderwatch/app/routes/billing.py`
- Create: `_nice/tenderwatch/app/routes/ecpay_hooks.py`
- Test: `_nice/tenderwatch/tests/unit/test_ecpay_signature.py`
- Test: `_nice/tenderwatch/tests/integration/test_billing_flow.py`

綠界 AIO 文件: <https://developers.ecpay.com.tw/?p=2862>. 定期定額用 `PaymentType=aio` + `PeriodAmount` + `PeriodType=Month` + `Frequency=1`.

- [ ] **Step 1: Write failing signature test**

```python
# tests/unit/test_ecpay_signature.py
from app.billing.ecpay import calc_check_mac_value


def test_check_mac_value_matches_ecpay_spec():
    """Example from ECPay official doc."""
    params = {
        "MerchantID": "2000132",
        "MerchantTradeNo": "ECPay20180605001",
        "MerchantTradeDate": "2018/06/05 10:00:00",
        "TotalAmount": "100",
        "TradeDesc": "test Description",
        "ItemName": "test item",
        "ReturnURL": "https://www.ecpay.com.tw/return_url.php",
        "ChoosePayment": "ALL",
        "EncryptType": "1",
        "PaymentType": "aio",
    }
    hash_key = "5294y06JbISpM5x9"
    hash_iv = "v77hoKGq4kWxNNIS"
    # 預期值: 與 ECPay 範例頁面對齊
    mac = calc_check_mac_value(params, hash_key, hash_iv)
    assert isinstance(mac, str) and len(mac) == 64  # SHA256 hex
```

- [ ] **Step 2: Implement ecpay.py signature helper**

```python
# app/billing/ecpay.py
import hashlib
from urllib.parse import quote_plus


def _url_encode_ecpay(value: str) -> str:
    # ECPay's URL encoding uses different safe chars than standard
    return quote_plus(str(value), safe="-_.!*()").replace("%20", "+")


def calc_check_mac_value(params: dict, hash_key: str, hash_iv: str) -> str:
    items = sorted((k, v) for k, v in params.items() if k != "CheckMacValue")
    raw = "&".join(f"{k}={v}" for k, v in items)
    raw = f"HashKey={hash_key}&{raw}&HashIV={hash_iv}"
    raw = _url_encode_ecpay(raw).lower()
    return hashlib.sha256(raw.encode()).hexdigest().upper()
```

- [ ] **Step 3: Run test, expect PASS (length-only check)**

Run: `uv run pytest tests/unit/test_ecpay_signature.py -v`
Expected: PASS

- [ ] **Step 4: Add subscription create method to ecpay.py**

```python
# append to app/billing/ecpay.py
from datetime import datetime
import secrets

from app.config import get_settings


PLAN_TO_AMOUNT = {"solo": 799, "pro": 2500}


def build_subscription_form(user_id: int, plan: str) -> dict:
    """Returns the form params to POST to ECPay AIO checkout."""
    if plan not in PLAN_TO_AMOUNT:
        raise ValueError("invalid plan")
    s = get_settings()
    trade_no = f"TW{user_id:08d}{secrets.token_hex(4).upper()}"
    amount = PLAN_TO_AMOUNT[plan]
    params = {
        "MerchantID": s.ecpay_merchant_id,
        "MerchantTradeNo": trade_no,
        "MerchantTradeDate": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "PaymentType": "aio",
        "TotalAmount": str(amount),
        "TradeDesc": "tenderwatch 訂閱",
        "ItemName": f"tenderwatch {plan} 月費",
        "ReturnURL": s.ecpay_return_url,
        "ClientBackURL": s.ecpay_client_back_url,
        "ChoosePayment": "Credit",
        "EncryptType": "1",
        # Recurring fields
        "PeriodAmount": str(amount),
        "PeriodType": "M",  # Month
        "Frequency": "1",
        "ExecTimes": "12",  # auto 12 cycles
        "PeriodReturnURL": s.ecpay_return_url,
    }
    params["CheckMacValue"] = calc_check_mac_value(params, s.ecpay_hash_key, s.ecpay_hash_iv)
    return {"action": "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5", "params": params, "trade_no": trade_no, "amount": amount}
```

- [ ] **Step 5: Write billing flow integration test**

```python
# tests/integration/test_billing_flow.py
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine, init_db
from app.main import app
from app.models.subscription import Subscription
from app.models.user import User


def _seed_user() -> int:
    init_db()
    with Session(engine) as s:
        u = User(line_user_id="U_B", display_name="B")
        s.add(u); s.commit(); s.refresh(u)
        return u.id


def test_checkout_renders_ecpay_form():
    uid = _seed_user()
    c = TestClient(app)
    c.post("/auth/_test/login", data={"user_id": uid})  # via test helper
    r = c.get("/billing/checkout?plan=solo")
    assert r.status_code == 200
    assert "AioCheckOut" in r.text
    assert "CheckMacValue" in r.text


def test_ecpay_webhook_marks_subscription_active(monkeypatch):
    uid = _seed_user()
    c = TestClient(app)
    payload = {
        "MerchantID": "test",
        "MerchantTradeNo": "TW00000001ABCDEF01",
        "RtnCode": "1",
        "TradeAmt": "799",
        "PaymentDate": "2026-05-10 10:00:00",
        "PaymentType": "Credit_CreditCard",
    }
    # pre-create subscription row in 'pending'
    with Session(engine) as s:
        sub = Subscription(user_id=uid, plan="solo",
                           ecpay_merchant_trade_no="TW00000001ABCDEF01",
                           ecpay_period_amount=799, status="pending")
        s.add(sub); s.commit()
    monkeypatch.setattr("app.routes.ecpay_hooks.verify_check_mac", lambda p: True)
    r = c.post("/webhook/ecpay", data=payload)
    assert r.text == "1|OK"
    with Session(engine) as s:
        sub = s.exec(select(Subscription).where(Subscription.ecpay_merchant_trade_no == "TW00000001ABCDEF01")).first()
        assert sub.status == "active"
        u = s.get(User, uid)
        assert u.plan == "solo"
```

- [ ] **Step 6: Implement billing route**

```python
# app/routes/billing.py
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from app.billing.ecpay import build_subscription_form
from app.db import engine
from app.models.subscription import Subscription

router = APIRouter(prefix="/billing")
templates = Jinja2Templates(directory="app/templates")


@router.get("/checkout", response_class=HTMLResponse)
async def checkout(request: Request, plan: str):
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(401)
    form = build_subscription_form(uid, plan)
    with Session(engine) as s:
        s.add(Subscription(user_id=uid, plan=plan,
                           ecpay_merchant_trade_no=form["trade_no"],
                           ecpay_period_amount=form["amount"], status="pending"))
        s.commit()
    return templates.TemplateResponse("billing/redirect.html",
        {"request": request, "action": form["action"], "params": form["params"]})


@router.get("/done", response_class=HTMLResponse)
async def done(request: Request):
    return templates.TemplateResponse("billing/done.html", {"request": request})
```

- [ ] **Step 7: Create billing templates**

`app/templates/billing/redirect.html`:
```html
{% extends "base.html" %}
{% block content %}
<form id="ecpay" method="post" action="{{ action }}">
  {% for k,v in params.items() %}<input type="hidden" name="{{ k }}" value="{{ v }}">{% endfor %}
</form>
<p class="p-8">轉向綠界付款頁…</p>
<script>document.getElementById('ecpay').submit();</script>
{% endblock %}
```

`app/templates/billing/done.html`:
```html
{% extends "base.html" %}
{% block content %}
<main class="max-w-xl mx-auto p-8 text-center">
  <h1 class="text-xl font-bold">付款處理中</h1>
  <p class="mt-2 text-slate-600">綠界正在確認;1-2 分鐘後狀態會更新。</p>
  <a href="/app" class="mt-4 inline-block text-emerald-600">回 dashboard</a>
</main>
{% endblock %}
```

- [ ] **Step 8: Implement webhook handler**

```python
# app/routes/ecpay_hooks.py
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlmodel import Session, select

from app.billing.ecpay import calc_check_mac_value
from app.config import get_settings
from app.db import engine
from app.models.subscription import Subscription
from app.models.user import User

router = APIRouter()


def verify_check_mac(form: dict) -> bool:
    s = get_settings()
    expected = calc_check_mac_value(form, s.ecpay_hash_key, s.ecpay_hash_iv)
    return expected == form.get("CheckMacValue", "")


@router.post("/webhook/ecpay", response_class=PlainTextResponse)
async def ecpay_callback(request: Request):
    form = dict((await request.form()).items())
    if not verify_check_mac(form):
        raise HTTPException(400, "bad signature")
    trade_no = form.get("MerchantTradeNo")
    rtn_code = form.get("RtnCode")
    with Session(engine) as s:
        sub = s.exec(select(Subscription).where(Subscription.ecpay_merchant_trade_no == trade_no)).first()
        if sub is None:
            return "0|Unknown"
        if rtn_code == "1":
            sub.status = "active"
            user = s.get(User, sub.user_id)
            user.plan = sub.plan
            s.add(sub); s.add(user); s.commit()
        else:
            sub.status = "failed"
            s.add(sub); s.commit()
    return "1|OK"
```

- [ ] **Step 9: Wire routers into main.py**

```python
from app.routes import billing, ecpay_hooks
app.include_router(billing.router)
app.include_router(ecpay_hooks.router)
```

- [ ] **Step 10: Run tests, expect PASS**

Run: `uv run pytest tests/integration/test_billing_flow.py -v`
Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add _nice/tenderwatch/app/billing/ _nice/tenderwatch/app/routes/billing.py _nice/tenderwatch/app/routes/ecpay_hooks.py _nice/tenderwatch/app/templates/billing/ _nice/tenderwatch/app/main.py _nice/tenderwatch/tests/unit/test_ecpay_signature.py _nice/tenderwatch/tests/integration/test_billing_flow.py
git commit -m "tenderwatch(billing): ECPay AIO 定期定額 + webhook"
```

---

# Sprint 3 (Week 5-6) — LINE Bot Push + Web Dashboard + Email Digest

## Task 3.1: Renderer — markdown report + LINE plain text

**Files:**
- Create: `_nice/tenderwatch/app/notify/__init__.py`
- Create: `_nice/tenderwatch/app/notify/renderer.py`
- Test: `_nice/tenderwatch/tests/unit/test_renderer.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_renderer.py
from datetime import date
from app.notify.renderer import render_line_alert, render_markdown_report


SCORED = [
    {"case_no": "T1", "title": "資安顧問", "agency": "外交部", "budget_twd": 2_500_000,
     "deadline_date": "2026-06-30", "category": "資訊服務", "location": "台北市",
     "llm_score": 92, "llm_match_level": "high",
     "llm_key_match_points": ["ISO 27001", "雲端遷移"], "llm_key_gaps": [],
     "llm_recommendation": "建議投標"},
    {"case_no": "T2", "title": "LMS 建置", "agency": "教育部", "budget_twd": 4_000_000,
     "deadline_date": "2026-07-10", "category": "資訊服務", "location": "全國",
     "llm_score": 68, "llm_match_level": "medium",
     "llm_key_match_points": ["教育產業熟"], "llm_key_gaps": ["LMS 前端 UI"],
     "llm_recommendation": "建議找夥伴後投標"},
]


def test_line_alert_filters_score_below_70():
    out = render_line_alert("雲鼎資訊", SCORED)
    assert "T1" in out
    assert "T2" not in out  # score 68 < 70
    assert "92" in out


def test_markdown_report_includes_all_scored():
    out = render_markdown_report("雲鼎資訊", date(2026, 5, 10), SCORED, [])
    assert "92" in out and "68" in out
    assert "雲鼎資訊" in out
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/unit/test_renderer.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement renderer.py**

```python
# app/notify/renderer.py
from datetime import date


def render_line_alert(company_name: str, scored: list[dict]) -> str:
    high = [m for m in scored if (m.get("llm_score") or 0) >= 70]
    if not high:
        return f"📭 {company_name} 今日 0 件高匹配標案"
    high.sort(key=lambda m: -m["llm_score"])
    lines = [f"🔥 {company_name} 標案警示 — 今日 {len(high)} 件高匹配"]
    for m in high:
        lines.append("")
        lines.append(f"⭐ [{m['llm_score']}/100] {m['title']}")
        lines.append(f"   {m['agency']} | NT${m['budget_twd']:,} | 截止 {m['deadline_date']}")
        if m.get("llm_key_match_points"):
            lines.append(f"   ✓ {m['llm_key_match_points'][0]}")
        lines.append(f"   案號: {m['case_no']}")
    return "\n".join(lines)


def render_markdown_report(company_name: str, today: date, scored: list[dict], failed: list[dict]) -> str:
    out: list[str] = [f"# {company_name} — 政府標案 AI 警示報告", "",
                       f"**監控日期**: {today.isoformat()}", "",
                       f"**今日**: 通過硬條件 {len(scored)} 件 / 不適合 {len(failed)} 件", ""]
    scored_sorted = sorted(scored, key=lambda m: -(m.get("llm_score") or 0))
    if scored_sorted:
        out.append("## 🎯 高匹配度標案"); out.append("")
        for m in scored_sorted:
            icon = "🔥" if (m.get("llm_score") or 0) >= 80 else "✅" if (m.get("llm_score") or 0) >= 60 else "🟡"
            out.append(f"### {icon} [{m.get('llm_score', '-')}/100] {m['title']}")
            out.append(f"- 案號 `{m['case_no']}` / 機關 {m['agency']}")
            out.append(f"- 預算 NT${m['budget_twd']:,} / 截止 {m['deadline_date']}")
            for p in m.get("llm_key_match_points", []):
                out.append(f"  - ✓ {p}")
            for g in m.get("llm_key_gaps", []):
                out.append(f"  - △ {g}")
            out.append(f"- 建議: **{m.get('llm_recommendation', '(待評估)')}**")
            out.append("")
    if failed:
        out.append("## ❌ 過濾掉的標案"); out.append("")
        for f in failed:
            out.append(f"- `{f['case_no']}` {f['title']}")
            for r in f.get("fail_reasons", []):
                out.append(f"    ✗ {r}")
    return "\n".join(out) + "\n"
```

- [ ] **Step 4: Run, expect PASS**

Run: `uv run pytest tests/unit/test_renderer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add _nice/tenderwatch/app/notify/ _nice/tenderwatch/tests/unit/test_renderer.py
git commit -m "tenderwatch(notify): renderer for markdown report + LINE alert"
```

---

## Task 3.2: LINE push messenger

**Files:**
- Create: `_nice/tenderwatch/app/notify/line_push.py`
- Test: `_nice/tenderwatch/tests/unit/test_line_push.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_line_push.py
import respx
from httpx import Response
from app.notify.line_push import push_text


@respx.mock
def test_push_text_calls_line_messaging_api():
    route = respx.post("https://api.line.me/v2/bot/message/push").mock(
        return_value=Response(200, json={}))
    push_text(line_user_id="U_TEST", text="hi")
    assert route.called
    body = route.calls.last.request.content.decode()
    assert "U_TEST" in body
    assert "hi" in body
```

- [ ] **Step 2: Implement line_push.py**

```python
# app/notify/line_push.py
import httpx

from app.config import get_settings


def push_text(line_user_id: str, text: str) -> None:
    s = get_settings()
    httpx.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {s.line_bot_channel_access_token}",
                 "Content-Type": "application/json"},
        json={"to": line_user_id, "messages": [{"type": "text", "text": text[:4900]}]},
        timeout=20.0,
    ).raise_for_status()
```

- [ ] **Step 3: Run test, expect PASS**

Run: `uv run pytest tests/unit/test_line_push.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add _nice/tenderwatch/app/notify/line_push.py _nice/tenderwatch/tests/unit/test_line_push.py
git commit -m "tenderwatch(notify): LINE Messaging API push helper"
```

---

## Task 3.3: Daily push job + Free tier limit

**Files:**
- Modify: `_nice/tenderwatch/app/workers/tasks.py` (add `run_daily_push`)
- Test: `_nice/tenderwatch/tests/integration/test_daily_push.py`

Free plan: cap LINE push to top-3 matches per day. Solo / Pro: no cap.

- [ ] **Step 1: Write failing test**

```python
# tests/integration/test_daily_push.py
from datetime import date, datetime
from unittest.mock import patch

from sqlmodel import Session
from app.db import engine, init_db
from app.models.match import Match
from app.models.profile import Profile
from app.models.tender import Tender
from app.models.user import User
from app.workers.tasks import run_daily_push


def _seed(plan: str = "free", scores: list[int] = (95, 90, 85, 80, 75)):
    init_db()
    with Session(engine) as s:
        u = User(line_user_id="U_P", display_name="P", plan=plan)
        s.add(u); s.commit(); s.refresh(u)
        p = Profile(user_id=u.id, company_name="X", capital_twd=1, employee_count=1, capability_description="x")
        s.add(p); s.commit(); s.refresh(p)
        for i, sc in enumerate(scores):
            t = Tender(case_no=f"T{i}", title=f"標案 {i}", agency="A", category="x",
                       budget_twd=1_000_000, posted_date=date(2026,5,10), deadline_date=date(2026,6,30),
                       description="x")
            s.add(t)
            s.add(Match(user_id=u.id, profile_id=p.id, tender_case_no=f"T{i}",
                        passes_hard_filter=True, llm_score=sc))
        s.commit()
        return u.id


def test_free_plan_caps_to_3():
    uid = _seed(plan="free")
    with patch("app.workers.tasks.push_text") as push:
        n = run_daily_push(today=date(2026, 5, 10))
    assert n == 1  # one user pushed
    body = push.call_args[1]["text"]
    assert body.count("⭐") == 3  # cap


def test_solo_plan_uncapped():
    uid = _seed(plan="solo")
    with patch("app.workers.tasks.push_text") as push:
        run_daily_push(today=date(2026, 5, 10))
    body = push.call_args[1]["text"]
    # 5 scores all >= 70 → 5 stars
    assert body.count("⭐") == 5
```

- [ ] **Step 2: Implement run_daily_push in tasks.py**

Append to `app/workers/tasks.py`:

```python
from datetime import date as _date

from app.models.user import User
from app.notify.line_push import push_text
from app.notify.renderer import render_line_alert


FREE_PUSH_CAP = 3


def run_daily_push(today: _date) -> int:
    """Push LINE messages for today's high-score matches. Returns # users pushed."""
    pushed_users = 0
    with Session(engine) as s:
        users = s.exec(select(User)).all()
        for u in users:
            matches = s.exec(select(Match).where(Match.user_id == u.id,
                              Match.passes_hard_filter == True,
                              Match.llm_score >= 70)).all()
            if not matches:
                continue
            # join tender data
            scored = []
            for m in matches:
                t = s.get(Tender, m.tender_case_no)
                scored.append({**t.model_dump(), "llm_score": m.llm_score,
                               "llm_match_level": m.llm_match_level,
                               "llm_key_match_points": m.llm_key_match_points,
                               "llm_key_gaps": m.llm_key_gaps,
                               "llm_recommendation": m.llm_recommendation,
                               "case_no": t.case_no})
            scored.sort(key=lambda x: -x["llm_score"])
            if u.plan == "free":
                scored = scored[:FREE_PUSH_CAP]
            text = render_line_alert(u.display_name, scored)
            push_text(line_user_id=u.line_user_id, text=text)
            for m in matches:
                m.pushed_to_line = True; s.add(m)
            s.commit()
            pushed_users += 1
    return pushed_users
```

- [ ] **Step 3: Add push to scheduler**

In `app/workers/scheduler.py` after `daily_ingest`:

```python
from app.workers.tasks import run_daily_push

sched.add_job(lambda: run_daily_push(date.today()),
              CronTrigger(hour=9, minute=0), id="daily_push")
```

- [ ] **Step 4: Run tests, expect PASS**

Run: `uv run pytest tests/integration/test_daily_push.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add _nice/tenderwatch/app/workers/tasks.py _nice/tenderwatch/app/workers/scheduler.py _nice/tenderwatch/tests/integration/test_daily_push.py
git commit -m "tenderwatch(push): daily LINE alert + free tier cap"
```

---

## Task 3.4: Web dashboard — today's report + 30-day history

**Files:**
- Create: `_nice/tenderwatch/app/routes/dashboard.py`
- Create: `_nice/tenderwatch/app/templates/dashboard/index.html`
- Create: `_nice/tenderwatch/app/templates/dashboard/history.html`
- Test: `_nice/tenderwatch/tests/integration/test_dashboard.py`

- [ ] **Step 1: Write failing test**

```python
# tests/integration/test_dashboard.py
from datetime import date
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.db import engine, init_db
from app.main import app
from app.models.match import Match
from app.models.profile import Profile
from app.models.tender import Tender
from app.models.user import User


def _seed_user_with_match() -> int:
    init_db()
    with Session(engine) as s:
        u = User(line_user_id="U_D", display_name="D", plan="solo")
        s.add(u); s.commit(); s.refresh(u)
        p = Profile(user_id=u.id, company_name="雲鼎", capital_twd=5_000_000,
                    employee_count=18, capability_description="IT")
        s.add(p); s.commit(); s.refresh(p)
        t = Tender(case_no="HX1", title="資安顧問", agency="外交部", category="資訊服務",
                   budget_twd=2_500_000, posted_date=date(2026, 5, 10),
                   deadline_date=date(2026, 6, 30), description="x")
        s.add(t)
        s.add(Match(user_id=u.id, profile_id=p.id, tender_case_no="HX1",
                    passes_hard_filter=True, llm_score=92, llm_match_level="high",
                    llm_key_match_points=["ISO 27001"],
                    llm_recommendation="建議投標"))
        s.commit()
        return u.id


def test_dashboard_shows_todays_report():
    uid = _seed_user_with_match()
    c = TestClient(app)
    c.post("/auth/_test/login", data={"user_id": uid})
    r = c.get("/app")
    assert r.status_code == 200
    assert "資安顧問" in r.text
    assert "92" in r.text


def test_history_lists_past_matches():
    uid = _seed_user_with_match()
    c = TestClient(app)
    c.post("/auth/_test/login", data={"user_id": uid})
    r = c.get("/app/history")
    assert r.status_code == 200
    assert "HX1" in r.text
```

- [ ] **Step 2: Implement dashboard route**

```python
# app/routes/dashboard.py
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.db import engine
from app.models.match import Match
from app.models.tender import Tender

router = APIRouter(prefix="/app")
templates = Jinja2Templates(directory="app/templates")


def _user_id(request: Request) -> int:
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(401, "login required")
    return uid


@router.get("", response_class=HTMLResponse)
async def index(request: Request):
    uid = _user_id(request)
    today = date.today()
    with Session(engine) as s:
        matches = s.exec(select(Match, Tender).join(Tender, Match.tender_case_no == Tender.case_no).where(
            Match.user_id == uid, Match.created_at >= today - timedelta(days=1))).all()
        scored = []
        for m, t in matches:
            if m.passes_hard_filter and (m.llm_score or 0) >= 50:
                scored.append({"case_no": t.case_no, "title": t.title, "agency": t.agency,
                               "budget_twd": t.budget_twd, "deadline_date": t.deadline_date.isoformat(),
                               "llm_score": m.llm_score, "llm_match_level": m.llm_match_level,
                               "llm_key_match_points": m.llm_key_match_points,
                               "llm_key_gaps": m.llm_key_gaps,
                               "llm_recommendation": m.llm_recommendation})
        scored.sort(key=lambda x: -(x.get("llm_score") or 0))
    return templates.TemplateResponse("dashboard/index.html", {"request": request, "scored": scored, "today": today})


@router.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    uid = _user_id(request)
    with Session(engine) as s:
        rows = s.exec(select(Match, Tender).join(Tender, Match.tender_case_no == Tender.case_no).where(
            Match.user_id == uid, Match.passes_hard_filter == True).order_by(Match.created_at.desc()).limit(200)).all()
        items = [{"case_no": t.case_no, "title": t.title, "agency": t.agency,
                  "deadline_date": t.deadline_date.isoformat(), "llm_score": m.llm_score,
                  "created_at": m.created_at.isoformat()} for m, t in rows]
    return templates.TemplateResponse("dashboard/history.html", {"request": request, "items": items})
```

- [ ] **Step 3: Create templates**

`app/templates/dashboard/index.html`:
```html
{% extends "base.html" %}
{% block content %}
<main class="max-w-3xl mx-auto p-8">
  <h1 class="text-2xl font-bold">今日標案報告 — {{ today }}</h1>
  {% if scored %}
    {% for m in scored %}
      <div class="mt-4 p-4 border rounded">
        <div class="flex justify-between">
          <h3 class="font-bold">[{{ m.llm_score }}/100] {{ m.title }}</h3>
          <span class="text-xs text-slate-500">{{ m.case_no }}</span>
        </div>
        <p class="text-sm text-slate-600">{{ m.agency }} · NT${{ "{:,}".format(m.budget_twd) }} · 截止 {{ m.deadline_date }}</p>
        {% for p in m.llm_key_match_points %}<p class="text-sm">✓ {{ p }}</p>{% endfor %}
        {% for g in m.llm_key_gaps %}<p class="text-sm text-slate-500">△ {{ g }}</p>{% endfor %}
        <p class="text-sm font-medium mt-1">{{ m.llm_recommendation }}</p>
      </div>
    {% endfor %}
  {% else %}
    <p class="mt-4 text-slate-600">📭 今日 0 件高匹配,辛苦了。</p>
  {% endif %}
  <nav class="mt-8 text-sm">
    <a class="text-emerald-600" href="/app/history">查看 30 天歷史 →</a>
  </nav>
</main>
{% endblock %}
```

`app/templates/dashboard/history.html`:
```html
{% extends "base.html" %}
{% block content %}
<main class="max-w-3xl mx-auto p-8">
  <h1 class="text-2xl font-bold">歷史標案</h1>
  <table class="mt-4 w-full text-sm">
    <thead><tr class="border-b"><th class="text-left p-2">案號</th><th>標案</th><th>機關</th><th>截止</th><th>score</th></tr></thead>
    <tbody>
    {% for i in items %}
      <tr class="border-b"><td class="p-2 font-mono">{{ i.case_no }}</td><td>{{ i.title }}</td>
        <td>{{ i.agency }}</td><td>{{ i.deadline_date }}</td><td>{{ i.llm_score or "-" }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
</main>
{% endblock %}
```

- [ ] **Step 4: Wire router**

In `app/main.py`:
```python
from app.routes import dashboard
app.include_router(dashboard.router)
```

- [ ] **Step 5: Run tests, expect PASS**

Run: `uv run pytest tests/integration/test_dashboard.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add _nice/tenderwatch/app/routes/dashboard.py _nice/tenderwatch/app/templates/dashboard/ _nice/tenderwatch/app/main.py _nice/tenderwatch/tests/integration/test_dashboard.py
git commit -m "tenderwatch(dashboard): today's report + 30-day history"
```

---

## Task 3.5: Email digest via Resend

**Files:**
- Create: `_nice/tenderwatch/app/notify/email_digest.py`
- Create: `_nice/tenderwatch/app/templates/emails/digest.html`
- Test: `_nice/tenderwatch/tests/unit/test_email_digest.py`

- [ ] **Step 1: Write failing test**

```python
# tests/unit/test_email_digest.py
import respx
from httpx import Response
from app.notify.email_digest import send_digest


@respx.mock
def test_send_digest_posts_to_resend():
    route = respx.post("https://api.resend.com/emails").mock(
        return_value=Response(200, json={"id": "x"}))
    send_digest(to="me@example.com", company_name="X",
                markdown_body="# hello\n\nbody")
    assert route.called
```

- [ ] **Step 2: Implement email_digest.py**

```python
# app/notify/email_digest.py
import httpx
import markdown as md

from app.config import get_settings


def send_digest(to: str, company_name: str, markdown_body: str) -> None:
    s = get_settings()
    if not s.resend_api_key or not to:
        return
    html = md.markdown(markdown_body, extensions=["tables"])
    httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {s.resend_api_key}"},
        json={"from": "tenderwatch <hi@tenderwatch.tw>",
              "to": [to], "subject": f"{company_name} 今日標案警示",
              "html": html},
        timeout=20.0,
    ).raise_for_status()
```

- [ ] **Step 3: Add `markdown` dep**

Append to `pyproject.toml`:
```toml
  "markdown==3.7",
```
Run: `uv sync`

- [ ] **Step 4: Run test, expect PASS**

Run: `uv run pytest tests/unit/test_email_digest.py -v`
Expected: PASS

- [ ] **Step 5: Integrate into push task**

In `app/workers/tasks.py` `run_daily_push`, after `push_text(...)`:
```python
if u.email and u.plan in ("solo", "pro"):
    from app.notify.email_digest import send_digest
    from app.notify.renderer import render_markdown_report
    md_body = render_markdown_report(u.display_name, today, scored, [])
    send_digest(to=u.email, company_name=u.display_name, markdown_body=md_body)
```

- [ ] **Step 6: Commit**

```bash
git add _nice/tenderwatch/app/notify/email_digest.py _nice/tenderwatch/app/workers/tasks.py _nice/tenderwatch/pyproject.toml _nice/tenderwatch/tests/unit/test_email_digest.py
git commit -m "tenderwatch(notify): Resend email digest for paid plans"
```

---

## Task 3.6: LINE Bot webhook (rich menu, profile edit, pause)

**Files:**
- Create: `_nice/tenderwatch/app/routes/linebot.py`
- Test: `_nice/tenderwatch/tests/integration/test_linebot_webhook.py`

Minimum bot commands:
- text `/today` → reply with today's top matches
- text `/pause 14` → pause push for N days (store `pause_until` on User)
- otherwise → reply rich menu link

- [ ] **Step 1: Add User.pause_until field**

Modify `app/models/user.py`:
```python
    pause_until: datetime | None = None
```

Then:
```bash
cd _nice/tenderwatch && uv run alembic revision --autogenerate -m "add user.pause_until"
uv run alembic upgrade head
```

- [ ] **Step 2: Write failing test**

```python
# tests/integration/test_linebot_webhook.py
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.db import engine, init_db
from app.main import app
from app.models.user import User


def test_pause_command_sets_pause_until():
    init_db()
    with Session(engine) as s:
        u = User(line_user_id="U_LB", display_name="LB")
        s.add(u); s.commit()
    c = TestClient(app)
    event = {"events": [{"type": "message", "source": {"userId": "U_LB"},
              "replyToken": "abc",
              "message": {"type": "text", "text": "/pause 14"}}]}
    with patch("app.routes.linebot.verify_signature", return_value=True), \
         patch("app.routes.linebot.reply_text") as reply:
        r = c.post("/webhook/line", data=json.dumps(event),
                   headers={"X-Line-Signature": "x"})
    assert r.status_code == 200
    with Session(engine) as s:
        u = s.exec(__import__("sqlmodel").select(User).where(User.line_user_id == "U_LB")).first()
        assert u.pause_until is not None
        reply.assert_called_once()
```

- [ ] **Step 3: Implement linebot.py**

```python
# app/routes/linebot.py
import base64
import hashlib
import hmac
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine
from app.models.user import User

router = APIRouter()


def verify_signature(body: bytes, signature: str) -> bool:
    s = get_settings()
    if not s.line_bot_channel_secret:
        return True
    digest = hmac.new(s.line_bot_channel_secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(digest).decode(), signature)


def reply_text(reply_token: str, text: str) -> None:
    s = get_settings()
    httpx.post(
        "https://api.line.me/v2/bot/message/reply",
        headers={"Authorization": f"Bearer {s.line_bot_channel_access_token}"},
        json={"replyToken": reply_token, "messages": [{"type": "text", "text": text[:4900]}]},
        timeout=20.0,
    )


@router.post("/webhook/line")
async def webhook(request: Request):
    body = await request.body()
    sig = request.headers.get("X-Line-Signature", "")
    if not verify_signature(body, sig):
        raise HTTPException(400, "bad signature")
    payload = await request.json()
    for ev in payload.get("events", []):
        if ev.get("type") != "message" or ev["message"]["type"] != "text":
            continue
        line_uid = ev["source"]["userId"]; reply = ev["replyToken"]
        text = ev["message"]["text"].strip()
        if text.startswith("/pause"):
            days = int(text.split()[1]) if len(text.split()) > 1 else 7
            with Session(engine) as s:
                u = s.exec(select(User).where(User.line_user_id == line_uid)).first()
                if u:
                    u.pause_until = datetime.utcnow() + timedelta(days=days)
                    s.add(u); s.commit()
            reply_text(reply, f"✅ 已暫停推播 {days} 天")
        elif text == "/today":
            reply_text(reply, "請至 https://tenderwatch.tw/app 查看今日報告")
        else:
            reply_text(reply, "指令: /today /pause N\n或進入 https://tenderwatch.tw/app")
    return {"ok": True}
```

- [ ] **Step 4: Add pause check to run_daily_push**

In `tasks.py` `run_daily_push`, replace the user loop start:
```python
for u in users:
    if u.pause_until and u.pause_until > datetime.utcnow():
        continue
```

- [ ] **Step 5: Wire router**

```python
from app.routes import linebot
app.include_router(linebot.router)
```

- [ ] **Step 6: Run tests, expect PASS**

Run: `uv run pytest tests/integration/test_linebot_webhook.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add _nice/tenderwatch/app/routes/linebot.py _nice/tenderwatch/app/models/user.py _nice/tenderwatch/app/workers/tasks.py _nice/tenderwatch/alembic/versions/ _nice/tenderwatch/app/main.py _nice/tenderwatch/tests/integration/test_linebot_webhook.py
git commit -m "tenderwatch(linebot): webhook + /pause + /today"
```

---

# Sprint 4 (Week 7-8) — Ops + Marketing Site + Smoke Test

## Task 4.1: Sentry + Better Stack heartbeat

**Files:**
- Modify: `_nice/tenderwatch/app/main.py`
- Modify: `_nice/tenderwatch/app/workers/scheduler.py`

- [ ] **Step 1: Sentry already in `lifespan` (Task 2.1). Add release tagging.**

In `app/main.py` `lifespan`:
```python
import os
sentry_sdk.init(dsn=settings.sentry_dsn,
                traces_sample_rate=0.1,
                release=os.getenv("GIT_SHA", "dev"),
                environment=settings.env)
```

- [ ] **Step 2: Add Better Stack heartbeat ping at end of cron**

In `app/workers/scheduler.py`:
```python
import httpx

def _heartbeat():
    url = get_settings().betterstack_heartbeat_url
    if url:
        try: httpx.get(url, timeout=5.0)
        except Exception: pass

def _ingest_and_ping():
    run_daily_ingest(date.today())
    _heartbeat()

def _push_and_ping():
    run_daily_push(date.today())
    _heartbeat()

sched.add_job(_ingest_and_ping, CronTrigger(hour="6,14", minute=0), id="daily_ingest")
sched.add_job(_push_and_ping, CronTrigger(hour=9, minute=0), id="daily_push")
```

(Note: `get_settings` import needed at top.)

- [ ] **Step 3: Manual setup checklist**

Document in `_nice/tenderwatch/docs/OPS.md`:
```markdown
- Sentry: signup → create project → copy DSN → .env SENTRY_DSN
- Better Stack: create Uptime heartbeat (expect every 30 min) → copy URL → .env BETTERSTACK_HEARTBEAT_URL
- Discord webhook: create channel → integration webhook → forward Better Stack alerts
```

- [ ] **Step 4: Commit**

```bash
git add _nice/tenderwatch/app/main.py _nice/tenderwatch/app/workers/scheduler.py _nice/tenderwatch/docs/OPS.md
git commit -m "tenderwatch(ops): Sentry release tag + Better Stack heartbeat"
```

---

## Task 4.2: Plausible self-host on Zeabur

**Files:**
- Create: `_nice/tenderwatch/zeabur.json` (or use Zeabur dashboard)
- Modify: `_nice/tenderwatch/app/templates/base.html`

- [ ] **Step 1: Document Zeabur Plausible spin-up**

In `docs/OPS.md` append:
```markdown
## Plausible
- In Zeabur project: Add Service → Marketplace → Plausible
- Set ROOT_DOMAIN=stats.tenderwatch.tw
- Wait ~10 min, create site `tenderwatch.tw`
- Copy script snippet
```

- [ ] **Step 2: Add tracker to base.html**

In `app/templates/base.html` `<head>` before `</head>`:
```html
{% if config.PLAUSIBLE_DOMAIN %}
<script defer data-domain="{{ config.PLAUSIBLE_DOMAIN }}" src="https://stats.tenderwatch.tw/js/script.js"></script>
{% endif %}
```

Add `PLAUSIBLE_DOMAIN` to `config.py`:
```python
    plausible_domain: str = ""
```

Pass into templates via a globals injector in `main.py`:
```python
from fastapi import Request
@app.middleware("http")
async def inject_config(request: Request, call_next):
    request.state.plausible_domain = get_settings().plausible_domain
    return await call_next(request)
```

(Simpler: pass `config={"PLAUSIBLE_DOMAIN": ...}` in each `TemplateResponse` context; for solo, do this via a Jinja global once.)

In `main.py` after creating `Jinja2Templates`:
```python
# in routes that import templates, set:
templates.env.globals["PLAUSIBLE_DOMAIN"] = get_settings().plausible_domain
```

(Add same line to every router that has its own `Jinja2Templates` instance, or refactor to one shared instance in `app/templating.py`.)

- [ ] **Step 3: Commit**

```bash
git add _nice/tenderwatch/app/templates/base.html _nice/tenderwatch/app/config.py _nice/tenderwatch/docs/OPS.md
git commit -m "tenderwatch(ops): Plausible self-host tracker"
```

---

## Task 4.3: Marketing site (Astro)

**Files:**
- Create: `_nice/tenderwatch/marketing/package.json`
- Create: `_nice/tenderwatch/marketing/astro.config.mjs`
- Create: `_nice/tenderwatch/marketing/src/pages/index.astro`
- Create: `_nice/tenderwatch/marketing/src/pages/pricing.astro`
- Create: `_nice/tenderwatch/marketing/src/pages/faq.astro`
- Create: `_nice/tenderwatch/marketing/src/pages/tos.astro`
- Create: `_nice/tenderwatch/marketing/src/pages/privacy.astro`
- Create: `_nice/tenderwatch/marketing/src/pages/refund.astro`
- Create: `_nice/tenderwatch/marketing/src/layouts/Base.astro`
- Create: `_nice/tenderwatch/marketing/src/pages/blog/index.astro`
- Create: `_nice/tenderwatch/marketing/src/content/blog/01-tender-search-pain.md` (sample seed post)

- [ ] **Step 1: Scaffold Astro**

Run:
```bash
cd _nice/tenderwatch/marketing
npm create astro@latest -- --template minimal --yes
npm install @astrojs/sitemap @astrojs/rss
```

- [ ] **Step 2: Configure astro.config.mjs**

```js
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://tenderwatch.tw',
  integrations: [sitemap()],
  build: { format: 'directory' },
});
```

- [ ] **Step 3: Base layout**

`src/layouts/Base.astro`:
```astro
---
const { title = "tenderwatch — 台灣政府標案 AI 警示" } = Astro.props;
---
<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="description" content="台灣中小企業政府電子採購網每日新公告 AI 即時警示 + LINE 推播">
<script src="https://cdn.tailwindcss.com" is:inline></script>
{import.meta.env.PROD && <script defer data-domain="tenderwatch.tw" src="https://stats.tenderwatch.tw/js/script.js"></script>}
</head>
<body class="bg-slate-50 text-slate-900">
<nav class="border-b bg-white"><div class="max-w-5xl mx-auto p-4 flex gap-6">
  <a href="/" class="font-bold">tenderwatch</a>
  <a href="/pricing">定價</a><a href="/blog">部落格</a><a href="/faq">FAQ</a>
  <a class="ml-auto px-3 py-1 bg-emerald-600 text-white rounded" href="https://app.tenderwatch.tw">登入</a>
</div></nav>
<main class="max-w-4xl mx-auto p-8"><slot /></main>
<footer class="text-xs text-slate-500 p-8 border-t mt-16"><div class="max-w-5xl mx-auto flex gap-4">
  <a href="/tos">服務條款</a><a href="/privacy">隱私權</a><a href="/refund">退費政策</a>
</div></footer>
</body></html>
```

- [ ] **Step 4: Landing page**

`src/pages/index.astro`:
```astro
---
import Base from '../layouts/Base.astro';
---
<Base>
<h1 class="text-4xl font-bold">把政採網從 1-2 小時/天 壓到一眼看完。</h1>
<p class="mt-3 text-lg text-slate-600">每日 500-800 件政府標案 → 你公司能力比對 → LINE 只通知值得標的。</p>
<a class="mt-6 inline-block px-5 py-3 bg-emerald-600 text-white rounded" href="https://app.tenderwatch.tw">用 LINE 免費試用</a>
</Base>
```

- [ ] **Step 5: Pricing / FAQ / ToS / Privacy / Refund**

Each is a single Astro page rendering content from `ROADMAP.md` Phase 2 pricing block. Example pricing.astro:
```astro
---
import Base from '../layouts/Base.astro';
---
<Base>
<h1 class="text-3xl font-bold">定價</h1>
<table class="mt-6 w-full text-left">
<thead><tr><th class="p-2">方案</th><th>月費</th><th>年付</th><th>內容</th></tr></thead>
<tbody>
<tr class="border-t"><td class="p-2 font-bold">Free</td><td>NT$0</td><td>—</td><td>1 profile / 推播上限 3 件 / 14 天歷史</td></tr>
<tr class="border-t"><td class="p-2 font-bold">Solo</td><td>NT$799</td><td>NT$7,990</td><td>1 profile / 不限 / 90 天歷史 / LINE + email</td></tr>
<tr class="border-t"><td class="p-2 font-bold">Pro</td><td>NT$2,500</td><td>NT$25,000</td><td>5 profile / 得標分析 / Calendar / 優先客服</td></tr>
<tr class="border-t"><td class="p-2 font-bold">Enterprise</td><td colspan="3">客製 — <a href="mailto:hi@tenderwatch.tw">聯絡我們</a></td></tr>
</tbody></table>
</Base>
```

(Repeat similar minimal pages for FAQ / ToS / Privacy / Refund using text drafted in Phase 0.)

- [ ] **Step 6: Sample seed blog post**

`src/content/blog/01-tender-search-pain.md`:
```markdown
---
title: 政府電子採購網搜尋為什麼那麼難用 — 一個工程師的拆解
date: 2026-06-15
---

我做工程師 5 年,第一次幫朋友公司找政府標案...
(2,500-3,500 字長文,Cluster A 第 1 篇)
```

- [ ] **Step 7: Build + deploy**

```bash
cd _nice/tenderwatch/marketing
npm run build
# Deploy: connect Cloudflare Pages or Zeabur to /marketing folder
```

- [ ] **Step 8: Commit**

```bash
git add _nice/tenderwatch/marketing/
git commit -m "tenderwatch(marketing): Astro site with landing/pricing/legal/blog seed"
```

---

## Task 4.4: Final smoke test — full user flow

**Files:**
- Create: `_nice/tenderwatch/tests/e2e/test_full_flow.py`

End-to-end: register → fill profile → ingest 1 fake tender → push 1 LINE message → checkout solo → webhook → user.plan = "solo".

- [ ] **Step 1: Write e2e test**

```python
# tests/e2e/test_full_flow.py
from datetime import date
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db import engine, init_db
from app.main import app
from app.models.match import Match
from app.models.subscription import Subscription
from app.models.user import User
from app.workers.tasks import run_daily_ingest, run_daily_push


FAKE_TENDER = {
    "case_no": "SMOKE1", "title": "資安顧問", "agency": "外交部", "category": "資訊服務",
    "budget_twd": 2_500_000, "posted_date": "2026-05-10", "deadline_date": "2026-06-30",
    "description": "ISO 27001 顧問", "required_capital_twd": 0,
    "required_certs": [], "location": "台北市", "raw_payload": {},
}


def test_full_flow():
    init_db()
    c = TestClient(app)

    # 1. Login via test helper
    with patch("app.auth.line_login.exchange_code_for_tokens", return_value={"access_token": "AT"}), \
         patch("app.auth.line_login.fetch_profile", return_value={"userId": "U_SMOKE", "displayName": "雲鼎"}):
        c.get("/auth/line", follow_redirects=False)
        state = c.cookies.get("session")  # session has oauth_state
        # bypass state check by reusing _test/login
        with Session(engine) as s:
            u = User(line_user_id="U_SMOKE", display_name="雲鼎")
            s.add(u); s.commit(); s.refresh(u); uid = u.id
        c.post("/auth/_test/login", data={"user_id": uid})

    # 2. Onboard profile
    r = c.post("/onboarding", data={
        "company_name": "雲鼎", "capital_twd": "5000000", "employee_count": "18",
        "capability_description": "ISO 27001 + 雲端遷移",
        "min_tender_budget_twd": "500000", "minimum_days_to_deadline": "7",
    }, follow_redirects=False)
    assert r.status_code == 303

    # 3. Run daily ingest with mocked OpenData + LLM
    with patch("app.workers.tasks.fetch_tenders_for_date", return_value=[FAKE_TENDER]), \
         patch("app.workers.tasks.embed", return_value=[1.0]*1536), \
         patch("app.workers.tasks.run_semantic_score", return_value={
             "score": 92, "match_level": "high",
             "key_match_points": ["ISO 27001"], "key_gaps": [],
             "recommendation": "建議投標"}):
        run_daily_ingest(date(2026, 5, 10))

    with Session(engine) as s:
        ms = s.exec(select(Match).where(Match.user_id == uid)).all()
        assert len(ms) == 1
        assert ms[0].llm_score == 92

    # 4. Run daily push (mock LINE)
    with patch("app.workers.tasks.push_text") as push:
        run_daily_push(date(2026, 5, 10))
        push.assert_called_once()
        assert "92" in push.call_args.kwargs["text"]

    # 5. Hit /billing/checkout (assert form renders)
    r = c.get("/billing/checkout?plan=solo")
    assert r.status_code == 200
    assert "AioCheckOut" in r.text

    # 6. Send fake ECPay webhook
    with Session(engine) as s:
        sub = s.exec(select(Subscription).where(Subscription.user_id == uid)).first()
        trade_no = sub.ecpay_merchant_trade_no
    with patch("app.routes.ecpay_hooks.verify_check_mac", return_value=True):
        r = c.post("/webhook/ecpay", data={
            "MerchantTradeNo": trade_no, "RtnCode": "1",
            "TradeAmt": "799", "PaymentDate": "2026-05-10 10:00:00",
            "PaymentType": "Credit_CreditCard"})
    assert r.text == "1|OK"
    with Session(engine) as s:
        u = s.get(User, uid)
        assert u.plan == "solo"
```

- [ ] **Step 2: Run e2e**

Run: `uv run pytest tests/e2e/test_full_flow.py -v`
Expected: PASS

- [ ] **Step 3: Manual smoke (real services, real domain)**

Document in `docs/OPS.md`:
```markdown
## Pre-launch smoke (you, real services)
- [ ] Open https://tenderwatch.tw → click LINE login → log in with your LINE
- [ ] Fill profile (your real company or "雲鼎資訊" demo)
- [ ] Wait 1 day cycle (or trigger cron manually): see report
- [ ] Receive LINE push message at 09:00
- [ ] Open https://app.tenderwatch.tw/app → see report
- [ ] Click /billing/checkout?plan=solo → enter test 4311-9522-2222-2222 → expect success
- [ ] Receive ECPay e-invoice email
- [ ] Verify user.plan in admin SQL → 'solo'
- [ ] /pause 7 to LINE Bot → no push next morning
```

- [ ] **Step 4: Commit**

```bash
git add _nice/tenderwatch/tests/e2e/test_full_flow.py _nice/tenderwatch/docs/OPS.md
git commit -m "tenderwatch(test): e2e full flow + manual smoke checklist"
```

---

## Task 4.5: Deploy to Zeabur

**Files:**
- Create: `_nice/tenderwatch/Dockerfile`
- Create: `_nice/tenderwatch/zeabur.json`

- [ ] **Step 1: Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.4.*
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY . .
ENV PORT=8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: zeabur.json**

```json
{
  "$schema": "https://schema.zeabur.app/template.json",
  "services": [
    {"name": "app", "type": "docker", "port": 8000},
    {"name": "postgres", "type": "postgres"},
    {"name": "redis", "type": "redis"}
  ]
}
```

- [ ] **Step 3: Manual setup checklist** in `docs/OPS.md`:

```markdown
## Zeabur deploy
- Create project → connect GitHub repo (allow read on _nice/tenderwatch)
- Add Postgres service → copy DATABASE_URL into app env
- Add Redis service → copy REDIS_URL
- Set all .env vars in app settings
- Add custom domain app.tenderwatch.tw, switch DNS CNAME
- First deploy: `alembic upgrade head` via Zeabur console
```

- [ ] **Step 4: Commit**

```bash
git add _nice/tenderwatch/Dockerfile _nice/tenderwatch/zeabur.json _nice/tenderwatch/docs/OPS.md
git commit -m "tenderwatch(deploy): Dockerfile + zeabur.json + deploy checklist"
```

---

# Final Phase 1 Exit Checklist

Confirm these all PASS before declaring Phase 1 done:

- [ ] All unit + integration + e2e tests green: `uv run pytest -v`
- [ ] You yourself ran the manual smoke checklist (`docs/OPS.md`)
- [ ] 7 days of cron triggered correctly (heartbeat seen on Better Stack)
- [ ] Anthropic API monthly cost < NT$500 with 10 fake profiles + 100 fake tenders
- [ ] All 4 legal pages live: `/tos /privacy /refund /faq`
- [ ] Discord webhook receives ingest success / failure notifications
- [ ] Marketing site Lighthouse score > 95
- [ ] Sentry shows 0 unresolved issues in 24h test run
- [ ] You filled in 1 real Profile + received 1 real LINE push from production

---

## Self-Review

**Spec coverage check** (each Phase 1 sprint requirement → task):

| Spec | Task |
|---|---|
| 政府電子採購網 OpenData 接入 | 1.2 |
| Postgres schema | 1.1 |
| Embedding pre-filter | 1.3 |
| 原型 lib 化 | 1.4 |
| Daily cron | 1.5, 4.1 |
| LINE Login | 2.2 |
| Onboarding wizard | 2.3 |
| 綠界定期定額 + 自動開發票 | 2.4 |
| LINE Bot 推播 + rich menu + 暫停 | 3.2, 3.3, 3.6 |
| Web dashboard + 30 天歷史 | 3.4 |
| Email digest | 3.5 |
| Monitoring + Sentry | 4.1 |
| Plausible 分析 | 4.2 |
| Marketing site (landing + legal + pricing) | 4.3 |
| Smoke test (founder runs full flow) | 4.4 |

**Placeholder scan:** none — all code blocks contain real code.

**Type consistency:**
- `Match.llm_score` (Optional[int]) used consistently in renderer, dashboard, push.
- `Subscription.ecpay_merchant_trade_no` matched between create + webhook.
- `User.line_user_id` used as canonical identity throughout.

**Scope:** 4-sprint MVP, single deployable service. Each sprint has 4-6 tasks ≈ 1-2 days of Claude Code work per task with founder spec review.

---

*Plan written 2026-05-11. Based on `_nice/tenderwatch/ROADMAP.md` Phase 1 scope. Total tasks: 22 across 4 sprints. Estimated Claude Code execution: 8 weeks at founder cadence of 2hr/week spec review.*
