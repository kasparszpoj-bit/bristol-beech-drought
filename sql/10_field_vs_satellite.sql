-- The field check against the satellite: each scored tree's 2026 summer
-- reading beside its crown scores. Every sample tree is listed, with the
-- reason when one side is missing, so no tree drops out silently.
CREATE OR REPLACE VIEW analysis.field_vs_satellite AS
SELECT f.tree_no, f.asset_id, f.stratum, f.species_group, f.found,
       f.compared, f.stressed, f.defoliation, f.discolour, f.dieback,
       f.leaf_fall, f.mast, f.fungus, f.excluded_reason,
       a.pixels, c.crown_area_m2, b.base_years,
       y.n_obs AS n_obs_2026,
       round(y.d_ndvi::numeric, 3) AS d_ndvi,
       round(y.d_ndmi::numeric, 3) AS d_ndmi,
       round(y.d_ndre::numeric, 3) AS d_ndre,
       round(y.z_ndvi::numeric, 2) AS z_ndvi,
       round(y.z_ndmi::numeric, 2) AS z_ndmi,
       round(y.z_ndre::numeric, 2) AS z_ndre,
       CASE WHEN NOT f.visited THEN 'not visited'
            WHEN NOT coalesce(f.compared, false) THEN 'set aside in the field'
            WHEN c.asset_id IS NULL THEN 'no LIDAR crown'
            WHEN pc.detached_share > 0.1 THEN 'crown includes detached canopy'
            WHEN b.base_years IS NULL OR b.base_years < 4 THEN 'too few clear normal years'
            WHEN a.asset_id IS NULL THEN 'crown under two pixels'
            WHEN y.asset_id IS NULL THEN 'no clear 2026 summer reading'
       END AS why_no_comparison
FROM analysis.field_check f
LEFT JOIN analysis.crowns c USING (asset_id)
LEFT JOIN analysis.crown_pieces pc USING (asset_id)
LEFT JOIN analysis.crown_baseline b USING (asset_id)
LEFT JOIN analysis.crown_analysable a USING (asset_id)
LEFT JOIN analysis.crown_anomaly y ON y.asset_id = f.asset_id AND y.year = 2026
ORDER BY f.tree_no;
