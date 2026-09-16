from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.dataset_metadata import DatasetMetadata

router = APIRouter(prefix='/datasets', tags=['datasets'])


@router.get('')
def list_datasets(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    """Returns provenance, record counts, date ranges, and connection status of all datasets."""
    rows = db.query(DatasetMetadata).order_by(DatasetMetadata.id.asc()).all()
    return [
        {
            "id": r.id,
            "dataset_name": r.dataset_name,
            "source": r.source,
            "file_name": r.file_name,
            "date_range": r.date_range,
            "record_count": r.record_count,
            "status": r.status,
            "purpose": r.purpose,
            "description": r.description,
            "last_ingested_at": r.last_ingested_at.isoformat() if r.last_ingested_at else "",
        }
        for r in rows
    ]
