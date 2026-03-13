import csv
import datetime as dt
import re
import urllib.request
from pathlib import Path

OUT_DIR = Path(r"C:/Users/Andrew/.openclaw/workspace/rental-ops")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCES = [
    {
        "property": "HFJ Uppi",
        "platform": "Airbnb",
        "url": "https://www.airbnb.com/calendar/ical/1283585732012152149.ics?s=e6ad39486a77ed21c8799e4faff58627&locale=en",
        "cleaner": "Darjia",
    },
    {
        "property": "HFJ Uppi",
        "platform": "VRBO",
        "url": "http://www.vrbo.com/icalendar/6d3751ffb7ec4463a4dc28e0ea5b5b2c.ics?nonTentative",
        "cleaner": "Darjia",
    },
    {
        "property": "HFJ Nidurri",
        "platform": "Airbnb",
        "url": "https://www.airbnb.com/calendar/ical/1547191095158517092.ics?s=ddf273d38253b4f173acb97846e65401&locale=en",
        "cleaner": "Darjia",
    },
    {
        "property": "HFJ Nidurri",
        "platform": "VRBO",
        "url": "http://www.vrbo.com/icalendar/2a5ca7a6d0c0466ba38f5644df5abac1.ics?nonTentative",
        "cleaner": "Darjia",
    },
    {
        "property": "RVK",
        "platform": "Airbnb",
        "url": "https://www.airbnb.com/calendar/ical/1283315904158961588.ics?s=49fa4a59267170a63d27b5854383425d&locale=en",
        "cleaner": "Jelena",
    },
    {
        "property": "RVK",
        "platform": "VRBO",
        "url": "http://www.vrbo.com/icalendar/bcffd44d28fd40948ded0d4fad0c14f4.ics?nonTentative",
        "cleaner": "Jelena",
    },
]


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def unfold_ics_lines(text: str):
    raw = text.replace("\r\n", "\n").split("\n")
    out = []
    for line in raw:
        if (line.startswith(" ") or line.startswith("\t")) and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def parse_dt(value: str):
    # Supports YYYYMMDD and YYYYMMDDTHHMMSSZ
    if re.fullmatch(r"\d{8}", value):
        return dt.datetime.strptime(value, "%Y%m%d").date()
    m = re.match(r"(\d{8})T", value)
    if m:
        return dt.datetime.strptime(m.group(1), "%Y%m%d").date()
    return None


def parse_ics(text: str, source_meta: dict):
    lines = unfold_ics_lines(text)
    events = []
    cur = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            cur = {}
            continue
        if line == "END:VEVENT":
            if cur:
                start = parse_dt(cur.get("DTSTART", ""))
                end = parse_dt(cur.get("DTEND", ""))
                if start and end and end > start:
                    summary = cur.get("SUMMARY", "").strip()
                    uid = cur.get("UID", "")
                    status = cur.get("STATUS", "CONFIRMED")
                    events.append({
                        "property": source_meta["property"],
                        "platform": source_meta["platform"],
                        "cleaner": source_meta["cleaner"],
                        "uid": uid,
                        "summary": summary,
                        "check_in": start,
                        "check_out": end,
                        "nights": (end - start).days,
                        "status": status,
                    })
            cur = None
            continue
        if cur is None:
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.split(";", 1)[0]
        if key in {"UID", "SUMMARY", "DTSTART", "DTEND", "STATUS"}:
            cur[key] = val
    return events


def dedupe(events):
    seen = set()
    out = []
    for e in sorted(events, key=lambda x: (x["property"], x["check_in"], x["check_out"], x["summary"])):
        k = (e["property"], e["check_in"], e["check_out"], e["summary"].lower())
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


def _is_blocked_or_empty(summary: str) -> bool:
    s = (summary or "").strip().lower()
    blocked_markers = [
        "not available",
        "airbnb (not available)",
        "blocked",
        "block",
        "unavailable",
    ]
    return any(m in s for m in blocked_markers)


def make_cleaning_rows(events):
    rows = []
    for e in events:
        # Do not create cleaner turnovers for blocked/empty holds
        if _is_blocked_or_empty(e.get("summary", "")):
            continue
        rows.append({
            "date": e["check_out"],
            "property": e["property"],
            "cleaner": e["cleaner"],
            "task": "Turnover Cleaning",
            "guest": e["summary"],
            "check_in": e["check_in"],
            "check_out": e["check_out"],
            "nights": e["nights"],
            "people": "",
            "cost_of_stay": "",
            "cleaning_cost_isk": 15000,
            "status": "Pending",
            "source": e["platform"],
        })
    return sorted(rows, key=lambda r: (r["date"], r["property"]))


def write_csv(path: Path, rows, headers):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            rr = dict(r)
            for k, v in rr.items():
                if isinstance(v, (dt.date, dt.datetime)):
                    rr[k] = v.isoformat()
            w.writerow(rr)


def monthly_cleaning_totals(cleaning_rows):
    totals = {}
    for r in cleaning_rows:
        month = str(r["date"])[:7]
        key = (month, r["property"], r["cleaner"])
        if key not in totals:
            totals[key] = {"month": month, "property": r["property"], "cleaner": r["cleaner"], "changeovers": 0, "total_cleaning_cost_isk": 0}
        totals[key]["changeovers"] += 1
        totals[key]["total_cleaning_cost_isk"] += int(r.get("cleaning_cost_isk", 0) or 0)
    return sorted(totals.values(), key=lambda x: (x["month"], x["property"], x["cleaner"]))


