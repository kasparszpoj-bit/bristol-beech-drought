-- 01_schema.sql
-- Schemas and raw tables. Safe to rerun: nothing here drops data.
--
--   raw       data exactly as delivered by each source
--   clean     parsed, typed, validated versions of raw
--   analysis  derived results (crowns, satellite observations, metrics)
--   qa        ingest log, parse failures, data quality checks
--
-- Everything spatial is British National Grid, EPSG:27700.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS clean;
CREATE SCHEMA IF NOT EXISTS analysis;
CREATE SCHEMA IF NOT EXISTS qa;

-- One row per ingest run, so every loaded record can be traced to when and
-- how it was fetched, and the loaded count checked against the service.
CREATE TABLE IF NOT EXISTS qa.ingest_log (
    run_id        serial PRIMARY KEY,
    source        text        NOT NULL,
    where_clause  text,
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    service_count integer,
    loaded_count  integer
);

-- The council tree register, as delivered. Every attribute is kept in
-- jsonb untouched, including the "No Code Allocated" strings and the unit
-- text, so the cleaning in 02_clean.sql is fully reproducible and auditable.
CREATE TABLE IF NOT EXISTS raw.register_trees (
    objectid   bigint PRIMARY KEY,
    attributes jsonb   NOT NULL,
    geom       geometry(Point, 27700) NOT NULL,
    run_id     integer NOT NULL REFERENCES qa.ingest_log (run_id)
);

CREATE INDEX IF NOT EXISTS register_trees_geom_idx
    ON raw.register_trees USING gist (geom);

-- Administrative boundaries (ONS Open Geography, Open Government Licence).
CREATE TABLE IF NOT EXISTS raw.boundaries (
    code   text PRIMARY KEY,
    name   text NOT NULL,
    source text NOT NULL,
    geom   geometry(MultiPolygon, 27700) NOT NULL,
    run_id integer NOT NULL REFERENCES qa.ingest_log (run_id)
);

-- The field sample as issued to the field on 29 September 2026, keyed by the
-- council's ASSET_ID. Frozen: never redrawn. (The council's OBJECTIDs were
-- regenerated between 28 and 30 September 2026, so OBJECTID cannot be used
-- to identify a tree across downloads; ASSET_ID is stable and unique.)
CREATE TABLE IF NOT EXISTS raw.field_sample_frozen (
    asset_id  text PRIMARY KEY,
    tree_no   integer NOT NULL UNIQUE,
    stratum   text    NOT NULL,
    priority  integer NOT NULL,
    issued_on date    NOT NULL,
    source    text    NOT NULL
);

-- Field scores exactly as returned from QField, one row per tree per
-- returned file, so a later walk (for example a re-score in summer 2027)
-- adds rows rather than overwriting. Unvisited trees are not stored.
CREATE TABLE IF NOT EXISTS raw.field_returns (
    asset_id    text        NOT NULL,
    tree_no     integer     NOT NULL,
    found       text,
    species_ok  text,
    defoliation integer,
    discolour   integer,
    dieback     text,
    leaf_fall   text,
    mast        text,
    fungus      text,
    photo       text,
    notes       text,
    survey_time timestamptz,
    surveyor    text,
    geom        geometry(Point, 27700),
    return_file text        NOT NULL,
    loaded_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (asset_id, return_file)
);
