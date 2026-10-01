# Building the Power BI report

A five-page report on the phase 1 results, built in Power BI Desktop from the
CSV files in `data/`. No database needed. About two to three hours the
first time.

Save the finished report as `powerbi/bristol_beech_drought.pbix` and export
one screenshot per page to `powerbi/screenshots/` (File, Export, or a
screen capture), so the results show on GitHub without Power BI.

## The data

Rebuild the CSVs at any time with `python -m beech.powerbi_export`.

| File | One row per | Key columns |
|---|---|---|
| `trees.csv` | mapped crown (8,623) | `asset_id`, species, size class, site, canopy share, `analysable`, latitude, longitude |
| `tree_year.csv` | analysable crown per year (1,927 crowns × up to 9 years) | `asset_id`, `year`, change in greenness, moisture, red edge (ground removed), raw greenness change |
| `species_year.csv` | species, year and subset | median change with 95% interval (`_lo`, `_hi`); `subset` is "all" or "similar canopy share" |
| `years.csv` | year | median changes, `below_normal` (share of crowns below their normal) |
| `grass_vs_trees.csv` | year | greenness change for open grass, tree crowns raw, and ground removed |
| `weather.csv` | station and year | growing season rain, July rain, summer mean maximum, ranks |
| `field_check.csv` | field sample tree (61) | field scores and the 2026 satellite change where available |
| `case_study.csv` | year | the garden tree against the median large council beech |

All changes are against each tree's own normal years (2019 to 2021, 2023,
2024). Negative means less green, drier or less chlorophyll than normal.

## 1. Install and load

1. Install Power BI Desktop (free) from the Microsoft Store:
   https://apps.microsoft.com/detail/9NTXR16HNW1T
2. Open it, close the start screen, and choose **Get data, Text/CSV**.
   Load `trees.csv`. In the preview check the columns look right, then
   **Load**. Repeat for every CSV in `data/`.
3. Check the data types in **Table view** (left bar, the grid icon):
   - `asset_id`: Text (if Power BI turns it into a number, change it back;
     some IDs start with zeros).
   - `year`: Whole number. Under **Column tools**, set **Summarization** to
     "Don't summarize", so Power BI never adds years together.
   - `latitude`, `longitude`: Decimal number, with **Data category** set to
     Latitude and Longitude.
   - All the `change_` columns: Decimal number.

## 2. The model

Go to **Model view** (left bar, the third icon). Create two relationships
by dragging one column onto another:

- `trees[asset_id]` to `tree_year[asset_id]`: one to many, single direction.
- `trees[asset_id]` to `field_check[asset_id]`: one to many, single
  direction (some field trees have no crown; that is expected).

The other tables stand alone.

## 3. Measures

In `tree_year`, choose **New measure** and add each of these:

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

Format `Share below normal` as a percentage, and the change measures to
three decimal places (**Measure tools**, decimal places).

## 4. Pages

Use one colour for beech throughout (orange, `#EB6834`) and grey for the
other species, so beech stands out on every page. Give every page a title
text box that states its finding, not just its topic.

### Page 1. How extreme was 2026?

- **Scatter chart** from `weather`: X `growing_season_rain_mm`, Y
  `summer_mean_max_c`, Values `year`, Legend `station`. Title: "2026 was the
  hottest summer on record at both stations".
- **Clustered column chart** from `years`: X `year`, Y `d_ndre`. Turn on
  **Data labels**. Title: "2018 and 2022 read below normal, so the method
  sees drought".
- **Card**: `Share below normal` with a page filter `tree_year[year] = 2026`
  (84%).

### Page 2. Grass against trees

- **Clustered column chart** from `grass_vs_trees`: X `year`, Y `grass`,
  `trees_raw` and `trees_ground_removed`. Filter `year` to 2018, 2022, 2025
  and 2026. Title: "In dry summers grass browns far more than trees".
- A text box of two or three sentences: at 10 m, crown pixels include the
  ground; the ground's share is removed using LIDAR canopy cover.

### Page 3. Species

- **Clustered bar chart** from `species_year`: Y `species`, X `d_ndre`.
  Slicers for `year` (single select, default 2026) and `subset` (default
  "all").
- Error bars: in the **Analytics** pane (magnifying glass), add **Error
  bars**, relationship "By field", upper bound `d_ndre_hi`, lower bound
  `d_ndre_lo` (both as Min or Max, not Sum).
- Colour beech orange: **Format, Bars, Colors**, set each species, or use
  conditional formatting on `species`.
- Title: "Beech was among the hardest hit in 2026; lime and plane much
  less".

### Page 4. Tree explorer (map)

- **Map** (or Azure Map) from `trees`: Latitude, Longitude, Bubble size
  off, colour by `Median red edge change` (conditional formatting, diverging
  scale, red below zero, grey at zero). If the map visual is greyed out,
  enable it in **File, Options and settings, Options, Security, Map and
  Filled Map visuals**.
- Slicers: `tree_year[year]` (default 2026), `trees[species]`,
  `trees[size_class]`, `trees[site_type]`, and a filter
  `trees[analysable] = True`.
- **Table**: species, site name, size class, `Median red edge change`,
  sorted most negative first.
- Cards: `Crowns`, `Median red edge change`.

### Page 5. Field check and the garden tree

- **Table** from `field_check`: `tree_no`, species, `thinning_class`,
  `browning_class`, `stressed`, `change_red_edge_2026`. Filter
  `compared = True`.
- **Scatter chart**: X `thinning_class`, Y `change_red_edge_2026`, Legend
  `species`. Text box: the direction agrees, but only 4 stressed trees have
  readings, too few to confirm.
- **Line chart** from `case_study`: X `year`, Y `case_red_edge` and
  `large_beech_red_edge_median`. Title: "The garden tree lost more red edge
  in 2026 than most large council beeches". Note that 2018, 2020 and 2023
  rest on three or fewer clear images.

## 5. Finish

- **View, Themes**: pick a plain light theme; keep the beech colour.
- Check every page with the slicers reset (**Reset to default** on the
  ribbon).
- Save as `bristol_beech_drought.pbix`, export screenshots to
  `screenshots/`, and link them from the README.

Never add the garden tree to a map. Its location is not in any of these
files, and it must stay that way.
