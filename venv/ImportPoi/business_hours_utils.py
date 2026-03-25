import ast
import json
from datetime import date, datetime, time

import pandas as pd

BUSINESS_HOURS_COLUMNS = (
    "BusinessHours",
    "businessHours",
    "Time",
    "time",
    "Hours",
    "hours",
)


def is_blank(value):
    return pd.isna(value) or str(value).strip() == ""


def normalize_time_value(value):
    if is_blank(value):
        return None

    if isinstance(value, pd.Timestamp):
        return value.strftime("%H%M")

    if isinstance(value, datetime):
        return value.strftime("%H%M")

    if isinstance(value, time):
        return value.strftime("%H%M")

    if isinstance(value, date):
        return "0000"

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if 0 <= float(value) < 1:
            total_minutes = round(float(value) * 24 * 60)
            hours, minutes = divmod(total_minutes, 60)
            hours %= 24
            return f"{hours:02d}{minutes:02d}"

        text_value = f"{float(value):g}".strip()
    else:
        text_value = str(value).strip()

    for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"):
        try:
            return datetime.strptime(text_value, fmt).strftime("%H%M")
        except ValueError:
            continue

    if len(text_value) == 4 and text_value.isdigit():
        return text_value

    if len(text_value) == 5 and text_value[2] == ":":
        return text_value.replace(":", "")

    raise ValueError(f"Khong doc duoc dinh dang gio: {value}")


def normalize_day_value(value):
    if is_blank(value):
        raise ValueError("Thieu gia tri day cho businessHours.")

    if isinstance(value, str):
        normalized = value.strip().lower()
        day_aliases = {
            "0": 0,
            "1": 1,
            "2": 2,
            "3": 3,
            "4": 4,
            "5": 5,
            "6": 6,
            "sun": 0,
            "sunday": 0,
            "cn": 0,
            "mon": 1,
            "monday": 1,
            "thu2": 1,
            "t2": 1,
            "tue": 2,
            "tuesday": 2,
            "thu3": 2,
            "t3": 2,
            "wed": 3,
            "wednesday": 3,
            "thu4": 3,
            "t4": 3,
            "thu": 4,
            "thursday": 4,
            "thu5": 4,
            "t5": 4,
            "fri": 5,
            "friday": 5,
            "thu6": 5,
            "t6": 5,
            "sat": 6,
            "saturday": 6,
            "thu7": 6,
            "t7": 6,
        }
        if normalized in day_aliases:
            return day_aliases[normalized]

    try:
        day_value = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Gia tri day khong hop le: {value}") from exc

    if 1 <= day_value <= 7:
        return 0 if day_value == 7 else day_value

    if not 0 <= day_value <= 6:
        raise ValueError(f"Day phai nam trong khoang 0-6, nhan duoc {value}")

    return day_value


def parse_business_hours_value(raw_value):
    if is_blank(raw_value):
        return []

    parsed_value = raw_value
    if isinstance(raw_value, str):
        text_value = raw_value.strip()
        if not text_value:
            return []

        try:
            parsed_value = json.loads(text_value)
        except json.JSONDecodeError:
            try:
                parsed_value = ast.literal_eval(text_value)
            except (ValueError, SyntaxError) as exc:
                raise ValueError(
                    "BusinessHours/Time phai la JSON hoac Python list/dict hop le."
                ) from exc

    if isinstance(parsed_value, dict):
        parsed_items = [parsed_value]
    elif isinstance(parsed_value, list):
        parsed_items = parsed_value
    else:
        raise ValueError("BusinessHours/Time phai la list hoac dict.")

    normalized_items = []
    for item in parsed_items:
        if not isinstance(item, dict):
            raise ValueError("Moi businessHours item phai la object/dict.")

        if "open" in item and "close" in item:
            open_payload = item["open"]
            close_payload = item["close"]
            if not isinstance(open_payload, dict) or not isinstance(close_payload, dict):
                raise ValueError("open/close trong businessHours phai la dict.")

            day_open = normalize_day_value(open_payload.get("day"))
            day_close = normalize_day_value(close_payload.get("day"))
            time_open = normalize_time_value(open_payload.get("time"))
            time_close = normalize_time_value(close_payload.get("time"))
        else:
            day_open = normalize_day_value(
                item.get(
                    "open_day",
                    item.get("start_day", item.get("day", item.get("week_day"))),
                )
            )
            day_close = normalize_day_value(
                item.get(
                    "close_day",
                    item.get("end_day", item.get("day", item.get("week_day"))),
                )
            )
            time_open = normalize_time_value(
                item.get("open_time", item.get("start_time", item.get("from")))
            )
            time_close = normalize_time_value(
                item.get("close_time", item.get("end_time", item.get("to")))
            )

        normalized_items.append(
            {
                "open": {"day": day_open, "time": time_open},
                "close": {"day": day_close, "time": time_close},
            }
        )

    return normalized_items


def get_business_hours(row):
    raw_business_hours = None
    for column_name in BUSINESS_HOURS_COLUMNS:
        if column_name in row and not is_blank(row.get(column_name)):
            raw_business_hours = row.get(column_name)
            break

    return parse_business_hours_value(raw_business_hours)
