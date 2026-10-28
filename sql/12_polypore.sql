-- 12_polypore.sql
-- Phase 2: giant polypore records, recording effort, and infected sites.
--
-- A record is one sighting. The same tree is often recorded many times, by
-- different people and in different years, so the unit for analysis is a
-- site: precise records (located to 30 m or better) within 15 m of each
-- other are one site, roughly one tree or one tight group of trees.
-- Records located worse than 30 m are kept for counts only.

CREATE TABLE IF NOT EXISTS raw.polypore_records (
    record_id   serial PRIMARY KEY,
    source      text    NOT NULL CHECK (source IN ('inaturalist', 'nbn', 'other')),
    source_id   text    NOT NULL,
    observed_on date,
    accuracy_m  numeric,           -- radius of location uncertainty
    quality     text,              -- iNaturalist grade: research, needs_id
    licence     text,              -- records with NC licences stay out of the repo
    dataset     text,
    url         text,
    geom        geometry(Point, 27700) NOT NULL,
    run_id      integer NOT NULL REFERENCES qa.ingest_log (run_id),
    UNIQUE (source, source_id)
);
CREATE INDEX IF NOT EXISTS polypore_records_geom_idx
    ON raw.polypore_records USING gist (geom);

-- iNaturalist counts in the same 12 km circle, per year and date window:
-- Meripilus records, and all fungus records as the effort measure.
--   to_date  1 August to today's day and month, so the unfinished current
--            season is compared like for like with earlier years
--   full     1 August to 31 December, finished years only
CREATE TABLE IF NOT EXISTS raw.inat_effort (
    year          integer NOT NULL,
    season_window text    NOT NULL CHECK (season_window IN ('to_date', 'full')),
    d1            date    NOT NULL,
    d2            date    NOT NULL,
    meripilus     integer NOT NULL,
    fungi         integer NOT NULL,
    run_id        integer NOT NULL REFERENCES qa.ingest_log (run_id),
    PRIMARY KEY (year, season_window)
);
-- All iNaturalist records (any taxon), added 28 October 2026: steadier as
-- an effort measure than fungus records, which fall in a poor fungus year.
ALTER TABLE raw.inat_effort ADD COLUMN IF NOT EXISTS all_records integer;

-- Precise records grouped into sites.
DROP TABLE IF EXISTS analysis.polypore_sites CASCADE;
CREATE TABLE analysis.polypore_sites AS
WITH precise AS (
    SELECT record_id, observed_on, geom,
           ST_ClusterDBSCAN(geom, eps := 15, minpoints := 1) OVER () AS site_id
    FROM raw.polypore_records
    WHERE accuracy_m <= 30
)
SELECT
    site_id,
    count(*)                                   AS n_records,
    min(observed_on)                           AS first_seen,
    max(observed_on)                           AS last_seen,
    array_agg(DISTINCT extract(year FROM observed_on)::int
              ORDER BY extract(year FROM observed_on)::int) AS years_seen,
    ST_Centroid(ST_Collect(geom))::geometry(Point, 27700) AS geom
FROM precise
GROUP BY site_id;
CREATE INDEX ON analysis.polypore_sites USING gist (geom);

-- Each site's nearest register tree and nearest register beech (KNN on the
-- GiST index). Matched when within 20 m.
DROP TABLE IF EXISTS analysis.polypore_site_trees;
CREATE TABLE analysis.polypore_site_trees AS
SELECT
    s.site_id,
    t.asset_id    AS nearest_tree,
    t.common_name AS nearest_tree_species,
    round(t.dist::numeric, 1) AS nearest_tree_m,
    b.asset_id    AS nearest_beech,
    round(b.dist::numeric, 1) AS nearest_beech_m,
    b.dbh_cm      AS nearest_beech_dbh_cm,
    b.site_name   AS nearest_beech_site,
    ST_Within(s.geom, bd.geom) AS in_bristol
FROM analysis.polypore_sites s
CROSS JOIN LATERAL (
    SELECT asset_id, common_name, ST_Distance(s.geom, c.geom) AS dist
    FROM clean.trees c
    ORDER BY s.geom <-> c.geom
    LIMIT 1
) t
CROSS JOIN LATERAL (
    SELECT asset_id, dbh_cm, site_name, ST_Distance(s.geom, c.geom) AS dist
    FROM clean.trees c
    WHERE c.latin_name LIKE 'Fagus%'
    ORDER BY s.geom <-> c.geom
    LIMIT 1
) b
LEFT JOIN raw.boundaries bd ON bd.code = 'E06000023';

-- The season question: were there more records this year than usual, once
-- recording effort is allowed for? Records per 1,000 fungus records, and
-- sites seen for the first time (new trees, not repeat visits).
CREATE OR REPLACE VIEW analysis.polypore_by_year AS
WITH first_year AS (
    SELECT extract(year FROM first_seen)::int AS year, count(*) AS new_sites
    FROM analysis.polypore_sites
    GROUP BY 1
)
SELECT
    e.year,
    e.season_window,
    e.meripilus,
    e.fungi,
    round(1000.0 * e.meripilus / nullif(e.fungi, 0), 1) AS per_1000_fungi,
    e.all_records,
    round(1000.0 * e.meripilus / nullif(e.all_records, 0), 2) AS per_1000_all,
    coalesce(f.new_sites, 0) AS new_sites_all_year
FROM raw.inat_effort e
LEFT JOIN first_year f USING (year)
ORDER BY e.season_window, e.year;
