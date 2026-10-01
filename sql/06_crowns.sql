-- 06_crowns.sql
-- Checks on the crowns drawn by QGIS model 01 (qgis/models/01_tree_crowns.model3),
-- loaded into analysis.crowns by src/beech/run_models.py. Crowns are linked
-- to trees by ASSET_ID, the council's stable identifier.

CREATE INDEX IF NOT EXISTS crowns_geom_idx  ON analysis.crowns USING gist (geom);
CREATE INDEX IF NOT EXISTS crowns_asset_idx ON analysis.crowns (asset_id);

-- The trees the model was asked to draw.
CREATE OR REPLACE VIEW analysis.crown_targets AS
SELECT *
FROM clean.trees
WHERE in_comparison AND in_study_area
  AND (dbh_cm >= 40 OR crown_width_m >= 10);

-- Large register trees with no canopy of 5 m or more where the register puts
-- them: felled since the LIDAR survey, planted small, misplaced points, or
-- crowns hidden under a building footprint. Worth a look; never silently lost.
CREATE OR REPLACE VIEW qa.targets_without_crown AS
SELECT t.asset_id, t.species_group, t.latin_name, t.dbh_cm, t.crown_width_m,
       t.site_name, t.site_type, t.geom
FROM analysis.crown_targets t
LEFT JOIN analysis.crowns c USING (asset_id)
WHERE c.asset_id IS NULL;

-- Crown size and height by species and size class.
CREATE OR REPLACE VIEW analysis.crown_summary AS
SELECT
    species_group,
    size_class,
    count(*)                                                        AS n_crowns,
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY crown_area_m2)::numeric) AS median_area_m2,
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY chm_max)::numeric, 1)    AS median_height_m,
    count(*) FILTER (WHERE crown_area_m2 >= 100)                    AS n_100m2_plus
FROM analysis.crowns
GROUP BY species_group, size_class
ORDER BY species_group, size_class;
