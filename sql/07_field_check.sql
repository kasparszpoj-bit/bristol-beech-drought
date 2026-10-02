-- Field check: crown scores from QField, joined to the frozen sample.
--
-- Scores are loaded as returned into raw.field_returns by
-- src/beech/qfield.py (beech-load-field-returns). Nothing here changes them;
-- the views below decide what is compared and record why.

-- Trees whose score reflects something other than the 2026 drought, found
-- in the field. They stay in every table but are left out of the drought
-- comparison, with the reason written down.
-- (Not dropped on rerun: later views depend on it. The list below is the
-- whole list; any other row is removed.)
CREATE TABLE IF NOT EXISTS analysis.field_exclusions (
    asset_id text PRIMARY KEY,
    reason   text NOT NULL
);
CREATE TEMP TABLE exclusions_now (asset_id text, reason text) ON COMMIT DROP;
INSERT INTO exclusions_now VALUES
    ('PK41290', 'Dead monolith: the crown was cut off some time before 2026 and '
                'giant polypore fruits in a ring around the trunk. The register '
                'still lists it as a live 100 cm beech.');
DELETE FROM analysis.field_exclusions
WHERE asset_id NOT IN (SELECT asset_id FROM exclusions_now);
INSERT INTO analysis.field_exclusions
SELECT * FROM exclusions_now
ON CONFLICT (asset_id) DO UPDATE SET reason = EXCLUDED.reason;

-- The latest walk for each sample tree. Unvisited trees are kept, with
-- visited = false, so coverage is always visible next to the results.
CREATE OR REPLACE VIEW analysis.field_check AS
WITH latest AS (
    SELECT DISTINCT ON (asset_id) *
    FROM raw.field_returns
    ORDER BY asset_id, survey_time DESC
)
SELECT s.tree_no, s.asset_id, s.stratum, s.priority,
       t.species_group, t.size_class, t.site_name, t.latin_name, t.dbh_cm,
       r.asset_id IS NOT NULL AS visited,
       r.found, r.species_ok, r.defoliation, r.discolour, r.dieback,
       r.leaf_fall, r.mast, r.fungus, r.photo, r.notes, r.survey_time,
       x.reason AS excluded_reason,
       -- In the drought comparison: found, the species confirmed, and no
       -- field reason to set it aside.
       (r.found = 'found' AND r.species_ok = 'yes' AND x.asset_id IS NULL)
           AS compared,
       -- Visibly stressed: moderate or worse thinning or browning (ICP
       -- Forests class 2 or more), or dead branches or limbs.
       (r.defoliation >= 2 OR r.discolour >= 2
        OR r.dieback IN ('branches', 'limbs')) AS stressed,
       s.geom
FROM analysis.field_sample s
JOIN clean.trees t USING (asset_id)
LEFT JOIN latest r USING (asset_id)
LEFT JOIN analysis.field_exclusions x USING (asset_id);

-- Coverage and results by stratum and by species, plus the total.
CREATE OR REPLACE VIEW analysis.field_check_summary AS
SELECT CASE WHEN GROUPING(stratum) = 0 THEN 'stratum'
            WHEN GROUPING(species_group) = 0 THEN 'species'
            ELSE 'all' END AS level,
       coalesce(stratum, species_group, 'all') AS grp,
       count(*) AS issued,
       count(*) FILTER (WHERE visited) AS visited,
       count(*) FILTER (WHERE found = 'found') AS found,
       count(*) FILTER (WHERE compared) AS compared,
       round(avg(defoliation) FILTER (WHERE compared), 2) AS mean_defoliation,
       count(*) FILTER (WHERE compared AND defoliation >= 2) AS defoliation_2plus,
       count(*) FILTER (WHERE compared AND discolour >= 2) AS discolour_2plus,
       count(*) FILTER (WHERE compared AND dieback <> 'none') AS any_dieback,
       count(*) FILTER (WHERE compared AND stressed) AS stressed,
       count(*) FILTER (WHERE compared AND leaf_fall = 'heavy') AS heavy_leaf_fall,
       count(*) FILTER (WHERE compared AND mast = 'heavy') AS heavy_mast,
       count(*) FILTER (WHERE fungus IS NOT NULL AND fungus <> 'none') AS fungus
