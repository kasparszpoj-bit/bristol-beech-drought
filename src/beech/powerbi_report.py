"""Write Power BI report pages as code (PBIR files in the .pbip project).

    python -m beech.powerbi_report

Power BI saves a project (.pbip) as one JSON file per visual. This writes
the report pages into powerbi/bristol_beech_drought.Report/, so they are
reproducible and reviewable in Git. Close Power BI Desktop before running
it (Power BI overwrites the files when it saves); reopen the .pbip and press
Refresh afterwards.

Colours follow the report figures: 2026 and beech orange, comparison
drought years blue, everything else grey.
"""

import hashlib
import json
import shutil
from pathlib import Path

from beech.db import PROJECT_ROOT

REPORT = PROJECT_ROOT / "powerbi" / "bristol_beech_drought.Report" / "definition"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
VISUAL_SCHEMA = f"{SCHEMA}/visualContainer/2.13.0/schema.json"
PAGE_SCHEMA = f"{SCHEMA}/page/2.1.0/schema.json"

ORANGE, BLUE, GREY = "#EB6834", "#2A78D6", "#B8B7AE"
DARK_BLUE, LIGHT_BLUE = "#184F95", "#6DA7EC"
SPECIES = ("beech", "sycamore", "oak", "lime", "plane")


# Field references --------------------------------------------------------

def vid(key: str) -> str:
    """A stable 20-character id, so reruns overwrite rather than duplicate."""
    return hashlib.md5(key.encode()).hexdigest()[:20]


def lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def text(value: str) -> dict:
    return lit("'" + value.replace("'", "''") + "'")


