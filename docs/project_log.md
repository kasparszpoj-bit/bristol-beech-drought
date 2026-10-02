# Project log

Every step of the project, in order: what was done, why, what came out of it,
and where the work lives. Updated after every step. The README is the short
report of findings; `methods.md` is the method in topic order;
`data_quality_register.md` holds the register audit; this file is the story
of how the project was actually built.

Each entry: **What**, **Why**, **Result**, **Files**, and **Skills** (from the
Arup Graduate Geospatial Specialist ad) where useful.

---

## 27 September 2026: the idea

- **What:** chose a portfolio project built around the family's copper beech
  in north Bristol, which has giant polypore (*Meripilus giganteus*), a root
  rot of beech. First framed as risk screening of Bristol's beeches against
  fungal records and fall zones.
- **Why:** a real, local problem to apply new Kaggle (Python, SQL) and Esri
  (imagery) training to, closing gaps from a skills audit against the Arup
  ad: PostGIS, remote sensing, machine learning, automation, web mapping,
  dashboards, a built environment angle.
- **Files:** first brief (since replaced), `brief.md`.

## 28 September 2026: research, refocus and set-up

### Background research on the tree and the fungus
- **What:** read the arboricultural literature and case studies on giant
  polypore; researched the tree's documented history (earlier tree works,
  a 2006 survey recording it at about 17 m with a trunk over 1 m across,
  and a dead main stem removed in 2017).
- **Why:** to understand what the fungus means for a tree like this, and to
  anchor the case study in facts rather than memory.
- **Result:** the tree is probably Victorian (planted about 1855 to 1885,
  from its size). Kept in the private case study folder.

### Refocus on the 2026 drought
- **What:** changed the main question to how Bristol's beeches, especially the
  older ones, responded to the 2026 drought, against other large broadleaves.
  Kept fungus and fall zones as a short second chapter (an inspection list).
- **Why:** a drought study uses remote sensing, time series, statistics and
  machine learning, which the Arup ad asks for, and it has a clear question
  with a measurable answer.
- **Files:** approved plan; `brief.md`.

### Folder restructure
- **What:** created `01_uk_job_projects/` for every portfolio project;
  renumbered the other folders; moved the Arup plan beside the Arup job ad.
- **Why:** projects that help get a UK job should be a prominent section, not
  buried or filed under one job's plan.

### Database set-up
- **What:** installed PostgreSQL 17.11 and PostGIS 3.6.2 on Windows, created
  the `beech` database, stored the password in the user's pgpass file (not in
  code), and connected QGIS. Tested a British National Grid to GPS
  transformation.
- **Why:** a spatial database is the single source of truth for QGIS, Python
  and Power BI, and published SQL makes every step auditable. Password-free
  local access was trialled and reverted to password authentication as the
  safer set-up.
- **Skills:** PostgreSQL/PostGIS, GIS concepts (coordinate systems).

### Loading the council tree register
- **What:** loaded the council register through its ArcGIS REST API, paged
  1,000 records at a time, raw attributes stored untouched as JSON, the count
  checked against the service.
- **Why:** repeatable (one command reloads it), auditable (raw data never
  edited), and verified (nothing lost in paging).
- **Result:** 16,451 beech, oak, lime, plane and sycamore records; 985
  beeches.
- **Files:** `src/beech/ingest_register.py`, `sql/01_schema.sql`.
- **Skills:** Python, APIs, large datasets.

### Cleaning and auditing in SQL
- **What:** SQL functions to parse sizes stored as text ("32 Centimetres"),
  tolerating typos; "No Code Allocated" converted to null; species grouped;
  purple-leaved trees flagged; size classes; every unparsed value logged;
  tests run against the real awkward strings.
- **Why:** the numbers are unusable as text, and cleaning in SQL (not by
  hand) is transparent and repeatable.
- **Result:** 49,353 measurement strings, none unexplained. Findings: no tree
  in the register is recorded as dead; trunk sizes are partly estimated
  (clustering on round numbers and nursery sizes), so size is used only in
  broad classes; oak is the worst-recorded group.
- **Files:** `sql/02_clean.sql`, `tests/test_parse_sql.py`,
  `docs/data_quality_register.md`.
- **Skills:** SQL, data assurance, data science.

### The report takes shape
- **What:** made the README the report itself, opening with the garden tree
  ("The tree that started it"), with a dated case study log and a
  "Decisions and trade-offs" section.
- **Why:** the report is the first thing anyone sees on GitHub and the thing
  to talk from in interviews.

## 29 September 2026: context, data sourcing and the field check

