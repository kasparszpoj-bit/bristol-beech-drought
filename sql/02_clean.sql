-- 02_clean.sql
-- Turns raw.register_trees into clean.trees. Rebuilt from scratch on every
-- run, so it always reflects the latest raw load.
--
-- Problems in the council register that this file handles (counted on
-- 28 September 2026):
--   * DBH, crown height and crown width are text with the unit inside the
--     value ("15 Metres", "32 Centimetres"), so they must be parsed.
--   * Typos inside those values: "36 Centrimetres", "93  Centimetres".
--   * "No Code Allocated" is used in place of null.
--   * LATIN_NAME mixes species, cultivars and genus-only records
--     ("Tilia - Species Unknown").
--   * Planting season is text ("Planting Season 19/20").

------------------------------------------------------------------------
-- Parsing functions
------------------------------------------------------------------------

-- Returns the number in a "<number> <unit>" string if the unit is the one
-- expected ('cm' or 'm'), otherwise NULL. Tolerates repeated spaces and the
-- "Centrimetres" typo.
CREATE OR REPLACE FUNCTION clean.parse_measure(raw_value text, expected_unit text)
RETURNS numeric
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN m IS NULL THEN NULL
        WHEN expected_unit = 'cm' AND m[2] ~* '^(centr?imetres?|cm)$' THEN m[1]::numeric
        WHEN expected_unit = 'm'  AND m[2] ~* '^(metres?|m)$'         THEN m[1]::numeric
        ELSE NULL
    END
    FROM (
        SELECT regexp_match(
            raw_value,
            '^\s*(\d+(?:\.\d+)?)\s*([A-Za-z]+)\s*$'
        ) AS m
    ) s
$$;

-- Classifies a measurement string: 'ok', 'missing' (null, empty or
-- "No Code Allocated") or 'unparsed' (something else, which is logged).
CREATE OR REPLACE FUNCTION clean.measure_status(raw_value text, expected_unit text)
RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN raw_value IS NULL
          OR btrim(raw_value) = ''
          OR btrim(raw_value) ILIKE 'No Code Allocated' THEN 'missing'
        WHEN clean.parse_measure(raw_value, expected_unit) IS NOT NULL THEN 'ok'
        ELSE 'unparsed'
    END
$$;

-- "Planting Season 19/20" -> 2019. Two-digit years above 30 are read as 19xx.
CREATE OR REPLACE FUNCTION clean.parse_planting_year(raw_value text)
RETURNS integer
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN m IS NULL THEN NULL
        WHEN m[1]::int > 30 THEN 1900 + m[1]::int
        ELSE 2000 + m[1]::int
    END
    FROM (SELECT regexp_match(raw_value, '(\d{2})\s*/\s*\d{2}') AS m) s
$$;

------------------------------------------------------------------------
-- Species lookup, rebuilt from the names actually present in raw
------------------------------------------------------------------------

DROP TABLE IF EXISTS clean.species_lookup CASCADE;
CREATE TABLE clean.species_lookup AS
WITH names AS (
    SELECT attributes->>'LATIN_NAME' AS latin_name, count(*) AS n_records
    FROM raw.register_trees
    GROUP BY 1
)
SELECT
    latin_name,
    n_records,
    CASE
        WHEN latin_name ~* '^Fagus'                                       THEN 'beech'
        WHEN latin_name ~* '^Quercus (robur|petraea)'                     THEN 'oak'
        WHEN latin_name ~* '^Quercus (ilex|suber|x hispanica|x turneri)'  THEN 'oak_evergreen'
        WHEN latin_name ~* '^Quercus - Species Unknown'                   THEN 'oak_unknown'
        WHEN latin_name ~* '^Quercus'                                     THEN 'oak_other'
        WHEN latin_name ~* '^Tilia'                                       THEN 'lime'
        WHEN latin_name ~* '^Platanus'                                    THEN 'plane'
        WHEN latin_name ~* '^Acer pseudoplatanus'                         THEN 'sycamore'
        ELSE 'other'
    END AS species_group,
    -- Genus-only records ("Fagus - Species Unknown") keep their group but
    -- are marked, so they can be excluded from species-level statements.
    coalesce(latin_name ~* 'Species Unknown', latin_name IS NULL) AS genus_only,
    -- Purple foliage lowers greenness indices, so purple trees are compared
    -- against their own baseline and reported separately where it matters.
    coalesce(latin_name ~* '(Purpurea|Purpureum|Dawyck Purple|Rohanii)', false) AS purple_leaved,
    NULLIF(btrim(regexp_replace(latin_name,
        '^(\S+\s+(x\s+)?\S+|\S+\s+-\s+Species Unknown)\s*', '')), '') AS cultivar
FROM names;

-- The five groups compared in the analysis. Evergreen oaks behave
-- differently in drought, and "oak_other" mixes many exotic species, so
-- neither is in the main comparison.
ALTER TABLE clean.species_lookup ADD COLUMN in_comparison boolean;
UPDATE clean.species_lookup
SET in_comparison = species_group IN ('beech', 'oak', 'lime', 'plane', 'sycamore');

------------------------------------------------------------------------
-- The cleaned tree table
------------------------------------------------------------------------

