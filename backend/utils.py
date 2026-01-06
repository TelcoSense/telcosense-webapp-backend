from datetime import datetime, timezone


def extract_timestamp_and_score(filename: str):
    stem = filename[:-4]  # strip ".png" / ".json" / etc.
    parts = stem.split("_")
    # old format: YYYY-MM-DD_HHMM
    if len(parts) == 2:
        ts = datetime.strptime(stem, "%Y-%m-%d_%H%M").replace(tzinfo=timezone.utc)
        return ts, None
    # new format: YYYY-MM-DD_HHMM_<score>
    if len(parts) >= 3:
        ts_str = "_".join(parts[:2])  # YYYY-MM-DD_HHMM
        ts = datetime.strptime(ts_str, "%Y-%m-%d_%H%M").replace(tzinfo=timezone.utc)
        try:
            score = float(parts[2])
        except ValueError:
            score = None
        return ts, score
    raise ValueError(f"Unrecognized filename format: {filename}")


def parse_isoformat_z(dt_str: str) -> datetime:
    if dt_str.endswith("Z"):
        dt_str = dt_str.replace("Z", "+00:00")
    return datetime.fromisoformat(dt_str).astimezone(timezone.utc)
