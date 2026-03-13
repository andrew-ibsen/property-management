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

generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

data_obj = {
    "bookings": bookings_js,
    "cleaning": cleaning_js,
    "monthly": monthly_rows,
    "props": properties,
    "cleaners": cleaners,
    "minDate": min_date.isoformat(),
    "maxDate": max_date.isoformat(),
    "generatedAt": generated_at,
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
    body { margin:0; font-family: Inter, Segoe UI, Arial, sans-serif; background: var(--bg); color: var(--text); }
    .wrap { padding: 18px; max-width: 1500px; margin: 0 auto; }
    h1 { margin: 0 0 12px 0; font-size: 28px; }
    .sub { color: var(--muted); margin-bottom: 14px; }
    .top-banner { display:flex; justify-content:space-between; gap:10px; align-items:center; flex-wrap:wrap; background:#10243b; border:1px solid #274262; border-radius:10px; padding:10px 12px; margin-bottom:12px; }
    .banner-left { font-weight:700; color:#f7d36b; }
    .banner-right { color:#9fb3d1; font-size:12px; }
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
    .footer { color:var(--muted); font-size:12px; margin-top: 8px; }
    .legend { color:var(--muted); font-size:12px; margin:8px 0; }

    .gantt-scroll { overflow-x:auto; border:1px solid #274262; border-radius:8px; background:#0f1d31; -webkit-overflow-scrolling: touch; }
    .gantt-grid { display:grid; min-width:1200px; }
    .gantt-cell { border-right:1px solid #1f3450; border-bottom:1px solid #1f3450; min-height:30px; display:flex; align-items:center; justify-content:center; font-size:11px; color:#9fb3d1; }
    .gantt-header { position:sticky; top:0; z-index:3; background:#112136; }
    .gantt-month { position:sticky; top:0; z-index:4; background:#112136; color:var(--accent2); font-weight:600; border-right:1px solid #274262; border-bottom:1px solid #274262; padding:4px 6px; font-size:12px; }
    .prop-label { position:sticky; left:0; z-index:2; background:#13253d; color:#e9f1ff; font-weight:600; justify-content:flex-start; padding-left:10px; min-width:180px; }
    .header-label { position:sticky; left:0; z-index:5; background:#13253d; color:#f7d36b; font-weight:700; justify-content:flex-start; padding-left:10px; min-width:180px; }
    .occ { background:#33e0ff; color:#06202c; font-weight:700; }

    .mobile-week { display:none; }

    @media (max-width: 1000px) { .grid { grid-template-columns: repeat(2,1fr); } }
    @media (max-width: 700px) {
      .wrap { padding:12px; }
      .grid { grid-template-columns: 1fr; }
      h1 { font-size:22px; }
      .v { font-size:24px; }
      .filters { flex-direction:column; align-items:stretch; }
      .filters label { display:flex; flex-direction:column; gap:6px; }
      th, td { font-size:12px; padding:6px; }
      .desktop-gantt { display:none; }
      .mobile-week { display:block; }
    }
  </style>
</head>
<body>
<div class=\"wrap\">
  <h1>Rental Ops Dashboard</h1>
  <div class=\"top-banner\">
    <div class=\"banner-left\">🇮🇸 Iceland Time: <span id=\"icelandNow\">--</span></div>
    <div class=\"banner-right\">Last data refresh: <span id=\"refreshAge\">--</span></div>
  </div>
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

  <div class=\"panel desktop-gantt\">
    <h3 style=\"margin-top:0\">Monthly Linear Gantt (Properties vs Timeline)</h3>
    <div class=\"legend\">1 block = 1 day. Includes month, weekday, and day number headers.</div>
    <div class=\"gantt-scroll\"><div id=\"ganttGrid\" class=\"gantt-grid\"></div></div>
  </div>

  <div class=\"panel mobile-week\">
    <h3 style=\"margin-top:0\">Cleaner Week View (Mobile)</h3>
    <div class=\"table-wrap\">
      <table id=\"mobileWeekTable\">
        <thead><tr><th>Date</th><th>Property</th><th>Cleaner</th><th>Guest</th><th>Cost</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
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
const currentMonth = new Date().toISOString().slice(0,7);
if ([...monthFilter.options].some(o => o.value === currentMonth)) monthFilter.value = currentMonth;

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
  const bt = document.querySelector('#bookingsTable tbody'); bt.innerHTML='';
  for (const b of filteredBookings()) bt.innerHTML += `<tr><td>${b.property}</td><td>${b.platform}</td><td>${b.guest||''}</td><td>${b.checkIn}</td><td>${b.checkOut}</td><td>${b.nights}</td><td>${b.cleaner||''}</td></tr>`;
  const mt = document.querySelector('#monthlyTable tbody'); mt.innerHTML='';
  for (const m of filteredMonthly()) mt.innerHTML += `<tr><td>${m.month}</td><td>${m.bookings}</td><td>${m.nights}</td><td>${m.changeovers||0}</td><td>${(m.cleaning_cost_isk||0).toLocaleString()}</td><td>${m.unique_guest_count}</td></tr>`;
}
function dateRange(minStr, maxStr) {
  const out = []; const d = new Date(minStr + 'T00:00:00'); const end = new Date(maxStr + 'T00:00:00');
  while (d <= end) { out.push(new Date(d)); d.setDate(d.getDate()+1); }
  return out;
}
function fmtLocalISO(d){
  const y = d.getFullYear();
  const m = String(d.getMonth()+1).padStart(2,'0');
  const day = String(d.getDate()).padStart(2,'0');
  return `${y}-${m}-${day}`;
}
function inStay(day, b) { return day >= b.checkIn && day < b.checkOut; }
function renderGridGantt() {
  const el = document.getElementById('ganttGrid');
  const bookings = filteredBookings();
  const props = [...new Set(bookings.map(b=>b.property))];

  const visibleMonth = monthFilter.value !== 'ALL' ? monthFilter.value : (new Date().toISOString().slice(0,7));
  const [y, m] = visibleMonth.split('-').map(Number);
  const monthStart = new Date(Date.UTC(y, m-1, 1));
  const monthEnd = new Date(Date.UTC(y, m, 0));
  const dates = dateRange(monthStart.toISOString().slice(0,10), monthEnd.toISOString().slice(0,10));

  const dayWidth = 34;
  el.style.gridTemplateColumns = `180px repeat(${dates.length}, minmax(${dayWidth}px, ${dayWidth}px))`;

  let html = '';
  html += `<div class="gantt-month header-label">Timeline</div>`;
  for (const d of dates) {
    const label = d.getDate() === 1 ? d.toLocaleString('en-US', {month:'short', year:'numeric'}) : '';
    html += `<div class="gantt-month">${label}</div>`;
  }

  html += `<div class="gantt-cell header-label">Property</div>`;
  for (const d of dates) {
    const wk = d.toLocaleString('en-US', {weekday:'short'}).slice(0,2);
    const ds = fmtLocalISO(d);
    html += `<div class="gantt-cell gantt-header" title="${ds}">${wk}<br>${d.getDate()}</div>`;
  }

  for (const p of props) {
    html += `<div class="gantt-cell prop-label">${p}</div>`;
    const pb = bookings.filter(b => b.property===p);
    for (const d of dates) {
      const ds = fmtLocalISO(d);
      const hit = pb.find(b => inStay(ds, b));
      if (hit) {
        const shortGuest = (hit.guest || 'Guest').replace(/^Reserved\\s*-\\s*/i,'').slice(0,3).toUpperCase();
        const title = `${hit.guest||'Guest'} | ${hit.checkIn}→${hit.checkOut} | ${hit.nights} nights | ${hit.platform} | Cleaner: ${hit.cleaner||''}`;
        html += `<div class="gantt-cell occ" title="${title}">${shortGuest}</div>`;
      } else {
        html += `<div class="gantt-cell"></div>`;
      }
    }
  }
  el.innerHTML = html;
}
function renderMobileWeek() {
  const tbody = document.querySelector('#mobileWeekTable tbody'); if (!tbody) return;
  const today = new Date(); const end = new Date(today); end.setDate(end.getDate()+6);
  const rows = data.cleaning.filter(c => {
    const d = new Date(c.date + 'T00:00:00');
    const t0 = new Date(today.toISOString().slice(0,10)+'T00:00:00');
    return d >= t0 && d <= end;
  }).filter(c =>
    (propertyFilter.value==='ALL' || c.property===propertyFilter.value) &&
    (cleanerFilter.value==='ALL' || c.cleaner===cleanerFilter.value)
  ).sort((a,b)=>a.date.localeCompare(b.date));
  tbody.innerHTML = '';
  for (const r of rows) tbody.innerHTML += `<tr><td>${r.date}</td><td>${r.property}</td><td>${r.cleaner}</td><td>${r.guest||''}</td><td>${(r.costISK||0).toLocaleString()} ISK</td></tr>`;
}
function updateIcelandBanner(){
  const nowEl = document.getElementById('icelandNow');
  const ageEl = document.getElementById('refreshAge');
  if(nowEl){
    const now = new Date();
    nowEl.textContent = new Intl.DateTimeFormat('en-GB', { timeZone:'Atlantic/Reykjavik', weekday:'short', year:'numeric', month:'short', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false }).format(now);
  }
  if(ageEl && data.generatedAt){
    const gen = new Date(data.generatedAt);
    const sec = Math.max(0, Math.floor((Date.now() - gen.getTime())/1000));
    const d = Math.floor(sec/86400);
    const h = Math.floor((sec%86400)/3600);
    const m = Math.floor((sec%3600)/60);
    if(d>0) ageEl.textContent = `${d}d ${h}h ${m}m ago`;
    else if(h>0) ageEl.textContent = `${h}h ${m}m ago`;
    else ageEl.textContent = `${m}m ago`;
  }
}

function renderAll() { renderTables(); renderGridGantt(); renderMobileWeek(); updateIcelandBanner(); }
[propertyFilter, cleanerFilter, monthFilter].forEach(el => el.addEventListener('change', renderAll));
renderAll();
setInterval(updateIcelandBanner, 1000);
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