FROM analysis.field_check
GROUP BY GROUPING SETS ((stratum), (species_group), ())
ORDER BY level DESC, grp;

-- QA: every return must belong to the issued sample.
CREATE OR REPLACE VIEW qa.field_returns_unmatched AS
SELECT r.*
FROM raw.field_returns r
LEFT JOIN raw.field_sample_frozen f USING (asset_id)
WHERE f.asset_id IS NULL;

-- QA: the tree number must match the issued list, and the point must not
-- have been dragged in the app (it should sit on the register point).
CREATE OR REPLACE VIEW qa.field_returns_mismatch AS
SELECT r.asset_id, r.tree_no AS returned_tree_no, f.tree_no AS issued_tree_no,
       round(ST_Distance(r.geom, s.geom)::numeric, 1) AS moved_m
FROM raw.field_returns r
JOIN raw.field_sample_frozen f USING (asset_id)
JOIN analysis.field_sample s USING (asset_id)
WHERE r.tree_no <> f.tree_no OR ST_Distance(r.geom, s.geom) > 1;

-- QA: found trees with a score or the photo left blank.
CREATE OR REPLACE VIEW qa.field_returns_incomplete AS
SELECT tree_no, asset_id, stratum,
       concat_ws(', ',
           CASE WHEN species_ok IS NULL THEN 'species_ok' END,
           CASE WHEN defoliation IS NULL THEN 'defoliation' END,
           CASE WHEN discolour IS NULL THEN 'discolour' END,
           CASE WHEN dieback IS NULL THEN 'dieback' END,
           CASE WHEN leaf_fall IS NULL THEN 'leaf_fall' END,
           CASE WHEN mast IS NULL THEN 'mast' END,
           CASE WHEN fungus IS NULL THEN 'fungus' END,
           CASE WHEN photo IS NULL THEN 'photo' END) AS blank
FROM analysis.field_check
WHERE found = 'found'
  AND (species_ok IS NULL OR defoliation IS NULL OR discolour IS NULL
       OR dieback IS NULL OR leaf_fall IS NULL OR mast IS NULL
       OR fungus IS NULL OR photo IS NULL);

-- Opportunistic observations: trees reported because they looked unwell,
-- outside the random sample. Kept apart so they never bias the field check,
-- but they feed Chapter 2 (which beeches to inspect).
CREATE TABLE IF NOT EXISTS raw.opportunistic_obs (
    obs_id       serial PRIMARY KEY,
    asset_id     text,
    observed_on  date NOT NULL,
    observer     text NOT NULL,
    reported_as  text,
    crown_note   text,
    fungus       text,
    photo        text,
    geom         geometry(Point, 27700),
    UNIQUE (asset_id, observed_on)
);
INSERT INTO raw.opportunistic_obs
    (asset_id, observed_on, observer, reported_as, crown_note, fungus, photo, geom)
VALUES ('PK31500', '2026-10-02', 'KS', 'copper beech',
        'Large majority of leaves lost; crown very thin, looked severely stressed.',
        'meripilus',
        'data/field_returns/opportunistic/2026-10-02_PK31500/tree.jpg',
        ST_Transform(ST_SetSRID(ST_MakePoint(-2.588222, 51.473250), 4326), 27700))
ON CONFLICT (asset_id, observed_on) DO NOTHING;

ALTER TABLE raw.opportunistic_obs ADD COLUMN IF NOT EXISTS council_report text;
UPDATE raw.opportunistic_obs SET council_report =
    'FixMyStreet 10102007: fungus reported 15 Sept 2026 (Tree in poor health); '
    'council investigated, job raised with contractors 25 Sept 2026, report closed'
WHERE asset_id = 'PK31500' AND council_report IS NULL;