def column(table: str, name: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def measure(table: str, name: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": name}}


def total(table: str, name: str) -> dict:
    """Sum of a column (one row per category here, so the sum is the value)."""
    return {"Aggregation": {"Expression": column(table, name), "Function": 0}}


def projection(field: dict, ref: str, display: str | None = None) -> dict:
    p = {"field": field, "queryRef": ref, "nativeQueryRef": ref.split(".")[-1].rstrip(")")}
    if display:
        p["displayName"] = display
    return p


def fill(colour: str) -> dict:
    return {"fill": {"solid": {"color": lit(f"'{colour}'")}}}


def colour_by(table: str, name: str, value: str, colour: str) -> dict:
    """A data colour for one value of a category or series column."""
    return {
        "properties": fill(colour),
        "selector": {"data": [{"scopeId": {"Comparison": {
            "ComparisonKind": 0,
            "Left": column(table, name),
            "Right": {"Literal": {"Value": f"'{value}'"}},
        }}}]},
    }


def colour_measure(query_ref: str, colour: str) -> dict:
    """A data colour for one measure when a chart has several."""
    return {"properties": fill(colour), "selector": {"metadata": query_ref}}


# Filters -------------------------------------------------------------------

def _condition(table: str, name: str, cond: dict) -> dict:
    return {"Version": 2, "From": [{"Name": "t", "Entity": table, "Type": 0}],
            "Where": [{"Condition": cond}]}


def _ref(name: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": name}}


def equals(key: str, table: str, name: str, literal: str) -> dict:
    """Keep rows where table[name] equals a literal ('text' or 2026L)."""
    return {"name": vid(key), "field": column(table, name), "type": "Advanced",
            "filter": _condition(table, name, {"Comparison": {
                "ComparisonKind": 0, "Left": _ref(name),
                "Right": {"Literal": {"Value": literal}}}}),
            "howCreated": "User"}


def one_of(key: str, table: str, name: str, literals: list[str]) -> dict:
    return {"name": vid(key), "field": column(table, name), "type": "Categorical",
            "filter": _condition(table, name, {"In": {
                "Expressions": [_ref(name)],
                "Values": [[{"Literal": {"Value": v}}] for v in literals]}}),
            "howCreated": "User"}


# Visuals ---------------------------------------------------------------------

def container(key: str, x: float, y: float, w: float, h: float, order: int,
              visual: dict, title: str | None = None,
              filters: list[dict] | None = None) -> dict:
    vco = visual.setdefault("visualContainerObjects", {})
    vco["subTitle"] = [{"properties": {"show": lit("false")}}]
    if title:
        vco["title"] = [{"properties": {
            "show": lit("true"), "text": text(title), "fontSize": lit("20D"),
            "bold": lit("true"), "fontColor": {"solid": {"color": lit("'#252423'")}},
            "titleWrap": lit("true")}}]
    visual.setdefault("drillFilterOtherVisuals", True)
    c = {"$schema": VISUAL_SCHEMA, "name": vid(key),
         "position": {"x": x, "y": y, "z": order, "width": w, "height": h,
                      "tabOrder": order},
         "visual": visual}
    if filters:
        c["filterConfig"] = {"filters": filters}
    return c


def textbox(key, x, y, w, h, order, value, size, bold=False):
    style = {"fontSize": f"{size}pt"}
    if bold:
        style["fontWeight"] = "bold"
    paragraphs = [{"textRuns": [{"value": line, "textStyle": style}]}
                  for line in value.split("\n")]
    return {"$schema": VISUAL_SCHEMA, "name": vid(key),
            "position": {"x": x, "y": y, "z": order, "width": w, "height": h,
                         "tabOrder": order},
            "visual": {"visualType": "textbox",
                       "objects": {"general": [{"properties": {"paragraphs": paragraphs}}]},
                       "drillFilterOtherVisuals": True}}


# Text sizes for charts: axes, axis titles, legend and data labels.
AXIS_PT, LEGEND_PT, LABEL_PT = "14D", "14D", "13D"


def readable(objects: dict, labels: bool = False, axis_title_pt: str = AXIS_PT) -> dict:
    """Bigger axis, legend and label text on a chart's objects."""
    axis = {"fontSize": lit(AXIS_PT), "titleFontSize": lit(axis_title_pt),
            "titleBold": lit("true"), "showAxisTitle": lit("true")}
    for name in ("categoryAxis", "valueAxis"):
        props = objects.setdefault(name, [{"properties": {}}])[0]["properties"]
        props.update(axis)
    objects["legend"] = [{"properties": {"show": lit("true"), "fontSize": lit(LEGEND_PT),
                                         "position": text("Top")}}]
    if labels:
        objects.setdefault("labels", [{"properties": {}}])[0]["properties"].update(
            {"show": lit("true"), "fontSize": lit(LABEL_PT)})
    return objects


def big_number(key, x, y, w, h, order, field, ref, label, filters, colour=ORANGE):
    """A classic card: one large number with its label underneath."""
    return container(key, x, y, w, h, order, {
        "visualType": "card",
        "query": {"queryState": {"Values": {"projections": [projection(field, ref, label)]}}},
        "objects": {
            "labels": [{"properties": {"fontSize": lit("54D"), "bold": lit("true"),
                                       "color": {"solid": {"color": lit(f"'{colour}'")}}}}],
            "categoryLabels": [{"properties": {"show": lit("true"),
                                               "fontSize": lit("18D")}}],
        },
    }, filters=filters)


def card(key, x, y, w, h, order, field, ref, label, filters):
    return container(key, x, y, w, h, order, {
        "visualType": "cardVisual",
        "query": {"queryState": {"Data": {"projections": [projection(field, ref, label)]}}},
    }, filters=filters)


def header(prefix: str, title: str, intro: str) -> list[dict]:
    return [textbox(f"{prefix}-title", 40, 15, 1840, 70, 0, title, 28, bold=True),
            textbox(f"{prefix}-intro", 40, 85, 1840, 80, 1, intro, 15)]


# Pages -----------------------------------------------------------------------

def page1() -> list[dict]:
    w, y = "weather", "years"
    scatter = {
        "visualType": "scatterChart",
        "query": {"queryState": {
            "Category": {"projections": [projection(column(w, "station_year"),
                                                    "weather.station_year")]},
            "Series": {"projections": [projection(column(w, "year_group"),
                                                  "weather.year_group", "Years")]},
            "X": {"projections": [projection(
                total(w, "growing_season_rain_mm"), "Sum(weather.growing_season_rain_mm)",
                "Rain, March to August (mm)")]},
            "Y": {"projections": [projection(
                total(w, "summer_mean_max_c"), "Sum(weather.summer_mean_max_c)",
                "Mean daily maximum, June to August (°C)")]},
        }},
        "objects": readable({"dataPoint": [
            colour_by(w, "year_group", "2026", ORANGE),
            colour_by(w, "year_group", "2018, 2022, 2025", BLUE),
            colour_by(w, "year_group", "Other years", GREY),
        ], "bubbles": [{"properties": {"bubbleSize": lit("6L")}}]}, axis_title_pt="18D"),
    }
    columns = {
        "visualType": "columnChart",
        "query": {"queryState": {
            "Category": {"projections": [projection(column(y, "year"), "years.year", "Year")]},
            "Series": {"projections": [projection(column(y, "year_group"), "years.year_group",
                                                  "Years")]},
            "Y": {"projections": [projection(total(y, "d_ndre"), "Sum(years.d_ndre)",
                                             "Change in red edge from normal")]},
        }},
        "objects": readable({
            "categoryAxis": [{"properties": {"axisType": text("Categorical")}}],
            "labels": [{"properties": {"show": lit("true"), "labelPrecision": lit("3L")}}],
            "dataPoint": [
                colour_by(y, "year_group", "2026", ORANGE),
                colour_by(y, "year_group", "Known drought (2018, 2022)", BLUE),
                colour_by(y, "year_group", "Other years", GREY),
            ],
        }, labels=True),
    }
    # Labels outside the bars, so a larger font never gets hidden.
    columns["objects"]["labels"][0]["properties"]["labelPosition"] = text("OutsideEnd")
    columns = {
        **columns,
    }
    slicer = {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [
            projection(column(w, "station"), "weather.station", "Weather station")]}}},
        "objects": {
            "data": [{"properties": {"mode": text("Basic")}}],
            "general": [{"properties": {"orientation": lit("1D")}}],
            "header": [{"properties": {"textSize": lit("16D"), "bold": lit("true")}}],
            "items": [{"properties": {"textSize": lit("16D")}}],
        },
    }
    visuals = header(
        "p1",
        "2026 brought record heat, but Bristol's trees coped no worse than in the 2018 "
        "drought",
        "Left: summer heat and rainfall at the two weather stations either side of Bristol, "
        "every year on record; 2026 was the hottest summer at both. Right: how Bristol's "
        "council trees responded each summer since 2018, measured from satellite images; "
        "below zero means less chlorophyll than in a tree's own normal years. Although the "
        "weather was extreme, the trees held up about as well as in the 2018 drought: more "
        "trees were affected in 2026, but not more deeply.")
    visuals += [
        container("p1-slicer", 40, 175, 920, 80, 2, slicer),
        container("p1-scatter", 40, 265, 920, 790, 3, scatter,
                  "Each dot is one year at one station: 2026 sits alone in the hot, "
                  "dry corner"),
        big_number("p1-card", 1000, 175, 880, 220, 4,
                   measure("tree_year", "Share below normal"),
                   "tree_year.Share below normal",
                   "of tree crowns read below their normal in 2026",
                   [equals("p1-card-year", "tree_year", "year", "2026L")]),
        container("p1-columns", 1000, 415, 880, 640, 5, columns,
                  "2026 drought compared with other years"),
    ]
    return visuals


