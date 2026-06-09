# AI Portfolio Analyst

A conversational AI-powered portfolio analyst. Upload your Robinhood CSV and ask natural-language questions about your holdings — returns, risk exposure, sector breakdown, and more.

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 14, Tailwind CSS, Recharts, shadcn/ui |
| Backend | Python 3.11, FastAPI, LangChain |
| AI | Claude (Anthropic) with tool calling + RAG |
| Database | PostgreSQL + pgvector (via Docker) |
| Data | Polygon.io, yfinance, SEC EDGAR, NewsAPI |
| Infra | Docker, Railway/Render, GitHub Actions, LangSmith |

## Project Structure

```
portfolio-analyst/
├── backend/                 # FastAPI Python backend
│   ├── app/
│   │   ├── api/routes/      # API endpoints
│   │   ├── core/            # Config, settings
│   │   ├── models/          # Pydantic models
│   │   ├── services/        # Business logic
│   │   ├── tools/           # LLM agent tools
│   │   └── db/              # DB connection + queries
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Next.js frontend
│   ├── src/
│   │   ├── app/             # Next.js app router
│   │   ├── components/      # UI components
│   │   ├── lib/             # Utilities + API client
│   │   └── hooks/           # Custom React hooks
│   ├── package.json
│   └── Dockerfile
├── docker/
│   └── init.sql             # DB initialization
├── docker-compose.yml
└── .env.example
```

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Node.js 18+
- Python 3.11+
- API keys (see `.env.example`)

### 1. Clone and configure

```bash
git clone <your-repo>
cd portfolio-analyst
cp .env.example .env
# Fill in your API keys in .env
```

### 2. Start everything with Docker

```bash
docker-compose up --build
```

This starts:
- PostgreSQL + pgvector on port 5432
- FastAPI backend on port 8000
- Next.js frontend on port 3000

### 3. Open the app

Visit [http://localhost:3000](http://localhost:3000)

### 4. Upload your portfolio

1. Go to Robinhood → Account → Statements → Export CSV
2. Click "Upload Portfolio" in the app
3. Drag and drop your CSV

## API Keys Needed

| Key | Where to get | Cost |
|-----|-------------|------|
| `ANTHROPIC_API_KEY` | console.anthropic.com | ~$2–5/mo low usage |
| `POLYGON_API_KEY` | polygon.io | Free tier |
| `NEWS_API_KEY` | newsapi.org | Free tier |
| `LANGSMITH_API_KEY` | smith.langchain.com | Free tier |

## Development

### Backend only
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend only
```bash
cd frontend
npm install
npm run dev
```

## Deployment

See `docs/deployment.md` for Railway/Render deployment guide.
