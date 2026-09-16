"""
LightGBM Demand Forecasting Training & Evaluation Pipeline.

Executes:
1. Dataset loading (M5 calendar, sales_train, sell_prices)
2. Feature engineering (lags, rolling means, date & price features)
3. Time-aware train/validation split (last 28 days for validation)
4. LightGBM model training
5. Model evaluation (MAE, RMSE, WMAPE)
6. Persistence of model artifact & metadata JSON
"""

import datetime
import json
from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error

from app.ml.features import build_forecasting_features, load_raw_datasets

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"


def calculate_wmape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Calculate Weighted Absolute Percentage Error (WMAPE)."""
    total_actual = np.sum(np.abs(y_true))
    if total_actual == 0:
        return 0.0
    return float(np.sum(np.abs(y_true - y_pred)) / total_actual * 100.0)


def train_lightgbm_model(
    max_days: int = 365,
    sample_items: int = 1500,
    n_estimators: int = 250,
):
    """Main training routine for LightGBM Demand Forecasting."""
    print("=" * 60)
    print("Starting INVINTELL LightGBM Demand Forecasting Training")
    print("=" * 60)
    print(f"Data directory: {DATA_DIR}")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load Datasets
    sales_df, calendar_df, prices_df = load_raw_datasets(DATA_DIR)
    print(f"Loaded raw datasets. Sales records: {len(sales_df)}")

    # 2. Feature Engineering
    print("Building retail forecasting features...")
    df_features = build_forecasting_features(
        sales_df=sales_df,
        calendar_df=calendar_df,
        prices_df=prices_df,
        max_days=max_days,
        sample_items=sample_items,
    )
    print(f"Feature matrix generated. Shape: {df_features.shape}")

    # Define feature set
    feature_cols = [
        "dept_id", "cat_id", "wday", "month", "year",
        "is_weekend", "has_event", "snap_CA", "snap_TX", "snap_WI",
        "lag_1", "lag_7", "lag_14", "lag_28",
        "rolling_7", "rolling_14", "rolling_28",
    ]
    if "sell_price" in df_features.columns:
        feature_cols.append("sell_price")
    if "price_diff" in df_features.columns:
        feature_cols.append("price_diff")

    feature_cols = [c for c in feature_cols if c in df_features.columns]
    target_col = "sales"

    # 3. Time-Aware Split (Last 28 days for validation - NEVER random)
    max_d_num = df_features["d_num"].max()
    val_cutoff = max_d_num - 28

    train_mask = df_features["d_num"] <= val_cutoff
    val_mask = df_features["d_num"] > val_cutoff

    X_train = df_features.loc[train_mask, feature_cols]
    y_train = df_features.loc[train_mask, target_col]

    X_val = df_features.loc[val_mask, feature_cols]
    y_val = df_features.loc[val_mask, target_col]

    print(f"Time-aware split: Train samples={len(X_train)} (d<={val_cutoff}), Val samples={len(X_val)} (d>{val_cutoff})")

    # 4. Train LightGBM Regressor
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=n_estimators,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
        n_jobs=-1,
        verbose=-1,
    )

    print("Training LightGBM Regressor model...")
    model.fit(
        X_train,
        y_train,
        eval_X=X_val,
        eval_y=y_val,
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
    )

    # 5. Model Evaluation
    y_pred = model.predict(X_val)
    y_pred = np.clip(y_pred, 0, None)  # Sales cannot be negative

    mae = float(mean_absolute_error(y_val, y_pred))
    rmse = float(root_mean_squared_error(y_val, y_pred))
    wmape = calculate_wmape(y_val.values, y_pred)

    print("\n" + "-" * 40)
    print("MODEL EVALUATION METRICS:")
    print(f"  - MAE (Mean Absolute Error):      {mae:.4f}")
    print(f"  - RMSE (Root Mean Squared Error):  {rmse:.4f}")
    print(f"  - WMAPE (Weighted Abs Pct Error): {wmape:.2f}%")
    print("-" * 40 + "\n")

    # 6. Save Model Artifact
    model_file = MODELS_DIR / "demand_forecasting.txt"
    model.booster_.save_model(str(model_file))
    print(f"Saved trained LightGBM model to: {model_file}")

    # 7. Save Model Metadata
    metadata = {
        "model_name": "LightGBM Retail Demand Forecast",
        "model_version": "1.0.0",
        "training_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dataset_source": "M5 Forecasting – Accuracy (Walmart Retail Sales)",
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "time_split_cutoff_day": int(val_cutoff),
        "features": feature_cols,
        "metrics": {
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "wmape_pct": round(wmape, 2),
        },
        "hyperparameters": {
            "n_estimators": n_estimators,
            "learning_rate": 0.05,
            "num_leaves": 31,
        },
    }

    meta_file = MODELS_DIR / "model_metadata.json"
    with open(meta_file, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved model metadata to: {meta_file}")

    # 8. Generate Product Forecast Cache for Instant App Serving
    build_product_forecast_cache(df_features, model, feature_cols)

    return metadata


def build_product_forecast_cache(df_features, model, feature_cols):
    """Generate 1-day, 7-day, 30-day demand forecasts for products to serve rapidly."""
    cache = {}

    max_d = df_features["d_num"].max()
    recent_df = df_features[df_features["d_num"] > (max_d - 28)]

    # Overall baseline daily sales mean and std
    overall_mean = float(recent_df["sales"].mean()) if not recent_df.empty else 1.5

    cache["generated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cache["overall_daily_mean"] = round(overall_mean, 2)
    cache["categories"] = {}

    if "cat_id" in recent_df.columns:
        cat_stats = recent_df.groupby("cat_id", observed=False)["sales"].agg(["mean", "std"]).to_dict("index")
        for cat_name, stats in cat_stats.items():
            base_daily = max(round(float(stats["mean"]), 2), 0.1) if pd.notna(stats["mean"]) else round(overall_mean, 2)
            cache["categories"][str(cat_name)] = {
                "daily_mean": base_daily,
                "forecast_1d": round(base_daily * 1.0, 1),
                "forecast_7d": round(base_daily * 7.0, 1),
                "forecast_30d": round(base_daily * 30.0, 1),
            }

    cache_file = MODELS_DIR / "forecast_cache.json"
    with open(cache_file, "w") as f:
        json.dump(cache, f, indent=2)
    print(f"Generated forecast cache at: {cache_file}")



if __name__ == "__main__":
    train_lightgbm_model()