def panel(key, x, y, w, h, order, lines, size=13, fill="#F3F2EE"):
    """A text box with a light background; the first line is a bold heading."""
    head, *rest = lines
    paragraphs = [{"textRuns": [{"value": head,
                                 "textStyle": {"fontSize": f"{size + 3}pt",
                                               "fontWeight": "bold"}}]}]
    paragraphs += [{"textRuns": [{"value": line, "textStyle": {"fontSize": f"{size}pt"}}]}
                   for line in rest]
    v = textbox(key, x, y, w, h, order, "", size)
    v["visual"]["objects"]["general"][0]["properties"]["paragraphs"] = paragraphs
    v["visual"]["visualContainerObjects"] = {
        "background": [{"properties": {"show": lit("true"),
                                       "color": {"solid": {"color": lit(f"'{fill}'")}},
                                       "transparency": lit("0D")}}],
        "border": [{"properties": {"show": lit("true"),
                                   "color": {"solid": {"color": lit("'#D9D8D2'")}},
                                   "radius": lit("8D")}}],
        "padding": [{"properties": {k: lit("12D") for k in ("top", "bottom", "left", "right")}}],
    }
    return v


def image(key, x, y, w, h, order, item, title):
    """An image from the report's registered resources."""
    return container(key, x, y, w, h, order, {
        "visualType": "image",
        "objects": {
            "general": [{"properties": {"imageUrl": {"expr": {"ResourcePackageItem": {
                "PackageName": "RegisteredResources", "PackageType": 1,
                "ItemName": item}}}}}],
            "imageScaling": [{"properties": {"imageScalingType": text("Fit")}}],
        },
    }, title)


