# Deployment Guide — Railway (Recommended for Portfolio Project)

Railway is the easiest path: free tier, Postgres included, automatic deploys from GitHub.

## 1. Prepare your repository

Push the project to a GitHub repo:

```bash
git init
git add .
git commit -m "initial commit"
gh repo create portfolio-analyst --private --push
```

## 2. Create a Railway project

1. Go to [railway.app](https://railway.app) and log in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Select your `portfolio-analyst` repo

## 3. Add services

Railway auto-detects Docker. You'll create **3 services**:

### Database
- Click **Add Service → Database → PostgreSQL**
- Railway gives you a `DATABASE_URL` env var automatically

### Backend
- Click **Add Service → GitHub Repo**
- Set **Root Directory** to `/backend`
- Railway detects the Dockerfile automatically

### Frontend
- Click **Add Service → GitHub Repo**
- Set **Root Directory** to `/frontend`

## 4. Set environment variables

In each service's **Variables** tab, add:

### Backend variables
```
ANTHROPIC_API_KEY=sk-ant-...
POLYGON_API_KEY=...
NEWS_API_KEY=...
LANGSMITH_API_KEY=...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=portfolio-analyst
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
ENVIRONMENT=production
CORS_ORIGINS=https://your-frontend.railway.app
```

### Frontend variables
```
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
```

## 5. Run database migrations

In the Railway shell for the backend service:

```bash
# The init.sql runs automatically on first boot via pgvector/pgvector image
# If you need to re-run manually:
psql $DATABASE_URL -f /docker-entrypoint-initdb.d/init.sql
```

## 6. Enable custom domain (optional)

Each Railway service gets a free `.railway.app` domain.
For a custom domain, go to **Settings → Domains**.

---

## Alternative: Render

Similar to Railway. Use `render.yaml` (ask Claude to generate one) for infrastructure-as-code.

---

## Estimated Railway costs

| Tier | Cost | Limits |
|------|------|--------|
| Hobby (free) | $0 | 500 CPU-hours/month, 100 GB egress |
| Pro | $20/month | Unlimited hours, team features |

For a portfolio project shown to hiring managers, the free tier is more than enough.
