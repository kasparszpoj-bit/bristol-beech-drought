# Skills in practice

Where each tool in this project is actually used, with the step, the object
it produces and, for SQL, the query. **Done** means built and tested as of
29 September 2026. **Planned** means designed, with table names that will be
used when it is built.

Everything spatial is British National Grid (EPSG:27700).

---

## 1. SQL and PostGIS

The database is the backbone: every dataset lands in `raw`, is cleaned into
`clean`, derived results go to `analysis`, and checks live in `qa`. QGIS,
Power BI and the web map all read from the `analysis` views, so there is one
version of every number.

### Done

| Step | Object | What it shows |
|---|---|---|
| Load the register untouched, attributes kept as JSON, points indexed | `raw.register_trees`, GiST index | Raw layer kept for auditing; spatial index for fast queries |
| Log every ingest run and compare loaded against served counts | `qa.ingest_log` | Traceable, repeatable loading |
| Parse `"15 Metres"`, `"36 Centrimetres"` and `"No Code Allocated"` into numbers or nulls | `clean.parse_measure()`, `clean.measure_status()` | SQL functions, regular expressions, data cleaning |
| Roll 60+ Latin names into species groups | `clean.species_lookup` | Lookup table design |
| One typed, keyed, indexed table of trees with size classes | `clean.trees` | Table design, primary key, CASE logic |
| Record every value that failed to parse | `qa.parse_failures` | Data assurance you can inspect |
| Completeness and implausible values per field | `qa.completeness`, `qa.implausible_values` | QA as views, rerun after every load |
| Summer rainfall, long-term normal and rank per year | `analysis.summer_rain`, `summer_rain_normal`, `summer_rain_ranked` | Aggregates, window functions |

### Planned, with the queries

**Pick analysable crowns: large beeches whose crown does not touch another.**
(Week 2, after the crown model has written `analysis.crowns`.)

```sql
SELECT c.tree_id
FROM analysis.crowns c
JOIN clean.trees t ON t.objectid = c.tree_id
WHERE t.species_group = 'beech'
  AND ST_Area(c.geom) >= 80
  AND NOT EXISTS (
      SELECT 1
      FROM analysis.crowns o
      WHERE o.tree_id <> c.tree_id
        AND ST_DWithin(c.geom, o.geom, 3)
  );
```

**Summer median per tree per year, from every cloud-free scene.** (Week 3,
reading `analysis.crown_obs`, one row per crown per scene.)

```sql
CREATE OR REPLACE VIEW analysis.summer_median AS
SELECT tree_id,
       extract(year FROM scene_date)::int AS yr,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY ndmi) AS ndmi_med,
       count(*) AS n_scenes
FROM analysis.crown_obs
WHERE extract(month FROM scene_date) IN (7, 8)
GROUP BY tree_id, yr;
```

**2026 against each tree's own normal years.**

```sql
CREATE OR REPLACE VIEW analysis.ndmi_anomaly AS
WITH base AS (
    SELECT tree_id, avg(ndmi_med) AS ndmi_base
    FROM analysis.summer_median
    WHERE yr NOT IN (2018, 2022, 2026)
    GROUP BY tree_id
)
SELECT s.tree_id, s.yr, s.ndmi_med - b.ndmi_base AS ndmi_anomaly
FROM analysis.summer_median s
JOIN base b USING (tree_id);
```

**Beech against oak, lime, plane and sycamore, by size class.** (Week 4.)

```sql
SELECT t.species_group, t.size_class,
       count(*) AS n_trees,
       round(avg(a.ndmi_anomaly)::numeric, 3) AS mean_anomaly
FROM analysis.ndmi_anomaly a
JOIN clean.trees t ON t.objectid = a.tree_id
WHERE a.yr = 2026 AND t.in_comparison
GROUP BY t.species_group, t.size_class
ORDER BY t.species_group, t.size_class;
```

**Setting: share of the ground within 10 m of each tree that is built on.**
(Idea 2, OS Open Map Local buildings loaded to `raw.os_buildings`.)

```sql
SELECT t.objectid,
       sum(ST_Area(ST_Intersection(ST_Buffer(t.geom, 10), b.geom)))
         / ST_Area(ST_Buffer(t.geom, 10)) AS built_share_10m
FROM clean.trees t
JOIN raw.os_buildings b ON ST_DWithin(t.geom, b.geom, 10)
GROUP BY t.objectid, t.geom;
```

**Chapter 2: load NBN fungal records and move them into British National
Grid.** (Week 5.)

```sql
INSERT INTO clean.fungal_records (record_id, year, geom)
SELECT record_id, year,
       ST_Transform(ST_SetSRID(ST_MakePoint(lon, lat), 4326), 27700)
FROM raw.nbn_meripilus;
```

**Nearest fungal record to every beech, using the index (`<->`).**

```sql
SELECT t.objectid, f.record_id, round(ST_Distance(t.geom, f.geom)) AS dist_m
FROM clean.trees t
CROSS JOIN LATERAL (
    SELECT record_id, geom
    FROM clean.fungal_records
    ORDER BY t.geom <-> geom
    LIMIT 1
) f
WHERE t.species_group = 'beech';
```

**Fall zone: how much road each beech could reach if it fell.** Height from
LIDAR where there is a crown, the register otherwise.

