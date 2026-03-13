# resale-pricer

Python/pandas tool that surfaces reprice and relist recommendations for Depop, Grailed, and Poshmark sellers. Built because none of these platforms give you a feedback loop between your pricing decisions and what actually sells.

Works by comparing active listings against your own sold history — calculating where each listing sits in the price distribution for its category, and flagging listings that have been up too long relative to how fast that category typically moves.

---

## Why I built this

I sell on Depop and had no way to know whether a listing was stalling because the price was wrong or for some other reason. The platform shows sold prices if you search manually, but there's no systematic way to compare your active inventory against recent comps in your own category.

Before writing any code I talked to 4 other active sellers. The main thing I learned: nobody was optimizing for revenue per item. Everyone cared about turnover — list it, move it, reinvest in new inventory. That changed the core output of the tool. V1 flagged listings where you were leaving money on the table. V2 switched to flagging listings that were stalling relative to how that category typically moves, which is what actually mattered.

---

## What it does

**Category benchmarks** — for each category in your sold history, computes p25/median/p75 for days-to-sell and sold price. This is the reference table everything else is built on.

**Price percentile positioning** — for each active listing, calculates where your price sits relative to sold comps in the same category. A score of 80 means you're priced higher than 80% of things that sold in that category.

**Reprice alerts** — the main weekly output. Flags active listings as:
- `HOLD` — listed recently or price is competitive
- `REPRICE` — past the slow threshold and priced above the 60th percentile. Suggests a specific price.
- `RELIST` — listing has been up so long a price drop alone won't fix it. The platform has deprioritized it algorithmically. Relist to reset exposure, then price correctly.

**Slow listings analysis** — breakdown of what stalled in your sold history, by category. Useful for identifying which categories need tighter pricing discipline.

**Sales velocity chart** — monthly sales volume vs median days-to-sell over time.

---

## How comparable listings are defined

A comp is any sold listing in the same `category`. I considered filtering by brand and condition but with a typical seller's inventory size, over-filtering produces comp sets too small for the percentiles to be meaningful. Category-level is coarser but more statistically reliable at this scale.

---

## Reprice vs relist — why they're different

**Reprice**: the listing still has algorithmic visibility, price is the blocker. A price drop fixes it.

**Relist**: the listing has gone stale. The platform has stopped surfacing it in search and feeds. Dropping the price on a dead listing doesn't help because buyers aren't seeing it. Delete and relist to reset that exposure, then price it correctly on the new listing.

Trigger: `days_active >= 2x slow_threshold AND price above median`.

---

## Platform calibration

**Depop** — slow threshold: 21 days, suggested drop: 10%.
Calibrated from my own sold history: 48% of listings sold within 7 days. Past 21 days is a genuine stall, not just slow movement. After applying the repricing logic consistently, stall rate dropped from 39% to 15%.

The config values for Grailed and Poshmark are set based on how those platforms work (see `PLATFORM_CONFIG` in both files), but I only have Depop data. The thresholds are reasonable starting points — treat them as priors to tune once you have your own history on those platforms.

---

## Roadmap

- Grailed and Poshmark data to validate and refine those platform configs
- Price retention tracking (requires manually logging original listed price alongside sold price, since Depop's export doesn't include it)
- Cross-platform comparison once multi-platform data exists

---

## My shop data (Jul 2020 – Mar 2026)

564 sold listings across tops, bottoms, dresses, accessories, swimwear, footwear, and outerwear.

| Category | Median days to sell | Median sold price |
|---|---|---|
| Accessories | 3 days | $11 |
| Swimwear | 6 days | $5 |
| Footwear | 7 days | $22 |
| Bottoms | 7 days | $18 |
| Tops | 10 days | $13 |
| Outerwear | 16 days | $24 |
| Dresses | 18 days | $16 |

Overall: median 8 days to sell, 48% of listings sold within 7 days, 30% stalled past 21 days before the repricing logic was applied consistently.

---

## Before/after

I started applying the repricing logic consistently around July 2024. The signal in the data is clear: before that point, stall rates were high and erratic. The shift shows up in both the stall rate and fast-sell rate.

| Metric | Before (Jul 2020 – Jun 2024) | After (Jul 2024 – present) |
|---|---|---|
| Items sold | 359 | 205 |
| Median days to sell | 11 days | 5 days |
| Sold within 7 days | 43% | 59% |
| Stalled 21+ days | 39% | 15% |
| Stuck 42+ days (relist territory) | 29% | 7% |

Note: the volume increase from 2024 onward also reflects listing more actively, not just better pricing. The days-to-sell and stall rate changes are the cleaner signal.

---

## Limitations

Depop's sales export gives sold price but not original listed price. This means price retention (listed to sold) can't be calculated from the export alone — you'd need to manually log original listed prices. The days-to-sell analysis and category benchmarks are fully functional. Price percentile for active listings compares against sold prices, which is still a useful signal.

---

## Setup

```bash
git clone https://github.com/liana-ngo/resale-pricer
cd resale-pricer
pip install pandas numpy matplotlib
```

Or open `resale_pricer.py` directly in Google Colab.

---

## Data format

```
platform, listing_id, title, category, brand, condition,
listed_price, sold_price, date_listed, date_sold, status
```

Export your sales history from your platform's seller dashboard and format to match. Dates should be `YYYY-MM-DD`. Status is `sold` or `active`.

Data is in `data/depop_full_alltime.csv` — complete selling history (Jul 2020 – Mar 2026, 583 listings). To use with your own shop, export your sales history and format to match.

---

## Usage

```python
# Set these two lines in Cell 2, then run all cells top to bottom
PLATFORM = "depop"   # or "grailed" / "poshmark"
FILE_PATH = "data/depop_full_alltime.csv" 
```

Add your current active listings to the CSV with `status = active` to get reprice alerts.

---

## Versions

**v1** — revenue-focused. Flagged listings priced below category median (wrong frame).
**v2** — switched core output to days-to-sell after user interviews showed that's what sellers actually optimize for.
**v3** — split reprice and relist into separate actions after finding that relisting outperforms price drops on stale listings.
