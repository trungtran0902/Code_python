import json
import re
import shutil
import subprocess
import unicodedata
import zipfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable
from uuid import uuid4

import folium
import geopandas as gpd
import pyogrio
from flask import Flask, abort, render_template_string, request, send_file, url_for


BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "outputs"
CONFIG_PATH = BASE_DIR / "mapping_rules.json"

# Template gdbs được đóng gói trong 1 zip. Hệ thống sẽ giải nén vào TEMP_DIR và lấy 4 gdb bên trong.
TEMPLATE_ZIP_PATH = Path(r"G:\Minh\01.HaNoi.CTDL_QuyHoachDTNT_TT16_VN2000_105-00_gdb_template.zip")
TEMPLATE_GDB_NAMES = ["HienTrang.gdb", "MocGioi.gdb", "NenDiaHinh.gdb", "QuyHoach.gdb"]
TEMPLATE_EXTRACT_ROOT = TEMP_DIR / "templates"
RUN_INFO_NAME = "run_info.json"
ALLOWED_EXTENSIONS = {".dwg"}
MAPPING_THRESHOLD = 0.72

for directory in [UPLOAD_DIR, TEMP_DIR, OUTPUT_DIR]:
    directory.mkdir(exist_ok=True)

ODA_EXE = Path(r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe")
ODA_SEARCH_DIRS = [
    Path(r"C:\Program Files\ODA"),
    Path(r"C:\Program Files (x86)\ODA"),
]

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
      max-width: 1360px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }
    h1 {
      margin: 0 0 20px;
      font-size: 48px;
      line-height: 1.05;
      letter-spacing: -0.03em;
    }
    h2 {
      margin: 0 0 14px;
      font-size: 24px;
    }
    .card {
      background: var(--card);
      border: 1px solid rgba(15, 118, 110, 0.12);
      border-radius: 18px;
      box-shadow: 0 18px 40px rgba(16, 24, 40, 0.08);
      padding: 24px;
      margin-bottom: 20px;
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
    input[type=file], select {
      border: 1px dashed var(--line);
      border-radius: 14px;
      background: #fbfcfd;
      padding: 14px 16px;
      width: 100%;
      font-size: 15px;
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
    .button.secondary { background: #344054; }
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
    .pill {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      background: #eef2f6;
    }
    .pill.good { background: #dff7e8; color: #166534; }
    .pill.mid { background: #fff2d6; color: #92400e; }
    .pill.low { background: #fde7e7; color: #b42318; }
    code {
      background: #f2f4f7;
      padding: 2px 6px;
      border-radius: 6px;
    }
    ul {
      margin: 10px 0 0;
      padding-left: 20px;
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
          <a class="button secondary" href="{{ url_for('download_zip', run_id=result.run_id) }}">Download Shapefile ZIP</a>
        </p>
      </div>

      <div class="card">
        <h2>Goi y anh xa layer CAD</h2>
        <div class="muted">Engine dang dung exact + alias + fuzzy match. Rule doc tu <code>{{ config_path }}</code>.</div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>CAD Layer</th>
                <th>So doi tuong</th>
                <th>Geometry</th>
                <th>De xuat</th>
                <th>Template</th>
                <th>Do tin cay</th>
                <th>Kieu match</th>
              </tr>
            </thead>
            <tbody>
              {% for item in result.layer_suggestions %}
                <tr>
                  <td>{{ item.source_layer }}</td>
                  <td>{{ item.feature_count }}</td>
                  <td>{{ item.geometry_types|join(', ') }}</td>
                  <td>{{ item.target_layer or 'Chua de xuat' }}</td>
                  <td>{{ item.template_name or '-' }}</td>
                  <td>
                    {% set score = item.score %}
                    {% if score >= 0.9 %}
                      <span class="pill good">{{ '%.2f'|format(score) }}</span>
                    {% elif score >= 0.72 %}
                      <span class="pill mid">{{ '%.2f'|format(score) }}</span>
                    {% else %}
                      <span class="pill low">{{ '%.2f'|format(score) }}</span>
                    {% endif %}
                  </td>
                  <td>{{ item.match_type }}</td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h2>Lua chon bo mau CSDL GIS</h2>
        <form method="post" action="{{ url_for('map_to_templates', run_id=result.run_id) }}">
          <label for="template_choice"><strong>Chon bo mau can anh xa</strong></label>
          <select id="template_choice" name="template_choice" required>
            <option value="ALL" disabled>Tat ca (khong ho tro theo yeu cau moi)</option>
            {% for template_name in template_names %}
              <option value="{{ template_name }}">{{ template_name }}</option>
            {% endfor %}
          </select>
          <div class="muted">Chon mot bo de loc ket qua theo bo do, hoac chon Tat ca de phan bo dong thoi.</div>
          <div>
            <button type="submit">Anh xa vao bo mau</button>
          </div>
        </form>
      </div>

      {% if mapping_result %}
        <div class="card">
          <h2>Ket qua anh xa</h2>
          <div class="alert {% if mapping_result.total_matched > 0 %}ok{% else %}warn{% endif %}">
            Da anh xa {{ mapping_result.total_matched }} doi tuong theo lua chon <strong>{{ mapping_result.selected_template }}</strong>.
          </div>
          <div class="muted">Che do anh xa hien tai: dung de xuat dang hien thi trong bang, ke ca low_confidence. Chi bo qua cac dong unmatched.</div>
          {% if mapping_result.download_url %}
            <p><a class="button" href="{{ mapping_result.download_url }}">Download goi ket qua anh xa</a></p>
          {% endif %}
          {% if mapping_result.template_summaries %}
            <ul>
              {% for item in mapping_result.template_summaries %}
                <li>{{ item.template_name }}: {{ item.matched_count }} doi tuong, {{ item.applied_rule_count }} rule duoc ap dung</li>
              {% endfor %}
            </ul>
          {% endif %}
          {% if mapping_result.unmatched_layers %}
            <div class="alert warn">Chua co de xuat du manh cho cac CAD layer: {{ mapping_result.unmatched_layers|join(', ') }}</div>
          {% endif %}
        </div>
      {% endif %}

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


def create_default_mapping_config() -> dict:
    return {
        "templates": {
            "HienTrang": {"rules": []},
            "MocGioi": {"rules": []},
            "NenDiaHinh": {"rules": []},
            "QuyHoach": {"rules": []}
        },
        "rule_examples": [
            {
                "description": "Vi du exact/alias cho polygon quy hoach",
                "template": "QuyHoach",
                "target_layer": "CongTrinh_A",
                "aliases": ["qh_dat_o", "cong_trinh", "dat_o", "congtrinh"],
                "keywords": ["cong", "trinh", "dat", "o"],
                "geometry_types": ["Polygon", "MultiPolygon"]
            },
            {
                "description": "Vi du exact/alias cho duong dong muc",
                "template": "NenDiaHinh",
                "target_layer": "DuongDongMuc_L",
                "aliases": ["duong_dong_muc", "dongmuc", "contour", "duongbinhdo"],
                "keywords": ["duong", "dong", "muc", "contour"],
                "geometry_types": ["LineString", "MultiLineString"]
            }
        ]
    }


if not CONFIG_PATH.exists():
    CONFIG_PATH.write_text(json.dumps(create_default_mapping_config(), indent=2, ensure_ascii=False), encoding="utf-8")


def load_mapping_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def template_names() -> list[str]:
    return list(load_mapping_config()["templates"].keys())


def normalize_name(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    lowered = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", ascii_text).lower()
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


def tokens_from_name(value: str) -> list[str]:
    normalized = normalize_name(value)
    return [token for token in normalized.split() if token]


def geometry_bonus(rule_geometry_types: list[str], source_geometry_types: list[str]) -> float:
    if not rule_geometry_types:
        return 0.05
    if set(rule_geometry_types) & set(source_geometry_types):
        return 0.15
    return -0.1


def infer_geometry_types_from_target(target_layer: str, layer_geom_type: str | None) -> list[str]:
    if layer_geom_type:
        return [layer_geom_type]
    if target_layer.endswith("_P"):
        return ["Point", "MultiPoint"]
    if target_layer.endswith("_L"):
        return ["LineString", "MultiLineString"]
    if target_layer.endswith("_A"):
        return ["Polygon", "MultiPolygon"]
    return []


def list_template_layers(template_path: Path) -> list[dict]:
    layers = []
    for layer_name, geom_type in pyogrio.list_layers(template_path):
        layers.append({"layer_name": str(layer_name), "geometry_type": str(geom_type)})
    return layers


def extract_templates_if_needed() -> dict[str, Path]:
    TEMPLATE_EXTRACT_ROOT.mkdir(parents=True, exist_ok=True)

    # Mỗi template là 1 folder gdb. Nếu đã có đủ thì không giải nén lại.
    extracted: dict[str, Path] = {}
    missing = []
    for gdb_name in TEMPLATE_GDB_NAMES:
        p = TEMPLATE_EXTRACT_ROOT / gdb_name
        extracted[gdb_name] = p
        if not p.exists():
            missing.append(gdb_name)

    if missing:
        if not TEMPLATE_ZIP_PATH.exists():
            raise FileNotFoundError(f"Khong tim thay template zip: {TEMPLATE_ZIP_PATH}")

        # Giải nén zip vào root, sau đó map name -> folder.
        with zipfile.ZipFile(TEMPLATE_ZIP_PATH, "r") as zf:
            zf.extractall(TEMPLATE_EXTRACT_ROOT)

        # đảm bảo lại
        for gdb_name in TEMPLATE_GDB_NAMES:
            extracted[gdb_name] = TEMPLATE_EXTRACT_ROOT / gdb_name
            if not extracted[gdb_name].exists():
                raise FileNotFoundError(f"Khong tim thay {gdb_name} sau khi giai nen: {TEMPLATE_EXTRACT_ROOT}")

    return {
        # map template_name theo convention: lấy phần trước ".gdb"
        name.replace(".gdb", ""): path for name, path in extracted.items()
    }


def build_template_rule_catalog(config: dict) -> dict[str, list[dict]]:
    template_gdb_map = extract_templates_if_needed()
    catalog = {}

    for template_name, template_cfg in config["templates"].items():
        template_path = template_gdb_map.get(template_name)
        if template_path is None:
            raise FileNotFoundError(f"Khong co template gdb cho template_name={template_name}")

        manual_rules = []
        for rule in template_cfg.get("rules", []):
            manual_rule = dict(rule)
            manual_rule["template_name"] = template_name
            manual_rule.setdefault("aliases", [])
            manual_rule.setdefault("keywords", [])
            manual_rules.append(manual_rule)

        existing_targets = {rule["target_layer"] for rule in manual_rules if rule.get("target_layer")}
        auto_rules = []
        for layer_info in list_template_layers(template_path):
            target_layer = layer_info["layer_name"]
            if target_layer in existing_targets:
                continue
            auto_rules.append(
                {
                    "template_name": template_name,
                    "target_layer": target_layer,
                    "aliases": [target_layer],
                    "keywords": tokens_from_name(target_layer),
                    "geometry_types": infer_geometry_types_from_target(target_layer, layer_info["geometry_type"]),
                }
            )

        catalog[template_name] = manual_rules + auto_rules
    return catalog


def score_rule(source_layer: str, source_geometry_types: list[str], rule: dict) -> tuple[float, str]:
    source_norm = normalize_name(source_layer)
    source_tokens = set(tokens_from_name(source_layer))

    target_name = rule.get("target_layer", "")
    target_norm = normalize_name(target_name)
    alias_norms = [normalize_name(alias) for alias in rule.get("aliases", []) if alias]
    candidate_norms = [target_norm] + alias_norms

    if source_norm and source_norm in candidate_norms:
        return min(1.0, 0.9 + geometry_bonus(rule.get("geometry_types", []), source_geometry_types)), "exact"

    best_name_score = max((SequenceMatcher(None, source_norm, item).ratio() for item in candidate_norms if item), default=0.0)
    candidate_tokens = set(tokens_from_name(target_name))
    for alias in rule.get("aliases", []):
        candidate_tokens.update(tokens_from_name(alias))

    token_overlap = 0.0
    if source_tokens and candidate_tokens:
        token_overlap = len(source_tokens & candidate_tokens) / max(len(source_tokens), len(candidate_tokens))

    keyword_tokens = {normalize_name(keyword) for keyword in rule.get("keywords", []) if keyword}
    keyword_tokens = {token for token in keyword_tokens if token}
    keyword_overlap = 0.0
    if source_tokens and keyword_tokens:
        keyword_overlap = len(source_tokens & keyword_tokens) / len(keyword_tokens)

    score = (
        (best_name_score * 0.6)
        + (token_overlap * 0.2)
        + (keyword_overlap * 0.1)
        + geometry_bonus(rule.get("geometry_types", []), source_geometry_types)
    )
    match_type = "fuzzy" if score >= MAPPING_THRESHOLD else "low_confidence"

    if token_overlap >= 0.8 and best_name_score >= 0.72:
        match_type = "alias"

    return max(0.0, min(1.0, score)), match_type


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

    table_html = gdf_preview.drop(columns="geometry").head(100).to_html(classes="data-table", index=False, border=0)
    return {
        "input_crs_status": input_crs_status or detected_input_crs_status,
        "output_crs": output_crs or detected_output_crs,
        "feature_count": len(gdf_preview),
        "geometry_types": list(gdf_preview.geometry.geom_type.unique()),
        "map_html": map_obj._repr_html_(),
        "table_html": table_html,
    }


def collect_cad_layers(source_gdf: gpd.GeoDataFrame) -> list[dict]:
    layer_groups = []
    if "Layer" not in source_gdf.columns:
        layer_groups.append(
            {
                "source_layer": "NO_LAYER_FIELD",
                "feature_count": len(source_gdf),
                "geometry_types": sorted(source_gdf.geometry.geom_type.unique().tolist()),
            }
        )
        return layer_groups

    grouped = source_gdf.groupby(source_gdf["Layer"].astype(str))
    for layer_name, subset in grouped:
        layer_groups.append(
            {
                "source_layer": layer_name,
                "feature_count": len(subset),
                "geometry_types": sorted(subset.geometry.geom_type.unique().tolist()),
            }
        )
    return sorted(layer_groups, key=lambda item: item["source_layer"])


def build_layer_suggestions(source_gdf: gpd.GeoDataFrame, catalog: dict[str, list[dict]]) -> list[dict]:
    suggestions = []
    for layer_group in collect_cad_layers(source_gdf):
        best = {
            "template_name": None,
            "target_layer": None,
            "score": 0.0,
            "match_type": "unmatched",
        }
        for template_name, rules in catalog.items():
            for rule in rules:
                score, match_type = score_rule(layer_group["source_layer"], layer_group["geometry_types"], rule)
                if score > best["score"]:
                    best = {
                        "template_name": template_name,
                        "target_layer": rule.get("target_layer"),
                        "score": score,
                        "match_type": match_type,
                    }
        suggestions.append({**layer_group, **best})
    return suggestions


def run_info_path(run_id: str) -> Path:
    return OUTPUT_DIR / run_id / RUN_INFO_NAME


def save_run_info(run_id: str, payload: dict) -> None:
    run_info_path(run_id).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_run_info(run_id: str) -> dict:
    path = run_info_path(run_id)
    if not path.exists():
        raise FileNotFoundError("Khong tim thay thong tin phien xu ly.")
    return json.loads(path.read_text(encoding="utf-8"))


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
    source_gdf = normalize_geometries(gpd.read_file(geojson_path))
    layer_suggestions = build_layer_suggestions(source_gdf, build_template_rule_catalog(load_mapping_config()))
    result = {
        "run_id": run_id,
        "upload_name": upload_name,
        "dxf_name": dxf_name,
        "geojson_path": str(geojson_path),
        "zip_path": str(zip_path),
        "layer_suggestions": layer_suggestions,
        **preview,
    }
    save_run_info(run_id, result)
    return result


def render_page(result: dict | None = None, error: str | None = None, mapping_result: dict | None = None, status_code: int = 200):
    return render_template_string(
        PAGE_TEMPLATE,
        result=result,
        error=error,
        mapping_result=mapping_result,
        template_names=template_names(),
        config_path=str(CONFIG_PATH),
    ), status_code


def select_templates(choice: str, config: dict) -> dict:
    templates = config["templates"]
    if choice == "ALL":
        return templates
    if choice not in templates:
        raise ValueError("Lua chon bo mau khong hop le.")
    return {choice: templates[choice]}


def align_to_template_schema(template_gdb: Path, target_layer: str, source_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    template_schema = gpd.read_file(template_gdb, layer=target_layer, rows=0)
    target_columns = [col for col in template_schema.columns if col != "geometry"]
    aligned = source_gdf[["geometry"]].copy()

    for column in target_columns:
        if column in source_gdf.columns:
            aligned[column] = source_gdf[column]
        else:
            aligned[column] = None

    ordered = aligned[target_columns + ["geometry"]]
    return gpd.GeoDataFrame(ordered, geometry="geometry", crs=source_gdf.crs)


def write_to_template(target_gdb: Path, target_layer: str, subset: gpd.GeoDataFrame) -> int:
    aligned = align_to_template_schema(target_gdb, target_layer, subset)

    # Lỗi: "Can only insert a Point in a esriGeometryPoint layer"
    # => Template layer yêu cầu Point nhưng dữ liệu thực tế có thể là Line/Polygon.
    # Chiến lược: đảm bảo dữ liệu đầu vào đúng type theo template.
    # - Nếu template là Point: convert mọi hình (Line/Polygon) sang Point đại diện.
    # - Nếu template là MultiPoint/Polygon/MultiPolygon tương ứng thì giữ đúng type (đúng như bạn yêu cầu).

    try:
        # rows=1 để lấy kiểu geometry mà layer template đang dùng.
        schema_gdf = gpd.read_file(target_gdb, layer=target_layer, rows=1)
        template_geom_types = set(schema_gdf.geometry.geom_type.unique().tolist())
    except Exception:
        template_geom_types = set()

    # Nếu không đọc được schema type thì fallback: chỉ ghi đè như cũ
    if not template_geom_types:
        if aligned.empty:
            return 0
        aligned.to_file(target_gdb, layer=target_layer, driver="OpenFileGDB", mode="a")
        return len(aligned)

    # Xác định template yêu cầu
    wants_point = bool(template_geom_types & {"Point", "MultiPoint"})
    wants_polygon = bool(template_geom_types & {"Polygon", "MultiPolygon"})
    wants_line = bool(template_geom_types & {"LineString", "MultiLineString"})

    if wants_point:
        # Convert mọi geometry không phải Point sang Point đại diện.
        # - Polygon/MultiPolygon => representative_point() (trả Point nằm trong polygon)
        # - LineString/MultiLineString => centroid (tạo Point đại diện)
        g = aligned.geometry
        point_series = []
        for geom in g:
            if geom is None or geom.is_empty:
                point_series.append(None)
                continue
            gt = geom.geom_type
            if gt == "Point":
                point_series.append(geom)
            elif gt == "MultiPoint":
                # Giữ đúng type: nếu layer template là MultiPoint thì giữ MultiPoint
                if "MultiPoint" in template_geom_types:
                    point_series.append(geom)
                else:
                    # MultiPoint -> Point lấy điểm đầu
                    point_series.append(list(geom.geoms)[0] if len(geom.geoms) else None)
            elif gt in {"Polygon", "MultiPolygon"}:
                pt = geom.representative_point()
                point_series.append(pt)
            elif gt in {"LineString", "MultiLineString"}:
                point_series.append(geom.centroid)
            else:
                # fallback: cố lấy representative point
                try:
                    point_series.append(geom.representative_point())
                except Exception:
                    point_series.append(geom.centroid)

        aligned = aligned.copy()
        aligned["geometry"] = point_series

        # ép cứng geometry type cho OpenFileGDB/ESRI
        # - Nếu template yêu cầu MultiPoint thì mọi hình đều phải là MultiPoint
        if "MultiPoint" in template_geom_types and "Point" not in template_geom_types:
            from shapely.geometry import MultiPoint as ShpMultiPoint
            aligned = aligned.copy()
            aligned["geometry"] = aligned.geometry.apply(
                lambda gg: None
                if gg is None or getattr(gg, "is_empty", True)
                else (gg if gg.geom_type == "MultiPoint" else ShpMultiPoint([gg]))
            )

        # - Nếu template yêu cầu Point thì mọi hình đều phải là Point
        if "Point" in template_geom_types:
            from shapely.geometry import Point as ShpPoint
            aligned = aligned.copy()
            aligned["geometry"] = aligned.geometry.apply(
                lambda gg: None
                if gg is None or getattr(gg, "is_empty", True)
                else (gg if gg.geom_type == "Point" else (list(gg.geoms)[0] if gg.geom_type == "MultiPoint" and len(gg.geoms) else getattr(gg, "centroid", None)))
            )

        # lọc chỉ đúng type mong muốn lần cuối
        aligned = aligned[aligned.geometry.notna()].copy()
        aligned = aligned[aligned.geometry.geom_type.isin(template_geom_types)].copy()


    elif wants_polygon:
        # Nếu template polygon nhưng source không phải polygon: convert sang polygon bằng buffer(0) (fallback)
        # (Trong thực tế cần chiến lược tốt hơn theo dữ liệu; nhưng để tránh crash thì buffer(0) giúp lấy polygon hợp lệ.)
        if any(gt in {"Point", "MultiPoint", "LineString", "MultiLineString"} for gt in aligned.geometry.geom_type.unique().tolist()):
            aligned = aligned.copy()
            aligned["geometry"] = aligned.geometry.apply(lambda gg: gg.buffer(0) if gg is not None and not gg.is_empty else gg)
        aligned = aligned[aligned.geometry.notna()].copy()
        aligned = aligned[aligned.geometry.geom_type.isin(template_geom_types)].copy()

    elif wants_line:
        if any(gt in {"Point", "MultiPoint", "Polygon", "MultiPolygon"} for gt in aligned.geometry.geom_type.unique().tolist()):
            # fallback convert polygon->line bằng boundary
            aligned = aligned.copy()
            aligned["geometry"] = aligned.geometry.apply(lambda gg: gg.boundary if gg is not None and not gg.is_empty else gg)
        aligned = aligned[aligned.geometry.notna()].copy()
        aligned = aligned[aligned.geometry.geom_type.isin(template_geom_types)].copy()

    # Nếu rỗng thì không ghi
    if aligned.empty:
        return 0

        # Chặn lần nữa trường hợp dữ liệu vẫn còn lẫn geometry type khác.
        allowed = aligned.geometry.geom_type.unique().tolist()
        if not set(allowed).issubset(template_geom_types):
            aligned = aligned[aligned.geometry.geom_type.isin(template_geom_types)].copy()
            if aligned.empty:
                return 0

        aligned.to_file(target_gdb, layer=target_layer, driver="OpenFileGDB", mode="a")
    return len(aligned)





def apply_template_mapping(run_id: str, template_choice: str) -> dict:
    run_info = load_run_info(run_id)
    config = load_mapping_config()

    # yêu cầu mới: mapping ghi vào CHỈ 1 gdb duy nhất tương ứng lựa chọn của UI.
    if template_choice == "ALL":
        raise ValueError("Chế độ mapping ALL không được hỗ trợ theo yêu cầu mới. Hãy chọn 1 trong 4 template.")

    # Build catalog (đồng thời đảm bảo template zip đã được giải nén)
    full_catalog = build_template_rule_catalog(config)
    template_gdb_map = extract_templates_if_needed()
    selected_templates = select_templates(template_choice, config)
    source_gdf = normalize_geometries(gpd.read_file(run_info["geojson_path"]))


    suggestion_map = {}
    for suggestion in run_info["layer_suggestions"]:
        if template_choice != "ALL" and suggestion["template_name"] != template_choice:
            continue
        if (
            suggestion["template_name"] in selected_templates
            and suggestion.get("target_layer")
            and suggestion.get("match_type") != "unmatched"
        ):
            suggestion_map[suggestion["source_layer"]] = suggestion

    mapped_root = OUTPUT_DIR / run_id / "mapped"
    mapped_root.mkdir(parents=True, exist_ok=True)
    unmatched_layers = set()
    template_summaries = []
    total_matched = 0

    if "Layer" in source_gdf.columns:
        grouped = source_gdf.groupby(source_gdf["Layer"].astype(str))
    else:
        grouped = [("NO_LAYER_FIELD", source_gdf)]

    grouped_subsets = {layer_name: subset.copy() for layer_name, subset in grouped}

    for template_name, _template_cfg in selected_templates.items():
        # Lấy gdb đã giải nén từ TEMP để đảm bảo đúng schema với catalog.
        template_path = template_gdb_map.get(template_name)
        if template_path is None or not template_path.exists():
            raise FileNotFoundError(f"Khong tim thay template gdb da giai nen cho template_name={template_name}")


        target_gdb = mapped_root / f"{template_name}.gdb"
        if target_gdb.exists():
            shutil.rmtree(target_gdb)

        # template_path là gdb đã giải nén.
        # copy ra để ghi dữ liệu mapping.
        shutil.copytree(template_path, target_gdb)

        matched_count = 0
        applied_rule_count = 0
        used_target_layers = set()
        _ = full_catalog.get(template_name, [])

        for layer_name, subset in grouped_subsets.items():
            suggestion = suggestion_map.get(layer_name)
            if not suggestion or suggestion["template_name"] != template_name:
                unmatched_layers.add(layer_name)
                continue

            target_layer = suggestion["target_layer"]
            if not target_layer:
                unmatched_layers.add(layer_name)
                continue

            matched_count += write_to_template(target_gdb, target_layer, subset)
            used_target_layers.add(target_layer)
            total_matched += len(subset)

        applied_rule_count = len(used_target_layers)
        template_summaries.append(
            {
                "template_name": template_name,
                "matched_count": matched_count,
                "applied_rule_count": applied_rule_count,
            }
        )

    # theo yêu cầu mới: mapping ghi vào CHỈ 1 gdb, nên zip cũng chỉ chứa 1 gdb
    package_path = OUTPUT_DIR / run_id / f"mapped_{template_choice}.zip"
    zip_folder(mapped_root, package_path)

    return {
        "selected_template": template_choice,
        "template_summaries": template_summaries,
        "total_matched": total_matched,
        "unmatched_layers": sorted(unmatched_layers),
        "download_url": url_for("download_mapped_package", run_id=run_id, template_choice=template_choice),
        "threshold_mode": "displayed_suggestions",
    }


@app.get("/")
def index():
    return render_page()


@app.post("/process")
def process_upload():
    uploaded_file = request.files.get("dwg_file")
    if uploaded_file is None or not uploaded_file.filename:
        return render_page(error="Chua chon file DWG.", status_code=400)

    suffix = Path(uploaded_file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return render_page(error="Chi ho tro file .dwg", status_code=400)

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
        return render_page(result=result)
    except Exception as exc:
        return render_page(error=str(exc), status_code=500)


@app.post("/map/<run_id>")
def map_to_templates(run_id: str):
    try:
        result = load_run_info(run_id)
        template_choice = request.form.get("template_choice", "ALL")
        mapping_result = apply_template_mapping(run_id, template_choice)
        return render_page(result=result, mapping_result=mapping_result)
    except Exception as exc:
        result = None
        try:
            result = load_run_info(run_id)
        except Exception:
            pass
        return render_page(result=result, error=str(exc), status_code=500)


@app.get("/download/<run_id>")
def download_zip(run_id: str):
    zip_path = OUTPUT_DIR / run_id / "shapefile_result.zip"
    if not zip_path.exists():
        abort(404)
    return send_file(zip_path, as_attachment=True, download_name="shapefile_result.zip")


@app.get("/download-mapped/<run_id>/<template_choice>")
def download_mapped_package(run_id: str, template_choice: str):
    zip_path = OUTPUT_DIR / run_id / f"mapped_{template_choice}.zip"
    if not zip_path.exists():
        abort(404)
    return send_file(zip_path, as_attachment=True, download_name=f"mapped_{template_choice}.zip")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
