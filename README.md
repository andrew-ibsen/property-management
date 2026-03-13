# Property Management

Interactive rental operations dashboard for Airbnb + VRBO calendars.

## Includes
- Merged booking feed pipeline (`scripts/build_rental_ops.py`)
- Interactive dashboard with scrollable monthly Gantt (`scripts/build_rental_dashboard.py`)
- Cleaning cost model (15,000 ISK per changeover)
- Monthly cleaner payout summaries

## Run

```powershell
python scripts/build_rental_ops.py
python scripts/build_rental_dashboard.py
```

Dashboard output:
- `rental-ops/dashboard.html`
