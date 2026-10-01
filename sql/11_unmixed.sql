-- Unmixed tree readings: each crown's reading with its ground share removed.
--
-- A crown's pixels are part canopy, part ground. With f the canopy share
-- of the reading (analysis.crown_cover, from LIDAR) and the ground's own
-- reading from a ring around the crown on the same image
-- (analysis.ground_obs, model 03):
--
--     observed = f * tree + (1 - f) * ground
--     tree     = (observed - (1 - f) * ground) / f
--
-- Done image by image, because grass can brown or green within days.
-- Mixing is strictly linear in reflectance, not in a ratio index such as
-- NDVI; applied to the indices it is an approximation, good enough to
-- remove most of the ground's influence (see docs/methods.md). Dividing by
-- f magnifies noise, so only crowns at least half canopy are unmixed.

-- Crowns in dense groves have no open ground in their own ring. For them,
-- the ground is the median of the rings of crowns within 100 m that do
-- have ground on the same image. Built only for the crown-images that need
-- it.
DROP TABLE IF EXISTS analysis.ground_nearby CASCADE;
CREATE TABLE analysis.ground_nearby AS
WITH eligible AS (
    SELECT c.asset_id, ST_Centroid(cr.geom) AS pt
    FROM analysis.crown_cover c JOIN analysis.crowns cr USING (asset_id)
    WHERE c.canopy_share >= 0.5
), missing AS (
    SELECT o.item_id, o.asset_id
    FROM analysis.crown_obs o
    JOIN eligible e USING (asset_id)
    LEFT JOIN analysis.ground_obs g USING (item_id, asset_id)
    WHERE o.clear_frac >= 0.9 AND o.ndvi IS NOT NULL
      AND (g.ndvi IS NULL OR g.ndvi_px < 2)
), neighbours AS (
    SELECT e.asset_id, n.asset_id AS nb
    FROM eligible e
    JOIN analysis.crowns n ON ST_DWithin(ST_Centroid(n.geom), e.pt, 100)
    WHERE n.asset_id <> e.asset_id
      AND e.asset_id IN (SELECT asset_id FROM missing)
)
SELECT m.item_id, m.asset_id, count(*) AS rings,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY g.ndvi) AS ndvi,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY g.ndmi) AS ndmi,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY g.ndre) AS ndre
FROM missing m
JOIN neighbours n USING (asset_id)
JOIN analysis.ground_obs g ON g.item_id = m.item_id AND g.asset_id = n.nb
WHERE g.ndvi IS NOT NULL AND g.ndvi_px >= 2
GROUP BY m.item_id, m.asset_id;
ALTER TABLE analysis.ground_nearby ADD PRIMARY KEY (item_id, asset_id);

DROP VIEW IF EXISTS analysis.crown_obs_unmixed CASCADE;
CREATE VIEW analysis.crown_obs_unmixed AS
WITH ground AS (
    SELECT o.item_id, o.asset_id,
           CASE WHEN g.ndvi_px >= 2 THEN g.ndvi ELSE n.ndvi END AS ndvi,
           CASE WHEN g.ndvi_px >= 2 THEN g.ndmi ELSE n.ndmi END AS ndmi,
           CASE WHEN g.ndvi_px >= 2 THEN g.ndre ELSE n.ndre END AS ndre,
           CASE WHEN g.ndvi_px >= 2 THEN 'own ring' ELSE 'nearby rings' END AS source
    FROM analysis.crown_obs o
    LEFT JOIN analysis.ground_obs g USING (item_id, asset_id)
    LEFT JOIN analysis.ground_nearby n USING (item_id, asset_id)
)
SELECT o.item_id, o.asset_id, c.canopy_share AS f,
       (o.ndvi - (1 - c.canopy_share) * g.ndvi) / c.canopy_share AS ndvi,
       (o.ndmi - (1 - c.canopy_share) * g.ndmi) / c.canopy_share AS ndmi,
       (o.ndre - (1 - c.canopy_share) * g.ndre) / c.canopy_share AS ndre,
       g.ndvi AS ground_ndvi, g.source AS ground_source
FROM analysis.crown_obs o
JOIN analysis.crown_cover c USING (asset_id)
JOIN ground g USING (item_id, asset_id)
WHERE c.canopy_share >= 0.5
  AND o.clear_frac >= 0.9 AND o.ndvi IS NOT NULL
  AND g.ndvi IS NOT NULL;

-- Summer (July and August) median per crown per year, as in 09_metrics.sql,
-- for the unmixed tree signal and for the ground on its own.
DROP TABLE IF EXISTS analysis.crown_year_unmixed CASCADE;
CREATE TABLE analysis.crown_year_unmixed AS
SELECT u.asset_id, s.year, count(*) AS n_obs,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY u.ndvi) AS ndvi,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY u.ndmi) AS ndmi,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY u.ndre) AS ndre,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY u.ground_ndvi) AS ground_ndvi
FROM analysis.crown_obs_unmixed u
JOIN analysis.s2_candidates s USING (item_id)
WHERE s.month IN (7, 8)
GROUP BY u.asset_id, s.year;
ALTER TABLE analysis.crown_year_unmixed ADD PRIMARY KEY (asset_id, year);

CREATE OR REPLACE VIEW analysis.crown_baseline_unmixed AS
SELECT asset_id, count(*) AS base_years,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ndvi) AS ndvi_base,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ndmi) AS ndmi_base,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ndre) AS ndre_base,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ground_ndvi) AS ground_base
FROM analysis.crown_year_unmixed
WHERE year IN (2019, 2020, 2021, 2023, 2024)
GROUP BY asset_id;

CREATE OR REPLACE VIEW analysis.crown_anomaly_unmixed AS
SELECT y.asset_id, y.year, y.n_obs, b.base_years,
       y.ndvi - b.ndvi_base AS d_ndvi,
       y.ndmi - b.ndmi_base AS d_ndmi,
       y.ndre - b.ndre_base AS d_ndre,
       y.ground_ndvi - b.ground_base AS d_ground_ndvi
FROM analysis.crown_year_unmixed y
JOIN analysis.crown_baseline_unmixed b USING (asset_id);

-- Crowns fit for the unmixed comparison: at least half canopy, one whole
-- pixel or more, four normal years, little detached canopy, not set aside.
CREATE OR REPLACE VIEW analysis.crown_analysable_unmixed AS
SELECT c.asset_id, c.species_group, c.size_class, c.site_type, c.dbh_cm,
       c.crown_area_m2, cc.canopy_share, px.pixels, b.base_years
FROM analysis.crowns c
JOIN analysis.crown_cover cc USING (asset_id)
JOIN (SELECT asset_id, max(clear_px) AS pixels
      FROM analysis.crown_obs GROUP BY asset_id) px USING (asset_id)
JOIN analysis.crown_baseline_unmixed b USING (asset_id)
JOIN analysis.crown_pieces p USING (asset_id)
LEFT JOIN analysis.field_exclusions x USING (asset_id)
WHERE cc.canopy_share >= 0.5
  AND px.pixels >= 1
  AND b.base_years >= 4
  AND p.detached_share <= 0.1
  AND x.asset_id IS NULL;
