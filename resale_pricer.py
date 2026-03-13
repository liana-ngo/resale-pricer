# resale_pricer.py
# ----------------
# Built this because Depop gives you zero feedback on whether your listings
# are priced competitively or just sitting for the wrong reasons.
#
# I sell mostly women's Y2K / early 2000s pieces like tops, bottoms, dresses,
# accessories. Categories move at very different speeds and I had no systematic
# way to know which listings to reprice vs relist vs leave alone.
#
# v1: flagged listings by revenue potential (wrong metric)
# v2: switched core output to days-to-sell after talking to other sellers -
#     nobody I interviewed was optimizing for revenue per item, they wanted turnover
# v3: split reprice vs relist into separate actions — they do different things
#     algorithmically. A stale listing needs a relist to reset visibility,
#     not just a price drop.
#
# Data: 564 sold listings from my own shop, Jul 2020 – Mar 2026


# ── Cell 1: Imports ───────────────────────────────────────────────────────────
# !pip install pandas numpy matplotlib  # uncomment if running in Colab

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings("ignore")

# Colab users: uncomment and update FILE_PATH below
# from google.colab import drive
# drive.mount('/content/drive')

print("libraries loaded")


# ── Cell 2: Config ────────────────────────────────────────────────────────────

PLATFORM = "depop"
FILE_PATH = "data/depop_full_alltime.csv"  # swap in your own CSV path

# Thresholds calibrated from my own 177-listing sold history.
# Depop slow threshold: 21 days — that's roughly where I noticed listings
# drop off in visibility. 59% of my listings sold within 7 days, so anything
# past 21 is genuinely stalling, not just taking a little longer.
#
# drop_pct: 10% suggested reduction on reprice. Based on what I observed —
# a $2–3 drop on a $20–25 item tends to be enough to move it.
# Grailed buyers research more carefully so less aggressive drop needed.
# Poshmark buyers almost always offer below listed so you need more room.

PLATFORM_CONFIG = {
    "depop": {
        "slow_days": 21,
        "fast_days": 7,
        "drop_pct": 0.10,
        "notes": "48% of listings sell within 7 days — past 21d is a real stall"
    },
    "grailed": {
        "slow_days": 30,
        "fast_days": 10,
        "drop_pct": 0.08,
        "notes": "Smaller buyer pool, more deliberate — longer cycles are normal"
    },
    "poshmark": {
        "slow_days": 21,
        "fast_days": 7,
        "drop_pct": 0.12,
        "notes": "Offer culture compresses final price ~10-15% — need room to accept"
    },
}

config = PLATFORM_CONFIG[PLATFORM]
print(f"platform: {PLATFORM} | slow threshold: {config['slow_days']}d | {config['notes']}")


# ── Cell 3: Load data ─────────────────────────────────────────────────────────

df = pd.read_csv(FILE_PATH, parse_dates=["date_listed", "date_sold"])
df.columns = df.columns.str.strip().str.lower()

# days_to_sell for sold items
sold_mask = df["status"] == "sold"
df.loc[sold_mask, "days_to_sell"] = (
    df.loc[sold_mask, "date_sold"] - df.loc[sold_mask, "date_listed"]
).dt.days

# days_active for active listings
today = pd.Timestamp("today").normalize()
active_mask = df["status"] == "active"
df.loc[active_mask, "days_active"] = (
    today - df.loc[active_mask, "date_listed"]
).dt.days

# price retention: what fraction of listed price you actually got
# note: Depop's export doesn't separate listed vs sold price, so this
# is 1.0 across the board in this dataset — would need manual logging
# of original listed prices to make this meaningful
df["price_retention"] = df["sold_price"] / df["listed_price"]

sold_df = df[df["status"] == "sold"].copy()
active_df = df[df["status"] == "active"].copy()

print(f"{len(df)} total | {len(sold_df)} sold | {len(active_df)} active")
print(df[["title", "category", "listed_price", "status", "days_to_sell"]].head(8).to_string())


# ── Cell 4: Top-line summary ──────────────────────────────────────────────────
# Real numbers from my shop Jul 2020 – Mar 2026

