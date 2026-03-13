import csv
import json
import datetime as dt
from pathlib import Path

BASE = Path(r"C:/Users/Andrew/.openclaw/workspace")
OPS = BASE / "rental-ops"
OUT = OPS / "dashboard.html"


def read_csv(path):
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_date(s):
    return dt.date.fromisoformat(s)


bookings = read_csv(OPS / "bookings_merged.csv")
cleaning = read_csv(OPS / "cleaning_schedule.csv")

for r in bookings:
    r["check_in_date"] = parse_date(r["check_in"])
    r["check_out_date"] = parse_date(r["check_out"])
    r["nights_int"] = int(r.get("nights", 0) or 0)

for r in cleaning:
    r["date_obj"] = parse_date(r["date"])
    r["cleaning_cost_isk_int"] = int(r.get("cleaning_cost_isk", 0) or 0)

properties = sorted({r["property"] for r in bookings})
cleaners = sorted({r["cleaner"] for r in cleaning})

monthly = {}
for b in bookings:
    m = b["check_in_date"].strftime("%Y-%m")
    monthly.setdefault(m, {"bookings": 0, "nights": 0, "unique_guests": set(), "changeovers": 0, "cleaning_cost_isk": 0})
    monthly[m]["bookings"] += 1
    monthly[m]["nights"] += b["nights_int"]
    monthly[m]["unique_guests"].add(b.get("summary", ""))

for c in cleaning:
    m = c["date_obj"].strftime("%Y-%m")
    monthly.setdefault(m, {"bookings": 0, "nights": 0, "unique_guests": set(), "changeovers": 0, "cleaning_cost_isk": 0})
    monthly[m]["cleaning_cost_isk"] += c["cleaning_cost_isk_int"]
    monthly[m]["changeovers"] += 1

monthly_rows = []
for m, v in sorted(monthly.items()):
    monthly_rows.append({
        "month": m,
        "bookings": v["bookings"],
        "nights": v["nights"],
        "changeovers": v["changeovers"],
        "cleaning_cost_isk": v["cleaning_cost_isk"],
        "unique_guest_count": len([x for x in v["unique_guests"] if x]),
    })

total_bookings = len(bookings)
total_nights = sum(b["nights_int"] for b in bookings)
total_cleaning_cost = sum(c["cleaning_cost_isk_int"] for c in cleaning)
avg_stay = round(total_nights / total_bookings, 2) if total_bookings else 0

if bookings:
    min_date = min(b["check_in_date"] for b in bookings)
    max_date = max(b["check_out_date"] for b in bookings)
else:
    min_date = dt.date.today()
    max_date = dt.date.today() + dt.timedelta(days=30)

bookings_js = []
for b in bookings:
    bookings_js.append({
        "property": b["property"],
        "platform": b["platform"],
        "guest": b.get("summary", ""),
        "checkIn": b["check_in"],
        "checkOut": b["check_out"],
        "nights": b["nights_int"],
        "cleaner": b.get("cleaner", ""),
    })

cleaning_js = []
for c in cleaning:
    cleaning_js.append({
        "date": c["date"],
        "property": c["property"],
        "cleaner": c["cleaner"],
        "guest": c.get("guest", ""),
        "costISK": c["cleaning_cost_isk_int"],
        "status": c.get("status", ""),
    })

data_obj = {
    "bookings": bookings_js,
    "cleaning": cleaning_js,
    "monthly": monthly_rows,
    "props": properties,
    "cleaners": cleaners,
    "minDate": min_date.isoformat(),
    "maxDate": max_date.isoformat(),
}

