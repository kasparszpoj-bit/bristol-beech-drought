"""Load Met Office monthly station data into raw.met_station_monthly.

Source: Met Office historic station data (open), one text file per station.
Each data line reads: yyyy mm tmax tmin af rain sun, where values may carry
"*" (estimated) or "#" (automatic sunshine sensor), "---" means missing, and
recent lines end with "Provisional".
"""

import re

import requests

from beech.db import apply_sql, connect

BASE = "https://www.metoffice.gov.uk/pub/data/weather/uk/climate/stationdata"
STATIONS = {
    "Yeovilton": f"{BASE}/yeoviltondata.txt",
    "Cardiff Bute Park": f"{BASE}/cardiffdata.txt",
}
DATA_LINE = re.compile(r"^\s*(\d{4})\s+(\d{1,2})\s+(.*)$")


def _value(token: str) -> tuple[float | None, bool]:
    """('12.3*') -> (12.3, True); ('---') -> (None, False)."""
    estimated = "*" in token
    clean = token.replace("*", "").replace("#", "").strip()
    if clean in ("", "---"):
        return None, estimated
    return float(clean), estimated


def parse_line(line: str) -> dict | None:
    """Parse one data line; returns None for headers and blank lines."""
    m = DATA_LINE.match(line)
    if not m:
        return None
    tokens = m.group(3).split()
    provisional = bool(tokens) and tokens[-1].lower() == "provisional"
    if provisional:
        tokens = tokens[:-1]
    tokens = (tokens + ["---"] * 5)[:5]
    (tmax, e1), (tmin, e2), (af, e3), (rain, e4), (sun, e5) = map(_value, tokens)
    return {
        "year": int(m.group(1)),
        "month": int(m.group(2)),
        "tmax_c": tmax,
        "tmin_c": tmin,
        "air_frost_days": None if af is None else int(af),
        "rain_mm": rain,
        "sun_hours": sun,
        "estimated": any((e1, e2, e3, e4, e5)),
        "provisional": provisional,
        "raw_line": line.rstrip(),
    }


def main() -> None:
    apply_sql(["01_schema.sql", "03_weather.sql"])
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (portfolio research)"
    with connect() as conn:
        for station, url in STATIONS.items():
            r = session.get(url, timeout=60)
            r.raise_for_status()
            rows = [p for p in map(parse_line, r.text.splitlines()) if p]
            run_id = conn.execute(
                "INSERT INTO qa.ingest_log (source, where_clause) VALUES (%s, %s) "
                "RETURNING run_id",
                (url, station),
            ).fetchone()[0]
            conn.execute(
                "DELETE FROM raw.met_station_monthly WHERE station = %s", (station,)
            )
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO raw.met_station_monthly (station, year, month, "
                    "tmax_c, tmin_c, air_frost_days, rain_mm, sun_hours, estimated, "
                    "provisional, raw_line, run_id) VALUES (%(station)s, %(year)s, "
                    "%(month)s, %(tmax_c)s, %(tmin_c)s, %(air_frost_days)s, "
                    "%(rain_mm)s, %(sun_hours)s, %(estimated)s, %(provisional)s, "
                    "%(raw_line)s, %(run_id)s)",
                    [{**p, "station": station, "run_id": run_id} for p in rows],
                )
            conn.execute(
                "UPDATE qa.ingest_log SET loaded_count = %s, finished_at = now() "
                "WHERE run_id = %s",
                (len(rows), run_id),
            )
            first, last = rows[0], rows[-1]
            print(
                f"{station}: {len(rows)} months, "
                f"{first['year']}-{first['month']:02d} to "
                f"{last['year']}-{last['month']:02d}"
            )
        conn.commit()


if __name__ == "__main__":
    main()