STEPS = [
    ("1  Trees", "56,581 council trees loaded, stored untouched, cleaned in SQL",
     "PostgreSQL, PostGIS"),
    ("2  Crowns", "A crown outline for 8,623 large trees from 1 m LIDAR, roofs removed",
     "QGIS model 01"),
    ("3  Satellite", "Greenness, moisture and red edge per crown, 243 images",
     "Sentinel-2, QGIS model 02"),
    ("4  Ground removed", "Canopy share from LIDAR; the ground around each crown subtracted",
     "QGIS model 03, SQL"),
    ("5  Own normal", "Each summer against the same tree in 2019 to 2021, 2023 and 2024",
     "SQL"),
    ("6  Compare and check", "Species and size with 95% intervals; 41 trees scored on foot",
     "Python, QField"),
]

CHECKS = [
    "Checks that the method works",
    "✓  The known droughts of 2018 and 2022 show up as stressed",
    ("✓  The satellite catalogue's correction was checked against the pixels, "
     "and found to be wrong"),
    "✓  QGIS model 02 matches an independent calculation",
    "✓  After the ground is removed, results no longer depend on crown size",
    "✓  The field survey agrees in direction",
    "✓  Every Power BI number reconciled with the analysis",
]


def page2() -> list[dict]:
    g = "grass_vs_trees"
    series = [("grass", "Open grass", GREY),
              ("trees_raw", "Tree crowns, raw", LIGHT_BLUE),
              ("trees_ground_removed", "Tree crowns, ground removed", DARK_BLUE)]
    chart = {
        "visualType": "clusteredColumnChart",
        "query": {"queryState": {
            "Category": {"projections": [projection(column(g, "year"), f"{g}.year", "Year")]},
            "Y": {"projections": [projection(total(g, c), f"Sum({g}.{c})", label)
                                  for c, label, _ in series]},
        }},
        "objects": readable({
            "categoryAxis": [{"properties": {"axisType": text("Categorical")}}],
            "labels": [{"properties": {"show": lit("true"), "labelPrecision": lit("2L"),
                                       "labelPosition": text("OutsideEnd")}}],
            "dataPoint": [colour_measure(f"Sum({g}.{c})", colour) for c, _, colour in series],
        }, labels=True),
    }
    # Larger text than the default, and a y-axis title that fits.
    o = chart["objects"]
    o["legend"][0]["properties"]["fontSize"] = lit("17D")
    o["labels"][0]["properties"]["fontSize"] = lit("15D")
    o["categoryAxis"][0]["properties"].update({"fontSize": lit("17D"), "titleFontSize": lit("16D")})
    o["valueAxis"][0]["properties"].update({"fontSize": lit("16D"), "titleFontSize": lit("16D"),
                                            "titleText": text("Change from normal")})
    visuals = header(
        "p2", "Methods",
        "Council tree records, a LIDAR laser survey and 243 satellite images, combined in "
        "PostGIS and three QGIS models. Every tree is compared with itself in normal years, "
        "and the grass around it is removed from every reading.")
    visuals.append(image("p2-crowns", 40, 165, 1300, 535, 2, "fig_crown_method.png",
                         "A. How a crown is drawn from LIDAR, on Durdham Down"))
    # Six steps stacked beside figure A: name and tool, then what happens.
    for i, (name, what, tool) in enumerate(STEPS):
        visuals.append(panel(f"p2-step{i}", 1365, 165 + i * 90, 515, 82, 3 + i,
                             [f"{name}   ·   {tool}", what], 12))
    visuals += [
        container("p2-chart", 40, 715, 1300, 345, 10, chart,
                  "B. Why the ground had to be removed: in dry summers grass browns far "
                  "more than trees",
                  filters=[one_of("p2-years", g, "year",
                                  ["2018L", "2022L", "2025L", "2026L"])]),
        panel("p2-checks", 1365, 715, 515, 345, 11, CHECKS, 13, fill="#EEF4FB"),
    ]
    return visuals


