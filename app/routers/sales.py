from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services import sales_service as svc

router = APIRouter(prefix='/sales', tags=['sales'])


@router.get('')
def list_sales(limit: int = 50, offset: int = 0, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.list_sales(db, limit=min(limit, 200), offset=offset)


@router.get('/today')
def today(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.get_today(db)


@router.get('/summary')
def summary(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.get_summary(db)


@router.get('/revenue')
def revenue(range: str = '7d', db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.get_revenue(db, range if range in ('today', '7d', '30d') else '7d')


@router.get('/top-products')
def top_products(limit: int = 5, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.get_top_products(db, min(limit, 20))


@router.get('/categories')
def categories(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    return svc.get_categories(db)


@router.get('/performance')
def performance(
    range: str = '7d',
    start_date: str | None = None,
    end_date: str | None = None,
    product_id: int | None = None,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    return svc.get_sales_performance(
        db,
        range_key=range,
        start_date=start_date,
        end_date=end_date,
        product_id=product_id,
    )


@router.post('/import')
def import_sales(payload: dict, db: Session = Depends(get_db), _user=Depends(get_current_user)):
    records = payload.get('records', [])
    return svc.import_sales_records(db, records)

