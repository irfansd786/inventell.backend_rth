from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    DATABASE_URL: str = 'postgresql+psycopg2://postgres:postgres@localhost:5432/invintell'
    SECRET_KEY: str = 'change-me-to-a-long-random-secret'
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_URL: str = 'https://inventell-rth.vercel.app'

    @property
    def cors_origins(self) -> list[str]:
        origins = set()
        if self.FRONTEND_URL:
            for item in self.FRONTEND_URL.split(','):
                cleaned = item.strip().rstrip('/')
                if cleaned:
                    origins.add(cleaned)
        default_origins = [
            'https://inventell-rth.vercel.app',
            'http://localhost:5173',
            'http://127.0.0.1:5173',
            'http://localhost:3000',
            'http://localhost:8000',
            'http://127.0.0.1:8000',
            'https://inventell-backend-rth.onrender.com',
        ]
        for orig in default_origins:
            origins.add(orig.rstrip('/'))
        return list(origins)


    # ---- Store Monitor person-only detection ----
    # COCO PERSON class id; only this class may ever reach the tracker.
    PERSON_CLASS_ID: int = 0
    # Minimum YOLO person confidence. Configurable so false positives can be
    # tuned without code changes (recommended initial value 0.40).
    PERSON_CONFIDENCE_THRESHOLD: float = 0.40
    # YOLO NMS IoU threshold. Lower keeps grouped/occluded people as separate
    # boxes instead of merging them into one detection (recommended 0.50).
    YOLO_NMS_IOU: float = 0.50
    # YOLO weights path for PersonDetector.
    YOLO_MODEL_PATH: str = 'yolov8n.pt'
    # When true, the CV pipeline logs per-frame detection/filter/track stats.
    DEBUG_DETECTION: bool = False


settings = Settings()
