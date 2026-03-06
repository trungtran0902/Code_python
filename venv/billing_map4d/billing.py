import json
import re
import uuid
from collections import OrderedDict
from flask import Flask, request, redirect, url_for, session, jsonify, render_template_string

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"

# =======================
# In-memory datastore
# =======================
DATASTORE = {}  # sid -> list[dict]

# =======================
# Mongo shell -> JSON
# =======================
def mongo_shell_to_json(text: str) -> str:
    text = re.sub(r'ISODate\("([^"]+)"\)', r'"\1"', text)
    text = re.sub(r'NumberLong\(([-]?\d+)\)', r'\1', text)
    text = re.sub(r'NumberDecimal\("([-]?\d+(?:\.\d+)?)"\)', r'\1', text)
    text = re.sub(r'ObjectId\("([^"]+)"\)', r'"\1"', text)
    return text

# =======================
# Parse upload file
# =======================
def parse_uploaded_file(file_bytes: bytes):
    raw = file_bytes.decode("utf-8", errors="replace").strip()
    normalized = mongo_shell_to_json(raw)

    try:
        data = json.loads(normalized)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        pass

    records = []
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(normalized):
        while idx < len(normalized) and normalized[idx].isspace():
            idx += 1
        if idx >= len(normalized):
            break
        obj, idx = decoder.raw_decode(normalized, idx)
        records.append(obj)

    if not records:
        raise ValueError("Không parse được document nào")

    return records

# =======================
# Helpers
# =======================
def safe_int(x, default=0):
    if x is None:
        return default
    try:
        if isinstance(x, str):
            x = x.replace(",", "").strip()
            if x == "":
                return default
        return int(float(x))
    except Exception:
        return default

def get_sid():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    return session["sid"]

def record_matches(rec, q, month, year):
    if month and safe_int(rec.get("month")) != safe_int(month):
        return False
    if year and safe_int(rec.get("year")) != safe_int(year):
        return False
    if q:
        hay = " ".join(str(rec.get(k, "")) for k in ["_id", "serviceName", "userId"])
        if q.lower() not in hay.lower():
            return False
    return True

# =======================
# GROUP user + month + year
# =======================
AGG_FIELDS = [
    "totalRequestSuccess",
    "totalRequestError",
    "totalElementSuccess",
    "amount",
]

def group_by_user_month_year(records):
    grouped = {}

    for r in records:
        uid = r.get("userId", "UNKNOWN")
        month = safe_int(r.get("month"))
        year = safe_int(r.get("year"))

        key = (uid, month, year)

        if key not in grouped:
            grouped[key] = {
                "_id": f"user:{uid}:{month}:{year}",
                "userId": uid,
                "month": month,
                "year": year,
                "serviceName": "MULTI",
                "__items": [],
                "totalRequestSuccess": 0,
                "totalRequestError": 0,
                "totalElementSuccess": 0,
                "amount": 0,
            }

        grouped[key]["totalRequestSuccess"] += safe_int(r.get("totalRequestSuccess"))
        grouped[key]["totalRequestError"] += safe_int(r.get("totalRequestError"))
        grouped[key]["totalElementSuccess"] += safe_int(r.get("totalElementSuccess"))
        grouped[key]["amount"] += safe_int(r.get("amount"))

        grouped[key]["__items"].append(r)

    return list(grouped.values())

# =======================
# Labels
# =======================
LABELS = {
    "_id": "ID",
    "serviceName": "Tên dịch vụ",
    "serviceId": "Service ID",
    "userId": "User ID",
    "month": "Tháng",
    "year": "Năm",
    "totalRequestSuccess": "Request thành công",
    "totalRequestError": "Request lỗi",
    "totalElementSuccess": "Element thành công",
    "amount": "Tổng tiền",
}

