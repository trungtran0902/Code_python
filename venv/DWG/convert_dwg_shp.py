import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Iterable
from uuid import uuid4

import folium
import geopandas as gpd
from flask import Flask, abort, render_template_string, request, send_file, url_for


BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


ODA_EXE = Path(r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe")
ODA_SEARCH_DIRS = [
    Path(r"C:\Program Files\ODA"),
    Path(r"C:\Program Files (x86)\ODA"),
]
ALLOWED_EXTENSIONS = {".dwg"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024


PAGE_TEMPLATE = """
<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DWG Viewer & Converter to Shapefile</title>
  <style>
    :root {
      --bg: #f4f6f8;
      --card: #ffffff;
      --text: #1f2937;
      --muted: #667085;
      --line: #d0d5dd;
      --ok-bg: #e8f7ee;
      --ok-text: #166534;
      --warn-bg: #fff7e6;
      --warn-text: #92400e;
      --err-bg: #fdecec;
      --err-text: #b42318;
      --accent: #0f766e;
      --accent-dark: #115e59;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      background: linear-gradient(180deg, #eef3f7 0%, #f7fafc 100%);
      color: var(--text);
    }
    .page {
      max-width: 1320px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }
    h1 {
      margin: 0 0 20px;
      font-size: 48px;
      line-height: 1.05;
      letter-spacing: -0.03em;
    }
    .card {
      background: var(--card);
      border: 1px solid rgba(15, 118, 110, 0.12);
      border-radius: 18px;
      box-shadow: 0 18px 40px rgba(16, 24, 40, 0.08);
      padding: 24px;
      margin-bottom: 20px;
    }
    .row {
      display: grid;
      gap: 16px;
    }
    .alert {
      border-radius: 12px;
      padding: 14px 16px;
      margin-bottom: 14px;
      font-size: 15px;
    }
    .ok { background: var(--ok-bg); color: var(--ok-text); }
    .warn { background: var(--warn-bg); color: var(--warn-text); }
    .err { background: var(--err-bg); color: var(--err-text); white-space: pre-wrap; }
    .muted { color: var(--muted); font-size: 14px; }
    form {
      display: grid;
      gap: 14px;
    }
    input[type=file] {
      border: 1px dashed var(--line);
      border-radius: 14px;
      background: #fbfcfd;
      padding: 20px;
      width: 100%;
    }
    button, .button {
      display: inline-block;
      border: 0;
      border-radius: 12px;
      background: var(--accent);
      color: white;
      text-decoration: none;
      padding: 12px 18px;
      font-size: 15px;
      cursor: pointer;
      transition: background 0.2s ease;
    }
    button:hover, .button:hover { background: var(--accent-dark); }
    .meta {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin: 16px 0 8px;
    }
    .meta-box {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px 16px;
      background: #fafbfc;
    }
    .meta-box strong {
      display: block;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      margin-bottom: 6px;
    }
    .map-frame {
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: hidden;
      background: white;
      min-height: 640px;
    }
    .table-wrap {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: white;
      margin-top: 14px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      padding: 10px 12px;
      border-bottom: 1px solid #eaecf0;
      text-align: left;
      vertical-align: top;
    }
    th {
      background: #f8fafc;
      position: sticky;
      top: 0;
    }
    code {
      background: #f2f4f7;
      padding: 2px 6px;
      border-radius: 6px;
    }
  </style>
</head>
<body>
  <div class="page">
    <h1>DWG Viewer & Converter to Shapefile</h1>

    <div class="card">
      <form method="post" action="{{ url_for('process_upload') }}" enctype="multipart/form-data">
        <label for="dwg_file"><strong>Upload file DWG</strong></label>
        <input id="dwg_file" type="file" name="dwg_file" accept=".dwg" required>
        <div class="muted">Limit 200MB per file. App chay local tai <code>localhost</code>.</div>
        <div>
          <button type="submit">Xu ly DWG</button>
        </div>
      </form>
    </div>

    {% if error %}
      <div class="card">
        <div class="alert err">{{ error }}</div>
      </div>
    {% endif %}

    {% if result %}
      <div class="card">
        <div class="alert ok">Da xu ly xong file: <strong>{{ result.upload_name }}</strong></div>
        <div class="meta">
          <div class="meta-box">
            <strong>DXF</strong>
            <span>{{ result.dxf_name }}</span>
          </div>
          <div class="meta-box">
            <strong>Input CRS</strong>
            <span>{{ result.input_crs_status }}</span>
          </div>
          <div class="meta-box">
            <strong>Output CRS</strong>
            <span>{{ result.output_crs }}</span>
          </div>
          <div class="meta-box">
            <strong>Feature count</strong>
            <span>{{ result.feature_count }}</span>
          </div>
          <div class="meta-box">
            <strong>Geometry types</strong>
            <span>{{ result.geometry_types|join(', ') }}</span>
          </div>
        </div>
        <p>
          <a class="button" href="{{ url_for('download_zip', run_id=result.run_id) }}">Download Shapefile ZIP</a>
        </p>
      </div>

      <div class="card">
        <h2>Preview ban ve</h2>
        <div class="map-frame">{{ result.map_html|safe }}</div>
      </div>

      <div class="card">
        <h2>Thong tin du lieu</h2>
        <div class="table-wrap">{{ result.table_html|safe }}</div>
      </div>
    {% endif %}
  </div>
</body>
</html>
"""


def find_first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def make_run_dirs() -> tuple[str, Path, Path]:
    run_id = uuid4().hex[:12]
    temp_run_dir = TEMP_DIR / run_id
    output_run_dir = OUTPUT_DIR / run_id
    temp_run_dir.mkdir(parents=True, exist_ok=True)
    output_run_dir.mkdir(parents=True, exist_ok=True)
    return run_id, temp_run_dir, output_run_dir


def resolve_oda_exe() -> Path:
    if ODA_EXE.exists():
        return ODA_EXE

    discovered = []
    for base_dir in ODA_SEARCH_DIRS:
        if base_dir.exists():
            discovered.extend(base_dir.glob("**/ODAFileConverter.exe"))

    existing = find_first_existing(discovered)
    if existing:
        return existing

    raise FileNotFoundError(
        "Khong tim thay ODAFileConverter.exe. "
        "Hay cai ODA File Converter hoac cap nhat bien ODA_EXE trong script."
    )


def get_crs_status(gdf: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, str, str]:
    if gdf.crs is None:
        assigned = gdf.set_crs(epsg=4326, allow_override=True)
        return assigned, "Chua co CRS", "EPSG:4326 (WGS84)"
    crs_text = str(gdf.crs)
    return gdf, f"Da co CRS: {crs_text}", crs_text


def read_dxf_as_geodataframe(dxf_path: Path) -> tuple[gpd.GeoDataFrame, str, str]:
    gdf = gpd.read_file(dxf_path)
    if gdf.empty:
        raise ValueError("Khong doc duoc doi tuong nao tu file DXF.")
    return get_crs_status(gdf)


def normalize_geometries(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    normalized = gdf.explode(index_parts=False).reset_index(drop=True)
    normalized = normalized[normalized.geometry.notna()].copy()
    normalized = normalized[~normalized.geometry.is_empty].copy()
    return normalized


def save_uploaded_file(uploaded_file, run_id: str) -> Path:
    file_path = UPLOAD_DIR / f"{run_id}_{Path(uploaded_file.filename).name}"
    uploaded_file.save(file_path)
    return file_path


def convert_dwg_to_dxf(dwg_path: Path, out_dir: Path) -> Path:
    oda_exe = resolve_oda_exe()
    cmd = [
        str(oda_exe),
        str(dwg_path.parent),
        str(out_dir),
        "ACAD2018",
        "DXF",
        "0",
        "1",
        dwg_path.name,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"ODA convert failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    dxf_files = list(out_dir.glob("*.dxf"))
    if not dxf_files:
        raise FileNotFoundError("Khong tim thay file DXF sau khi convert tu DWG.")
    return dxf_files[0]


def dxf_to_geojson(dxf_path: Path, geojson_path: Path) -> tuple[str, str]:
    gdf, input_crs_status, output_crs = read_dxf_as_geodataframe(dxf_path)
    gdf = normalize_geometries(gdf)
    gdf.to_file(geojson_path, driver="GeoJSON")
    return input_crs_status, output_crs


def dxf_to_shapefile_by_geometry(dxf_path: Path, shp_out_dir: Path) -> tuple[Path, str, str]:
    shp_out_dir.mkdir(parents=True, exist_ok=True)
    gdf, input_crs_status, output_crs = read_dxf_as_geodataframe(dxf_path)
    gdf = normalize_geometries(gdf)

    geometry_groups = {
        "points": {"Point", "MultiPoint"},
        "lines": {"LineString", "MultiLineString"},
        "polygons": {"Polygon", "MultiPolygon"},
    }

    created_files = []
    for name, geom_names in geometry_groups.items():
        subset = gdf[gdf.geometry.geom_type.isin(geom_names)].copy()
        if subset.empty:
            continue
        out_path = shp_out_dir / f"{name}.shp"
        subset.to_file(out_path, driver="ESRI Shapefile")
        created_files.append(out_path)

    if not created_files:
        out_path = shp_out_dir / "cad_entities.shp"
        gdf.to_file(out_path, driver="ESRI Shapefile")

    return shp_out_dir, input_crs_status, output_crs


def zip_folder(folder_path: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file_path in folder_path.rglob("*"):
            if file_path.is_file():
                zipf.write(file_path, file_path.relative_to(folder_path))
    return zip_path


def build_preview_data(geojson_path: Path, input_crs_status: str, output_crs: str) -> dict:
    gdf, detected_input_crs_status, detected_output_crs = get_crs_status(gpd.read_file(geojson_path))
    gdf = normalize_geometries(gdf)
    if gdf.empty:
        raise ValueError("GeoJSON rong, khong co doi tuong de hien thi.")

    try:
        gdf_preview = gdf.to_crs(epsg=4326)
    except Exception:
        gdf_preview = gdf

    preview_types = {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}
    gdf_preview = gdf_preview[gdf_preview.geometry.geom_type.isin(preview_types)].copy()
    if gdf_preview.empty:
        raise ValueError("Khong co geometry ho tro preview sau khi lam sach du lieu.")

    bounds = gdf_preview.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    map_obj = folium.Map(location=[center_lat, center_lon], zoom_start=17)
    folium.GeoJson(gdf_preview.to_json(), name="DWG Preview").add_to(map_obj)
    folium.LayerControl().add_to(map_obj)

    table_html = gdf_preview.drop(columns="geometry").head(100).to_html(
        classes="data-table",
        index=False,
        border=0,
    )
    return {
        "input_crs_status": input_crs_status or detected_input_crs_status,
        "output_crs": output_crs or detected_output_crs,
        "feature_count": len(gdf_preview),
        "geometry_types": list(gdf_preview.geometry.geom_type.unique()),
        "map_html": map_obj._repr_html_(),
        "table_html": table_html,
    }


def result_payload(
    run_id: str,
    upload_name: str,
    dxf_name: str,
    geojson_path: Path,
    zip_path: Path,
    input_crs_status: str,
    output_crs: str,
) -> dict:
    preview = build_preview_data(geojson_path, input_crs_status, output_crs)
    return {
        "run_id": run_id,
        "upload_name": upload_name,
        "dxf_name": dxf_name,
        "geojson_path": str(geojson_path),
        "zip_path": str(zip_path),
        **preview,
    }


@app.get("/")
def index():
    return render_template_string(PAGE_TEMPLATE, result=None, error=None)


@app.post("/process")
def process_upload():
    uploaded_file = request.files.get("dwg_file")
    if uploaded_file is None or not uploaded_file.filename:
        return render_template_string(PAGE_TEMPLATE, result=None, error="Chua chon file DWG."), 400

    suffix = Path(uploaded_file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return render_template_string(PAGE_TEMPLATE, result=None, error="Chi ho tro file .dwg"), 400

    run_id, temp_run_dir, output_run_dir = make_run_dirs()
    try:
        dwg_path = save_uploaded_file(uploaded_file, run_id)
        dxf_dir = temp_run_dir / "dxf"
        dxf_dir.mkdir(exist_ok=True)
        dxf_path = convert_dwg_to_dxf(dwg_path, dxf_dir)

        geojson_path = output_run_dir / "preview.geojson"
        input_crs_status, output_crs = dxf_to_geojson(dxf_path, geojson_path)

        shp_dir = output_run_dir / "shapefile"
        _, shp_input_crs_status, shp_output_crs = dxf_to_shapefile_by_geometry(dxf_path, shp_dir)
        zip_path = output_run_dir / "shapefile_result.zip"
        zip_folder(shp_dir, zip_path)

        result = result_payload(
            run_id=run_id,
            upload_name=Path(uploaded_file.filename).name,
            dxf_name=dxf_path.name,
            geojson_path=geojson_path,
            zip_path=zip_path,
            input_crs_status=input_crs_status or shp_input_crs_status,
            output_crs=output_crs or shp_output_crs,
        )
        return render_template_string(PAGE_TEMPLATE, result=result, error=None)
    except Exception as exc:
        return render_template_string(PAGE_TEMPLATE, result=None, error=str(exc)), 500


@app.get("/download/<run_id>")
def download_zip(run_id: str):
    zip_path = OUTPUT_DIR / run_id / "shapefile_result.zip"
    if not zip_path.exists():
        abort(404)
    return send_file(zip_path, as_attachment=True, download_name="shapefile_result.zip")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