### Drought context from the Met Office
- **What:** loaded monthly station records for Yeovilton (62 years) and
  Cardiff Bute Park (49 years), the long records either side of Bristol;
  ranked every year in SQL; made Figure 1 (growing season rain against summer
  heat), with colours checked for colour-blind readers.
- **Why:** to state honestly how extreme 2026 was before measuring its effect.
- **Result:** summer rainfall alone was not a record (1976, 1995 and 2018
  were drier), but 2026 was **the hottest summer and driest July on record at
  both stations**, straight after **the driest growing season on record at
  Yeovilton (2025)**.
- **Files:** `src/beech/ingest_weather.py`, `sql/03_weather.sql`,
  `src/beech/figures.py`, `outputs/figures/fig01_drought_context.png`.
- **Skills:** data science, clear visualisation, explaining technical
  information.

### Sentinel-2 image inventory
- **What:** searched the Earth Search STAC catalogue for every Sentinel-2
  image over the study area, 2017 to September 2026; stored each image's
  footprint, cloud cover and per-band scale and offset; reduced to one image
  per satellite pass.
- **Why:** to know what data exist before heavy processing, and to capture the
  metadata needed to correct a 2022 processing change.
- **Result:** 3,731 catalogue items. Chose the original archive over the
  reprocessed Collection 1 because Collection 1 has no 2022 images over
  Bristol (a drought year used to test the method). 2017 dropped (too few
  images). Clear July and August images are rare in normal years (0 to 2)
  but 12 in 2026, so cloud is masked pixel by pixel.
- **Files:** `src/beech/sentinel.py`, `sql/04_sentinel.sql`.
- **Skills:** remote sensing, large datasets, Python.

### Study area from the official boundary
- **What:** the first study area was 41 km by 42 km because the register
  includes distant council sites; replaced with Bristol's ONS boundary plus
  3 km.
- **Why:** keeps council land just over the line (such as Ashton Court),
  drops sites near Chippenham and in the Forest of Dean.
- **Result:** 16,435 comparison trees, all 985 beeches, 14 km by 14 km.
- **Skills:** spatial analysis, PostGIS.

### LIDAR download
- **What:** downloaded Environment Agency 1 m terrain (DTM) and first-return
  surface (DSM) models through WCS, only for the 1 km squares holding large
  trees, plus neighbours where a crown crosses an edge; built virtual mosaics
  with GDAL.
- **Why:** the whole area would be about 1.5 GB, mostly roofs and roads.
- **Result:** 122 squares, 244 tiles, 978 MB, no failures.
- **Files:** `src/beech/lidar.py`.

### Field check design and QField project
- **What:** designed a stratified random sample of 61 trees on Clifton and
  Durdham Downs (37 beeches across three size classes, 8 oaks, 8 limes, plus
  8 extras); built a QField project with PyQGIS (form with drop-downs, ICP
  Forests crown condition classes, photo, numbered route); wrote a one-page
  field protocol.
- **Why:** the only way to check that the satellite signal reflects what is
  on the trees. Random selection avoids picking trees that look stressed.
- **Files:** `sql/05_field_sample.sql`, `qfield/beech_field_check/`,
  `docs/field_protocol.md`.
- **Skills:** field data capture (the open equivalent of Field Maps and
  Survey123), survey design, PyQGIS.

### Canopy height model
- **What:** canopy height = DSM minus DTM, built with the GDAL raster
  calculator in QGIS.
- **Result:** 14,000 by 13,000 pixels at 1 m. The garden tree reads 17.8 m,
  matching the 2006 arboriculturist's "about 17 m". Found that roofs appear as
  "canopy", so building footprints are needed.

## 30 September 2026: crowns

### The arborist
- **What:** read the family's correspondence with a Registered Consultant
  arboriculturist.
- **Result:** fruiting quantity is not a direct measure of decay; the tree
  may not be compromised yet but decay will progress; options are a dynamic
  stability assessment or removal and replanting. Added to the case study
  log; the family wants to keep the tree if possible.

### OS buildings and roads; the whole register
- **What:** loaded OS OpenMap Local buildings (73,538) and roads (19,505) for
  the study area; reloaded the whole council register (56,581 trees) so every
  tree can act as a neighbour when crowns are split.
- **Why:** buildings to remove roofs from the canopy; roads for the chapter 2
  fall zones; every tree as a neighbour so no register tree claims a
  neighbour's canopy.
- **Files:** `src/beech/ingest_os.py`.

### The council's IDs changed
- **What:** found that every OBJECTID in the council's service had been
  regenerated between 28 and 30 September.
- **Why it matters:** anything keyed on OBJECTID would silently mix up trees.
- **Result:** every link now uses the stable ASSET_ID; the field sample is
  frozen as issued (all 61 trees still matched).