```sql
WITH fall_zone AS (
    SELECT t.objectid,
           ST_Buffer(t.geom, coalesce(c.height_m, t.crown_height_m)) AS geom
    FROM clean.trees t
    LEFT JOIN analysis.crowns c ON c.tree_id = t.objectid
    WHERE t.species_group = 'beech'
)
SELECT z.objectid,
       coalesce(sum(ST_Length(ST_Intersection(r.geom, z.geom))), 0) AS road_m_in_reach
FROM fall_zone z
LEFT JOIN raw.os_roads r ON ST_Intersects(r.geom, z.geom)
GROUP BY z.objectid;
```

These three feed one view, `analysis.inspection_priority`, which scores drought
stress, distance to fungus and what is in reach.

**Export for the web map, straight from the database.**

```sql
SELECT json_build_object(
    'type', 'FeatureCollection',
    'features', json_agg(ST_AsGeoJSON(p.*)::json)
)
FROM (
    SELECT objectid, priority, ST_Transform(geom, 4326) AS geom
    FROM analysis.inspection_priority
) p;
```

**Optional: zonal statistics inside the database** (`postgis_raster` is
already enabled), to check the QGIS model's numbers for a few crowns:
`ST_SummaryStats(ST_Clip(s.rast, c.geom))`.

**Power BI** connects to `analysis.ndmi_anomaly`, `analysis.inspection_priority`
and `analysis.summer_rain_ranked` through its PostgreSQL connector. No
geometry needed, just the numbers.

---

## 2. ModelBuilder and FME: the open equivalents used here

No Esri or FME licence is used. The same job is done with **QGIS Graphical
Modeler**, which is the open equivalent of ModelBuilder: tools chained into a
diagram with parameters, saved as a file and rerun. Both models run headless
with `qgis_process`, looped over every LIDAR tile and every Sentinel-2 scene by
`src/beech/run_models.py`.

### Model 01: crowns from LIDAR (planned, week 2)

`qgis/models/01_crowns.model3`

1. Inputs: LIDAR DSM tile, DTM tile, tree points from `clean.trees`.
2. Raster calculator: DSM minus DTM gives canopy height.
3. Keep canopy above a height threshold (a model parameter, about 5 m).
4. Sieve out specks, then polygonise into canopy patches.
5. Keep the patch that contains each tree point; join the tree id.
6. Canopy height statistics per crown (maximum = tree height).
7. Output: `analysis.crowns` in PostGIS.

### Model 02: crown indices per scene (planned, week 3)

`qgis/models/02_crown_indices.model3`

1. Inputs: one Sentinel-2 scene (bands 4, 5, 8, 11 and the scene
   classification layer), crowns.
2. Mask cloud, cloud shadow and snow using the scene classification.
3. Raster calculator: NDVI, NDMI and NDRE.
4. Zonal statistics of each index over every crown.
5. Output: rows appended to `analysis.crown_obs`.

### Model 03: fall zone screening (suggested addition, week 5)

A vector model that repeats the chapter 2 SQL: buffer each beech by its
height (a field-driven buffer), extract the roads and buildings inside,
join the nearest fungal record, score. Running the same analysis as a model
and as SQL, and checking they agree, is a good way to show both, and to
explain when each is the better tool.

### The same steps in ModelBuilder and FME

For explaining the models to people who work in Esri or FME. The steps
translate almost one to one.

| Step | QGIS model (used here) | ArcGIS ModelBuilder | FME transformer |
|---|---|---|---|
| Canopy height | Raster calculator | Raster Calculator | RasterExpressionEvaluator |
| Canopy to polygons | Sieve, Polygonize | Raster to Polygon | RasterToPolygonCoercer |
| Tree to crown | Join attributes by location | Spatial Join | SpatialFilter |
| Index per crown | Zonal statistics | Zonal Statistics as Table | RasterCellValueStatisticsCalculator / point on area overlays |
| Fall zone | Buffer (field-driven distance) | Buffer | Bufferer |
| Nearest fungal record | Join attributes by nearest | Near | NeighborFinder |
| Road length in reach | Clip, field calculator `$length` | Clip, Calculate Geometry | Clipper, LengthCalculator |
| Run over every tile or scene | `qgis_process` loop | Iterate Rasters | Directory reader, batch |

**The FME-style job in this project is the ingest.** `ingest_register.py`
reads a paged ArcGIS REST service, transforms and validates, and writes to
PostGIS with a log: an extract, transform and load workflow, which is what an
FME workspace does. Built in Python here, not FME, and described that way.

If an ArcGIS Pro licence becomes available for personal projects, model 01 or
model 03 is the one to rebuild in ModelBuilder, since every step has a
direct equivalent.

---

## 3. Everything else, briefly

| Skill | Where in this project |
|---|---|
| Python | Ingest from the council REST API and the Met Office, `run_models.py`, figures, pytest (34 tests) |
| Remote sensing | Sentinel-2 L2A from the Earth Search STAC catalogue, cloud masking, NDVI, NDMI and NDRE, 2017 to 2026 |
| LIDAR | Environment Agency 1 m DSM and DTM, canopy height model, crown outlines |
| Machine learning | k-means clustering of each tree's 2017 to 2026 series into response types |
| Statistics | Bootstrap confidence intervals, a simple regression |
| Field capture | QField check of 30 to 40 beeches on the Downs (the open equivalent of Field Maps and Survey123) |
| Dashboards | Power BI report on the `analysis` views |
| Web mapping | MapLibre page on GitHub Pages, fed by the GeoJSON export above |
| Data assurance | `qa` schema, parse failure log, `docs/data_quality_register.md` |
| Version control | Public GitHub repo |
