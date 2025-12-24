# Railway Web App Architecture - DPC Enrichment V2

## 🎯 Objective

Transform the CLI enrichment system into a **web application** hosted on Railway that allows users to:
- Start enrichment from a web UI
- Monitor progress in real-time
- Pause/resume enrichment
- View results and statistics
- Manage API keys securely
- Access from anywhere

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Railway Platform                         │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────┐     │
│  │   Web UI     │   │  REST API    │   │  Background    │     │
│  │  (Flask +    │◄─►│  (Flask)     │◄─►│  Worker        │     │
│  │   Tailwind)  │   │              │   │  (Celery)      │     │
│  └──────────────┘   └──────────────┘   └────────────────┘     │
│         │                  │                     │              │
│         │                  │                     │              │
│         ▼                  ▼                     ▼              │
│  ┌──────────────────────────────────────────────────────┐     │
│  │            PostgreSQL Database                        │     │
│  │  - Progress tracking                                  │     │
│  │  - Practice data                                      │     │
│  │  - Enrichment results                                 │     │
│  │  - User sessions                                      │     │
│  └──────────────────────────────────────────────────────┘     │
│         │                                                       │
│         ▼                                                       │
│  ┌──────────────┐                                              │
│  │  Redis       │   (Task queue + caching)                     │
│  └──────────────┘                                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
         │
         │  External APIs
         ▼