- **Files:** `raw.field_sample_frozen`, `src/beech/qfield.py`.
- **Skills:** data assurance.

### QGIS model 01: tree crowns
- **What:** prototyped the crown method on a 1.5 km square of Durdham Down,
  checked it by eye, then built it as a 15-step QGIS Graphical Modeler model,
  written as code (`qgis/scripts/build_model01.py`) and run headless with
  `qgis_process` (`src/beech/run_models.py`). Steps: large trees; a search
  circle per tree; Voronoi cells from every register tree; canopy of 5 m or
  more; roofs removed; each tree's canopy within its own circle and cell;
  crown area and height.
- **Why:** crowns decide which satellite pixels belong to each tree. Voronoi
  cells split touching crowns; circles stop register trees claiming private
  gardens' canopy. A model reruns the same way on new data.
- **Result:** 8,623 crowns from 9,157 large trees (94%). Median crown area:
  beech 111 m², oak 88 m², plane 84 m², sycamore 47 m², lime 42 m². 198
  beeches have crowns of 100 m² or more. 533 large trees showed no canopy at
  their point, mostly pollarded street limes and planes.
- **Files:** `qgis/models/01_tree_crowns.model3`, `sql/06_crowns.sql`.
- **Skills:** desktop GIS (QGIS), repeatable workflows and automation (the
  open equivalent of ModelBuilder), LIDAR, spatial analysis.

### QGIS project and figures
- **What:** built `qgis/beech_drought.qgz` (every layer grouped and styled,
  live from PostGIS) and rendered report figures with QGIS's own Python:
  the model 01 diagram, a three-panel crown method figure, and a study area
  map.
- **Files:** `qgis/scripts/render_figures.py`, `outputs/figures/`.

### Sentinel-2 download started
- **What:** downloading the study-area window of the six needed bands for
  all 243 candidate images (May to October, 2018 to 2026) with GDAL straight
  from the cloud-hosted files.
- **Why:** a Bristol window is about 8.5 MB per image, against about 1 GB for
  a full scene.
- **Files:** `src/beech/s2_download.py`.
- **Result:** all 1,458 band windows (243 images × 6 bands) downloaded,
  about 2 GB, in 72 minutes, with no failures.

### The field walk
- **What:** walked Clifton and Durdham Downs with QField on a phone from
  15:08 to 16:45, scoring 41 of the 61 sample trees in the order they were
  numbered (north to south): whether the tree was found and was the right
  species, crown thinning and browning (ICP Forests classes 0 to 4), dieback,
  early leaf fall, nut crop, fungus at the base, a photo and notes. 39
  photos.
- **Why:** ground truth for the satellite. A drop in greenness over a crown
  could be drought stress, browned grass or a neighbouring tree in a mixed
  pixel, or a felled tree; only looking at the trees tells them apart.
- **First impression in the field:** the trees looked healthy, with no
  widespread browning or leaf loss. That is a result, not a failure: the
  satellite analysis now has to agree with it, or explain why not.
- **Not visited:** 20 trees, mostly a block in the middle of the route
  (trees 13, 15 and 18 to 26: five oaks, five small beeches and one large
  beech), the south end (52, 53)
  and all eight extras in other parks. Coverage by stratum is reported with
  every result.

### Field scores into PostGIS
- **What:** the exported QField project (a 280 MB zip, sent from the phone)
  was unzipped, untouched, into `data/field_returns/2026-09-30/`. A loader
  reads the scores straight from the GeoPackage, read only, and copies them
  as returned into `raw.field_returns`, keyed by the council's ASSET_ID; one
  row per tree per returned file, so a second walk adds rows rather than
  overwriting. SQL views join them to the frozen sample, set aside trees
  whose score is not about the drought, and check the returns.
- **Why:** the same rules as the register: raw data kept as delivered, every
  decision in published SQL, and tree identity on the stable ASSET_ID.
- **QA:** all 41 returns match the issued sample (asset ID and tree number);
  no point was moved in the app; one tree (57, a sycamore) has no photo; one
  (8, a 32 cm beech) was not found at its register point.
- **Result:** 39 trees compared (found, species confirmed, not set aside).
  Mean crown thinning 0.46, between "none" and "slight": broadly healthy,
  as seen on the walk. 8 of the 39 show some visible stress (thinning or
  browning of class 2 or more, or dead branches). By species: beech 6 of 27,
  lime 1 of 8, oak 1 of 3, sycamore 0 of 1. The 5 trees with moderate
  thinning include 4 beeches; 3 of those also carry a heavy nut crop, and
  all 4 trees with heavy early leaf fall are beeches. The numbers are too
  small to test; they are a check on the satellite, not a result on their
  own.
