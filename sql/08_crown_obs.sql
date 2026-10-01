-- Satellite readings per crown per scene, from QGIS model 02.
--
-- Loaded by src/beech/crown_indices.py (beech-crown-indices). Tables are
-- created only if missing, so rerunning the SQL never discards a two hour
-- model run; the loader replaces their contents.

-- One row per crown per scene. clear_px is every pixel in the crown,
-- clear_frac the share not masked as cloud, shadow or snow; ndvi_px the
-- clear pixels the indices were averaged over. Pixel counts can be
-- fractional: where no pixel centre falls inside a small crown, QGIS weights
-- the pixels it touches by the share of each that overlaps the crown.
CREATE TABLE IF NOT EXISTS analysis.crown_obs (
    item_id    text    NOT NULL,
    asset_id   text    NOT NULL,
    clear_px   real,
    clear_frac real,
    ndvi_px    real,
    ndvi       real,
    ndmi       real,
    ndre       real,
    PRIMARY KEY (item_id, asset_id)
);
CREATE INDEX IF NOT EXISTS crown_obs_asset_idx ON analysis.crown_obs (asset_id);

-- Stored (raw) red and NIR values over clear vegetation, per scene.
CREATE TABLE IF NOT EXISTS analysis.s2_scene_qa (
    item_id text PRIMARY KEY,
    veg_px  integer,
    red_p01 real,
    red_p50 real,
    nir_p50 real
);

-- Readings with their date, for the metrics views.
CREATE OR REPLACE VIEW analysis.crown_obs_dated AS
SELECT o.*, c.acquired_on, c.year, c.month, c.platform, c.processing_baseline
FROM analysis.crown_obs o
JOIN analysis.s2_candidates c USING (item_id);

-- The evidence for the offset decision, by processing version. If the files
-- carried the catalogue's +1000 offset (reflectance -0.1), the darkest 1% of
-- vegetation would store about 1000 or more. It does not, in any version.
CREATE OR REPLACE VIEW qa.s2_offset_evidence AS
SELECT left(c.processing_baseline, 2) AS baseline_major,
       (c.bands -> 'red' ->> 'offset')::real AS catalogue_offset,
       count(*) AS scenes,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY q.red_p01)::numeric) AS red_p01_median,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY q.red_p50)::numeric) AS red_p50_median,
       round(percentile_cont(0.5) WITHIN GROUP (ORDER BY q.nir_p50)::numeric) AS nir_p50_median,
       count(*) FILTER (WHERE q.red_p01 >= 900) AS scenes_with_offset_in_file
FROM analysis.s2_scene_qa q
JOIN analysis.s2_candidates c USING (item_id)
WHERE q.veg_px > 10000
GROUP BY 1, 2
ORDER BY 1, 2;

-- Crowns never seen clearly: no scene with a clear pixel inside them.
CREATE OR REPLACE VIEW qa.crowns_never_clear AS
SELECT asset_id, max(clear_px) AS pixels
FROM analysis.crown_obs
GROUP BY asset_id
HAVING coalesce(max(ndvi_px), 0) = 0;
