from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.services import analytics_service as analytics
from app.services import dashboard_service as dashboard
from app.services import sales_service as sales

router = APIRouter(prefix='/reports', tags=['reports'])


@router.get('/daily')
def daily(db: Session = Depends(get_db), _user=Depends(require_permission('report_center'))):
    return {
        'summary': dashboard.get_summary(db),
        'sales': sales.get_summary(db),
        'hourly': analytics.hourly_sales_today(db),
    }


@router.get('/inventory-turnover')
def turnover(db: Session = Depends(get_db), _user=Depends(require_permission('report_center'))):
    return analytics.inventory_turnover(db)
