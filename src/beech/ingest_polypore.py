"""Load giant polypore records and recording effort into PostGIS.

Sources (both open APIs, no key):
- iNaturalist: every verifiable Meripilus giganteus record within 12 km of
  the centre, plus yearly counts of all fungus records and all records in
  the same circle and date window. These are the effort measures: more
  people recording means more polypore records even if the fungus is no
  commoner.
- NBN Atlas: the same species and circle. In Bristol none of its records
  come from iNaturalist, so the two sources do not overlap.

Observer names and photos are not stored.
"""

import datetime as dt
import time

import requests

from beech.db import apply_sql, connect

CENTRE = (51.4545, -2.5879)  # lat, lon of Bristol centre
RADIUS_KM = 12
MERIPILUS = 157989  # iNaturalist taxon id
FUNGI = 47170
INAT = "https://api.inaturalist.org/v1/observations"
NBN = "https://records-ws.nbnatlas.org/occurrences/search"
NBN_FIELDS = (
    "id,eventDate,decimalLatitude,decimalLongitude,"
    "coordinateUncertaintyInMeters,year,month,dataResourceName,license"
)
EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)
FIRST_YEAR = 2016  # iNaturalist use in Bristol is too thin before this


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "bristol-beech-drought (portfolio research)"
    return s


def _circle() -> dict:
    return {"lat": CENTRE[0], "lng": CENTRE[1], "radius": RADIUS_KM}


def inat_row(obs: dict) -> dict | None:
    """One iNaturalist observation -> a record row; None without a location."""
    geo = obs.get("geojson")
    if not geo:
        return None
    lon, lat = geo["coordinates"]
    return {
        "source": "inaturalist",
        "source_id": str(obs["id"]),
        "observed_on": obs.get("observed_on"),
        "lat": lat,
        "lon": lon,
        "accuracy_m": obs.get("positional_accuracy"),
        "quality": obs.get("quality_grade"),
        "licence": obs.get("license_code"),
        "dataset": "iNaturalist",
        "url": f"https://www.inaturalist.org/observations/{obs['id']}",
    }


def nbn_row(occ: dict) -> dict | None:
    """One NBN Atlas occurrence -> a record row; None without a location."""
    if occ.get("decimalLatitude") is None:
        return None
    ms = occ.get("eventDate")
    day = (
        # epoch plus offset, as Windows rejects negative timestamps (pre-1970)
        (EPOCH + dt.timedelta(milliseconds=ms)).date().isoformat()
        if ms is not None
        else None
    )
    return {
        "source": "nbn",
        "source_id": occ["uuid"],
        "observed_on": day,
        "lat": occ["decimalLatitude"],
        "lon": occ["decimalLongitude"],
        "accuracy_m": occ.get("coordinateUncertaintyInMeters"),
        "quality": None,
        "licence": occ.get("license"),
        "dataset": occ.get("dataResourceName"),
        "url": f"https://records.nbnatlas.org/occurrences/{occ['uuid']}",
    }


def fetch_inat(s: requests.Session, area: dict | None = None) -> list[dict]:
    """All verifiable records in the area (default: the Bristol circle)."""
    rows, id_above = [], 0
    while True:
        r = s.get(
            INAT,
            params={
                **(area or _circle()),
                "taxon_id": MERIPILUS,
                "verifiable": "true",
                "per_page": 200,
                "order_by": "id",
                "order": "asc",
                "id_above": id_above,
            },
            timeout=60,
        )
        r.raise_for_status()
        page = r.json()["results"]
        if not page:
            return [row for row in map(inat_row, rows) if row]
        rows += page
        id_above = page[-1]["id"]
        time.sleep(1)