- **A caution for interpretation:** beech crowns look thinner in heavy mast
  years, because buds that would make leaves make flowers instead. A heavy
  2026 nut crop is itself a response to the hot 2025 summer. So thin crowns
  with heavy mast are not simply drought damage, and the satellite analysis
  has to keep that in mind.
- **Tree 10, the find of the day:** listed in the register as a live 100 cm
  beech, it is a dead monolith: the crown has been cut off, leaving the
  trunk and stubs, and giant polypore is fruiting in a ring around it. The
  LIDAR composite still shows a 205 m² crown up to 20.5 m tall, so the
  crown was cut after the survey was flown. It is set aside from the drought
  comparison in `analysis.field_exclusions`, with the reason written down.
  It becomes a test for the satellite method (the record should show when
  the crown was lost) and an example for Chapter 2.
- **Files:** `src/beech/qfield.py` (`beech-load-field-returns`),
  `sql/07_field_check.sql`, `tests/test_qfield.py`, 50 tests passing.
- **Skills:** field data capture (mobile GIS), data assurance, SQL.

### The satellite offset: checking the pixels
- **What:** before building model 02, compared the reflectance offset the
  catalogue gives each scene with the values actually stored in the files.
- **Why:** from 2022 ESA files store reflectance × 10,000 + 1,000, and the
  catalogue records an offset of −0.1 for every scene processed that way,
  including all scenes from June 2018 (reprocessed by ESA). If the offset is
  applied wrongly, every index is wrong.
- **Result:** the files do not carry the offset. The darkest vegetation
  stores values near 0 and the median red over vegetation is about 450 in
  every processing version; a file with the offset could not store less
  than about 1,000. So no offset is applied, and the per-scene evidence is
  stored (`analysis.s2_scene_qa`, `qa.s2_offset_evidence`). Had the
  catalogue been trusted, every image from June 2018 would have read 0.1
  too dark and the drought signal would have been swamped.
- **Skills:** remote sensing, data assurance.

### QGIS model 02: satellite readings per crown
- **What:** a 9-step QGIS Graphical Modeler model, written as code
  (`qgis/scripts/build_model02.py`): mask cloud from the scene
  classification, compute NDVI, NDMI and NDRE on the 10 m grid, and take
  zonal statistics over every crown. A runner (`qgis/scripts/run_model02.py`)
  loops it over all 243 images inside one QGIS session (about 19 seconds an
  image), and `beech-crown-indices` exports the crowns, runs it and loads
  the results into `analysis.crown_obs`.
- **Why:** the same reasons as model 01: one tested, documented chain,
  rerun identically on every image.
- **Checks:** on one image the model's NDVI matched an independent NumPy
  calculation to within 3 × 10⁻⁸; the cloud masks differed on 0.18% of
  pixels, all on mask edges (the 20 m classification grid sits 10 m off the
  10 m grid; QGIS aligns it by position, the quick NumPy check did not).
- **Two QGIS 4 details:** `processing.run` no longer accepts a model file
  path, so the runner loads the model object; the output parameter is named
  from the output's label ("crown_readings"), so the runner looks it up.
- **Files:** `qgis/models/02_crown_indices.model3`, `src/beech/crown_indices.py`,
  `sql/08_crown_obs.sql`, `outputs/figures/model02_crown_indices.png`.
- **Skills:** remote sensing, automation, desktop GIS.

### Crowns in pieces
- **What:** drawing the case study crown showed a sliver of a neighbouring
  tree, across the road, caught inside the search circle. Measured the same
  thing across all council crowns.
- **Result:** 5,983 of 8,623 crowns come in more than one piece, but almost
  all are one crown split by a gap of a pixel or two: treating pieces within
  2 m of the piece at the tree as one crown, only 0.4% of all crown area is
  detached (0.2% for beeches). For 281 crowns, more than 10% is detached and
  may be a neighbour's canopy; they are left out of the comparison
  (`analysis.crown_pieces`).
- **Why not fix and rerun:** the satellite run takes over an hour for a
  0.4% change in area. Trimming inside model 01 is noted as an improvement.

### The case study tree's crown
- **What:** the garden tree was run through model 01 exactly like the
  council trees, with its register neighbours for the Voronoi split, into
  the private schema (`src/beech/case_study.py`). A check image, kept
  private, was confirmed with the owner: the right tree, and a plausible
  size. The detached sliver from across the road was trimmed.
- **Result:** crown 145 m², top 17.8 m.

