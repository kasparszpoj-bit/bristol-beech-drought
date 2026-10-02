# The Power BI report

A four-page report on the Phase 1 results, saved as a Power BI project
(`.pbip`): the model and every page are plain text files, so they can be
read, compared and rebuilt from code. It reads the CSV files in `data/` and
needs no database.

| Page | What it shows |
|---|---|
| 1 Tree explorer | Every analysable council tree on a Bristol basemap, coloured by its change in red edge; filters for year, species, trunk size and site; the most affected trees |
| 2 Drought | 2026 against every summer on record at two stations, and the trees' response each year since 2018 |
| 3 Methods | How a crown is drawn from LIDAR, the six steps, why the ground had to be removed, and the checks that the method works |
| 4 Main findings | Beech against the other four species, in 2018 and 2026, and the change between them for the same trees |

Screenshots of each page are in `screenshots/`.

## Open it

1. Install Power BI Desktop (free, Windows) from the Microsoft Store:
   https://apps.microsoft.com/detail/9NTXR16HNW1T
2. Clone or download the repo, and open `powerbi/bristol_beech_drought.pbip`.
3. The data folder is one parameter, `DataFolder`. Choose **Home, Transform
   data, Edit parameters** and set it to the full path of your copy of
   `powerbi\data\`, ending in a backslash. Then **Refresh**.

## How it is built

| Part | Built by | Files |
|---|---|---|
| Data | `beech-powerbi-export` (`src/beech/powerbi_export.py`) | `data/*.csv` |
| Model: tables, types, relationships, measures | TMDL, edited with the Power BI modeling MCP server and by hand | `bristol_beech_drought.SemanticModel/definition/` |
| Pages | `beech-powerbi-report` (`src/beech/powerbi_report.py`) writes every visual as PBIR JSON | `bristol_beech_drought.Report/definition/pages/` |
| Tree explorer basemap | `qgis/scripts/render_basemap.py`, run with QGIS's Python | `bristol_beech_drought.Report/StaticResources/RegisteredResources/` |

**Close Power BI before running `beech-powerbi-report`.** Power BI holds the
project in memory and writes it back when it saves, overwriting any change
made on disk while it was open.

### The data

| File | One row per | Key columns |
|---|---|---|
| `trees.csv` | mapped crown (8,623) | `asset_id`, species, size class, site, canopy share, `analysable`, latitude, longitude |
| `tree_year.csv` | analysable crown per year (1,927 crowns, up to 9 years) | `asset_id`, `year`, change in greenness, moisture, red edge (ground removed), raw greenness change, `change_band` |
| `species_year.csv` | species, year and subset | median change with 95% interval (`_lo`, `_hi`); `subset` is "all" or "similar canopy share" |
| `species_change.csv` | species | median change in 2018 and 2026 for the same trees, the paired difference with its 95% interval, and a verdict |
| `years.csv` | year | median changes, share of crowns below their normal |
| `grass_vs_trees.csv` | year | greenness change for open grass, tree crowns raw, and ground removed |
| `weather.csv` | station and year | growing season rain, July rain, summer mean maximum, ranks |
| `field_check.csv` | field sample tree (61) | field scores and the 2026 satellite change where available (used in Phase 2) |
| `case_study.csv` | year | the garden tree against the median large council beech; no location |

All changes are against each tree's own normal years (2019 to 2021, 2023,
2024). Negative means less green, drier or less chlorophyll than normal.

### The model

Two relationships, both one to many and single direction:
`trees[asset_id]` to `tree_year[asset_id]`, and `trees[asset_id]` to
`field_check[asset_id]`. The other tables stand alone.

Measures, in `tree_year`:

```DAX
Crowns = DISTINCTCOUNT ( tree_year[asset_id] )
Median red edge change = MEDIAN ( tree_year[change_red_edge] )
Median moisture change = MEDIAN ( tree_year[change_moisture] )
Median greenness change = MEDIAN ( tree_year[change_greenness] )
Share below normal =
    DIVIDE (
        CALCULATE ( COUNTROWS ( tree_year ), tree_year[change_red_edge] < 0 ),
        COUNTROWS ( tree_year )
    )
```

Every number on the pages was checked against the Python analysis with DAX
queries (for example, beech in 2026: 195 crowns, median −0.063, 99% below
normal).

## Traps found while building it

- **IDs read as numbers.** Power BI guesses types from the first rows. The
  first IDs in `tree_year` are all digits (`00809493`), so it made `asset_id`
  a number: leading zeros vanished, every `PK...` ID became an error, and
  most readings lost their tree. `asset_id` is set to text in every table
  (check: `Crowns` over all years is 1,927, not a few dozen).
- **Commas inside quotes.** Some site names contain commas ("Bonnville Road,
  Oakenhill Cottages"). Every table reads with `QuoteStyle.Csv`; with
  `QuoteStyle.None` those rows shift into the wrong columns.
- **Whole numbers written as "12.0".** pandas turns a whole-number column
  with blanks into decimals, which Power BI will not convert to whole
  numbers. The export writes them as true whole numbers
  (`powerbi_export.whole_numbers`, tested).
- **Map visuals need a work or school account.** Power BI's Azure Maps and
  map visuals ask for an organisational sign-in, so the tree explorer is a
  scatter chart of longitude against latitude, with a QGIS-rendered basemap
  as the plot background, drawn for exactly the chart's axis range. The
  fully interactive map is the web map in `web/`.

## Privacy

The garden tree's location is in none of these files. `case_study.csv` holds
its yearly readings only, and it never appears on a map.
