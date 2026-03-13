"""
resale_pricer/core.py
---------------------
Platform-agnostic pricing analysis engine.
Works with Depop, Grailed, Poshmark, or any resale platform
as long as data matches the standard schema.

Standard schema columns:
  platform, listing_id, title, category, brand, condition,
  listed_price, sold_price, date_listed, date_sold, status
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ── Platform configs ──────────────────────────────────────────────────────────
# Each platform has different velocity norms and pricing dynamics.
# These thresholds were calibrated from observed sell-through patterns.

PLATFORM_CONFIG = {
    "depop": {
        "fast_sell_days": 7,       # days-to-sell considered "fast"
        "slow_sell_days": 21,      # days-to-sell that triggers reprice alert
        "price_drop_pct": 0.10,    # suggested drop when repricing
        "velocity_window_days": 30, # lookback for category velocity calc
        "notes": "Trend-driven; velocity matters more than brand. "
                 "Categories move fast when aesthetic is peaking."
    },
    "grailed": {
        "fast_sell_days": 10,
        "slow_sell_days": 30,
        "price_drop_pct": 0.08,
        "velocity_window_days": 45,
        "notes": "Brand/condition drives price ceiling. "
                 "Buyers research comps heavily — percentile positioning is critical."
    },
    "poshmark": {
        "fast_sell_days": 7,
        "slow_sell_days": 21,
        "price_drop_pct": 0.12,
        "velocity_window_days": 30,
        "notes": "Offer culture compresses final sale price ~10-15% below listed. "
                 "Days-to-sell improves sharply after first price drop or relisting."
    },
}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_listings(filepath: str) -> pd.DataFrame:
    """Load and clean a listings CSV into the standard schema."""
    df = pd.read_csv(filepath, parse_dates=["date_listed", "date_sold"])
    df.columns = df.columns.str.strip().str.lower()

    # Compute days_to_sell for sold items
    sold = df["status"] == "sold"
    df.loc[sold, "days_to_sell"] = (
        df.loc[sold, "date_sold"] - df.loc[sold, "date_listed"]
    ).dt.days

    # Days listed so far for active items
    today = pd.Timestamp(datetime.today().date())
    active = df["status"] == "active"
    df.loc[active, "days_active"] = (today - df.loc[active, "date_listed"]).dt.days

    # Price retention (what % of asking price you got)
    df["price_retention"] = df["sold_price"] / df["listed_price"]

    return df


# ── Category analytics ────────────────────────────────────────────────────────

def category_benchmarks(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each category, compute:
      - median / p25 / p75 days-to-sell
      - median / p25 / p75 sold price
      - sell-through rate
      - avg price retention
    """
    sold = df[df["status"] == "sold"].copy()

    benchmarks = sold.groupby("category").agg(
        listings_sold=("listing_id", "count"),
        days_to_sell_p25=("days_to_sell", lambda x: x.quantile(0.25)),
        days_to_sell_median=("days_to_sell", "median"),
        days_to_sell_p75=("days_to_sell", lambda x: x.quantile(0.75)),
        sold_price_p25=("sold_price", lambda x: x.quantile(0.25)),
        sold_price_median=("sold_price", "median"),
        sold_price_p75=("sold_price", lambda x: x.quantile(0.75)),
        avg_price_retention=("price_retention", "mean"),
    ).reset_index()

    # Sell-through rate = sold / total listed per category
    total_per_cat = df.groupby("category")["listing_id"].count().reset_index()
    total_per_cat.columns = ["category", "total_listed"]
    benchmarks = benchmarks.merge(total_per_cat, on="category")
    benchmarks["sell_through_rate"] = (
        benchmarks["listings_sold"] / benchmarks["total_listed"]
    )

    # Category velocity: sold listings in last N days / total
    benchmarks["category_velocity"] = (
        benchmarks["listings_sold"] / benchmarks["days_to_sell_median"]
    ).round(3)

    return benchmarks.round(2)


# ── Reprice signals ───────────────────────────────────────────────────────────

