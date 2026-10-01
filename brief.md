# Bristol's beeches and the 2026 drought

Self-directed portfolio project in `01_uk_job_projects/`, a peer of Weston Big
Wood. Written 28 September 2026, replacing the giant polypore brief of
27 September. Status, 28 September 2026: **week 1 core done.** PostgreSQL 17.11
and PostGIS 3.6.2 installed, the `beech` database connected in QGIS, the
register loaded (16,451 trees, 985 beeches) and cleaned in SQL, 29 tests
passing. Findings so far in `docs/data_quality_register.md`.
29 September 2026: Met Office data loaded (`sql/03_weather.sql`) and figure
F1 made. 2026 was the hottest summer and driest July on record at Yeovilton
and Cardiff, after the driest growing season on record (2025, Yeovilton), but
it was not a record for summer rainfall totals. 34 tests passing.
29 September 2026, later: Sentinel-2 inventory done (3,731 items, 2018 to 2026
usable, `sentinel-2-l2a` with per-band offsets; Collection 1 lacks 2022).
Study area set to Bristol plus 3 km using the ONS boundary (16,435 trees, all
985 beeches). Method decisions in `docs/methods.md`. 38 tests passing. Next:
LIDAR download, the QField project, then phase 2 (QGIS crown model).

Full approved plan: `C:\Users\Kaspa\.claude\plans\streamed-noodling-cascade.md`.

---

## The one line version

How did Bristol's council-managed beeches, especially the big old ones,
respond to the 2026 drought, compared with 2018, 2022, normal years and other
large broadleaves? And which drought-stressed beeches near giant polypore
records could fall onto a road or building?

## Why this project

- **The hook.** Kaspar's own Victorian copper beech has giant polypore, lost a
  main stem in 2017, and went through the 2026 drought with a very heavy nut
  crop. It is the case study.
- **Skills it proves.** PostGIS and published SQL, QGIS Processing models (the
  open equivalent of ModelBuilder), Sentinel-2 remote sensing, LIDAR, a
  machine learning step, a hand-written web map, Power BI, and a built
  environment angle (fall zones over roads and buildings). Where each one is
  used, with the SQL and the model steps, is in `docs/skills_in_practice.md`,
  including a suggested third QGIS model (fall zone screening) and a QGIS,
  ModelBuilder and FME translation table.
- **Everything is free and open.** No Esri licence is used.

## Questions

1. How did large beeches respond to the 2026 drought, against 2018, 2022 and
   normal years?
2. Were beeches hit harder than oak, lime, plane and sycamore of similar size?
3. Were the older (larger DBH) beeches hit hardest?
4. Does setting matter: hard surface around the tree, street against park?
5. **Chapter 2:** which drought-stressed large beeches are near giant polypore
   records and within falling distance of roads or buildings? The output is
   an inspection priority list.
6. **Case study:** how does the garden copper beech compare with its peers
   from 2017 to 2026?

## Data, checked 28 September 2026

| Dataset | What it gives | Licence | Checked |
|---|---|---|---|
| Bristol City Council tree register, ArcGIS REST MapServer/32 | 985 beeches (about 277 with crown width of 12 m or more; DBH up to 156 cm), plus comparison species | OGL 3.0 | Counted live |
| Sentinel-2 L2A, Earth Search STAC (AWS, no account) | Summer scenes over Bristol with under 20% cloud: 15 in 2026, 9 in 2018, 6 in 2022 | Copernicus open | Counted live |
| Met Office monthly station data, Yeovilton and Cardiff Bute Park | July 2026 rainfall 2.2 mm and 4.2 mm (provisional) | Open | Read live |
| EA National LIDAR 1 m DSM and DTM | Canopy height, crowns, tree height | OGL | To download |
| OS Open Roads, OS Open Map Local | Roads and buildings | OGL | To download |
| NBN Atlas, *Meripilus giganteus* | 4,753 UK records, 69 within 15 km of Bristol | Mostly CC-BY-NC | Counted live |

Register caveats, from `../_ideas/bristol_tree_register_qa/brief.md` and the
28 September check: DBH, crown height and crown width are text with units
(`"15 Metres"`), including typos (`"36 Centrimetres"`, `"93  Centimetres"`).
"No Code Allocated" stands in for null (125 beeches have no DBH). Woodland
trees are excluded.

## Method in brief

1. **PostGIS.** Load the raw register. All cleaning is done in SQL and
   published: numbers parsed from the text, nulls fixed, species rolled up,
   and failures logged.
2. **Crowns, in QGIS (model 01).** Canopy height from LIDAR, and a crown
   polygon for each tree. Run headless with `qgis_process`.
3. **Sentinel-2 (model 02).** Per scene: cloud mask, then NDVI (greenness),
   NDMI (canopy moisture) and NDRE (red edge), averaged over each crown.
   Covers 2017 to 2026.
4. **SQL views.** July to August median per tree per year; the anomaly
   against non-drought years; the early browning date in 2026.
5. **Analysis.** Species and size comparisons with bootstrap confidence
   intervals, a simple regression, and k-means clustering of each tree's
   2017 to 2026 series into response types.
6. **Chapter 2, in SQL.** Nearest fungal record, a fall zone of radius equal
   to the tree's height, and the roads and buildings inside it, combined into
   an inspection priority view.

## Outputs

**Main aim (set 28 September 2026): a concise technical report that is the
repo's README**, so it is the first thing anyone sees and easy to talk about
in an application or interview. Readable in about five minutes: a summary
table, three to five key findings each tied to a figure, a short method,
results, the field check, the inspection list and honest limits. Detailed
methods go in `docs/methods.md`, not in the README.

