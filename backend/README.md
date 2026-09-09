# FastAPI Backend

FastAPI backend application with modular routing, environment settings, and CORS support.

## Setup Instructions

### 1. Activate Virtual Environment
```bash
# Using existing venv
source .venv/bin/activate
```

If you ever need to recreate the virtual environment:
```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 2. Environment Variables
Copy `.env.example` to `.env` if not already present:
```bash
cp .env.example .env
```

### 3. Run Development Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Or directly using Python:
```bash
python -m app.main
```

The server will be available at:
- API Base: `http://localhost:8000`
- Interactive Swagger Docs: `http://localhost:8000/docs`
- Redoc: `http://localhost:8000/redoc`
- Health Check: `http://localhost:8000/api/v1/health`
