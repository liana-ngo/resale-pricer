Sample output from resale_pricer.py running on real Depop sales data (564 sold listings, Jul 2020 – Mar 2026).

category_benchmarks.csv — p25/median/p75 days-to-sell and sold price for each category, plus sell-through rate. This is the reference table all reprice recommendations are built on.

category_performance.png — bar charts of median days-to-sell and median sold price by category, color-coded against the fast/slow thresholds.

reprice_alerts.csv — the main weekly output. Each active listing flagged as HOLD, REPRICE, or RELIST with a suggested price and reason.

sales_velocity.png — monthly sales volume vs median days-to-sell over time. The Jul 2024 inflection point where stall rate dropped from 39% to 15% is visible here.