def fetch_nbn(s: requests.Session) -> list[dict]:
    r = s.get(
        NBN,
        params={
            "q": 'taxon_name:"Meripilus giganteus"',
            "lat": CENTRE[0],
            "lon": CENTRE[1],
            "radius": RADIUS_KM,
            "pageSize": 1000,
            "fl": NBN_FIELDS,
        },
        timeout=60,
    )
    r.raise_for_status()
    return [row for row in map(nbn_row, r.json()["occurrences"]) if row]


def effort_windows(today: dt.date) -> list[tuple[int, str, dt.date, dt.date]]:
    """Per year: the season to date (1 Aug to today's day and month), which
    compares every year like for like with the unfinished current season,
    and the full season (1 Aug to 31 Dec) for finished years."""
    out = []
    for y in range(FIRST_YEAR, today.year + 1):
        out.append((y, "to_date", dt.date(y, 8, 1), today.replace(year=y)))
        if y < today.year:
            out.append((y, "full", dt.date(y, 8, 1), dt.date(y, 12, 31)))
    return out


def inat_count(
    s: requests.Session, taxon: int | None, d1: dt.date, d2: dt.date,
    area: dict | None = None,
) -> int:
    """Verifiable records in the area and window; taxon None counts all."""
    r = s.get(
        INAT,
        params={
            **(area or _circle()),
            **({"taxon_id": taxon} if taxon else {}),
            "verifiable": "true",
            "d1": d1.isoformat(),
            "d2": d2.isoformat(),
            "per_page": 0,
        },
        timeout=60,
    )
    r.raise_for_status()
    time.sleep(1)
    return r.json()["total_results"]


def main() -> None:
    apply_sql(["01_schema.sql", "12_polypore.sql"])
    s = _session()
    records = fetch_inat(s) + fetch_nbn(s)
    today = dt.datetime.now(dt.UTC).date()
    effort = [
        {
            "year": y,
            "season_window": w,
            "d1": d1,
            "d2": d2,
            "meripilus": inat_count(s, MERIPILUS, d1, d2),
            "fungi": inat_count(s, FUNGI, d1, d2),
            "all_records": inat_count(s, None, d1, d2),
        }
        for y, w, d1, d2 in effort_windows(today)
    ]
    with connect() as conn:
        run_id = conn.execute(
            "INSERT INTO qa.ingest_log (source, where_clause) VALUES (%s, %s) "
            "RETURNING run_id",
            ("iNaturalist + NBN Atlas", f"Meripilus giganteus, {RADIUS_KM} km"),
        ).fetchone()[0]
        conn.execute("DELETE FROM raw.polypore_records")
        conn.execute("DELETE FROM raw.inat_effort")
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO raw.polypore_records (source, source_id, observed_on, "
                "accuracy_m, quality, licence, dataset, url, geom, run_id) VALUES "
                "(%(source)s, %(source_id)s, %(observed_on)s, %(accuracy_m)s, "
                "%(quality)s, %(licence)s, %(dataset)s, %(url)s, ST_Transform("
                "ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326), 27700), "
                "%(run_id)s)",
                [{**r, "run_id": run_id} for r in records],
            )
            cur.executemany(
                "INSERT INTO raw.inat_effort (year, season_window, d1, d2, "
                "meripilus, fungi, all_records, run_id) VALUES (%(year)s, "
                "%(season_window)s, %(d1)s, %(d2)s, %(meripilus)s, %(fungi)s, "
                "%(all_records)s, %(run_id)s)",
                [{**e, "run_id": run_id} for e in effort],
            )
        conn.execute(
            "UPDATE qa.ingest_log SET loaded_count = %s, finished_at = now() "
            "WHERE run_id = %s",
            (len(records), run_id),
        )
        conn.commit()
    apply_sql(["12_polypore.sql"])  # rebuild the derived tables on new data
    n_inat = sum(r["source"] == "inaturalist" for r in records)
    print(f"{n_inat} iNaturalist and {len(records) - n_inat} NBN records")
    print(f"effort: {len(effort)} year windows")


if __name__ == "__main__":
    main()