def stat(key, x, y, w, h, order, big, label, colour=ORANGE):
    """A headline figure as text: a large coloured line and a label under it."""
    v = panel(key, x, y, w, h, order, ["", label], 16, fill="#FFFFFF")
    v["visual"]["objects"]["general"][0]["properties"]["paragraphs"] = [
        {"textRuns": [{"value": big, "textStyle": {"fontSize": "40pt", "fontWeight": "bold",
                                                   "color": colour}}]},
        {"textRuns": [{"value": label, "textStyle": {"fontSize": "16pt"}}]},
    ]
    return v


FINDINGS = [
    "Key findings",
    ("1.  Beech was the only species clearly worse in 2026 than in the 2018 drought, "
     "and the hardest hit of the five."),
    ("2.  Overall, trees coped no worse than in 2018: more were affected, but not more "
     "deeply. Oak did better than in 2018."),
    ("3.  The oldest beeches (trunks of 80 cm and over) were not clearly worse than "
     "middle-sized ones."),
    ("4.  The stress was inside the leaves: chlorophyll and moisture fell, but crowns "
     "looked healthy on the ground in late September."),
]


def page3() -> list[dict]:
    c = "species_change"
    sort_2026 = {"sort": [{"field": total(c, "change_2026"), "direction": "Ascending"}]}
    both_years = {
        "visualType": "clusteredBarChart",
        "query": {"queryState": {
            "Category": {"projections": [projection(column(c, "species"), f"{c}.species",
                                                    "Species")]},
            "Y": {"projections": [
                projection(total(c, "change_2018"), f"Sum({c}.change_2018)", "2018 drought"),
                projection(total(c, "change_2026"), f"Sum({c}.change_2026)", "2026 drought")]},
        }, "sortDefinition": sort_2026},
        "objects": readable({
            "labels": [{"properties": {"show": lit("true"), "labelPrecision": lit("3L"),
                                       "labelPosition": text("OutsideEnd")}}],
            "dataPoint": [colour_measure(f"Sum({c}.change_2018)", BLUE),
                          colour_measure(f"Sum({c}.change_2026)", ORANGE)],
        }, labels=True),
    }
    both_years["objects"]["valueAxis"][0]["properties"]["titleText"] = text(
        "Change in red edge from normal")
    change = {
        "visualType": "clusteredBarChart",
        "query": {"queryState": {
            "Category": {"projections": [projection(column(c, "species"), f"{c}.species",
                                                    "Species")]},
            "Y": {"projections": [projection(total(c, "difference"), f"Sum({c}.difference)",
                                             "2026 minus 2018")]},
            "Tooltips": {"projections": [
                projection(column(c, "verdict"), f"{c}.verdict", "Verdict"),
                projection(total(c, "difference_lo"), f"Sum({c}.difference_lo)",
                           "95% range, low"),
                projection(total(c, "difference_hi"), f"Sum({c}.difference_hi)",
                           "95% range, high"),
                projection(total(c, "crowns"), f"Sum({c}.crowns)", "Trees")]},
        }, "sortDefinition": {"sort": [{"field": total(c, "difference"),
                                        "direction": "Ascending"}]}},
        "objects": readable({
            "labels": [{"properties": {"show": lit("true"), "labelPrecision": lit("3L"),
                                       "labelPosition": text("OutsideEnd")}}],
            # A one-series chart only uses per-category colours with "Show all" on.
            "dataPoint": [{"properties": {"showAllDataPoints": lit("true")}},
                          colour_by(c, "species", "beech", ORANGE),
                          colour_by(c, "species", "oak", BLUE),
                          colour_by(c, "species", "lime", GREY),
                          colour_by(c, "species", "plane", GREY),
                          colour_by(c, "species", "sycamore", GREY)],
        }, labels=True),
    }
    change["objects"]["valueAxis"][0]["properties"]["titleText"] = text(
        "Below zero: worse in 2026")
    change["objects"]["legend"][0]["properties"]["show"] = lit("false")

    beech_2026 = [equals("p3-card-year", "tree_year", "year", "2026L"),
                  equals("p3-card-species", "trees", "species", "'beech'")]
    return header(
        "p3", "Main findings: beech was the only species hit harder in 2026 than in the "
              "2018 drought",
        "Change in red edge (leaf chlorophyll) from each tree's own normal years, July and "
        "August, with the ground removed. Further below zero means more stressed.") + [
        big_number("p3-card", 40, 170, 600, 170, 2,
                   measure("tree_year", "Share below normal"), "tree_year.Share below normal",
                   "of beeches read below their normal in 2026", beech_2026),
        stat("p3-worst", 660, 170, 600, 170, 3, "Worst of 5",
             "beech had the largest drop of the five species in 2026"),
        stat("p3-only", 1280, 170, 600, 170, 4, "Only beech",
             "was worse than in 2018; oak did better, the rest unchanged"),
        container("p3-both", 40, 360, 900, 480, 5, both_years,
                  "A. 2018 against 2026, by species"),
        container("p3-change", 960, 360, 920, 480, 6, change,
                  "B. Change since 2018, same trees (hover for the 95% range)"),
        panel("p3-findings", 40, 860, 1840, 200, 7, FINDINGS, 14, fill="#EEF4FB"),
    ]


