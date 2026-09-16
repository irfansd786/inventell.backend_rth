"""Risk & alert read-models."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.risk import Risk


def list_risks(db: Session, status: str | None = None, severity: str | None = None, limit: int = 50):
    q = db.query(Risk).order_by(Risk.created_at.desc())
    if status:
        q = q.filter(Risk.status == status)
    if severity:
        q = q.filter(Risk.severity == severity)
    return q.limit(limit).all()


def resolve_risk(db: Session, risk: Risk, note: str = '') -> Risk:
    risk.status = 'resolved'
    if note:
        risk.description = f'{risk.description}\nResolution: {note}'.strip()
    db.commit()
    db.refresh(risk)
    return risk


def risk_summary(db: Session) -> dict:
    rows = dict(
        db.query(Risk.severity, func.count(Risk.id))
        .filter(Risk.status == 'active')
        .group_by(Risk.severity)
        .all()
    )
    return {
        'critical': int(rows.get('CRITICAL', 0)),
        'high': int(rows.get('HIGH', 0)),
        'medium': int(rows.get('MEDIUM', 0)),
        'low': int(rows.get('LOW', 0)),
    }


def list_alerts(db: Session, limit: int = 20):
    return db.query(Alert).order_by(Alert.created_at.desc()).limit(limit).all()