### Model 02 run and the sanity test
- **What:** model 02 over all 243 images: 2,095,389 crown readings, loaded
  into `analysis.crown_obs`. The run stopped once at the tool's background
  time limit (at image 124); the runner skips finished images, so it was
  restarted as a detached process and lost nothing. Then each tree's summer
  median per year, its normal (2019 to 2021, 2023, 2024) and each year's
  change from normal (`sql/09_metrics.sql`), and four checks
  (`beech-checks`).
- **Offset evidence, all images:** the darkest 1% of vegetation stores a
  median of 163 (old processing), 175 (2022 processing) and 185 (current);
  not one of 237 images carries the offset in its files.
- **Analysable crowns:** 1,166 of 8,623 (118 beeches, 148 oaks, 217 limes,
  540 planes, 143 sycamores) have at least two whole 10 m pixels, at least
  four clear normal years and little detached canopy. A crown needs to be
  about 16 m across to cover two whole pixels, so most crowns are mixed
  pixels: a 13 m beech is about 1.4 pixels' worth.
- **Sanity test, passed:** median change in summer greenness (NDVI) from
  each tree's normal, across the analysable crowns:

  | Year | NDVI | Moisture (NDMI) | Red edge (NDRE) | Below normal |
  |---|---|---|---|---|
  | 2018 (drought) | −0.070 | −0.064 | −0.048 | 91% |
  | 2022 (drought) | −0.024 | −0.030 | −0.024 | 78% |
  | 2025 | −0.011 | −0.025 | −0.023 | 61% |
  | 2026 | −0.029 | −0.035 | −0.042 | 79% |

  Both known drought years read below normal, 2018 most strongly, so the
  method detects drought. 2026 is clearly below normal, with the second
  largest red edge fall after 2018. (2020, a normal year, also reads
  −0.029: its spring was exceptionally dry and sunny; with five normal
  years, single normal years scatter around zero by design.)
- **Open question that stops the tree-level conclusions for now:** almost
  every Downs tree reads below normal in 2026, including trees scored
  healthy on the walk (tree 9, a big healthy beech, reads −0.26). Because
  crowns are mixed pixels, browned summer grass around them may be part of
  the signal. A grass reference is being run to separate the two.

### Grass reference: the mixed pixel problem confirmed
- **What:** 20 squares of open grass on the Downs (30 m, at least 25 m from
  any register tree, 20 m from buildings, 15 m from roads, nothing over 1 m
  on the LIDAR), chosen by a fixed hash from 243 that qualify, run through
  model 02 like crowns (`src/beech/grass_reference.py`).
- **Result:** in dry summers the grass collapses. Median change in summer
  NDVI from normal:

  | Year | Open grass | Downs beeches | Downs limes | Downs oaks |
  |---|---|---|---|---|
  | 2018 | −0.44 | −0.08 | −0.17 | −0.15 |
  | 2022 | −0.37 | −0.03 | −0.06 | −0.07 |
  | 2025 | −0.40 | −0.02 | −0.08 | −0.06 |
  | 2026 | −0.46 | −0.07 | −0.11 | −0.06 |

- **What it means:** if only 15% of a beech crown's reading were grass, the
  grass alone would produce the whole 2026 beech drop. The species ranking
  mirrored crown size (limes, the smallest crowns, dropped most), which is
  what grass mixing would produce. So the raw numbers cannot show species
  differences. Decision (with Kaspar): remove the ground's share using the
  LIDAR, rather than report the raw numbers with a caveat.

### Tree 10: what the satellite can and cannot say
- **What:** placed each of tree 10's readings on a scale from its grass
  (0) to the other Downs beeches (1).
- **First reading:** tree-like until early July 2026, a steady fall through
  July and August, and nothing green by 5 September, which suggested the
  crown was cut in late August 2026.
- **The field said otherwise:** Kaspar recalled the cut ends as old and
  grey, so the crown came off well before September. The green in tree
  10's pixels in 2025 and 2026 must have come from neighbouring canopy and
  the scrub around the trunk, mixed into the same 10 m pixels; the fall on
  5 September may be mowing or clearance.
- **Lesson:** at 10 m, one tree's history cannot be dated from the
  satellite alone. Asking the person who stood at the tree stopped a wrong
  conclusion going into the report. Dated aerial photographs would settle
  it.

### Canopy cover on the satellite grid
- **What:** from the 1 m LIDAR, canopy (5 m or taller, buildings burnt out)
  averaged onto the exact Sentinel-2 10 m grid (all 243 images share one
  grid, checked), then averaged over each crown with the same pixel
  weighting as model 02: the canopy share of each crown's reading
  (`src/beech/canopy_cover.py`, `analysis.crown_cover`).
- **Result:** median canopy share of a crown's reading: beech 0.72, plane
  0.58, oak 0.57, sycamore 0.42, lime 0.35. A typical lime reading is two
  thirds ground, which explains why limes looked hardest hit.
