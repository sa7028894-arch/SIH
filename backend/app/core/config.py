import json
import os
from typing import List, Union
from dotenv import load_dotenv

load_dotenv()

class Settings:
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "FastAPI Backend")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api/v1")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "t")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

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
