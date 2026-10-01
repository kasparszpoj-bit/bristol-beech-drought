-- 04_sentinel.sql
-- Sentinel-2 L2A scene inventory from the Earth Search STAC catalogue (AWS).
--
-- Collection choice (checked 29 September 2026): "sentinel-2-l2a" rather than
-- the consistently reprocessed "sentinel-2-c1-l2a", because Collection 1 has
-- no 2022 scenes over Bristol (a drought year this project needs) and none in
-- 2017. The cost is a processing change in January 2022 that added a +1000
-- offset to reflectance values. Each band records its own scale and offset,
-- stored here per scene, and every reflectance is computed as
--   DN * scale + offset
-- so values are comparable across the whole 2018 to 2026 series.

CREATE TABLE IF NOT EXISTS raw.s2_items (
    item_id             text PRIMARY KEY,
    collection          text        NOT NULL,
    acquired_at         timestamptz NOT NULL,
    platform            text,
    mgrs_tile           text,
    cloud_cover         numeric,          -- whole tile, not the study area
    processing_baseline text,
    boa_offset_applied  boolean,
    footprint           geometry(Geometry, 4326) NOT NULL,
    bands               jsonb NOT NULL,   -- href, scale, offset, nodata per band
    properties          jsonb NOT NULL,   -- full STAC properties, untouched
    run_id              integer NOT NULL REFERENCES qa.ingest_log (run_id)
);
CREATE INDEX IF NOT EXISTS s2_items_footprint_idx ON raw.s2_items USING gist (footprint);
CREATE INDEX IF NOT EXISTS s2_items_acquired_idx  ON raw.s2_items (acquired_at);

-- The study area: the envelope of every comparison tree inside the study
-- area (Bristol plus 3 km), plus 500 m.
CREATE OR REPLACE VIEW analysis.study_area AS
SELECT ST_Buffer(ST_Envelope(ST_Collect(geom)), 500)::geometry(Polygon, 27700) AS geom
FROM clean.trees
WHERE in_comparison AND in_study_area;

-- One scene per satellite pass. Where a pass appears more than once (two
-- MGRS tiles, or a reprocessed copy), keep the one covering most of the
-- study area, then the latest item id.
CREATE OR REPLACE VIEW analysis.s2_acquisitions AS
SELECT DISTINCT ON (i.platform, i.acquired_at::date)
    i.item_id,
    i.acquired_at,
    i.acquired_at::date                      AS acquired_on,
    extract(year FROM i.acquired_at)::int    AS year,
    extract(month FROM i.acquired_at)::int   AS month,
    i.platform,
    i.mgrs_tile,
    i.cloud_cover,
    i.processing_baseline,
    round((ST_Area(ST_Intersection(ST_Transform(i.footprint, 27700), a.geom))
           / ST_Area(a.geom))::numeric, 3)   AS study_area_coverage,
    i.bands
FROM raw.s2_items i
CROSS JOIN analysis.study_area a
WHERE ST_Intersects(ST_Transform(i.footprint, 27700), a.geom)
ORDER BY i.platform, i.acquired_at::date,
         ST_Area(ST_Intersection(ST_Transform(i.footprint, 27700), a.geom)) DESC,
         i.item_id DESC;

-- Candidate scenes for the analysis: May to October, nearly full coverage of
-- the study area, and tile cloud under 60% (per-pixel cloud is masked later
-- with the scene classification layer, so this is only a first sieve).
CREATE OR REPLACE VIEW analysis.s2_candidates AS
SELECT *
FROM analysis.s2_acquisitions
WHERE month BETWEEN 5 AND 10
  AND study_area_coverage >= 0.95
  AND cloud_cover < 60;

-- Data availability by year: the table behind the "how much data" statement.
CREATE OR REPLACE VIEW analysis.s2_availability AS
SELECT
    year,
    count(*)                                         AS passes_may_oct,
    count(*) FILTER (WHERE study_area_coverage >= 0.95)                     AS full_coverage,
    count(*) FILTER (WHERE study_area_coverage >= 0.95 AND cloud_cover < 60) AS candidates,
    count(*) FILTER (WHERE study_area_coverage >= 0.95 AND cloud_cover < 20) AS clear_under_20pct,
    count(*) FILTER (WHERE study_area_coverage >= 0.95 AND cloud_cover < 20
                       AND month IN (7, 8))                                AS clear_jul_aug
FROM analysis.s2_acquisitions
WHERE month BETWEEN 5 AND 10
GROUP BY year
ORDER BY year;
