"""
Feature engineering module for M5 Retail Demand Forecasting.

Extracts retail features:
- Product, Department, Category, Store identifiers
- Date, Day of Week, Month, Year, Weekend Flag
- Calendar Events & SNAP Flags
- Sell Price & Relative Price Changes
- Lag Sales (1, 7, 14, 28 days)
- Rolling Sales Means (7, 14, 28 days)
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd


def load_raw_datasets(data_dir: str | Path):
    """Load raw CSV files from M5 dataset directory."""
    data_dir = Path(data_dir)
    m5_dir = data_dir / "raw" / "m5"
    if not m5_dir.exists():
        # Fallback search
        m5_dir = data_dir / "m5"

    cal_path = m5_dir / "calendar.csv"
    prices_path = m5_dir / "sell_prices.csv"
    
    sales_path = m5_dir / "sales_train_evaluation.csv"
    if not sales_path.exists():
        sales_path = m5_dir / "sales_train_validation.csv"

    if not cal_path.exists() or not sales_path.exists():
        raise FileNotFoundError(f"M5 dataset files not found in {m5_dir}")

    calendar_df = pd.read_csv(cal_path)
    prices_df = pd.read_csv(prices_path) if prices_path.exists() else None
    sales_df = pd.read_csv(sales_path)

    return sales_df, calendar_df, prices_df


def build_forecasting_features(
    sales_df: pd.DataFrame,
    calendar_df: pd.DataFrame,
    prices_df: pd.DataFrame | None = None,
    max_days: int = 365,
    sample_items: int = 1500,
) -> pd.DataFrame:
    """Build tabular feature matrix from raw M5 time-series data."""
    # Filter item sample for efficient, representative training across categories
    if len(sales_df) > sample_items:
        # Stratified sample by cat_id
        sampled_sales = (
            sales_df.groupby("cat_id", group_keys=False)
            .apply(lambda x: x.sample(min(len(x), sample_items // 3), random_state=42))
            .reset_index(drop=True)
        )
    else:
        sampled_sales = sales_df.copy()

    # Determine day columns to melt (e.g. d_1549 .. d_1913 for last 365 days)
    day_cols = [c for c in sales_df.columns if c.startswith("d_")]
    if max_days and len(day_cols) > max_days:
        day_cols = day_cols[-max_days:]

    id_vars = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    id_vars = [c for c in id_vars if c in sampled_sales.columns]

    # Melt wide sales matrix to long format
    df_long = pd.melt(
        sampled_sales,
        id_vars=id_vars,
        value_vars=day_cols,
        var_name="d",
        value_name="sales",
    )

    # Convert d (e.g. 'd_1800') to integer
    df_long["d_num"] = df_long["d"].apply(lambda x: int(x.split("_")[1]))

    # Sort time series per item for lag & rolling calculations
    df_long.sort_values(by=["id", "d_num"], inplace=True)
    df_long.reset_index(drop=True, inplace=True)

    # Feature Engineering: Lags
    for lag in [1, 7, 14, 28]:
        df_long[f"lag_{lag}"] = df_long.groupby("id")["sales"].shift(lag)

    # Feature Engineering: Rolling Means
    for window in [7, 14, 28]:
        df_long[f"rolling_{window}"] = (
            df_long.groupby("id")["sales"]
            .transform(lambda x: x.shift(1).rolling(window=window, min_periods=1).mean())
        )

    # Merge Calendar Features
    calendar_cols = [
        "d", "date", "wm_yr_wk", "wday", "month", "year",
        "event_name_1", "event_type_1", "snap_CA", "snap_TX", "snap_WI"
    ]
    avail_cal_cols = [c for c in calendar_cols if c in calendar_df.columns]
    df_long = df_long.merge(calendar_df[avail_cal_cols], on="d", how="left")

    # Day of week and weekend features
    df_long["is_weekend"] = df_long["wday"].isin([1, 2]).astype(int)  # 1: Sat, 2: Sun in M5 calendar
    df_long["has_event"] = df_long["event_name_1"].notna().astype(int)

    # Merge Prices if available
    if prices_df is not None and "wm_yr_wk" in df_long.columns:
        df_long = df_long.merge(
            prices_df, on=["store_id", "item_id", "wm_yr_wk"], how="left"
        )
        if "sell_price" in df_long.columns:
            # Price change vs item mean
            item_avg_price = df_long.groupby("item_id")["sell_price"].transform("mean")
            df_long["price_diff"] = df_long["sell_price"] - item_avg_price
            df_long["sell_price"] = df_long["sell_price"].fillna(df_long["sell_price"].median())
            df_long["price_diff"] = df_long["price_diff"].fillna(0.0)

    # Drop rows with NaN in primary lag features due to shift
    df_long.dropna(subset=["lag_28"], inplace=True)
    df_long.reset_index(drop=True, inplace=True)

    # Convert categorical strings to category codes for LightGBM
    cat_columns = ["item_id", "dept_id", "cat_id", "store_id", "state_id", "event_type_1"]
    for col in cat_columns:
        if col in df_long.columns:
            df_long[col] = df_long[col].astype("category")

    return df_long
