-- 05_field_sample.sql
-- The trees scored in the field (QField) on Clifton and Durdham Downs, plus
-- the few large beeches in St Andrews Park and Redland Playing Fields.
--
-- How the sample was drawn (29 September 2026): stratified random, a fixed
-- number of trees per species and size stratum, ordered by a hash of each
-- tree's OBJECTID with a fixed salt so the draw was reproducible:
--
--   beech 80 cm and over     15   priority 1
--   beech 50 to 79 cm        12   priority 1
--   beech 20 to 49 cm        10   priority 1
--   oak 50 cm and over        8   priority 1
--   lime 50 cm and over       8   priority 1
--   sycamore 50 cm and over   5   priority 2
--   beech, nearby parks       3   priority 2 (every large beech there)
--
-- On 30 September 2026 the council's service had regenerated its OBJECTIDs,
-- which would have changed a redraw. A sample issued to the field must not
-- change, so the issued list is frozen in raw.field_sample_frozen (loaded
-- from the QField project by src/beech/qfield.py) and linked to the current
-- register through the stable ASSET_ID.

DROP TABLE IF EXISTS analysis.field_sample CASCADE;
CREATE TABLE analysis.field_sample AS
SELECT t.objectid, f.asset_id, f.tree_no, f.stratum, f.priority, t.geom
FROM raw.field_sample_frozen f
JOIN clean.trees t USING (asset_id);

ALTER TABLE analysis.field_sample ADD PRIMARY KEY (asset_id);

-- The layer QField uses: the sample with the register details the surveyor
-- needs to find and confirm each tree.
CREATE OR REPLACE VIEW analysis.field_sample_trees AS
SELECT f.tree_no, f.asset_id, f.objectid, f.stratum, f.priority,
       t.site_name, t.latin_name, t.common_name, t.dbh_cm,
       t.crown_width_m, t.crown_height_m, t.purple_leaved, t.geom
FROM analysis.field_sample f
JOIN clean.trees t USING (objectid);

-- Every frozen tree must still be in the register.
CREATE OR REPLACE VIEW qa.field_sample_missing AS
SELECT f.*
FROM raw.field_sample_frozen f
LEFT JOIN clean.trees t USING (asset_id)
WHERE t.asset_id IS NULL;
