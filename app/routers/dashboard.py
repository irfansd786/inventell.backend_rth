from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services import dashboard_service as svc

router = APIRouter(prefix='/dashboard', tags=['dashboard'])


@router.get('/summary')
def summary(range: str = '7d', db: Session = Depends(get_db), _user=Depends(get_current_user)):
    if range not in ('today', '7d', '30d'):
        range = '7d'
    return svc.get_summary(db, range_key=range)


@router.get('/revenue')
def revenue(range: str = '7d', metric: str = 'revenue', db: Session = Depends(get_db), _user=Depends(get_current_user)):
    if range not in ('today', '7d', '30d'):
        range = '7d'
    if metric not in ('revenue', 'orders', 'units'):
        metric = 'revenue'
    return svc.get_revenue_series(db, range_key=range, metric=metric)


@router.get('/sales-intelligence')
def sales_intelligence(range: str = '7d', db: Session = Depends(get_db), _user=Depends(get_current_user)):
    if range not in ('today', '7d', '30d'):
        range = '7d'
    return svc.get_sales_intelligence(db, range_key=range)


@router.get('/store-intelligence')
def store_intelligence(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.get_store_intelligence(db)


@router.get('/inventory-health')
def inventory_health(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.get_inventory_health(db)


@router.get('/risks')
def risks(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.get_risks(db)


@router.get('/ai-insights')
def ai_insights(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return {'items': svc.get_ai_insights(db)}


@router.get('/operations')
def operations(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.get_operations(db)
