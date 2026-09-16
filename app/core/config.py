from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    DATABASE_URL: str = 'postgresql+psycopg2://postgres:postgres@localhost:5432/invintell'
    SECRET_KEY: str = 'change-me-to-a-long-random-secret'
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    FRONTEND_URL: str = 'https://inventell-rth.vercel.app'

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