total = len(df)
n_sold = len(sold_df)
sell_through = n_sold / total
median_days = sold_df["days_to_sell"].median()
mean_days = sold_df["days_to_sell"].mean()

print(f"\n{'='*45}")
print(f"  DEPOP SHOP SUMMARY (Jul 2020 – Mar 2026)")
print(f"{'='*45}")
print(f"  Total sold items:       {n_sold}")
print(f"  Sell-through rate:      {sell_through:.0%}")
print(f"  Median days to sell:    {median_days:.0f} days")
print(f"  Mean days to sell:      {mean_days:.1f} days")
print(f"  Sold within 7 days:     {(sold_df['days_to_sell'] <= 7).sum()} ({(sold_df['days_to_sell'] <= 7).mean():.0%})")
print(f"  Stalled 21+ days:       {(sold_df['days_to_sell'] >= 21).sum()} ({(sold_df['days_to_sell'] >= 21).mean():.0%})")
print(f"  Total revenue:          ${sold_df['sold_price'].sum():.0f}")
print(f"{'='*45}")


# ── Cell 5: Category benchmarks ───────────────────────────────────────────────
# Core reference table. I use category-level comps rather than brand-level
# because with ~564 sold items across many brands, filtering by brand produces
# comp sets that are too small for the percentiles to be reliable.
# Category is coarser but more statistically sound at this scale.
#
# Full-history category medians:
#   accessories: 3d   |  swimwear: 6d   |  footwear: 7d
#   bottoms: 7d       |  tops: 10d      |  outerwear: 16d
#   dresses: 18d

benchmarks = sold_df.groupby("category").agg(
    n_sold=("listing_id", "count"),
    days_p25=("days_to_sell", lambda x: x.quantile(0.25)),
    days_median=("days_to_sell", "median"),
    days_p75=("days_to_sell", lambda x: x.quantile(0.75)),
    price_p25=("sold_price", lambda x: x.quantile(0.25)),
    price_median=("sold_price", "median"),
    price_p75=("sold_price", lambda x: x.quantile(0.75)),
).reset_index().round(1)

cat_totals = df.groupby("category").size().reset_index(name="total")
benchmarks = benchmarks.merge(cat_totals, on="category")
benchmarks["sell_through"] = (benchmarks["n_sold"] / benchmarks["total"]).round(2)

print("\nCATEGORY BENCHMARKS (from real sold data)")
print(benchmarks[[
    "category", "n_sold", "days_median", "days_p75",
    "price_median", "sell_through"
]].sort_values("days_median").to_string(index=False))


# ── Cell 6: Charts ────────────────────────────────────────────────────────────

fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.suptitle("Depop shop — category performance (Jul 2020 – Mar 2026)",
             fontsize=12, y=1.01)

# color by speed vs my actual thresholds
cats = benchmarks.sort_values("days_median")
bar_colors = [
    "#27ae60" if d <= config["fast_days"] else
    "#e74c3c" if d >= config["slow_days"] else
    "#f39c12"
    for d in cats["days_median"]
]

axes[0].barh(cats["category"], cats["days_median"], color=bar_colors, alpha=0.8)
axes[0].axvline(config["slow_days"], color="#e74c3c", linestyle="--",
                linewidth=1.2, label=f"slow threshold ({config['slow_days']}d)")
axes[0].axvline(config["fast_days"], color="#27ae60", linestyle="--",
                linewidth=1.2, label=f"fast threshold ({config['fast_days']}d)")
axes[0].set_xlabel("median days to sell")
axes[0].set_title("days to sell by category")
axes[0].legend(fontsize=8)

# price distribution by category
cats_price = benchmarks.sort_values("price_median", ascending=False)
axes[1].barh(cats_price["category"], cats_price["price_median"],
             color="#3498db", alpha=0.75, label="median sold price")
axes[1].barh(cats_price["category"], cats_price["price_p75"],
             color="#3498db", alpha=0.25, label="p75 sold price")
axes[1].set_xlabel("sold price ($)")
axes[1].set_title("sold price by category")
axes[1].legend(fontsize=8)

