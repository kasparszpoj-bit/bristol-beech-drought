-- Drought metrics per crown: each tree's summer reading every year, and its
-- difference from the same tree's own normal years.
--
-- Normal (baseline) years: 2019, 2020, 2021, 2023, 2024. 2018 and 2022 are
-- known drought years that test the method; 2025 was also dry. Summer is
-- July and August, when drought stress shows most. A reading counts only if
-- at least 90% of the crown was clear of cloud in that image.

-- One row per crown per year: how many clear summer readings, and their
-- median (robust to a single hazy or mis-masked image).
DROP TABLE IF EXISTS analysis.crown_year CASCADE;
CREATE TABLE analysis.crown_year AS
SELECT asset_id, year,
       count(*) AS n_obs,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ndvi) AS ndvi,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ndmi) AS ndmi,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ndre) AS ndre
FROM analysis.crown_obs_dated
WHERE month IN (7, 8)
  AND clear_frac >= 0.9
  AND ndvi IS NOT NULL
GROUP BY asset_id, year;
ALTER TABLE analysis.crown_year ADD PRIMARY KEY (asset_id, year);

-- Each crown's normal: the median of its baseline years, and how much those
-- years vary (the yardstick for a z score).
CREATE OR REPLACE VIEW analysis.crown_baseline AS
SELECT asset_id,
       count(*) AS base_years,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ndvi) AS ndvi_base,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ndmi) AS ndmi_base,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ndre) AS ndre_base,
       stddev_samp(ndvi) AS ndvi_sd,
       stddev_samp(ndmi) AS ndmi_sd,
       stddev_samp(ndre) AS ndre_sd
FROM analysis.crown_year
WHERE year IN (2019, 2020, 2021, 2023, 2024)
GROUP BY asset_id;

-- Every crown-year against its own normal. Negative = less green, drier or
-- less chlorophyll than usual for that tree.
CREATE OR REPLACE VIEW analysis.crown_anomaly AS
SELECT y.asset_id, y.year, y.n_obs, b.base_years,
       y.ndvi, y.ndvi - b.ndvi_base AS d_ndvi,
       y.ndmi - b.ndmi_base AS d_ndmi,
       y.ndre - b.ndre_base AS d_ndre,
       (y.ndvi - b.ndvi_base) / nullif(b.ndvi_sd, 0) AS z_ndvi,
       (y.ndmi - b.ndmi_base) / nullif(b.ndmi_sd, 0) AS z_ndmi,
       (y.ndre - b.ndre_base) / nullif(b.ndre_sd, 0) AS z_ndre
FROM analysis.crown_year y
JOIN analysis.crown_baseline b USING (asset_id);

-- Detached canopy. Model 01 keeps all canopy in a tree's zone, and most
-- crowns come out in several pieces split by one or two gap pixels. Pieces
-- within 2 m of the piece at the tree are treated as the same crown; the
-- rest may be a neighbour's canopy caught by the search circle.
DROP TABLE IF EXISTS analysis.crown_pieces CASCADE;
CREATE TABLE analysis.crown_pieces AS
WITH parts AS (
    SELECT c.asset_id, (c.d).geom AS geom, ST_Area((c.d).geom) AS area,
           ST_Distance((c.d).geom, t.geom) AS dist
    FROM (SELECT asset_id, ST_Dump(geom) AS d FROM analysis.crowns) c
    JOIN clean.trees t USING (asset_id)
), clusters AS (
    SELECT *, ST_ClusterDBSCAN(geom, eps := 2, minpoints := 1)
                  OVER (PARTITION BY asset_id) AS cluster
    FROM parts
), anchor AS (
    SELECT DISTINCT ON (asset_id) asset_id, cluster
    FROM clusters
    ORDER BY asset_id, dist, area DESC
)
SELECT c.asset_id, count(*) AS pieces,
       1 - sum(c.area) FILTER (WHERE c.cluster = a.cluster) / sum(c.area)
           AS detached_share
FROM clusters c
JOIN anchor a USING (asset_id)
GROUP BY c.asset_id;
ALTER TABLE analysis.crown_pieces ADD PRIMARY KEY (asset_id);

-- Crowns fit for comparison: at least two 10 m pixels, at least four of
-- the five baseline years observed, at most 10% of the crown detached, and
-- trees not set aside in the field.
CREATE OR REPLACE VIEW analysis.crown_analysable AS
SELECT c.asset_id, c.species_group, c.size_class, c.site_type, c.dbh_cm,
       c.crown_area_m2, c.chm_max, px.pixels, b.base_years, p.detached_share
FROM analysis.crowns c
JOIN (SELECT asset_id, max(clear_px) AS pixels
      FROM analysis.crown_obs GROUP BY asset_id) px USING (asset_id)
JOIN analysis.crown_baseline b USING (asset_id)
JOIN analysis.crown_pieces p USING (asset_id)
LEFT JOIN analysis.field_exclusions x USING (asset_id)
WHERE px.pixels >= 2
  AND b.base_years >= 4
  AND p.detached_share <= 0.1
  AND x.asset_id IS NULL;