def reprice_alerts(df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """
    For active listings, flag which ones need attention and why.

    Returns a DataFrame of active listings with:
      - days_active
      - category benchmark (median days-to-sell for that category)
      - price percentile vs sold comps in same category
      - recommended action: REPRICE / RELIST / HOLD
      - suggested_price
    """
    config = PLATFORM_CONFIG.get(platform, PLATFORM_CONFIG["depop"])
    benchmarks = category_benchmarks(df)
    sold = df[df["status"] == "sold"].copy()
    active = df[df["status"] == "active"].copy()

    if active.empty:
        return pd.DataFrame(columns=["listing_id", "title", "action", "reason"])

    # Merge benchmark data onto active listings
    active = active.merge(
        benchmarks[["category", "days_to_sell_median", "sold_price_p25",
                     "sold_price_median", "sold_price_p75"]],
        on="category",
        how="left"
    )

    # Price percentile: where does this listing's price sit vs sold comps?
    def price_percentile(row):
        cat_sold = sold[sold["category"] == row["category"]]["sold_price"]
        if cat_sold.empty:
            return np.nan
        return round((cat_sold < row["listed_price"]).mean() * 100, 1)

    active["price_percentile"] = active.apply(price_percentile, axis=1)

    # Recommended action logic
    def recommend(row):
        days = row.get("days_active", 0) or 0
        pct = row.get("price_percentile", 50) or 50
        slow_threshold = config["slow_sell_days"]
        drop = config["price_drop_pct"]

        if days < config["fast_sell_days"]:
            return pd.Series({
                "action": "HOLD",
                "reason": f"Only {int(days)}d listed — too early to act",
                "suggested_price": row["listed_price"]
            })
        elif days >= slow_threshold * 2 and pct > 50:
            suggested = round(row["listed_price"] * (1 - drop * 2), 0)
            return pd.Series({
                "action": "RELIST",
                "reason": f"{int(days)}d listed, price above median — "
                          f"relist at ${suggested} to reset algo exposure",
                "suggested_price": suggested
            })
        elif days >= slow_threshold and pct > 60:
            suggested = round(row["listed_price"] * (1 - drop), 0)
            return pd.Series({
                "action": "REPRICE",
                "reason": f"{int(days)}d listed, in top {100-int(pct)}% of prices "
                          f"— drop to ${suggested}",
                "suggested_price": suggested
            })
        else:
            return pd.Series({
                "action": "HOLD",
                "reason": f"{int(days)}d listed, price is competitive",
                "suggested_price": row["listed_price"]
            })

    recommendations = active.apply(recommend, axis=1)
    active = pd.concat([active, recommendations], axis=1)

    cols = [
        "listing_id", "title", "category", "listed_price",
        "days_active", "days_to_sell_median", "price_percentile",
        "action", "reason", "suggested_price"
    ]
    return active[[c for c in cols if c in active.columns]]


# ── Cross-platform comparison ─────────────────────────────────────────────────

def platform_comparison(dataframes: dict) -> pd.DataFrame:
    """
    Given a dict of {platform_name: dataframe}, return a summary
    comparing key metrics across platforms.

    dataframes = {
        "depop": depop_df,
        "grailed": grailed_df,
        "poshmark": poshmark_df,
    }
    """
    rows = []
    for platform, df in dataframes.items():
        sold = df[df["status"] == "sold"]
        total = len(df)
        n_sold = len(sold)

        rows.append({
            "platform": platform,
            "total_listings": total,
            "sold_listings": n_sold,
            "sell_through_rate": round(n_sold / total, 2) if total > 0 else 0,
            "median_days_to_sell": round(sold["days_to_sell"].median(), 1) if n_sold > 0 else None,
            "median_sold_price": round(sold["sold_price"].median(), 2) if n_sold > 0 else None,
            "avg_price_retention": round(sold["price_retention"].mean(), 3) if n_sold > 0 else None,
            "fastest_category": (
                sold.groupby("category")["days_to_sell"].median().idxmin()
                if n_sold > 0 else None
            ),
            "slowest_category": (
                sold.groupby("category")["days_to_sell"].median().idxmax()
                if n_sold > 0 else None
            ),
        })

    return pd.DataFrame(rows).set_index("platform")


# ── Iteration tracking ────────────────────────────────────────────────────────

def before_after_summary(df_before: pd.DataFrame, df_after: pd.DataFrame,
                          label_before="Before", label_after="After") -> pd.DataFrame:
    """
    Compare two time-sliced DataFrames to measure tool impact.
    Used to generate the before/after numbers for your resume.
    """
    def metrics(df):
        sold = df[df["status"] == "sold"]
        total = len(df)
        n_sold = len(sold)
        return {
            "period": None,
            "total_listings": total,
            "sold_listings": n_sold,
            "sell_through_rate": f"{round(n_sold/total*100, 1)}%" if total else "N/A",
            "median_days_to_sell": round(sold["days_to_sell"].median(), 1) if n_sold else None,
            "avg_price_retention": f"{round(sold['price_retention'].mean()*100, 1)}%" if n_sold else "N/A",
        }

    before = metrics(df_before)
    after = metrics(df_after)
    before["period"] = label_before
    after["period"] = label_after

    return pd.DataFrame([before, after]).set_index("period")
