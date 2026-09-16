"""
Inventory Risk & Replenishment Decision Engine.

Consumes:
- LightGBM Predicted Demand (1-day, 7-day, 30-day)
- Current Store Stock
- Warehouse Stock Availability
- Safety Stock Configuration (15% buffer)

Calculates:
- Stock Coverage (days)
- Projected Ending Inventory
- Stockout Risk Tier (HIGH, MEDIUM, LOW, CRITICAL)
- Replenishment Order Quantity (calculated dynamically)
- Overstock Risk
- Slow-Moving Inventory Risk
- Priority & Actionable Recommendation
"""

import math


def evaluate_inventory_risk(
    product_id: int | str,
    product_name: str,
    category: str,
    current_store_stock: int,
    warehouse_stock: int,
    predicted_7d_demand: float,
    daily_sales_avg: float,
    unit_price: float = 15.0,
    reorder_level: int = 15,
) -> dict:
    """Evaluates inventory risk and computes actionable replenishment recommendations."""
    predicted_7d_demand = max(0.0, float(predicted_7d_demand))
    daily_demand = max(0.01, predicted_7d_demand / 7.0)

    # Calculate stock coverage in days
    stock_coverage_days = round(current_store_stock / daily_demand, 1)

    # Target stock required for 7 days + 15% safety stock buffer
    safety_buffer = 1.15
    required_stock = math.ceil(predicted_7d_demand * safety_buffer)

    # Dynamic calculation of deficit (replenishment quantity)
    raw_deficit = required_stock - current_store_stock
    suggested_transfer_qty = max(0, min(raw_deficit, warehouse_stock))

    # Calculate risk tiers and recommendations using explicit business logic
    if daily_sales_avg == 0.0 and current_store_stock == 0:
        risk_level = "Insufficient Data"
        priority = "Low"
        action = "Review Data"
        reason = "No historical sales transactions or store stock recorded."
        overstock_risk = False
        slow_moving_risk = False
        stockout_risk = False
    elif stock_coverage_days < 3.0 or (current_store_stock < predicted_7d_demand and suggested_transfer_qty > 0):
        stockout_risk = True
        overstock_risk = False
        slow_moving_risk = False
        
        if stock_coverage_days < 2.0 or current_store_stock <= 5:
            risk_level = "High"
            priority = "Critical"
        else:
            risk_level = "High"
            priority = "High"

        action = "Replenish"
        reason = (
            f"Predicted 7-day demand ({predicted_7d_demand:.0f} units) exceeds store stock ({current_store_stock} units). "
            f"Stock coverage is only {stock_coverage_days} days. "
            f"Recommended transfer of {suggested_transfer_qty} units from central warehouse."
        )
    elif stock_coverage_days < 7.0:
        stockout_risk = False
        overstock_risk = False
        slow_moving_risk = False
        risk_level = "Medium"
        priority = "Medium"
        action = "Monitor Stock"
        reason = f"Inventory covers {stock_coverage_days} days of demand. Monitor sales checkout velocity."
    elif stock_coverage_days > 45.0 and current_store_stock > 40:
        stockout_risk = False
        overstock_risk = True
        slow_moving_risk = stock_coverage_days > 60.0
        risk_level = "Low"
        priority = "Medium"
        action = "Promote Product"
        reason = f"High stock coverage ({stock_coverage_days} days) with low forecast velocity. Recommend promotional bundle."
    else:
        stockout_risk = False
        overstock_risk = False
        slow_moving_risk = False
        risk_level = "Low"
        priority = "Low"
        action = "Maintain Stock"
        reason = f"Stock level ({current_store_stock} units) aligns with predicted 7-day demand."

    return {
        "product_id": product_id,
        "product_name": product_name,
        "category": category,
        "current_stock": current_store_stock,
        "warehouse_stock": warehouse_stock,
        "predicted_7d_demand": round(predicted_7d_demand, 1),
        "daily_demand": round(daily_demand, 1),
        "stock_coverage_days": stock_coverage_days,
        "required_stock": required_stock,
        "suggested_transfer_qty": suggested_transfer_qty,
        "stockout_risk": stockout_risk,
        "overstock_risk": overstock_risk,
        "slow_moving_risk": slow_moving_risk,
        "risk_level": risk_level,
        "priority": priority,
        "recommended_action": action,
        "recommendation_reason": reason,
    }