def monthly_cleaner_payouts(cleaning_rows):
    payouts = {}
    for r in cleaning_rows:
        month = str(r["date"])[:7]
        key = (month, r["cleaner"])
        if key not in payouts:
            payouts[key] = {"month": month, "cleaner": r["cleaner"], "changeovers": 0, "total_cleaning_cost_isk": 0}
        payouts[key]["changeovers"] += 1
        payouts[key]["total_cleaning_cost_isk"] += int(r.get("cleaning_cost_isk", 0) or 0)
    return sorted(payouts.values(), key=lambda x: (x["month"], x["cleaner"]))


def build_weekly_cleaner_message(cleaning_rows, today=None):
    if today is None:
        today = dt.date.today()
    week_end = today + dt.timedelta(days=6)
    upcoming = [r for r in cleaning_rows if today <= r["date"] <= week_end]

    lines = []
    lines.append(f"Cleaner Schedule ({today.isoformat()} to {week_end.isoformat()})")
    if not upcoming:
        lines.append("No turnovers this week.")
        return "\n".join(lines)

    by_cleaner = {}
    for r in upcoming:
        by_cleaner.setdefault(r["cleaner"], []).append(r)

    for cleaner in sorted(by_cleaner.keys()):
        rows = sorted(by_cleaner[cleaner], key=lambda x: (x["date"], x["property"]))
        total = sum(int(x.get("cleaning_cost_isk", 0) or 0) for x in rows)
        lines.append("")
        lines.append(f"{cleaner}:")
        for x in rows:
            lines.append(f"- {x['date']} | {x['property']} | checkout {x['check_out']} | {x['guest']} | {x['cleaning_cost_isk']} ISK")
        lines.append(f"Weekly total for {cleaner}: {total} ISK ({len(rows)} changeovers)")

    grand = sum(int(x.get("cleaning_cost_isk", 0) or 0) for x in upcoming)
    lines.append("")
    lines.append(f"All cleaners weekly total: {grand} ISK ({len(upcoming)} changeovers)")
    return "\n".join(lines)


def write_html_gantt(path: Path, cleaning_rows, monthly_totals):
    rows_html = []
    for r in cleaning_rows:
        rows_html.append(
            f"<tr><td>{r['date']}</td><td>{r['cleaner']}</td><td>{r['property']}</td><td>{r['task']}</td><td>{r['guest']}</td><td>{r['check_in']}</td><td>{r['check_out']}</td><td>{r['nights']}</td><td>{r['cleaning_cost_isk']}</td><td>{r['status']}</td></tr>"
        )

    monthly_html = []
    for m in monthly_totals:
        monthly_html.append(
            f"<tr><td>{m['month']}</td><td>{m['property']}</td><td>{m['cleaner']}</td><td>{m['changeovers']}</td><td>{m['total_cleaning_cost_isk']}</td></tr>"
        )

    html = f"""
<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<title>Cleaner Schedule (Gantt-style)</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 13px; }}
th {{ background: #f3f4f6; text-align: left; }}
tr:nth-child(even) {{ background: #fafafa; }}
</style>
</head>
<body>
<h2>Cleaner Schedule (Live Snapshot)</h2>
<p>Generated: {dt.datetime.now().isoformat(timespec='seconds')}</p>

<h3>Monthly Cleaning Totals</h3>
<table>
<thead><tr><th>Month</th><th>Property</th><th>Cleaner</th><th>Changeovers</th><th>Total Cleaning Cost (ISK)</th></tr></thead>
<tbody>
{''.join(monthly_html)}
</tbody>
</table>

<h3>Turnover Schedule</h3>
<table>
<thead><tr><th>Cleaning Date</th><th>Cleaner</th><th>Property</th><th>Task</th><th>Booking/Guest</th><th>Check-in</th><th>Check-out</th><th>Nights</th><th>Cleaning Cost (ISK)</th><th>Status</th></tr></thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def main():
    all_events = []
    failures = []
    for s in SOURCES:
        try:
            txt = fetch_text(s["url"])
            ev = parse_ics(txt, s)
            all_events.extend(ev)
        except Exception as e:
            failures.append((s["property"], s["platform"], str(e)))

    events = dedupe(all_events)
    cleaning = make_cleaning_rows(events)

    write_csv(
        OUT_DIR / "bookings_merged.csv",
        events,
        ["property", "platform", "cleaner", "uid", "summary", "check_in", "check_out", "nights", "status"],
    )

    write_csv(
        OUT_DIR / "cleaning_schedule.csv",
        cleaning,
        ["date", "cleaner", "property", "task", "guest", "check_in", "check_out", "nights", "people", "cost_of_stay", "cleaning_cost_isk", "status", "source"],
    )

    monthly_totals = monthly_cleaning_totals(cleaning)
    write_csv(
        OUT_DIR / "monthly_cleaning_totals.csv",
        monthly_totals,
        ["month", "property", "cleaner", "changeovers", "total_cleaning_cost_isk"],
    )

    monthly_payouts = monthly_cleaner_payouts(cleaning)
    write_csv(
        OUT_DIR / "monthly_cleaner_payouts.csv",
        monthly_payouts,
        ["month", "cleaner", "changeovers", "total_cleaning_cost_isk"],
    )

    weekly_msg = build_weekly_cleaner_message(cleaning)
    (OUT_DIR / "weekly_cleaner_summary.txt").write_text(weekly_msg, encoding="utf-8")

    write_html_gantt(OUT_DIR / "cleaner_gantt.html", cleaning, monthly_totals)

    print(f"Events total: {len(all_events)} | deduped: {len(events)}")
    print(f"Cleaning rows: {len(cleaning)}")
    print(f"Monthly total rows: {len(monthly_totals)}")
    print(f"Monthly cleaner payout rows: {len(monthly_payouts)}")
    print(f"Output dir: {OUT_DIR}")
    if failures:
        print("Failures:")
        for f in failures:
            print(" - ", f)


if __name__ == "__main__":
    main()
