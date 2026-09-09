# Project Workspace (React + FastAPI)

Fullstack monorepo featuring a React single-page application and a FastAPI backend.

```
.
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/v1/          # Modular API endpoints & routers
│   │   │   └── endpoints/   # Health check & custom route handlers
│   │   ├── core/            # Configuration & settings
│   │   └── main.py          # Application entry point & CORS
│   ├── .env.example
│   ├── requirements.txt
│   └── pyproject.toml
│
├── frontend/                 # React Application
│   ├── src/
│   │   ├── services/api.ts  # Preconfigured API client
│   │   ├── App.tsx          # Main dashboard & status checker
│   │   └── index.css        # Tailwind CSS styling
│   ├── .env.example
│   ├── package.json
│   └── vite.config.ts
│
└── README.md
```

---

## Getting Started

### 1. Run Backend (FastAPI)

In a terminal, navigate to `backend/`:

```bash
cd backend

# Activate virtual environment
source .venv/bin/activate

# (Optional) If setting up on a fresh machine:
# uv venv .venv && source .venv/bin/activate && uv pip install -r requirements.txt

# Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check Endpoint**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

### 2. Run Frontend (React + Vite)

In a separate terminal, navigate to `frontend/`:

```bash
cd frontend

# Install dependencies (already installed initially)
npm install

# Start development server
npm run dev
```

- **Frontend App**: [http://localhost:5173](http://localhost:5173)

---

## Verification & Testing

- **Build Frontend**:
  ```bash
  cd frontend && npm run build
  ```

- **Test Backend Import**:
  ```bash
  cd backend && .venv/bin/python -c "from app.main import app; print('Backend OK!')"
  ```