html_template = """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Rental Ops Dashboard</title>
  <style>
    :root {
      --bg: #0f1724;
      --panel: #16243a;
      --text: #e9f1ff;
      --muted: #9fb3d1;
      --accent: #33e0ff;
      --accent2: #f7d36b;
      --grid: #274262;
    }
    body { margin:0; font-family: Inter, Segoe UI, Arial, sans-serif; background: var(--bg); color: var(--text);} 
    .wrap { padding: 18px; max-width: 1500px; margin: 0 auto; }
    h1 { margin: 0 0 12px 0; font-size: 28px; }
    .sub { color: var(--muted); margin-bottom: 14px; }
    .grid { display:grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 14px; }
    .card { background: var(--panel); border:1px solid #223b5d; border-radius: 12px; padding: 12px; }
    .k { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .8px; }
    .v { font-size: 28px; font-weight: 700; margin-top: 6px; color: var(--accent); }
    .filters { display:flex; gap:10px; flex-wrap:wrap; margin-bottom: 12px; }
    select { background:#0e1c30; color:var(--text); border:1px solid #2a466c; border-radius:8px; padding:8px; }
    .panel { background: var(--panel); border:1px solid #223b5d; border-radius: 12px; padding: 12px; margin-bottom: 14px; }
    table { width:100%; border-collapse: collapse; }
    th, td { border-bottom:1px solid #274262; padding:8px; font-size: 13px; }
    th { color: var(--accent2); text-align:left; position: sticky; top: 0; background: #16243a; }
    .table-wrap { max-height: 340px; overflow:auto; }
    .gantt-wrap { overflow-x:auto; overflow-y:hidden; border:1px solid #274262; border-radius: 8px; background:#0f1d31; -webkit-overflow-scrolling: touch; }
    .gantt-wrap svg { display:block; min-width: 1200px; }
    .legend { color:var(--muted); font-size:12px; margin:8px 0; }
    .footer { color:var(--muted); font-size:12px; margin-top: 8px; }
    @media (max-width: 1000px) { .grid { grid-template-columns: repeat(2,1fr); } }
    @media (max-width: 700px) {
      .wrap { padding: 12px; }
      .grid { grid-template-columns: 1fr; }
      h1 { font-size: 22px; }
      .v { font-size: 24px; }
      .filters { flex-direction: column; align-items: stretch; }
      .filters label { display: flex; flex-direction: column; gap: 6px; }
      th, td { font-size: 12px; padding: 6px; }
    }
  </style>
</head>
<body>
<div class=\"wrap\">
  <h1>Rental Ops Dashboard</h1>
  <div class=\"sub\">Interactive live view for bookings, stay length, guests, cleaning costs, and monthly property Gantt.</div>

  <div class=\"grid\">
    <div class=\"card\"><div class=\"k\">Total Bookings</div><div class=\"v\">__TOTAL_BOOKINGS__</div></div>
    <div class=\"card\"><div class=\"k\">Total Nights</div><div class=\"v\">__TOTAL_NIGHTS__</div></div>
    <div class=\"card\"><div class=\"k\">Avg Length of Stay</div><div class=\"v\">__AVG_STAY__</div></div>
    <div class=\"card\"><div class=\"k\">Total Cleaning Cost (ISK)</div><div class=\"v\">__TOTAL_CLEANING__</div></div>
  </div>

  <div class=\"panel\">
    <div class=\"filters\">
      <label>Property
        <select id=\"propertyFilter\"><option value=\"ALL\">All</option></select>
      </label>
      <label>Cleaner
        <select id=\"cleanerFilter\"><option value=\"ALL\">All</option></select>
      </label>
      <label>Month
        <select id=\"monthFilter\"><option value=\"ALL\">All</option></select>
      </label>
    </div>
  </div>

  <div class=\"panel\">
    <h3 style=\"margin-top:0\">Monthly Linear Gantt (Properties vs Timeline)</h3>
    <div class=\"legend\">Bars = occupied stay windows. Timeline shown by day with monthly headers.</div>
    <div class=\"gantt-wrap\"><svg id=\"gantt\" width=\"1400\" height=\"420\"></svg></div>
  </div>

  <div class=\"panel\">
    <h3 style=\"margin-top:0\">Bookings Detail</h3>
    <div class=\"table-wrap\">
      <table id=\"bookingsTable\">
        <thead><tr><th>Property</th><th>Platform</th><th>Guest</th><th>Check-in</th><th>Check-out</th><th>Nights</th><th>Cleaner</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div class=\"panel\">
    <h3 style=\"margin-top:0\">Monthly Metrics</h3>
    <div class=\"table-wrap\">
      <table id=\"monthlyTable\">
        <thead><tr><th>Month</th><th>Bookings</th><th>Nights</th><th>Changeovers</th><th>Cleaning Cost (ISK)</th><th>Unique Guests</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div class=\"footer\">Generated from rental-ops CSV files. Refresh by rerunning build scripts.</div>
</div>

<script>
const data = __DATA_JSON__;

const propertyFilter = document.getElementById('propertyFilter');
const cleanerFilter = document.getElementById('cleanerFilter');
const monthFilter = document.getElementById('monthFilter');

for (const p of data.props) propertyFilter.innerHTML += `<option value="${p}">${p}</option>`;
for (const c of data.cleaners) cleanerFilter.innerHTML += `<option value="${c}">${c}</option>`;
for (const m of [...new Set(data.monthly.map(x=>x.month))]) monthFilter.innerHTML += `<option value="${m}">${m}</option>`;

function monthOf(d) { return d.slice(0,7); }

function filteredBookings() {
  return data.bookings.filter(b =>
    (propertyFilter.value==='ALL' || b.property===propertyFilter.value) &&
    (cleanerFilter.value==='ALL' || b.cleaner===cleanerFilter.value) &&
    (monthFilter.value==='ALL' || monthOf(b.checkIn)===monthFilter.value || monthOf(b.checkOut)===monthFilter.value)
  );
}

function filteredMonthly() {
  return data.monthly.filter(m => (monthFilter.value==='ALL' || m.month===monthFilter.value));
}

function renderTables() {
  const bt = document.querySelector('#bookingsTable tbody');
  bt.innerHTML='';
  for (const b of filteredBookings()) {
    bt.innerHTML += `<tr><td>${b.property}</td><td>${b.platform}</td><td>${b.guest||''}</td><td>${b.checkIn}</td><td>${b.checkOut}</td><td>${b.nights}</td><td>${b.cleaner||''}</td></tr>`;
  }

  const mt = document.querySelector('#monthlyTable tbody');
  mt.innerHTML='';
  for (const m of filteredMonthly()) {
    mt.innerHTML += `<tr><td>${m.month}</td><td>${m.bookings}</td><td>${m.nights}</td><td>${m.changeovers||0}</td><td>${(m.cleaning_cost_isk||0).toLocaleString()}</td><td>${m.unique_guest_count}</td></tr>`;
  }
}

function renderGantt() {
  const svg = document.getElementById('gantt');
  const bookings = filteredBookings();
  const props = [...new Set(bookings.map(b=>b.property))];

  const margin = { top: 50, right: 20, bottom: 20, left: 220 };
  const rowH = 34;
  const minDate = new Date(data.minDate + 'T00:00:00');
  const maxDate = new Date(data.maxDate + 'T00:00:00');
  const dayMs = 24*3600*1000;
  const days = Math.max(1, Math.round((maxDate-minDate)/dayMs));

  const pxPerDay = window.innerWidth < 700 ? 12 : 20;
  const timelineWidth = Math.max(1200, days * pxPerDay);
  const width = margin.left + margin.right + timelineWidth;
  const height = Math.max(260, margin.top + margin.bottom + props.length*rowH + 30);
  svg.setAttribute('width', width);
  svg.setAttribute('height', height);

  const x0 = margin.left;
  const xW = timelineWidth;

  function xFor(dateStr) {
    const d = new Date(dateStr + 'T00:00:00');
    const t = (d - minDate) / dayMs;
    return x0 + (t/days)*xW;
  }

  let g = '';
  g += `<rect x="0" y="0" width="${width}" height="${height}" fill="#0f1d31"/>`;

  let cur = new Date(minDate);
  cur.setDate(1);
  while (cur <= maxDate) {
    const monthStart = new Date(cur);
    const next = new Date(cur.getFullYear(), cur.getMonth()+1, 1);
    const x = xFor(monthStart.toISOString().slice(0,10));
    const label = monthStart.toLocaleString('en-US', { month:'short', year:'numeric' });
    g += `<line x1="${x}" y1="${margin.top-22}" x2="${x}" y2="${height-18}" stroke="#274262"/>`;
    g += `<text x="${x+4}" y="${margin.top-28}" fill="#f7d36b" font-size="12">${label}</text>`;
    cur = next;
  }

  props.forEach((p,i)=>{
    const y = margin.top + i*rowH;
    g += `<line x1="${margin.left}" y1="${y+18}" x2="${width-margin.right}" y2="${y+18}" stroke="#1f3450"/>`;
    g += `<text x="18" y="${y+22}" fill="#e9f1ff" font-size="13">${p}</text>`;
  });

  for (const b of bookings) {
    const i = props.indexOf(b.property);
    if (i < 0) continue;
    const y = margin.top + i*rowH + 6;
    const x1 = xFor(b.checkIn);
    const x2 = Math.max(x1+2, xFor(b.checkOut));
    const w = x2-x1;
    const title = `${b.property} | ${b.guest||'Guest'} | ${b.checkIn}→${b.checkOut} | ${b.nights} nights | ${b.platform}`;
    g += `<rect x="${x1}" y="${y}" width="${w}" height="18" rx="4" fill="#33e0ff" opacity="0.86"><title>${title}</title></rect>`;
  }

  svg.innerHTML = g;
}

function renderAll() { renderTables(); renderGantt(); }
[propertyFilter, cleanerFilter, monthFilter].forEach(el => el.addEventListener('change', renderAll));
renderAll();
</script>
</body>
</html>
"""

html = html_template
html = html.replace("__TOTAL_BOOKINGS__", str(total_bookings))
html = html.replace("__TOTAL_NIGHTS__", str(total_nights))
html = html.replace("__AVG_STAY__", str(avg_stay))
html = html.replace("__TOTAL_CLEANING__", f"{total_cleaning_cost:,}")
html = html.replace("__DATA_JSON__", json.dumps(data_obj))

OUT.write_text(html, encoding="utf-8")
print(f"Dashboard written: {OUT}")