# =======================
# HTML Template
# =======================
TEMPLATE = r"""
<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>MongoDB JSON Viewer</title>
<style>
body{font-family:Arial;margin:20px}
.card{border:1px solid #ddd;border-radius:10px;padding:15px;margin-bottom:15px}
table{width:100%;border-collapse:collapse}
th,td{border-bottom:1px solid #eee;padding:8px}
th{background:#fafafa}
input,select,button{padding:8px;border-radius:8px;border:1px solid #ccc}
.link{color:#0b57d0;cursor:pointer}
.pill{border:1px solid #ddd;border-radius:999px;padding:2px 8px}
.pagination a{margin:0 4px;text-decoration:none}
.pagination b{margin:0 4px}
.modal,.backdrop{display:none}
.modal{position:fixed;inset:8%;background:#fff;border-radius:12px;padding:15px;overflow:auto}
.backdrop{position:fixed;inset:0;background:rgba(0,0,0,.4)}
</style>
</head>
<body>

<h2>MongoDB JSON Viewer</h2>

<div class="card">
<form method="post" action="/upload" enctype="multipart/form-data">
<input type="file" name="jsonfile" required>
<button type="submit">Upload</button>
<a href="/clear"><button type="button">Clear</button></a>
</form>
</div>

{% if records %}
<div class="card">
<form method="get">
<input name="q" placeholder="Search" value="{{ q }}">
<input name="month" placeholder="Month" value="{{ month }}" style="width:80px">
<input name="year" placeholder="Year" value="{{ year }}" style="width:80px">
<label>
  <input type="checkbox" name="group" value="user"
    {% if request.args.get('group')=='user' %}checked{% endif %}>
  Group User/Month
</label>
<select name="size">
{% for s in [20,50,100] %}
<option value="{{s}}" {% if size==s %}selected{% endif %}>{{s}}</option>
{% endfor %}
</select>
<button type="submit">Filter</button>
</form>

<p>Tổng: <span class="pill">{{ total }}</span></p>

<table>
<thead>
<tr>
<th>#</th>
<th>User</th>
<th>Month</th>
<th>Year</th>
<th>Success</th>
<th>Amount</th>
<th>Detail</th>
</tr>
</thead>
<tbody>
{% for r in rows %}
<tr>
<td>{{ r.no }}</td>
<td>{{ r.userId }}</td>
<td>{{ r.month }}</td>
<td>{{ r.year }}</td>
<td>{{ r.totalRequestSuccess }}</td>
<td>{{ r.amount }}</td>
<td><span class="link" onclick="openDetail('{{ r.id }}')">Xem</span></td>
</tr>
{% endfor %}
</tbody>
</table>

<div class="pagination">
{% for p in page_numbers %}
  {% if p == page %}
    <b>{{ p }}</b>
  {% else %}
    <a href="{{ page_url(p) }}">{{ p }}</a>
  {% endif %}
{% endfor %}
{% if page < pages %}
  <a href="{{ page_url(page+1) }}">Next</a>
{% endif %}
</div>

</div>
{% endif %}

<div class="backdrop" id="bd" onclick="closeModal()"></div>
<div class="modal" id="modal">
<button onclick="closeModal()">Close</button>
<pre id="detail"></pre>
</div>

<script>
function openDetail(id){
fetch('/api/record/'+id)
.then(r=>r.json())
.then(d=>{
document.getElementById('detail').textContent = JSON.stringify(d.raw,null,2);
document.getElementById('modal').style.display='block';
document.getElementById('bd').style.display='block';
});
}
function closeModal(){
document.getElementById('modal').style.display='none';
document.getElementById('bd').style.display='none';
}
</script>

</body>
</html>
"""

# =======================
# Routes
# =======================
@app.route("/")
def index():
    sid = get_sid()
    data = DATASTORE.get(sid, [])

    q = request.args.get("q", "")
    month = request.args.get("month", "")
    year = request.args.get("year", "")
    size = safe_int(request.args.get("size"), 50)
    page = safe_int(request.args.get("page"), 1)
    group = request.args.get("group") == "user"

    filtered = [r for r in data if record_matches(r, q, month, year)]
    if group:
        filtered = group_by_user_month_year(filtered)

    total = len(filtered)
    pages = max(1, (total + size - 1) // size)
    page = max(1, min(page, pages))

    start = (page - 1) * size
    end = start + size

    rows = []
    for i, r in enumerate(filtered[start:end], start=start + 1):
        rows.append({
            "no": i,
            "id": r.get("_id"),
            "userId": r.get("userId"),
            "month": r.get("month"),
            "year": r.get("year"),
            "totalRequestSuccess": r.get("totalRequestSuccess"),
            "amount": r.get("amount"),
        })

    def page_url(p):
        args = dict(request.args)
        args["page"] = p
        return url_for("index", **args)

    page_numbers = list(range(1, pages + 1))

    return render_template_string(
        TEMPLATE,
        records=data,
        rows=rows,
        total=total,
        page=page,
        pages=pages,
        page_numbers=page_numbers,
        q=q,
        month=month,
        year=year,
        size=size,
        page_url=page_url
    )

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("jsonfile")
    if f:
        DATASTORE[get_sid()] = parse_uploaded_file(f.read())
    return redirect(url_for("index"))

@app.route("/clear")
def clear():
    DATASTORE.pop(get_sid(), None)
    return redirect(url_for("index"))

@app.route("/api/record/<rid>")
def api_record(rid):
    data = DATASTORE.get(get_sid(), [])

    if rid.startswith("user:"):
        _, uid, m, y = rid.split(":")
        items = [
            r for r in data
            if str(r.get("userId")) == uid
            and safe_int(r.get("month")) == safe_int(m)
            and safe_int(r.get("year")) == safe_int(y)
        ]
        return jsonify({"raw": items})

    for r in data:
        if str(r.get("_id")) == rid:
            return jsonify({"raw": r})

    return jsonify({"error": "not found"}), 404

# =======================
# Run
# =======================
if __name__ == "__main__":
    app.run(debug=True)