┌──────────────────────────────────┐
│  • OpenRouter (Gemini AI)        │
│  • ScraperAPI (Web Scraping)     │
└──────────────────────────────────┘
```

---

## 📦 Tech Stack

### Backend
- **Web Framework**: Flask (lightweight, simple, perfect for Railway)
- **Background Jobs**: Celery + Redis
- **Database**: PostgreSQL (Railway's managed database)
- **ORM**: SQLAlchemy
- **Auth**: Flask-Login (simple session-based auth)
- **API**: Flask-RESTX (Swagger documentation)

### Frontend
- **UI**: Jinja2 templates + Tailwind CSS
- **Real-time Updates**: Server-Sent Events (SSE) or WebSockets
- **Charts**: Chart.js for progress visualization
- **AJAX**: Fetch API for async operations

### Infrastructure (Railway)
- **Web Service**: Flask app (main web server)
- **Worker Service**: Celery worker (background enrichment)
- **Database**: PostgreSQL addon
- **Cache/Queue**: Redis addon
- **File Storage**: Railway volumes (for markdown files)

---

## 🗂️ Database Schema

### `practices` table
```sql
CREATE TABLE practices (
    id SERIAL PRIMARY KEY,
    practice_id VARCHAR(100) UNIQUE NOT NULL,
    practice_name VARCHAR(500),
    website_url TEXT,
    address_street VARCHAR(500),
    address_city VARCHAR(200),
    address_state VARCHAR(10),
    address_zip VARCHAR(20),
    phone VARCHAR(50),
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    enrichment_status VARCHAR(50),  -- pending, in_progress, completed, failed, skipped
    enriched_at TIMESTAMP,
    data JSONB,  -- Full enriched data
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_practices_status ON practices(enrichment_status);
CREATE INDEX idx_practices_practice_id ON practices(practice_id);
```

### `enrichment_runs` table
```sql
CREATE TABLE enrichment_runs (
    id SERIAL PRIMARY KEY,
    status VARCHAR(50),  -- pending, running, paused, completed, failed
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_practices INTEGER,
    successful INTEGER DEFAULT 0,
    failed INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    total_cost DECIMAL(10, 4) DEFAULT 0,
    total_time INTEGER,  -- seconds
    config JSONB,  -- Run configuration (workers, limit, etc.)
    statistics JSONB,  -- Runtime statistics
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### `api_status` table
```sql
CREATE TABLE api_status (
    id SERIAL PRIMARY KEY,
    api_name VARCHAR(100) NOT NULL,  -- OpenRouter, ScraperAPI
    status VARCHAR(50),  -- active, paused, budget_exceeded, rate_limited
    last_error TEXT,
    paused_at TIMESTAMP,
    resumed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### `users` table (simple auth)
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(500) NOT NULL,
    email VARCHAR(200),
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 🌐 REST API Endpoints

### Enrichment Control
```
POST   /api/enrichment/start      - Start enrichment run
POST   /api/enrichment/pause      - Pause running enrichment
POST   /api/enrichment/resume     - Resume paused enrichment
POST   /api/enrichment/stop       - Stop enrichment
GET    /api/enrichment/status     - Get current status
```

### Progress & Stats
```
GET    /api/enrichment/progress   - Real-time progress (SSE)
GET    /api/enrichment/stats      - Statistics summary
GET    /api/enrichment/runs       - List all runs
GET    /api/enrichment/runs/:id   - Get specific run details
```

### Practices
```
GET    /api/practices             - List practices (paginated)
GET    /api/practices/:id         - Get practice details
GET    /api/practices/export      - Export enriched data (JSON)
```

### API Management
```
GET    /api/status                - Check API status (OpenRouter, ScraperAPI)
POST   /api/status/refresh        - Refresh API keys
GET    /api/costs                 - Get cost estimates
```

### Authentication
```
POST   /api/auth/login            - Login
POST   /api/auth/logout           - Logout
GET    /api/auth/user             - Get current user
```

---

## 🎨 Web UI Pages

### 1. Dashboard (`/`)
- Overview statistics
- Current enrichment status
- Start/Pause/Resume buttons
- Real-time progress bar
- Cost tracker
- API status indicators

### 2. Progress Monitor (`/progress`)
- Live progress feed
- Practice-by-practice updates
- Error log
- Performance metrics
- Cost tracking
- Time estimates

### 3. Practices List (`/practices`)
- Searchable/filterable table
- Status filters (completed, failed, pending)
- Export button
- View practice details (modal)

### 4. API Settings (`/settings`)
- API key management (masked)
- Test API connections
- View current quotas/limits
- Cost thresholds/alerts

### 5. Runs History (`/runs`)
- List of all enrichment runs
- Statistics per run
- Logs and errors
- Comparison between runs

---

## 🔧 Celery Task Structure

### Background Tasks

**`tasks/enrichment_task.py`**
```python
@celery.task(bind=True)
def run_enrichment(self, run_id, limit=None):
    """
    Main enrichment task
    - Updates progress in database
    - Handles API pause/resume
    - Sends real-time updates via Redis
    """
    # Initialize orchestrator (reuse existing code)
    orchestrator = EnrichmentOrchestrator(...)

    # Run with progress callback
    async def progress_callback(practice_id, status):
        # Update database
        update_practice_status(practice_id, status)
        # Publish to Redis for real-time updates
        publish_progress_update(run_id, practice_id, status)

    # Run enrichment
    result = await orchestrator.run(progress_callback=progress_callback)

    return result
```

**Other tasks:**
- `tasks/export_task.py` - Export enriched data
- `tasks/cleanup_task.py` - Clean old runs
- `tasks/test_apis_task.py` - Test API connections

---

## 🔄 Real-Time Progress Updates

### Server-Sent Events (SSE)
```python
@app.route('/api/enrichment/progress/stream')
def progress_stream():
    """Stream real-time progress updates"""
    def generate():
        pubsub = redis_client.pubsub()
        pubsub.subscribe('enrichment_progress')

        for message in pubsub.listen():
            if message['type'] == 'message':
                yield f"data: {message['data']}\n\n"

    return Response(generate(), mimetype='text/event-stream')
```

### Frontend (JavaScript)
```javascript
const eventSource = new EventSource('/api/enrichment/progress/stream');

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateProgressBar(data.completed, data.total);
    addLogEntry(data.practice_name, data.status);
};
```

---

## 🚀 Railway Deployment

### File Structure for Railway
```
railway-app/
├── Procfile                    # Process definitions
├── railway.toml                # Railway config
├── requirements.txt            # Python dependencies
├── runtime.txt                 # Python version
│
├── app/
│   ├── __init__.py             # Flask app factory
│   ├── routes/
│   │   ├── main.py             # Dashboard routes
│   │   ├── api.py              # API endpoints
│   │   └── auth.py             # Auth routes
│   │
│   ├── models/
│   │   ├── practice.py         # SQLAlchemy models
│   │   ├── enrichment_run.py
│   │   └── user.py
│   │
│   ├── tasks/
│   │   ├── celery_app.py       # Celery config
│   │   └── enrichment_task.py  # Background tasks
│   │
│   ├── templates/              # Jinja2 templates
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── progress.html
│   │   └── ...
│   │
│   ├── static/                 # CSS, JS, images
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   │
│   └── services/               # Business logic
│       ├── enrichment_service.py
│       └── api_service.py
│
├── src/enrichment_v2/          # Existing enrichment code
│   └── ... (all existing modules)
│
└── config/
    ├── development.py
    ├── production.py
    └── railway.py
```

### `Procfile`
```
web: gunicorn app:create_app()
worker: celery -A app.tasks.celery_app worker --loglevel=info
```

### `railway.toml`
```toml
[build]
builder = "NIXPACKS"
buildCommand = "pip install -r requirements.txt && playwright install chromium"

[deploy]
startCommand = "gunicorn app:create_app()"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

### Environment Variables (Railway)
```
DATABASE_URL=postgresql://...  # Auto-provided by Railway
REDIS_URL=redis://...          # Auto-provided by Railway
OPENROUTER_API_KEY=...         # User sets
SCRAPERAPI_KEY=...             # User sets
FLASK_SECRET_KEY=...           # Random key for sessions
FLASK_ENV=production
```

---

## 🔐 Security Considerations

1. **Authentication**: Flask-Login for session management
2. **API Keys**: Stored in environment variables (Railway dashboard)
3. **CSRF Protection**: Flask-WTF for forms
4. **Rate Limiting**: Flask-Limiter on API endpoints
5. **Input Validation**: Marshmallow schemas
6. **SQL Injection**: SQLAlchemy ORM (parameterized queries)
7. **XSS Protection**: Jinja2 auto-escaping

---

## 📊 Monitoring & Logging

- **Application Logs**: Railway logs dashboard
- **Database Monitoring**: Railway PostgreSQL metrics
- **Cost Tracking**: Store in database, display on dashboard
- **Error Tracking**: Log to database + Railway logs
- **Performance**: Track enrichment speed, API response times

---

## 🎯 Implementation Phases

### Phase 1: Basic Web UI (Week 1)
- [x] Flask app setup
- [ ] PostgreSQL database schema
- [ ] Basic dashboard UI
- [ ] Start/stop enrichment
- [ ] Simple progress display

### Phase 2: Background Processing (Week 2)
- [ ] Celery worker setup
- [ ] Task queue integration
- [ ] Real-time progress updates (SSE)
- [ ] API pause/resume handling

### Phase 3: Full Features (Week 3)
- [ ] Practice list/search
- [ ] Export functionality
- [ ] API settings management
- [ ] Run history
- [ ] Authentication

### Phase 4: Railway Deployment (Week 4)
- [ ] Railway configuration
- [ ] PostgreSQL addon
- [ ] Redis addon
- [ ] Environment variable setup
- [ ] Testing & optimization

---

## 💰 Cost Estimates (Railway)

### Monthly Costs
- **Hobby Plan**: $5/month (limited resources)
- **Pro Plan**: $20/month (recommended)
  - Web service: 2 vCPU, 2 GB RAM
  - Worker service: 2 vCPU, 2 GB RAM
  - PostgreSQL: 1 GB storage
  - Redis: 256 MB

**Total**: ~$20-30/month for Railway hosting + API costs for enrichment

---

## 🔄 Migration from CLI

The existing CLI code will be **reused** as much as possible:
- `src/enrichment_v2/` - All existing modules work as-is
- `orchestrator.py` - Add database callbacks
- `config.py` - Adapt for database config
- Progress tracking - Switch from JSON files to PostgreSQL

**No major rewrites needed!** Just wrap existing functionality in web/API layer.

---

## 🎉 Benefits of Web App

1. **Accessible Anywhere** - No local setup needed
2. **Team Collaboration** - Multiple users can monitor
3. **Always Running** - No need to keep computer on
4. **Better Monitoring** - Real-time dashboards
5. **Scheduled Runs** - Auto-start enrichment
6. **Data Persistence** - PostgreSQL instead of JSON files
7. **Scalable** - Add more workers as needed

---

**Next Steps**: Start implementing Phase 1 (Basic Web UI)