- **Two GDAL details:** this QGIS build's GDAL has no expression engine, so
  the canopy threshold uses `gdal raster reclassify`; and its heights start
  at 0, so the class boundaries stay clear of the −9999 no data value.

### QGIS model 03: each crown's local ground
- **What:** model 02's chain with one change: the mask keeps only clear
  pixels with under 10% canopy, and it runs over a 15 m ring around each
  crown. Both models are built by the same script, with a switch
  (`qgis/scripts/build_model02.py`), and run by the same runner.
- **Why a ring, not one grass reference:** the ground next to a crown is
  what mixes into its pixels, and it varies: grass on the Downs, pavement
  on streets. On one test image (13 August 2026) ground in Downs rings read
  NDVI 0.41 against 0.24 for open grass: grass by trees is shaded and has
  low shrubs, so it stays greener.
- **Unmixing** (`sql/11_unmixed.sql`): image by image,
  tree = (observed − (1 − f) × ground) / f, for crowns at least half
  canopy; then the same summer, normal and change steps as before.

## 1 October 2026: unmixing and the first real results

### Model 03 run and the unmixed readings
- **What:** model 03 over all 243 images (2,095,389 ground readings; the
  detached run finished overnight), loaded into `analysis.ground_obs`, then
  unmixed (`sql/11_unmixed.sql`).
- **Grove crowns:** 580 of the 3,701 crowns that are at least half canopy
  stand in dense groves, with no open ground in their own ring: many are
  the old Downs beeches. For them the ground is the median of the rings of
  crowns within 100 m on the same image (`analysis.ground_nearby`). This
  raised the analysable beeches from 141 to 195.
- **Result:** 1,927 analysable crowns (195 beech, 199 oak, 414 lime, 900
  plane, 219 sycamore).
- **Check that it worked:** before unmixing, the 2026 change grew with the
  ground share of a crown; after unmixing, the red edge change is flat
  across canopy share (−0.041 to −0.039), so red edge is the headline
  index. Greenness (NDVI) still drifts slightly and is reported second.

### Results (unmixed, July and August, change from each tree's normal)
- **Sanity test still passes.** Red edge: 2018 −0.041 (78% of crowns
  below normal), 2022 −0.019 (70%), 2026 −0.037 (84%, the highest share of
  any year).
- **Over half the raw 2026 greenness drop was ground.** Once removed, 2026
  canopy greenness barely fell (−0.011), but leaf moisture (−0.028) and red
  edge (−0.037) did: stress inside the leaves rather than visible browning,
  which matches the healthy-looking crowns on the walk.
- **Species, 2026, red edge (95% bootstrap interval):** beech −0.063
  (−0.069 to −0.056), sycamore −0.052, oak −0.049, lime −0.034, plane
  −0.027. Beech minus all others −0.028 (−0.035 to −0.020); moisture
  −0.035, greenness −0.034. Among crowns of similar canopy share (0.70 to
  0.85), beech (−0.056) overlaps with oak and sycamore: beech, oak and
  sycamore form the hardest hit group, lime and plane were much less
  affected.
- **A shift from 2018:** in 2018 oak was hit hardest (−0.068) and beech
  less (−0.052); in 2026 beech moved to the top of the group.
- **Size within beech:** no clear age effect. 2026: 80 cm and over −0.064
  (−0.070 to −0.054), 50 to 79 cm −0.050 (−0.067 to −0.042). In 2018 the
  largest beeches were the least affected.
- **Field check:** 23 scored trees have unmixed readings, 4 scored as
  stressed. Stressed trees read a little lower (red edge −0.074 against
  −0.062); rank correlation with crown thinning −0.32. Same direction, but
  too few stressed trees to confirm. Two clear disagreements: tree 9 (a
  healthy-looking beech) reads as one of the most affected; tree 31 (an
  oak with dead limbs) reads normal.
- **The case study tree** (canopy share 0.54, so noisier): 2026 greenness
  −0.125 against −0.064 for the median large council beech, red edge
  −0.099 (only 15 of 63 large beeches fell further), moisture −0.037
  against −0.071. A stronger than typical drop in greenness and red edge,
  consistent with a tree with root decay, but one tree with half its
  reading unmixed: an observation, not proof.
- **Files:** `src/beech/analysis.py` (`beech-analysis`) writes
  `outputs/tables/`; `src/beech/case_study.py ground`.
- **Skills:** remote sensing, spatial statistics, data assurance.

