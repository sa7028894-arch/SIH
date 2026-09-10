import json
import os
from pathlib import Path
from typing import List, Union
from dotenv import load_dotenv

# Ensure .env in backend directory or parent directories is resolved
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
load_dotenv()

class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "FastAPI Backend")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "t")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Sarvam AI Document AI Configurations
    SARVAM_API_KEY: str = os.getenv("SARVAM_API_KEY", "")
    SARVAM_BASE_URL: str = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")
    SARVAM_POLL_INTERVAL: float = float(os.getenv("SARVAM_POLL_INTERVAL", "1.0"))
    SARVAM_TIMEOUT_SECONDS: int = int(os.getenv("SARVAM_TIMEOUT_SECONDS", "45"))

    # Face Recognition Configurations
    FACE_MATCH_THRESHOLD: float = float(os.getenv("FACE_MATCH_THRESHOLD", "1.10"))
    WEIGHTS_DIR: str = os.getenv("WEIGHTS_DIR", str(Path(__file__).resolve().parent.parent / "models" / "weights"))

    @property
    def BACKEND_CORS_ORIGINS(self) -> List[str]:
        raw_origins = os.getenv("BACKEND_CORS_ORIGINS", "")
        if not raw_origins:
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        try:
            parsed = json.loads(raw_origins)
            if isinstance(parsed, list):
                return parsed
            return [str(parsed)]
        except json.JSONDecodeError:
            return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

settings = Settings()
