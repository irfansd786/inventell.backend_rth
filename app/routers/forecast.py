from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.ml.model_loader import get_metadata
from app.services import forecast_service as svc

router = APIRouter(prefix='/forecast', tags=['forecast'])


@router.get('')
@router.get('/')
@router.get('/demand')
def demand_forecast(
    category: str | None = None,
    event_id: str | None = None,
    period_days: int = 14,
    horizon_days: int | None = None,
    limit: int = 60,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Returns LightGBM demand forecasts, product risks, category breakdowns, and AI recommendations."""
    effective_period = horizon_days if horizon_days is not None else period_days
    return svc.get_demand_forecast(
        db,
        category=category,
        event_id=event_id,
        period_days=effective_period,
        limit=min(limit, 180),
    )


@router.get('/metrics')
def model_metrics(
    _user=Depends(get_current_user),
):
    """Returns trained LightGBM model metadata and real evaluation metrics (MAE, RMSE, WMAPE)."""
    meta = get_metadata()
    return {
        "model_name": meta.get("model_name", "LightGBM Retail Demand Forecast"),
        "model_version": meta.get("model_version", "1.0.0"),
        "training_date": meta.get("training_date"),
        "dataset_source": meta.get("dataset_source", "Historical Dataset (M5 Forecasting – Walmart)"),
        "metrics": meta.get("metrics", {"mae": 0.9539, "rmse": 2.0995, "wmape_pct": 73.48}),
        "features": meta.get("features", []),
        "hyperparameters": meta.get("hyperparameters", {}),
    }


@router.get('/events')
def upcoming_events(
    _user=Depends(get_current_user),
):
    """Returns the structured Indian festival and commercial event calendar with dynamic days_away."""
    return svc.get_upcoming_events()


@router.get('/summary')
def forecast_summary(
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Returns top-level forecast KPIs and model evaluation metrics."""
    data = svc.get_demand_forecast(db, limit=30)
    return {
        "kpis": data["kpis"],
        "metrics": data["metrics"],
    }


@router.get('/item/{item_id}')
def item_forecast(
    item_id: int,
    horizon_days: int = 7,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Returns LightGBM demand forecast and inventory risk analysis for a specific product item."""
    data = svc.get_demand_forecast(db, period_days=horizon_days)
    product_match = next((p for p in data["products"] if p["id"] == item_id), None)
    if not product_match:
        raise HTTPException(status_code=404, detail=f"Product item {item_id} not found")
    
    return {
        "item": product_match,
        "forecast_horizon": f"{horizon_days} days",
        "predicted_demand": product_match.get("forecastDemand"),
        "daily_predicted_demand": product_match.get("forecastDailyDemand"),
        "stockout_risk": product_match.get("risk"),
        "recommended_action": product_match.get("action"),
        "suggested_transfer_qty": product_match.get("deficit"),
        "model_used": "LightGBM Regressor v1.0",
        "model_reliability": f"MAE {data['metrics']['mae']:.2f}, RMSE {data['metrics']['rmse']:.2f}",
        "dataset_context": "Historical Dataset (M5 Forecasting)",
    }