### Phase 1 written up: the initial analysis
- **What:** the work so far named "Phase 1: initial analysis" and written
  up in full in the README (findings, figures, method, limitations,
  decisions, what comes next, how to reproduce). Five result figures added
  (`src/beech/figures.py`: years, grass against trees, species, beech by
  size, the case study tree), checked for colour-blind separation and by
  eye. The remaining field walk and a blind satellite check were set aside
  by choice, to get the results out.
- **Wording corrected by a figure:** among crowns at least half canopy, the
  raw readings already put beech first, but bunched with the rest; removing
  the ground is what made beech stand apart. The "limes looked worst"
  effect was the Downs comparison. The README says exactly that.
- **Power BI:** clean CSV tables exported to `powerbi/data/`
  (`python -m beech.powerbi_export`), a star schema keyed on asset ID, and
  a step-by-step build guide (`powerbi/GUIDE.md`) for a five-page report.
- **Privacy audit before GitHub:** every file to be committed searched for
  the case study tree's coordinates (both grids), address and names,
  including inside the QGIS project archives. The QGIS project held the
  tree's coordinates through its private layer, so the working project
  moved to the private folder and a public copy without it is generated
  (`qgis/scripts/make_public_project.py`). A log line listing the years of
  council works on the tree was generalised, since those dates are
  searchable.
- **Skills:** data visualisation, technical writing, dashboards, data
  governance.

### Power BI model checked against the analysis
- **What:** Kaspar loaded the CSVs and built the model (relationships, DAX
  measures). Connected to the open file through Microsoft's Power BI
  Modeling MCP server and checked every number with DAX queries against
  the analysis tables.
- **Found:** the yearly medians matched exactly, but the crown count read
  37 instead of 1,927. Power BI had guessed `tree_year[asset_id]` was a
  number from its first rows (IDs like `00809493`), dropping leading zeros
  and turning every `PK...` ID into an error, so no reading linked to a
  tree. Separately, the CSV loader ignored quotes, so seven rows with a
  comma inside a value ("Bonnville Road, Oakenhill Cottages") were split
  across the wrong columns.
- **Fixed:** the load queries set IDs to text and read quotes properly;
  years no longer summed; measure formats corrected. Afterwards the 2026
  species medians in Power BI match the report to the third decimal place.
- **New fact surfaced:** 99% of analysable beeches read below their normal
  in 2026, against 78% of limes and 80% of planes.
- **Lesson:** a dashboard can look right while its joins are broken;
  reconcile its numbers with the source before trusting a single visual.

## 2 October 2026: an unhappy beech in St Andrews Park

### Opportunistic observation, PK31500
- **What:** Kaspar found a large beech at the south edge of St Andrews Park
  (by the Grenville Road entrance) with most of its leaves gone and giant
  polypore at the base, photographed it and dropped a pin. The pin is 2.1 m
  from register tree PK31500, so the match is certain. Recorded in
  `raw.opportunistic_obs`, kept apart from the random field sample so a
  tree chosen because it looked bad cannot bias the field check.
- **What the register says:** green beech (*Fagus sylvatica*), no trunk
  diameter, crown 18 m, height 19 m. Kaspar reported a copper beech; to be
  confirmed. LIDAR crown 86 m², 18.1 m tall, canopy share 0.68.
- **What the satellite says (ground removed):** 2026 greenness −0.077, more
  than three quarters of the city's 195 analysable beeches; red edge −0.051,
  middling. Its raw greenness fell steadily through the summer, from about
  0.81 in early July to about 0.66 by mid August.
- **Why the satellite understates it:** the July and August window misses
  leaf loss in September, when much of this crown went; and the crown is
  ringed by evergreen yews and a Leyland cypress 5 to 9 m away, whose
  foliage keeps its mixed pixels green.
- **Two lessons:** heavy crown loss seen on 1 October can sit only in the
  top quarter on July and August satellite data, so September images
  matter for late damage; and a tree with root rot and severe crown loss
  beside a road and a pavement, with someone sleeping rough beneath it,
  is exactly what Chapter 2's inspection list is for.
