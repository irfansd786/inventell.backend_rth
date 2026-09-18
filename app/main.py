from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    alerts,
    allocation,
    analytics,
    auth,
    dashboard,
    datasets,
    dispatch,
    finance,
    forecast,
    inventory,
    orders,
    packing,
    picking,
    products,
    recommendations,
    reports,
    risks,
    sales,
    staff,
    store_monitor,
    suppliers,
    transfers,
    warehouse,
)
from app.routers.fulfillment import (
    allocation_router,
    dispatch_router,
    packing_router,
    picking_router,
)

app = FastAPI(title='INVINTELL Retail Intelligence API', version='1.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r'^https?://.*\.vercel\.app$|^https?://.*\.onrender\.com$|^https?://(localhost|127\.0\.0\.1)(:\d+)?$',
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/')
@app.head('/')
@app.get('/health')
@app.head('/health')
@app.get('/api/health')
@app.head('/api/health')
def health():
    return {'status': 'ok', 'service': 'INVINTELL Retail Intelligence API'}


app.include_router(auth.router, prefix='/api')
app.include_router(dashboard.router, prefix='/api')
app.include_router(analytics.router, prefix='/api')
app.include_router(forecast.router, prefix='/api')
app.include_router(recommendations.router, prefix='/api')
app.include_router(datasets.router, prefix='/api')
app.include_router(products.router, prefix='/api')
app.include_router(inventory.router, prefix='/api')
app.include_router(sales.router, prefix='/api')
app.include_router(orders.router, prefix='/api')
app.include_router(allocation_router, prefix='/api')
app.include_router(picking_router, prefix='/api')
app.include_router(packing_router, prefix='/api')
app.include_router(dispatch_router, prefix='/api')
app.include_router(finance.router, prefix='/api')
app.include_router(transfers.router, prefix='/api')
app.include_router(warehouse.router, prefix='/api')
app.include_router(suppliers.router, prefix='/api')
app.include_router(risks.router, prefix='/api')
app.include_router(alerts.router, prefix='/api')
app.include_router(reports.router, prefix='/api')
app.include_router(staff.router, prefix='/api')
app.include_router(store_monitor.router, prefix='/api')