BASEMAP = "powerbi_basemap.png"
# lon_min, lon_max, lat_min, lat_max: the same box as qgis/scripts/render_basemap.py
MAP_EXTENT = (-2.7258, -2.4862, 51.4015, 51.5163)
BANDS = [("1 Strong drop", "#B4380A"), ("2 Drop", "#F08A4B"),
         ("3 Near normal", "#D9D8D2"), ("4 Above normal", "#2A78D6")]


def slicer(key, x, y, w, h, order, table, name, label, selected=None, single=False):
    """A list slicer; `selected` pre-selects literal values ('text' or 2026L)."""
    objects = {
        "data": [{"properties": {"mode": text("Basic")}}],
        "header": [{"properties": {"textSize": lit("15D"), "bold": lit("true")}}],
        "items": [{"properties": {"textSize": lit("14D")}}],
    }
    if single:
        objects["selection"] = [{"properties": {"singleSelect": lit("true")}}]
    if selected:
        objects["general"] = [{"properties": {"filter": {"filter": one_of(
            f"{key}-sel", table, name, selected)["filter"]}}}]
    return container(key, x, y, w, h, order, {
        "visualType": "slicer",
        "query": {"queryState": {"Values": {"projections": [
            projection(column(table, name), f"{table}.{name}", label)]}}},
        "objects": objects,
    })


