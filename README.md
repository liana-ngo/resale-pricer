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

See [sample output](screenshots/) for charts and alerts generated from real shop data (177 sold listings, Jan 2025 – Mar 2026).

---

## How comparable listings are defined

A comp is any sold listing in the same `category`. I considered filtering by brand and condition but with a typical seller's inventory size, over-filtering produces comp sets too small for the percentiles to be meaningful. In my own data, 78 of 177 sold listings were tagged "Other" brand — brand-level filtering would have been useless. Category-level is coarser but more statistically reliable at this scale.

---

## Reprice vs relist — why they're different

**Reprice**: the listing still has algorithmic visibility, price is the blocker. A price drop fixes it.

**Relist**: the listing has gone stale. The platform has stopped surfacing it in search and feeds. Dropping the price on a dead listing doesn't help because buyers aren't seeing it. Delete and relist to reset that exposure, then price it correctly on the new listing.

Trigger: `days_active >= 2x slow_threshold AND price above median`.

---

## Platform calibration

**Depop** — slow threshold: 21 days, suggested drop: 10%.
Based on my own 177-listing sold history: 59% of listings sold within 7 days, 77% within 14. Past 21 days is a genuine stall, not just slow movement.

**Grailed** — slow threshold: 30 days, suggested drop: 8%.
Smaller, more deliberate buyer pool. Longer sell cycles are normal even when priced correctly. Brand and condition anchor price more strongly than on Depop.

**Poshmark** — slow threshold: 21 days, suggested drop: 12%.
Offer culture compresses final sale price roughly 10–15% below listed. The higher drop suggestion accounts for this — you need to list with room to accept an offer.

---

## My shop data (Jan 2025 – Mar 2026)

177 sold listings across tops, bottoms, dresses, accessories, swimwear, footwear, and outerwear.

| Category | Median days to sell | Median sold price |
|---|---|---|
| Accessories | 2.5 days | $22 |
| Footwear | 3 days | $42 |
| Bottoms | 4 days | $11 |
| Tops | 6 days | $6 |
| Swimwear | 6 days | $5 |
| Dresses | 10 days | $8 |
| Outerwear | 15.5 days | $35 |

Overall: median 5 days to sell, 59% of listings sold within 7 days, 16% stalled past 21 days.

The 28 listings that stalled 21+ days are the cases this tool is built to catch going forward.

---

## Limitations

Depop's sales export gives sold price but not original listed price. This means price retention (listed → sold) can't be calculated from the export alone — you'd need to manually log original listed prices. The days-to-sell analysis and category benchmarks are fully functional. Price percentile for active listings compares against sold prices, which is still a useful signal.

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

Export your sales history from your platform's seller dashboard and format to match. Dates should be `YYYY-MM-DD`. Status is `sold` or `active`. Sample data for all three platforms is in `data/sample/`.

---

## Usage

```python
# Set these two lines in Cell 2, then run all cells top to bottom
PLATFORM = "depop"   # or "grailed" / "poshmark"
FILE_PATH = "data/sample/depop_listings.csv"
```

Add your current active listings to the CSV with `status = active` to get reprice alerts.

---

## Versions

**v1** — revenue-focused. Flagged listings priced below category median (wrong frame).  
**v2** — switched core output to days-to-sell after user interviews showed that's what sellers actually optimize for.  
**v3** — split reprice and relist into separate actions after finding that relisting outperforms price drops on stale listings.