DROP TABLE IF EXISTS clean.trees CASCADE;
CREATE TABLE clean.trees AS
SELECT
    r.objectid,
    a->>'ASSET_ID'                                        AS asset_id,
    a->>'SITE_NAME'                                       AS site_name,
    regexp_replace(a->>'TYPE', '^PK:\s*Tree\s*-\s*', '')  AS site_type,
    s.latin_name,
    a->>'COMMON_NAME'                                     AS common_name,
    s.species_group,
    s.in_comparison,
    s.genus_only,
    s.purple_leaved,
    s.cultivar,
    clean.parse_measure(a->>'DBH', 'cm')                  AS dbh_cm,
    clean.parse_measure(a->>'CROWN_HEIGHT', 'm')          AS crown_height_m,
    clean.parse_measure(a->>'CROWN_WIDTH', 'm')           AS crown_width_m,
    NULLIF(a->>'LOCATION_RISK_ZONE', 'No Code Allocated') AS risk_zone,
    clean.parse_planting_year(a->>'PLANTING_SEASON')      AS planting_year,
    (a->>'DEAD') = 'Y' OR (a->>'DEAD_FLAG') = 'Y'         AS dead,
    r.run_id,
    r.geom
FROM raw.register_trees r
CROSS JOIN LATERAL (SELECT r.attributes AS a) x
JOIN clean.species_lookup s ON s.latin_name IS NOT DISTINCT FROM a->>'LATIN_NAME';

ALTER TABLE clean.trees ADD PRIMARY KEY (objectid);
CREATE INDEX trees_geom_idx ON clean.trees USING gist (geom);
CREATE INDEX trees_group_idx ON clean.trees (species_group);

-- Study area: inside Bristol or within 3 km of its boundary. This keeps
-- council land just over the line (such as Ashton Court) and drops distant
-- council sites (a special school near Chippenham and a field centre in the
-- Forest of Dean, 13 trees, no beeches).
ALTER TABLE clean.trees ADD COLUMN in_study_area boolean;
UPDATE clean.trees t
SET in_study_area = EXISTS (
    SELECT 1 FROM raw.boundaries b
    WHERE b.code = 'E06000023' AND ST_DWithin(t.geom, b.geom, 3000)
);

-- Size classes by trunk diameter. DBH is the age proxy in this project:
-- bigger trees of the same species are, on the whole, older.
ALTER TABLE clean.trees ADD COLUMN size_class text;
UPDATE clean.trees SET size_class = CASE
    WHEN dbh_cm IS NULL THEN 'unknown'
    WHEN dbh_cm < 20    THEN '1: under 20 cm'
    WHEN dbh_cm < 50    THEN '2: 20 to 49 cm'
    WHEN dbh_cm < 80    THEN '3: 50 to 79 cm'
    ELSE                     '4: 80 cm and over'
END;

------------------------------------------------------------------------
-- Data quality outputs
------------------------------------------------------------------------

-- Every measurement string that is neither a valid value nor an explicit
-- "missing" code. Reviewed by hand, never silently dropped.
DROP TABLE IF EXISTS qa.parse_failures;
CREATE TABLE qa.parse_failures AS
SELECT r.objectid, f.field, f.raw_value, f.expected_unit
FROM raw.register_trees r
CROSS JOIN LATERAL (VALUES
    ('DBH',          r.attributes->>'DBH',          'cm'),
    ('CROWN_HEIGHT', r.attributes->>'CROWN_HEIGHT', 'm'),
    ('CROWN_WIDTH',  r.attributes->>'CROWN_WIDTH',  'm')
) AS f(field, raw_value, expected_unit)
WHERE clean.measure_status(f.raw_value, f.expected_unit) = 'unparsed';

-- Values that parse but are not believable for a UK street or park tree.
CREATE OR REPLACE VIEW qa.implausible_values AS
SELECT objectid, species_group, latin_name, dbh_cm, crown_height_m, crown_width_m,
       concat_ws('; ',
           CASE WHEN dbh_cm > 300          THEN 'DBH over 3 m' END,
           CASE WHEN crown_height_m > 45   THEN 'height over 45 m' END,
           CASE WHEN crown_width_m > 40    THEN 'crown over 40 m wide' END,
           CASE WHEN dbh_cm = 0 OR crown_height_m = 0 OR crown_width_m = 0
                                           THEN 'zero value' END
       ) AS problem
FROM clean.trees
WHERE dbh_cm > 300 OR crown_height_m > 45 OR crown_width_m > 40
   OR dbh_cm = 0 OR crown_height_m = 0 OR crown_width_m = 0;

-- Trees left out of the study area, for the record.
CREATE OR REPLACE VIEW qa.outside_study_area AS
SELECT site_name, site_type, species_group, count(*) AS n_trees
FROM clean.trees
WHERE NOT in_study_area
GROUP BY 1, 2, 3
ORDER BY n_trees DESC;

-- Completeness by species group: the headline data quality table.
CREATE OR REPLACE VIEW qa.completeness AS
SELECT
    species_group,
    count(*)                                                        AS n_trees,
    round(100.0 * count(*) FILTER (WHERE dbh_cm IS NULL) / count(*), 1)         AS pct_no_dbh,
    round(100.0 * count(*) FILTER (WHERE crown_height_m IS NULL) / count(*), 1) AS pct_no_height,
    round(100.0 * count(*) FILTER (WHERE crown_width_m IS NULL) / count(*), 1)  AS pct_no_crown_width,
    count(*) FILTER (WHERE dead)                                    AS n_flagged_dead
FROM clean.trees
GROUP BY species_group
ORDER BY n_trees DESC;