def page4() -> list[dict]:
    t, y = "trees", "tree_year"
    red_edge = measure(y, "Median red edge change")
    # Power BI's map visuals need a work or school sign-in, so the map is a
    # scatter of longitude against latitude over a QGIS basemap
    # (qgis/scripts/render_basemap.py) drawn for exactly the same axis range.
    lon0, lon1, lat0, lat1 = MAP_EXTENT

    def axis(start, end):
        return [{"properties": {"show": lit("false"), "start": lit(f"{start}D"),
                                "end": lit(f"{end}D"), "gridlineShow": lit("false")}}]

    tree_map = {
        "visualType": "scatterChart",
        "query": {"queryState": {
            "Category": {"projections": [projection(column(t, "asset_id"), f"{t}.asset_id",
                                                    "Tree")]},
            "Series": {"projections": [projection(column(y, "change_band"),
                                                  f"{y}.change_band", "Change in red edge")]},
            "X": {"projections": [projection(
                {"Aggregation": {"Expression": column(t, "longitude"), "Function": 1}},
                f"Avg({t}.longitude)", "Longitude")]},
            "Y": {"projections": [projection(
                {"Aggregation": {"Expression": column(t, "latitude"), "Function": 1}},
                f"Avg({t}.latitude)", "Latitude")]},
            "Tooltips": {"projections": [
                projection(column(t, "species"), f"{t}.species", "Species"),
                projection(column(t, "site_name"), f"{t}.site_name", "Site"),
                projection(column(t, "size_class"), f"{t}.size_class", "Trunk size"),
                projection(red_edge, f"{y}.Median red edge change", "Red edge change")]},
        }},
        "objects": {
            "dataPoint": [colour_by(y, "change_band", band, colour) for band, colour in BANDS],
            "legend": [{"properties": {"show": lit("true"), "fontSize": lit("14D"),
                                       "position": text("Top")}}],
            "categoryAxis": axis(lon0, lon1),
            "valueAxis": axis(lat0, lat1),
            "bubbles": [{"properties": {"bubbleSize": lit("-4L")}}],
            "plotArea": [{"properties": {"transparency": lit("0D"), "image": {"image": {
                "name": text(BASEMAP),
                "url": {"expr": {"ResourcePackageItem": {
                    "PackageName": "RegisteredResources", "PackageType": 1,
                    "ItemName": BASEMAP}}},
                "scaling": text("Fit")}}}}],
        },
    }
    table = {
        "visualType": "tableEx",
        "query": {"queryState": {"Values": {"projections": [
            projection(column(t, "site_name"), f"{t}.site_name", "Site"),
            projection(column(t, "species"), f"{t}.species", "Species"),
            projection(column(t, "size_class"), f"{t}.size_class", "Trunk size"),
            projection(red_edge, f"{y}.Median red edge change", "Red edge change"),
        ]}}, "sortDefinition": {"sort": [{"field": red_edge, "direction": "Ascending"}]}},
        "objects": {
            "columnHeaders": [{"properties": {"fontSize": lit("12D"), "bold": lit("true")}}],
            "values": [{"properties": {"fontSize": lit("12D")}}],
        },
    }
    analysable = [equals("p4-analysable", t, "analysable", "true")]
    cards = [
        big_number("p4-crowns", 1380, 170, 163, 130, 6, measure(y, "Crowns"), f"{y}.Crowns",
                   "trees", [], colour="#252423"),
        big_number("p4-median", 1548, 170, 163, 130, 7, red_edge,
                   f"{y}.Median red edge change", "median change", []),
        big_number("p4-below", 1716, 170, 164, 130, 8, measure(y, "Share below normal"),
                   f"{y}.Share below normal", "below normal", []),
    ]
    for c in cards:
        c["visual"]["objects"]["labels"][0]["properties"]["fontSize"] = lit("28D")
        c["visual"]["objects"]["categoryLabels"][0]["properties"]["fontSize"] = lit("13D")
    page = header(
        "p4", "Tree explorer: where were Bristol's beeches hit hardest in 2026?",
        "Each dot is a council tree with a usable satellite reading. Colour shows the change "
        "in red edge from that tree's normal. It opens on beech in 2026: change the filters "
        "on the left to see other species or years, and click a tree in the table to find "
        "it on the map.") + [
        slicer("p4-year", 40, 170, 300, 200, 2, y, "year", "Year", ["2026L"], single=True),
        slicer("p4-species", 40, 380, 300, 230, 3, t, "species", "Species", ["'beech'"]),
        slicer("p4-size", 40, 620, 300, 200, 4, t, "size_class", "Trunk size"),
        slicer("p4-site", 40, 830, 300, 230, 5, t, "site_type", "Site type"),
        *cards,
        container("p4-map", 360, 170, 1000, 840, 9, tree_map,
                  "Change in red edge, 2026 against each tree's normal"),
        container("p4-table", 1380, 310, 500, 700, 10, table,
                  "Most affected trees (worst first)"),
        textbox("p4-note", 360, 1015, 1520, 50, 11,
                "Council trees only. Private trees, including the case study tree, are not "
                "shown. Bands: strong drop below −0.08, drop −0.08 to −0.03, near normal "
                "−0.03 to +0.03.", 11),
    ]
    for v in page:
        if v["name"] != vid("p4-note") and "visual" in v and v["visual"].get("visualType") not in (
                "textbox",):
            v.setdefault("filterConfig", {"filters": []})["filters"] += analysable
    return page