plt.tight_layout()
plt.savefig("category_performance.png", dpi=150, bbox_inches="tight")
plt.show()
print("saved category_performance.png")


# ── Cell 7: Price positioning for active listings ─────────────────────────────
# For each active listing: where does its price sit vs sold comps?
#
# price_pct = 80 → your listing is priced higher than 80% of things
# that sold in that category. Not automatically bad — but combined with
# high days_active it's a reliable signal to reprice.
#
# Limitation: because Depop's export only gives sold price (not original
# listed price), the comp pool here is sold prices only. If you want to
# compare against currently active listings on Depop you'd need to
# manually log a sample of live comps.

def price_percentile(listed_price, category, sold_data):
    comps = sold_data[sold_data["category"] == category]["sold_price"]
    if len(comps) < 3:  # don't compute percentile on tiny comp sets
        return None
    return round((comps < listed_price).mean() * 100, 1)

if not active_df.empty:
    active_df = active_df.copy()
    active_df["price_pct"] = active_df.apply(
        lambda r: price_percentile(r["listed_price"], r["category"], sold_df), axis=1
    )
    active_df = active_df.merge(
        benchmarks[["category", "days_median"]].rename(
            columns={"days_median": "cat_days_median"}
        ),
        on="category", how="left"
    )
    print("\nACTIVE LISTINGS — price vs sold comps")
    print(active_df[[
        "title", "category", "listed_price", "days_active", "price_pct"
    ]].to_string(index=False))
    print("\nprice_pct = % of sold comps in same category cheaper than your listing")
else:
    print("\nno active listings in this dataset — add your current listings with status='active'")


# ── Cell 8: Reprice alerts ────────────────────────────────────────────────────
# The main output. Run this weekly against your current active listings.
#
# REPRICE vs RELIST distinction:
# REPRICE — listing still has visibility, price is the blocker
# RELIST  — listing has gone stale algorithmically. The platform has stopped
#           surfacing it. Dropping price alone won't fix this. Delete and
#           relist to reset exposure, then price it correctly.
#
# Trigger logic:
#   RELIST:  days_active >= 42 (2x slow threshold) AND price above median
#   REPRICE: days_active >= 21 AND price in top 40% for category
#   HOLD:    everything else

def get_action(row, config):
    days = row.get("days_active") or 0
    pct  = row.get("price_pct") or 50
    drop = config["drop_pct"]
    slow = config["slow_days"]
    fast = config["fast_days"]

    if days < fast:
        return "HOLD", f"only {int(days)}d listed — too early", row["listed_price"]
    elif days >= slow * 2 and pct > 50:
        suggested = round(row["listed_price"] * (1 - drop * 2), 0)
        return "RELIST", f"{int(days)}d + above median — relist at ${suggested}", suggested
    elif days >= slow and pct > 60:
        suggested = round(row["listed_price"] * (1 - drop), 0)
        return "REPRICE", f"{int(days)}d + top {100 - int(pct)}% — drop to ${suggested}", suggested
    else:
        return "HOLD", f"{int(days)}d, price looks competitive", row["listed_price"]

if not active_df.empty:
    actions = active_df.apply(
        lambda r: pd.Series(
            get_action(r, config),
            index=["action", "reason", "suggested_price"]
        ), axis=1
    )
    alerts = pd.concat([
        active_df[["listing_id", "title", "category",
                   "listed_price", "days_active", "price_pct"]],
        actions
    ], axis=1)

    print(f"\n{'='*55}")
    print("  REPRICE ALERTS")
    print(f"{'='*55}")
    for _, row in alerts.iterrows():
        icon = ("🔴" if row["action"] == "RELIST"
                else "🟡" if row["action"] == "REPRICE"
                else "🟢")
        print(f"\n  {icon} {row['action']} — {row['title']}")
        print(f"     {row['reason']}")

    print()
    print(alerts[[
        "title", "action", "listed_price", "suggested_price", "days_active"
    ]].to_string(index=False))
else:
    print("add active listings to your CSV to see reprice alerts")


