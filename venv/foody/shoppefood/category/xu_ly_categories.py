import io
import re
import unicodedata
from difflib import SequenceMatcher

import pandas as pd
import streamlit as st

SOURCE_CATEGORY_COLUMN = "categories"
MAP4D_NAME_COLUMN = "Tên"
MAP4D_IDENTIFIER_COLUMN = "Định danh"
OUTPUT_NAME_COLUMN = "map4d_ten"
OUTPUT_IDENTIFIER_COLUMN = "map4d_dinh_danh"

MANUAL_CATEGORY_MAP = {
    "an vat via he": "food_service",
    "an vat": "food_service",
    "via he": "food_service",
    "quan an": "eatery",
    "nha hang": "restaurant",
    "cafe dessert": "cafe",
    "cafe": "cafe",
    "ca phe dessert": "cafe",
    "ca phe": "cafe",
    "tra sua": "milk_tea",
    "tiem banh": "bakery",
    "giao com van phong": "food_service",
    "an chay": "food_service",
    "do an nhanh": "fast_food",
    "shop cua hang": "store",
    "shop online": "store",
    "mua sam online": "store",
    "cho": "local_market",
    "nha thuoc": "pharmacy",
    "khu am thuc": "food_service",
}

st.set_page_config(page_title="Xu ly categories Foody -> Map4D", layout="wide")
st.title("Xu ly categories Foody -> Map4D")


def normalize_text(value):
    text = "" if value is None else str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("đ", "d")
    text = re.sub(r"[/,_\\-]+", " ", text)
    text = re.sub(r"\\s+", " ", text)
    return text.strip()


def load_map4d_type_rows(uploaded_file):
    df = pd.read_excel(uploaded_file)

    missing_columns = [
        col for col in (MAP4D_NAME_COLUMN, MAP4D_IDENTIFIER_COLUMN) if col not in df.columns
    ]
    if missing_columns:
        raise ValueError(f"File type Map4D thieu cot: {', '.join(missing_columns)}")

    df = df.dropna(subset=[MAP4D_NAME_COLUMN, MAP4D_IDENTIFIER_COLUMN]).copy()
    df["normalized_name"] = df[MAP4D_NAME_COLUMN].map(normalize_text)
    return df.to_dict(orient="records")


def build_identifier_lookup(type_rows):
    return {row[MAP4D_IDENTIFIER_COLUMN]: row for row in type_rows}


def find_manual_match(normalized_category, identifier_lookup):
    for keyword, identifier in MANUAL_CATEGORY_MAP.items():
        if keyword in normalized_category and identifier in identifier_lookup:
            row = identifier_lookup[identifier]
            return {
                "matched_name": row[MAP4D_NAME_COLUMN],
                "identifier": row[MAP4D_IDENTIFIER_COLUMN],
                "score": 1.0,
                "match_type": "manual",
            }
    return None


def score_candidate(normalized_category, normalized_name):
    if not normalized_category or not normalized_name:
        return 0.0

    ratio = SequenceMatcher(None, normalized_category, normalized_name).ratio()
    category_tokens = set(normalized_category.split())
    name_tokens = set(normalized_name.split())
    overlap = len(category_tokens & name_tokens)
    token_score = overlap / max(len(category_tokens), len(name_tokens), 1)
    contains_bonus = 0.15 if (
        normalized_category in normalized_name or normalized_name in normalized_category
    ) else 0.0
    return ratio * 0.65 + token_score * 0.35 + contains_bonus


def map_single_category(category_value, type_rows, identifier_lookup):
    normalized_category = normalize_text(category_value)
    if not normalized_category:
        return None

    manual_match = find_manual_match(normalized_category, identifier_lookup)
    if manual_match:
        return manual_match

    best_row = None
    best_score = -1.0
    for row in type_rows:
        score = score_candidate(normalized_category, row["normalized_name"])
        if score > best_score:
            best_score = score
            best_row = row

    if not best_row:
        return None

    return {
        "matched_name": best_row[MAP4D_NAME_COLUMN],
        "identifier": best_row[MAP4D_IDENTIFIER_COLUMN],
        "score": round(best_score, 4),
        "match_type": "fuzzy",
    }


def split_categories_cell(value):
    if pd.isna(value):
        return []

    text = str(value).strip()
    if not text:
        return []

    return [item.strip() for item in text.split(",") if item.strip()]


def map_categories_cell(value, type_rows, identifier_lookup):
    matched_names = []
    matched_identifiers = []

    for category in split_categories_cell(value):
        mapped = map_single_category(category, type_rows, identifier_lookup)
        if not mapped:
            continue

        if mapped["identifier"] not in matched_identifiers:
            matched_names.append(mapped["matched_name"])
            matched_identifiers.append(mapped["identifier"])

    return ", ".join(matched_names), ", ".join(matched_identifiers)


def process_source_file(source_df, type_rows):
    if SOURCE_CATEGORY_COLUMN not in source_df.columns:
        raise ValueError(f"File nguon thieu cot '{SOURCE_CATEGORY_COLUMN}'.")

    identifier_lookup = build_identifier_lookup(type_rows)
    result_df = source_df.copy()

    mapped_values = result_df[SOURCE_CATEGORY_COLUMN].apply(
        lambda value: map_categories_cell(value, type_rows, identifier_lookup)
    )
    result_df[[OUTPUT_NAME_COLUMN, OUTPUT_IDENTIFIER_COLUMN]] = pd.DataFrame(
        mapped_values.tolist(),
        index=result_df.index,
    )
    return result_df


st.markdown("### B1: Tai file Excel can chuyen doi categories")
source_file = st.file_uploader(
    "Upload file nguon",
    type=["xlsx", "xls"],
    key="source_file",
)

st.markdown("### B2: Tai file Excel type Map4D chuan")
map4d_type_file = st.file_uploader(
    "Upload file type Map4D",
    type=["xlsx", "xls"],
    key="map4d_type_file",
)

if source_file and map4d_type_file:
    try:
        source_df = pd.read_excel(source_file)
        type_rows = load_map4d_type_rows(map4d_type_file)
    except Exception as exc:
        st.error(f"Khong doc duoc file: {exc}")
        st.stop()

    st.markdown("### B3: Xu ly chuyen doi")
    if st.button("Bat dau xu ly"):
        try:
            result_df = process_source_file(source_df, type_rows)
        except Exception as exc:
            st.error(str(exc))
            st.stop()

        st.success("Xu ly thanh cong.")
        st.dataframe(result_df.head(20), use_container_width=True)

        preview_columns = [
            col
            for col in (
                "Name",
                SOURCE_CATEGORY_COLUMN,
                OUTPUT_NAME_COLUMN,
                OUTPUT_IDENTIFIER_COLUMN,
            )
            if col in result_df.columns
        ]
        if preview_columns:
            st.markdown("### Preview anh xa")
            st.dataframe(result_df[preview_columns].head(20), use_container_width=True)

        st.markdown("### B4: Xuat file")
        output_buffer = io.BytesIO()
        with pd.ExcelWriter(output_buffer, engine="openpyxl") as writer:
            result_df.to_excel(writer, index=False, sheet_name="mapped_categories")

        output_buffer.seek(0)
        st.download_button(
            "Download file ket qua",
            data=output_buffer.getvalue(),
            file_name="mapped_categories_result.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