# Writing ---------------------------------------------------------------------

OUTPUTS = PROJECT_ROOT / "outputs" / "figures"


def register_image(path: Path) -> None:
    """Copy an image into the report and list it in report.json's resources."""
    res = REPORT.parent / "StaticResources" / "RegisteredResources"
    res.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, res / path.name)
    report_file = REPORT / "report.json"
    report = json.loads(report_file.read_text(encoding="utf-8"))
    packages = report.setdefault("resourcePackages", [])
    pkg = next((p for p in packages if p["name"] == "RegisteredResources"), None)
    if pkg is None:
        pkg = {"name": "RegisteredResources", "type": "RegisteredResources", "items": []}
        packages.append(pkg)
    if not any(i["name"] == path.name for i in pkg["items"]):
        pkg["items"].append({"name": path.name, "path": path.name, "type": "Image"})
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")


def write_page(page_id: str, display: str, visuals: list[dict]) -> None:
    page_dir = REPORT / "pages" / page_id
    (page_dir / "visuals").mkdir(parents=True, exist_ok=True)
    page_file = page_dir / "page.json"
    page = (json.loads(page_file.read_text(encoding="utf-8")) if page_file.exists() else
            {"$schema": PAGE_SCHEMA, "name": page_id, "displayOption": "FitToPage",
             "height": 1080, "width": 1920})
    page["displayName"] = display
    page_file.write_text(json.dumps(page, indent=2), encoding="utf-8")
    keep = {v["name"] for v in visuals}
    for stale in (page_dir / "visuals").iterdir():
        if stale.name not in keep:
            shutil.rmtree(stale)
    for v in visuals:
        d = page_dir / "visuals" / v["name"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "visual.json").write_text(json.dumps(v, indent=2, ensure_ascii=False),
                                       encoding="utf-8")


# The page made by hand in the first session, kept by its Power BI id. It
# is no longer first in the page order, so it cannot be looked up by position.
DROUGHT_PAGE = "8a8747db4c885d282665"


def main() -> None:
    pages_file = REPORT / "pages" / "pages.json"
    meta = json.loads(pages_file.read_text(encoding="utf-8"))
    first = DROUGHT_PAGE

    # The hand-made card from the first session is replaced by p1-card.
    for f in (REPORT / "pages" / first / "visuals").glob("*/visual.json"):
        v = json.loads(f.read_text(encoding="utf-8"))
        if v["visual"]["visualType"] == "cardVisual":
            shutil.rmtree(f.parent)
    write_page(first, "2 Drought", page1())
    register_image(OUTPUTS / "fig_crown_method.png")
    write_page(vid("page2"), "3 Methods", page2())
    write_page(vid("page3"), "4 Main findings", page3())

    register_image(OUTPUTS / BASEMAP)
    write_page(vid("page4"), "1 Tree explorer", page4())

    # The tree explorer opens the report.
    meta["pageOrder"] = [vid("page4"), first, vid("page2"), vid("page3")]
    meta["activePageName"] = vid("page4")
    pages_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print("written pages:", ", ".join(meta["pageOrder"]))


if __name__ == "__main__":
    main()