# ── Cell 9: Slow listings deep dive ──────────────────────────────────────────
# Look at listings that stalled 21+ days in the sold history.
# Before applying repricing logic consistently (pre-July 2024), 39% of
# listings stalled. After, that dropped to 15%. These are the cases
# the tool is built to catch.

slow = sold_df[sold_df["days_to_sell"] >= 21].copy()
print(f"\nSLOW LISTINGS ANALYSIS (21+ days to sell)")
print(f"Total: {len(slow)} listings ({len(slow)/len(sold_df):.0%} of sold history)\n")

print("By category:")
print(slow.groupby("category").agg(
    count=("listing_id", "count"),
    median_days=("days_to_sell", "median"),
    median_price=("listed_price", "median")
).sort_values("count", ascending=False).to_string())

print("\nWorst offenders (longest to sell):")
print(slow.nlargest(8, "days_to_sell")[[
    "title", "category", "listed_price", "days_to_sell"
]].to_string(index=False))


# ── Cell 10: Sales velocity over time ─────────────────────────────────────────
# Monthly sales volume — shows the Jul 2024 inflection when repricing
# logic was applied consistently. Stall rate drops visibly from that point.

sold_df_copy = sold_df.copy()
sold_df_copy["month"] = pd.to_datetime(sold_df_copy["date_sold"]).dt.to_period("M")
monthly = sold_df_copy.groupby("month").agg(
    sales=("listing_id", "count"),
    revenue=("sold_price", "sum"),
    median_days=("days_to_sell", "median")
).reset_index()
monthly["month_str"] = monthly["month"].astype(str)

fig, ax1 = plt.subplots(figsize=(12, 4))
ax2 = ax1.twinx()

bars = ax1.bar(monthly["month_str"], monthly["sales"],
               color="#3498db", alpha=0.7, label="items sold")
ax2.plot(monthly["month_str"], monthly["median_days"],
         color="#e74c3c", marker="o", linewidth=2,
         markersize=5, label="median days to sell")

ax1.set_xlabel("month")
ax1.set_ylabel("items sold", color="#3498db")
ax2.set_ylabel("median days to sell", color="#e74c3c")
ax1.tick_params(axis="x", rotation=45)
ax1.set_title("monthly sales volume vs days to sell")

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc="upper left")

plt.tight_layout()
plt.savefig("sales_velocity.png", dpi=150, bbox_inches="tight")
plt.show()
print("saved sales_velocity.png")


# ── Cell 11: Cross-platform (uncomment when you have Grailed/Poshmark data) ───
# The interesting finding here won't be the numbers — it'll be what drives
# the differences. Grailed buyers research more carefully, longer cycles.
# Poshmark offer culture means price retention is structurally lower.

# platforms = {
#     "depop":    "data/sample/depop_listings.csv",
#     "grailed":  "data/sample/grailed_listings.csv",
#     "poshmark": "data/sample/poshmark_listings.csv",
# }
# dfs = {}
# for name, path in platforms.items():
#     d = pd.read_csv(path, parse_dates=["date_listed", "date_sold"])
#     d.columns = d.columns.str.strip().str.lower()
#     m = d["status"] == "sold"
#     d.loc[m, "days_to_sell"] = (
#         d.loc[m, "date_sold"] - d.loc[m, "date_listed"]
#     ).dt.days
#     d["price_retention"] = d["sold_price"] / d["listed_price"]
#     dfs[name] = d
#
# rows = []
# for pname, pdf in dfs.items():
#     s = pdf[pdf["status"] == "sold"]
#     rows.append({
#         "platform":            pname,
#         "sell_through":        f"{len(s)/len(pdf):.0%}",
#         "median_days_sell":    round(s["days_to_sell"].median(), 1),
#         "avg_price_retention": f"{s['price_retention'].mean():.1%}",
#         "fastest_category":    s.groupby("category")["days_to_sell"].median().idxmin(),
#         "slowest_category":    s.groupby("category")["days_to_sell"].median().idxmax(),
#     })
# print(pd.DataFrame(rows).set_index("platform").to_string())

print("\ndone — see reprice alerts in cell 8")