- **Already known to the council:** a member of the public reported the
  fungus on FixMyStreet on 15 September 2026 (ref 10102007, category "Tree
  in poor health", photos showing the rosettes at the base). The council
  investigated and raised a job with its contractors on 25 September, and
  the report was closed. An independent, dated record of the fungus, and
  evidence the inspection system works; the crown loss and the tent may
  postdate it, so are worth adding as an update.
- **A data source for Chapter 2:** Bristol's FixMyStreet holds dated,
  located public reports by category, including tree health. Matched to
  register trees by location, they could show which stressed beeches the
  council already knows about. Use counts and locations only, never
  reporters' names.
- **Privacy:** the photo shows a rough sleeper's tent; it will not be
  published uncropped.
- **Files:** `data/field_returns/opportunistic/2026-10-02_PK31500/`,
  `sql/07_field_check.sql`.

### 2026 against 2018: a correction to the headline
- **What:** reviewing the Power BI drought chart, Kaspar pointed out that
  2026 is not as deep as 2018 (median red edge −0.037 against −0.041),
  although the page title implied 2026 was the worst year. Rechecked by
  comparing the same 1,924 crowns in both years.
- **Result:** across all species there is no difference in red edge
  (+0.001, 95% interval −0.001 to +0.004), and greenness and moisture fell
  less in 2026 (−0.011 and −0.028 against −0.049 and −0.060 in 2018). 2026
  affected more crowns (84% below normal on red edge, against 78%) but not
  more deeply. By species, same trees: beech 0.012 worse in 2026 (interval
  0.004 to 0.028), the only species clearly worse; oak 0.012 better (0.006
  to 0.017); lime, plane and sycamore unchanged.
- **Change:** key findings 1 and 2 rewritten. The headline is now that the
  hottest summer on record did not hurt Bristol's trees more than 2018 in
  general, but did hurt beech more: a sharper and more defensible finding
  than "2026 was the worst year".
- **Lesson:** a share-below-normal statistic and a median change can tell
  different stories; the title must match what the chart shows.

### Power BI report, pages 1 to 4
- **What:** the report is now a Power BI project (.pbip), with every page
  written as code (`src/beech/powerbi_report.py`) and reviewed page by page
  in Power BI Desktop: 1 Drought, 2 Methods, 3 Main findings, 4 Tree
  explorer. A new analysis table (`species_change.csv`: 2026 against 2018,
  same trees, 95% intervals) feeds page 3.
- **The map problem:** every Power BI map visual (Azure Maps; the old Bing
  maps are retired) needs a work or school sign-in. The tree explorer is
  instead a scatter of longitude against latitude over a basemap rendered in
  QGIS for exactly the same axis range (`qgis/scripts/render_basemap.py`).
  It filters, cross-highlights and shows tooltips, but does not zoom.
- **Decision (Kaspar):** one of the first things seen on GitHub must be a
  first-rate interactive map. That is the phase 2 web map (MapLibre on
  GitHub Pages), linked at the top of the README.


### Two phases, and the interactive web map (2 October 2026)
- **What:** the project is now framed in two phases. Phase 1, the desk
  analysis and report, is complete. Phase 2 checks it on the ground (the
  QField sample, a blind rescore, field against satellite) and looks for
  real giant polypore cases (FixMyStreet, NBN Atlas, field sightings; St
  Andrews Park is the first). The web map moved into Phase 1, because it
  should be the first thing seen on GitHub. The Power BI pages were
  reordered so the tree explorer opens first.
- **Web map:** `web/`, hand-written MapLibre GL JS with no build step,
  published to GitHub Pages by a workflow (`.github/workflows/pages.yml`).
  `beech-web-export` writes trees (1 MB), LIDAR crowns simplified to 0.5 m
  (2.7 MB) and the boundary as GeoJSON straight from PostGIS. Year buttons
  with a play control, species, size and setting filters, live headline
  numbers and a species chart, crowns from zoom 15, a street map or aerial
  basemap (OpenFreeMap, Esri imagery; neither needs a key), a site search,
  and a per-tree history chart. Checked in a browser at desktop and phone
  widths; the headline numbers match Power BI and the analysis (2026, all
  species: 1,927 trees, median −0.037, 84% below normal; beech −0.063).
- **Power BI made portable:** the eight hard-coded CSV paths became one
  `DataFolder` parameter, a leftover error query was removed, and the guide
  was rewritten for the `.pbip` workflow (`powerbi/README.md`). Screenshots
  of the four pages are in `powerbi/screenshots/`. A `.gitignore` rule
  (`*case_study*`) would have silently left the case study table out of the
  Power BI project; an exception was added.
- **Tests:** `tests/test_reporting.py` covers the Power BI number fix, the
  bootstrap median, the paired species change and its verdicts, and the web
  export's yearly arrays. 62 tests pass; ruff clean.
- **Privacy:** every file to be committed searched for the garden tree's
  street names, house number and coordinates; no names or address terms.
  The nearest published tree is 61 m from it and the nearest crown 116 m.
- **Skills:** web mapping (MapLibre, GeoJSON, HTML, CSS, JavaScript), CI
  and GitHub Pages, Power BI as code, testing.

---

## Next

Phase 2: finish the field sample before leaf fall (late October 2026) with
a blind rescore; collect giant polypore cases from FixMyStreet, NBN Atlas
and sightings; the inspection list; September images; response clusters; a
Power BI ground-truth page; re-score in summer 2027.