Supporting outputs, in priority order (they back up the report, and are cut
before the report is if time runs short):

1. The SQL, QGIS models and code in the repo, which prove the work was done.
2. The Power BI report (screenshots and `.pbix` in the repo), built by
   Kaspar from a step-by-step guide on views prepared in PostGIS.
3. A MapLibre web map on GitHub Pages.
4. Two CV bullets and one STAR story, kept outside the repo.

## Rules

- **The garden tree is the project's hook (decided 28 September 2026).** The
  README opens with it ("The tree that started it") and keeps a dated case
  study log, updated as things happen, including the arborist's findings.
- **Talking about the tree (updated 30 September 2026):** Kaspar is happy to
  talk about the tree openly, in interviews and in the project. It is part of
  the analysis like any other tree: its crown, height, satellite history,
  photos of the tree and fungus, the 2017 stem, the arborist's findings (if
  the arborist agrees) and what the family decides.
- **Public location wording:** "a house in north Bristol". The exact location
  is not published: no street, house number, coordinates, map pin or aerial
  view in the public repo, web map or Power BI, and no council planning
  references for its tree works (they are searchable by address). The
  tree's location stays in the `private` database schema and
  `../_private/beech_case_study/`, and public exports are checked for its
  coordinates before anything is published. Locally (the QGIS project on
  Kaspar's machine) it is shown like any other layer.
- NBN records are credited to each data provider, and CC-BY-NC data is used
  for non-commercial portfolio work only.
- This is desk screening and research, not an arboricultural risk assessment.
- At 10 m pixels a crown is a few mixed pixels, so only large, isolated crowns
  are analysed. "No detectable signal" is reported as a finding.

## Roadmap to a finished project (set 29 September 2026)

Arup skills are from the Graduate Geospatial Specialist ad audit in
`02_uk_data_science_goal/role_prep/arup_geospatial_specialist/README.md`.

| Phase | Dates | Work | Arup skills evidenced | Status |
|---|---|---|---|---|
| 0 | 28 to 29 Sept | Restructure; PostGIS install; register loaded and cleaned in SQL; data quality audit; Met Office data and F1 | PostgreSQL/PostGIS, SQL, data assurance, large datasets, Python, clear visualisation | Done |
| 1 | 30 Sept to 4 Oct | Sentinel-2 scene inventory; LIDAR download; QField project built; Kaspar explores the data in QGIS and installs QField and Power BI | Remote sensing (data sourcing), field data capture, desktop GIS | Next |
| 2 | 5 to 11 Oct | QGIS model 01: crowns from LIDAR; selection rules in SQL; crowns checked in QGIS | Desktop GIS, spatial analysis, repeatable workflows (Graphical Modeler as the ModelBuilder equivalent), LIDAR | Done early, 30 Sept: canopy height model, OS buildings and roads, full register as neighbours, 15-step model 01, 8,624 crowns |
| 3 | 12 to 18 Oct | QGIS model 02: satellite indices per crown, 2017 to 2026; metrics views; **QField walk on the Downs** (any day 11 to 25 Oct) | Remote sensing and image analysis, automation, large datasets, field capture | |
| 4 | 19 to 25 Oct | Species and size comparisons; clustering; case study chart; figures F2 to F6 | Data science, machine learning, spatial analysis, clear visualisation | |
| 5 | 26 Oct to 1 Nov | Chapter 2 inspection list (roads and buildings in fall zones); field check results; web map | Built environment subject, PostGIS spatial SQL, web mapping (HTML, CSS, JavaScript) | |
| 6 | 2 to 8 Nov | Power BI report; README findings written; methods note; repo checked for private data and published; CV bullets and STAR story | Dashboards (Power BI), explaining technical information, Git and GitHub | |
| Ongoing | | Case study log (arborist findings) | Explaining technical information | |

The Esri MOOC crunch (8 to 21 October) overlaps phases 2 and 3; if time
runs short, cut in this order: web map, Power BI polish, clustering. The
README report is never cut. The Arup application does not wait for this
project: apply first, then use the project in the interview stages.

## Ideas to work on later

1. **QField field check (favoured, time critical).** Score 20 to 40 large
   beeches in one or two parks for browning, thinning and dieback, with a
   photo, using QField, as ground truth for the satellite signal. **Must
   happen before leaf fall, about late October 2026**, so the decision is
   needed in week 1.
2. **Spatial drivers.** A terrain wetness index, aspect, BGS 1:625,000
   geology, Landsat summer surface temperature and hard surface around each
   tree; then hot spot analysis and Moran's I.
3. **Map set and QGIS Atlas "tree cards".** One Atlas page per large beech.
4. **Historic map age class.** Beeches overlaid on the georeferenced 1880s
   and 1900s Ordnance Survey maps, to flag probably Victorian trees.

## Open

1. ~~PostgreSQL and PostGIS install~~ Done 28 September 2026. The password
   is in Kaspar's pgpass file; QGIS stores the username only.
2. QField field check: **yes (28 September 2026)**. Site: Clifton and
   Durdham Downs, which has 87 large council beeches (crown of 10 m or more,
   or DBH of 50 cm or more), plus St Andrew's Park (4) and Redland Playing
   Fields (2). Aim for 30 to 40 beeches, plus some oak and lime as
   comparisons. The QField project is built in week 1, and the walk happens
   before leaf fall (by about 25 October 2026). **Built 29 September 2026**
   (`qfield/beech_field_check/`, 53 core and 8 extra trees, ICP Forests
   classes, guide in `docs/field_protocol.md`). **Walk planned for
   30 September 2026.** LIDAR also downloaded on 29 September (122 squares,
   244 tiles, 978 MB, mosaics built).
3. Hours per week available.
