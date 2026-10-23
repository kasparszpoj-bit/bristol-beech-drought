// Bristol's trees in the 2026 drought: the interactive map.
// Data: data/trees.geojson (one point per analysable council tree, with its
// yearly change from normal), data/crowns.geojson (LIDAR crown outlines) and
// data/boundary.geojson. Built by `beech-web-export`.

const YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
const DROUGHTS = new Set([2018, 2022, 2026]);
const SPECIES = ["beech", "sycamore", "oak", "lime", "plane"];
// Band colours match the Power BI report. `ink` is the text colour that reads on each.
const BANDS = [
  { key: "strong", short: "Strong drop", range: "below −0.08", colour: "#B4380A", ink: "#FFFFFF", test: v => v < -0.08 },
  { key: "drop", short: "Drop", range: "−0.08 to −0.03", colour: "#F08A4B", ink: "#1C2721", test: v => v < -0.03 },
  { key: "near", short: "Near normal", range: "−0.03 to +0.03", colour: "#D9D8D2", ink: "#1C2721", test: v => v <= 0.03 },
  { key: "above", short: "Above normal", range: "over +0.03", colour: "#2A78D6", ink: "#FFFFFF", test: () => true },
];
const TICKS = ["−0.08", "−0.03", "+0.03"];
const INK = "#1C2721";
const NO_IMAGE = "#8A9189";

// Quiet base map: Positron re-tinted so green space reads as sage and water as
// cool grey-blue, with labels pulled back. Keys are OpenFreeMap Positron layer ids.
const BASE_PAINT = {
  background: { "background-color": "#EEF0EA" },
  park: { "fill-color": "#DCE6D3" },
  landcover_wood: { "fill-color": "#D3DFCA" },
  landuse_residential: { "fill-color": "#E9ECE5" },
  water: { "fill-color": "#C3D3DA" },
  waterway: { "line-color": "#AFC4CD" },
  building: { "fill-color": "#E1E5DD", "fill-outline-color": "#D2D8CE" },
  highway_major_inner: { "line-color": "#FBFCF9" },
  highway_motorway_inner: { "line-color": "#FBFCF9" },
  water_name_point_label: { "text-color": "#4E6F82", "text-halo-color": "rgba(238,240,234,0.8)" },
  water_name_line_label: { "text-color": "#4E6F82", "text-halo-color": "rgba(238,240,234,0.8)" },
  "highway-name-minor": { "text-color": "#7D877F" },
  "highway-name-major": { "text-color": "#6F7A72" },
};
const PLACE_LABELS = ["label_other", "label_village", "label_town", "label_city", "label_city_capital"];
const HIDDEN_BASE = ["highway-shield-non-us", "highway-shield-us-interstate", "road_shield_us", "airport"];
const SIZES = [
  { key: "small", label: "Under 50 cm", match: s => s.startsWith("1") || s.startsWith("2") },
  { key: "mid", label: "50 to 79 cm", match: s => s.startsWith("3") },
  { key: "large", label: "80 cm and over", match: s => s.startsWith("4") },
  { key: "unknown", label: "Not recorded", match: () => true },
];
const SITES = [
  { key: "park", label: "Parks", match: t => t.startsWith("Parks") },
  { key: "street", label: "Streets", match: t => t.startsWith("Highways") },
  { key: "other", label: "Other council land", match: () => true },
];
const BOUNDS = [[-2.72, 51.40], [-2.49, 51.52]];

const state = {
  year: 2026,
  species: new Set(SPECIES),
  sizes: new Set(SIZES.map(s => s.key)),
  sites: new Set(SITES.map(s => s.key)),
  selected: null,
  playing: null,
};

let trees = [];        // feature list
const byId = new Map(); // id to feature

const fmt = v => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(3);
const band = v => BANDS.find(b => b.test(v));
const median = values => {
  if (!values.length) return null;
  const s = [...values].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const yearValue = (props, year) => props.red_edge ? props.red_edge[YEARS.indexOf(year)] : null;
const el = (tag, attrs = {}, text) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text !== undefined) e.textContent = text;
  return e;
};

// ---- Map ----------------------------------------------------------------

const map = new maplibregl.Map({
  container: "map",
  style: "https://tiles.openfreemap.org/styles/positron",
  bounds: BOUNDS,
  fitBoundsOptions: { padding: 20 },
  maxBounds: [[-3.1, 51.2], [-2.1, 51.7]],
  hash: true,
  attributionControl: false,
});
map.addControl(new maplibregl.AttributionControl({
  compact: true,
  customAttribution: "Trees: Bristol City Council (OGL) · Crowns: EA LIDAR · Readings: Copernicus Sentinel-2 · Terrain: Mapzen",
}));
map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");
map.addControl(new maplibregl.FullscreenControl(), "top-right");
map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

function colourExpression(year) {
  const v = ["get", `r${year}`];
  return ["case",
    ["==", v, null], "#FFFFFF",
    ["<", v, -0.08], BANDS[0].colour,
    ["<", v, -0.03], BANDS[1].colour,
    ["<=", v, 0.03], BANDS[2].colour,
    BANDS[3].colour];
}

function filterExpression() {
  return ["all",
    ["in", ["get", "species"], ["literal", [...state.species]]],
    ["in", ["get", "sizeKey"], ["literal", [...state.sizes]]],
    ["in", ["get", "siteKey"], ["literal", [...state.sites]]]];
}

// Every tree layer sorts its strongest changes to the top, so a scorched tree
// is never hidden under a near-normal neighbour.
const sortKey = year => ["abs", ["coalesce", ["get", `r${year}`], 0]];
const missing = year => ["==", ["get", `r${year}`], null];

function styleBasemap() {
  const set = (id, prop, value) => { if (map.getLayer(id)) map.setPaintProperty(id, prop, value); };
  for (const [id, paint] of Object.entries(BASE_PAINT)) {
    for (const [prop, value] of Object.entries(paint)) set(id, prop, value);
  }
  for (const id of PLACE_LABELS) {
    set(id, "text-color", "#36433B");
    set(id, "text-halo-color", "rgba(238,240,234,0.9)");
    set(id, "text-halo-width", 1.4);
  }
  for (const id of HIDDEN_BASE) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", "none");

  // Soft relief: the Avon Gorge, the Downs and the ridges behind the city.
  map.addSource("terrain", {
    type: "raster-dem",
    tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
    encoding: "terrarium",
    tileSize: 256,
    maxzoom: 15,
  });
  map.addLayer({ id: "hillshade", type: "hillshade", source: "terrain",
    paint: { "hillshade-exaggeration": 0.32,
             "hillshade-shadow-color": "#4B5C4E",
             "hillshade-highlight-color": "#FFFFFF",
             "hillshade-accent-color": "#5F6E62",
             "hillshade-illumination-direction": 315 } },
    map.getLayer("building") ? "building" : undefined);
}

// Everything outside the city boundary, as one polygon with Bristol cut out.
function outsideMask(boundary) {
  const holes = boundary.features.flatMap(f =>
    f.geometry.type === "Polygon" ? [f.geometry.coordinates[0]] : f.geometry.coordinates.map(p => p[0]));
  return { type: "Feature", properties: {}, geometry: { type: "Polygon",
    coordinates: [[[-4, 50.5], [-1, 50.5], [-1, 52.5], [-4, 52.5], [-4, 50.5]], ...holes] } };
}

function addLayers(treeData, crownData, boundary) {
  styleBasemap();
  map.addSource("aerial", {
    type: "raster",
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    tileSize: 256,
    maxzoom: 19,
    attribution: "Aerial: Esri, Maxar, Earthstar Geographics",
  });
  // Above the basemap's own layers, below the trees.
  map.addLayer({ id: "aerial", type: "raster", source: "aerial",
    layout: { visibility: "none" } });

  // Dim the land outside Bristol so the eye stays on the city's trees.
  map.addSource("outside", { type: "geojson", data: outsideMask(boundary) });
  map.addLayer({ id: "outside", type: "fill", source: "outside",
    paint: { "fill-color": "#F6F7F3", "fill-opacity": 0.55 } });

  map.addSource("boundary", { type: "geojson", data: boundary });
  map.addLayer({ id: "boundary-halo", type: "line", source: "boundary",
    paint: { "line-color": "#FFFFFF", "line-width": 5, "line-opacity": 0.7 } });
  map.addLayer({ id: "boundary", type: "line", source: "boundary",
    paint: { "line-color": INK, "line-width": 1.3, "line-opacity": 0.75, "line-dasharray": [4, 2] } });

  map.addSource("crowns", { type: "geojson", data: crownData, promoteId: "id" });
  map.addLayer({ id: "crowns", type: "fill", source: "crowns", minzoom: 14.5,
    layout: { "fill-sort-key": sortKey(state.year) },
    paint: { "fill-color": colourExpression(state.year),
             "fill-opacity": ["interpolate", ["linear"], ["zoom"], 14.5, 0, 15.5, 0.82] } });
  map.addLayer({ id: "crown-lines", type: "line", source: "crowns", minzoom: 14.5,
    paint: { "line-color": INK,
             "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 2.5, 0.7],
             "line-opacity": ["interpolate", ["linear"], ["zoom"], 14.5, 0, 15.5, 0.55] } });

  map.addSource("trees", { type: "geojson", data: treeData, promoteId: "id" });
  map.addLayer({ id: "trees", type: "circle", source: "trees",
    layout: { "circle-sort-key": sortKey(state.year) },
    paint: {
      "circle-color": colourExpression(state.year),
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 2.4, 12, 4, 14, 6, 15.5, 4, 18, 5],
      // A thin dark rim gives the pale bands contrast against the light base map.
      "circle-stroke-color": ["case", missing(state.year), NO_IMAGE, "rgba(28,39,33,0.5)"],
      "circle-stroke-width": ["case", missing(state.year), 1.5, 0.7],
    } });
  // The selected tree: a dark ring on a white halo, visible on both basemaps.
  for (const [id, colour, width] of [["selected-halo", "#FFFFFF", 6], ["selected", INK, 2.5]]) {
    map.addLayer({ id, type: "circle", source: "trees",
      filter: ["==", ["get", "id"], ""],
      paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 9, 18, 13],
               "circle-color": "rgba(0,0,0,0)",
               "circle-stroke-color": colour, "circle-stroke-width": width } });
  }
}

function applyYear() {
  const colour = colourExpression(state.year);
  const none = missing(state.year);
  map.setPaintProperty("trees", "circle-color", colour);
  map.setPaintProperty("trees", "circle-stroke-color", ["case", none, NO_IMAGE, "rgba(28,39,33,0.5)"]);
  map.setPaintProperty("trees", "circle-stroke-width", ["case", none, 1.5, 0.7]);
  map.setLayoutProperty("trees", "circle-sort-key", sortKey(state.year));
  map.setPaintProperty("crowns", "fill-color", colour);
  map.setLayoutProperty("crowns", "fill-sort-key", sortKey(state.year));
  document.getElementById("key-year").textContent = state.year;
  const kind = document.getElementById("key-kind");
  kind.textContent = DROUGHTS.has(state.year) ? "drought summer" : "summer";
  kind.classList.toggle("drought", DROUGHTS.has(state.year));
}

function applyFilters() {
  const f = filterExpression();
  for (const id of ["trees", "crowns", "crown-lines"]) map.setFilter(id, f);
}

// ---- Panel --------------------------------------------------------------

function visible(props) {
  return state.species.has(props.species) && state.sizes.has(props.sizeKey) &&
    state.sites.has(props.siteKey);
}

function updateStats() {
  const values = trees.map(f => f.properties)
    .filter(visible)
    .map(p => yearValue(p, state.year))
    .filter(v => v !== null);
  const m = median(values);
  document.getElementById("stat-n").textContent = values.length.toLocaleString("en-GB");
  document.getElementById("stat-median").textContent = m === null ? "none" : fmt(m);
  const below = values.length ? values.filter(v => v < 0).length / values.length : null;
  document.getElementById("stat-below").textContent =
    below === null ? "none" : `${Math.round(below * 100)}%`;
}

function updateSpecies() {
  const box = document.getElementById("species");
  box.replaceChildren();
  const rows = SPECIES.map(sp => {
    const values = trees.map(f => f.properties)
      .filter(p => p.species === sp && state.sizes.has(p.sizeKey) && state.sites.has(p.siteKey))
      .map(p => yearValue(p, state.year))
      .filter(v => v !== null);
    return { sp, m: median(values), n: values.length };
  });
  const scale = 0.08; // half the track in red edge units
  for (const r of rows) {
    const on = state.species.has(r.sp);
    const b = el("button", { class: "sp", type: "button", "aria-pressed": String(on),
      title: `${r.sp}: ${r.n} trees` });
    b.append(el("span", { class: "sp-name" }, r.sp));
    const track = el("span", { class: "sp-track" });
    track.append(el("span", { class: "sp-zero", style: "left:50%" }));
    if (r.m !== null) {
      const w = Math.min(Math.abs(r.m) / scale, 1) * 50;
      const left = r.m < 0 ? 50 - w : 50;
      track.append(el("span", { class: `sp-bar ${r.m < 0 ? "neg" : "pos"}`,
        style: `left:${left}%;width:${w}%;background:${band(r.m).colour}` }));
    }
    b.append(track, el("span", { class: "sp-value" }, r.m === null ? "none" : fmt(r.m)));
    b.addEventListener("click", () => {
      if (on && state.species.size === 1) {
        SPECIES.forEach(s => state.species.add(s)); // last one off: show all again
      } else if (on) {
        state.species.delete(r.sp);
      } else {
        state.species.add(r.sp);
      }
      refresh();
    });
    box.append(b);
  }
}

function chips(boxId, options, set, counter) {
  const box = document.getElementById(boxId);
  box.replaceChildren();
  for (const o of options) {
    const on = set.has(o.key);
    const b = el("button", { type: "button", "aria-pressed": String(on) }, o.label);
    b.append(el("span", { class: "count" }, counter(o.key).toLocaleString("en-GB")));
    b.addEventListener("click", () => {
      if (on && set.size === 1) options.forEach(x => set.add(x.key));
      else if (on) set.delete(o.key);
      else set.add(o.key);
      refresh();
    });
    box.append(b);
  }
}

function updateChips() {
  const props = trees.map(f => f.properties).filter(p => state.species.has(p.species));
  chips("sizes", SIZES, state.sizes,
    k => props.filter(p => p.sizeKey === k && state.sites.has(p.siteKey)).length);
  chips("sites", SITES, state.sites,
    k => props.filter(p => p.siteKey === k && state.sizes.has(p.sizeKey)).length);
}

function buildYears() {
  const box = document.getElementById("years");
  box.replaceChildren();
  const shown = trees.map(f => f.properties).filter(visible);
  for (const y of YEARS) {
    const m = median(shown.map(p => yearValue(p, y)).filter(v => v !== null));
    const b = el("button", { type: "button", role: "radio",
      "aria-checked": String(y === state.year),
      class: DROUGHTS.has(y) ? "drought" : "",
      title: m === null ? `${y}: no readings` : `${y}: median ${fmt(m)}`,
      "aria-label": `${y}${DROUGHTS.has(y) ? ", drought year" : ""}` }, String(y));
    if (m !== null) b.style.cssText = `--c:${band(m).colour};--t:${band(m).ink}`;
    b.addEventListener("click", () => { stopPlay(); setYear(y); });
    box.append(b);
  }
}

function setYear(y) {
  state.year = y;
  applyYear();
  refresh(false);
  if (state.selected) showDetail(state.selected);
}

function togglePlay() {
  if (state.playing) return stopPlay();
  const btn = document.getElementById("play");
  btn.setAttribute("aria-pressed", "true");
  btn.textContent = "Stop";
  let i = YEARS.indexOf(state.year);
  state.playing = setInterval(() => {
    i = (i + 1) % YEARS.length;
    setYear(YEARS[i]);
  }, 1400);
}

function stopPlay() {
  if (!state.playing) return;
  clearInterval(state.playing);
  state.playing = null;
  const btn = document.getElementById("play");
  btn.setAttribute("aria-pressed", "false");
  btn.textContent = "Play years";
}

// A diverging scale bar, with the band edges marked above it.
function buildLegend() {
  const ul = document.getElementById("legend");
  for (const b of BANDS) {
    const li = el("li", { title: `${b.short} (${b.range})` });
    li.append(el("span", { class: "bar", style: `background:${b.colour}` }),
      el("span", { class: "lab" }, b.short), el("span", { class: "sr-only" }, ` (${b.range})`));
    ul.append(li);
  }
  const ticks = el("div", { class: "ticks", "aria-hidden": "true" });
  TICKS.forEach((t, i) => ticks.append(el("span", { style: `left:${(i + 1) * 25}%` }, t)));
  ul.append(ticks);
}

function buildFinder() {
  const counts = new Map();
  for (const f of trees) {
    const s = f.properties.site;
    if (s) counts.set(s, (counts.get(s) || 0) + 1);
  }
  const list = document.getElementById("site-list");
  [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0])).forEach(([s, n]) => {
    list.append(el("option", { value: s, label: `${n} tree${n > 1 ? "s" : ""}` }));
  });
  document.getElementById("find").addEventListener("change", e => {
    const hits = trees.filter(f => f.properties.site === e.target.value);
    if (!hits.length) return;
    const b = new maplibregl.LngLatBounds();
    hits.forEach(f => b.extend(f.geometry.coordinates));
    map.fitBounds(b, { padding: 80, maxZoom: 17.5, duration: 1200 });
    if (hits.length === 1) select(hits[0].properties.id);
  });
}

// ---- Selected tree ------------------------------------------------------

function historyChart(p) {
  const W = 320, H = 150, L = 34, R = 6, T = 10, B = 22;
  const vals = p.red_edge || [];
  const biggest = Math.max(0, ...vals.filter(v => v !== null).map(Math.abs));
  const max = [0.05, 0.1, 0.15, 0.2, 0.3, 0.5].find(m => m >= biggest) || 1;
  const y = v => T + (H - T - B) / 2 * (1 - v / max);
  const step = (W - L - R) / YEARS.length;
  const bw = step * 0.62;
  const parts = [];
  for (const t of [max, 0, -max]) {
    parts.push(`<line x1="${L}" x2="${W - R}" y1="${y(t)}" y2="${y(t)}" stroke="${t === 0 ? "#626e66" : "#e6eae3"}" stroke-width="1"/>`);
    parts.push(`<text x="${L - 5}" y="${y(t) + 4}" text-anchor="end" font-size="10" fill="#626e66">${t === 0 ? "0" : (t > 0 ? "+" : "−") + Math.abs(t).toFixed(2)}</text>`);
  }
  YEARS.forEach((yr, i) => {
    const v = vals[i];
    const x = L + i * step + (step - bw) / 2;
    const current = yr === state.year;
    if (v === null || v === undefined) {
      parts.push(`<text x="${x + bw / 2}" y="${y(0) - 4}" text-anchor="middle" font-size="9" fill="#8a9189">n/a</text>`);
    } else {
      const top = Math.min(y(v), y(0));
      const h = Math.max(Math.abs(y(v) - y(0)), 1);
      parts.push(`<rect x="${x}" y="${top}" width="${bw}" height="${h}" rx="2" fill="${band(v).colour}"${current ? ' stroke="#1c2721" stroke-width="1.5"' : ""}><title>${yr}: ${fmt(v)}</title></rect>`);
    }
    parts.push(`<text x="${x + bw / 2}" y="${H - 6}" text-anchor="middle" font-size="10" fill="${current ? "#1c2721" : "#626e66"}"${current ? ' font-weight="700"' : ""}>${String(yr).slice(2)}${DROUGHTS.has(yr) ? "*" : ""}</text>`);
  });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Change in red edge from normal, 2018 to 2026">${parts.join("")}</svg>`;
}

function showDetail(id) {
  const f = byId.get(id);
  if (!f) return;
  const p = f.properties;
  const i = YEARS.indexOf(state.year);
  const v = k => (p[k] && p[k][i] !== null && p[k][i] !== undefined) ? fmt(p[k][i]) : "no reading";
  const box = document.getElementById("detail");
  const name = p.name || (p.species[0].toUpperCase() + p.species.slice(1));
  box.innerHTML = `
    <button class="close" type="button" aria-label="Close tree details">×</button>
    <h3></h3>
    <p class="latin"></p>
    <dl>
      <dt>Site</dt><dd data-k="site"></dd>
      <dt>Trunk</dt><dd>${p.dbh ? `${Math.round(p.dbh)} cm across` : "not recorded"}</dd>
      <dt>Height</dt><dd>${p.height ? `${p.height} m (LIDAR)` : "unknown"}</dd>
      <dt>Canopy share</dt><dd>${p.canopy !== null ? `${Math.round(p.canopy * 100)}% of its pixels` : "unknown"}</dd>
      <dt>Council ID</dt><dd>${p.id}</dd>
    </dl>
    <p class="chart-title">Change in red edge from its normal, by year</p>
    ${historyChart(p)}
    <dl>
      <dt>${state.year} red edge</dt><dd>${v("red_edge")}</dd>
      <dt>${state.year} greenness</dt><dd>${v("greenness")}</dd>
      <dt>${state.year} leaf moisture</dt><dd>${v("moisture")}</dd>
    </dl>
    <p class="note">* drought years. Below zero: less chlorophyll than in this tree's
      normal summers (2019 to 2021, 2023, 2024). One tree's reading is noisy; patterns
      across many trees are what the method can show.</p>`;
  box.querySelector("h3").textContent = name;
  box.querySelector(".latin").textContent =
    (p.latin || "").replace(/\s*-\s*Species Unknown/i, " (species not recorded)");
  box.querySelector('[data-k="site"]').textContent = p.site || "unnamed site";
  box.querySelector(".close").addEventListener("click", () => select(null));
  box.style.borderLeftColor = yearValue(p, state.year) === null ? NO_IMAGE : band(yearValue(p, state.year)).colour;
  box.hidden = false;
}

function select(id) {
  if (state.selected) map.setFeatureState({ source: "crowns", id: state.selected }, { selected: false });
  state.selected = id;
  for (const layer of ["selected-halo", "selected"]) map.setFilter(layer, ["==", ["get", "id"], id || ""]);
  if (id) {
    map.setFeatureState({ source: "crowns", id }, { selected: true });
    showDetail(id);
    const box = document.getElementById("detail");
    box.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } else {
    document.getElementById("detail").hidden = true;
  }
}

// ---- Wiring -------------------------------------------------------------

function refresh(rebuildMap = true) {
  if (rebuildMap) applyFilters();
  buildYears();
  updateStats();
  updateSpecies();
  updateChips();
}

function prepare(treeData, crownData) {
  for (const f of treeData.features) {
    const p = f.properties;
    YEARS.forEach((y, i) => { p[`r${y}`] = p.red_edge ? p.red_edge[i] : null; });
    p.sizeKey = SIZES.find(s => s.match(p.size || "")).key;
    p.siteKey = SITES.find(s => s.match(p.site_type || "")).key;
    byId.set(p.id, f);
  }
  // Crowns carry the same styling fields as their tree.
  for (const f of crownData.features) {
    const t = byId.get(f.properties.id);
    if (!t) continue;
    const { species, sizeKey, siteKey } = t.properties;
    Object.assign(f.properties, { species, sizeKey, siteKey });
    YEARS.forEach(y => { f.properties[`r${y}`] = t.properties[`r${y}`]; });
  }
  trees = treeData.features;
}

function hoverTips() {
  const tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 });
  const show = e => {
    const p = byId.get(e.features[0].properties.id)?.properties;
    if (!p) return;
    map.getCanvas().style.cursor = "pointer";
    const v = yearValue(p, state.year);
    const node = el("div");
    node.append(el("strong", {}, p.name || p.species), el("span", { class: "tip-site" }, p.site || ""), el("br"),
      el("span", { class: "tip-value", style: `--c:${v === null ? "#FFFFFF" : band(v).colour}` },
        v === null ? `${state.year}: no clear image` : `${state.year}: ${fmt(v)} red edge`));
    tip.setLngLat(e.lngLat).setDOMContent(node).addTo(map);
  };
  const hide = () => { map.getCanvas().style.cursor = ""; tip.remove(); };
  for (const layer of ["trees", "crowns"]) {
    map.on("mousemove", layer, show);
    map.on("mouseleave", layer, hide);
    map.on("click", layer, e => select(e.features[0].properties.id));
  }
}

function basemapButtons() {
  document.querySelectorAll(".basemaps button").forEach(b => {
    b.addEventListener("click", () => {
      const aerial = b.dataset.base === "aerial";
      map.setLayoutProperty("aerial", "visibility", aerial ? "visible" : "none");
      map.setPaintProperty("outside", "fill-color", aerial ? "#10140F" : "#F6F7F3");
      map.setPaintProperty("outside", "fill-opacity", aerial ? 0.45 : 0.55);
      map.setPaintProperty("boundary", "line-color", aerial ? "#FFFFFF" : INK);
      map.setLayoutProperty("boundary-halo", "visibility", aerial ? "none" : "visible");
      document.querySelectorAll(".basemaps button").forEach(x =>
        x.setAttribute("aria-pressed", String(x === b)));
    });
  });
}

async function load(name) {
  const r = await fetch(`data/${name}.geojson`);
  if (!r.ok) throw new Error(`${name}: ${r.status}`);
  return r.json();
}

Promise.all([load("trees"), load("crowns"), load("boundary"),
  new Promise(res => map.on("load", res))])
  .then(([treeData, crownData, boundary]) => {
    prepare(treeData, crownData);
    addLayers(treeData, crownData, boundary);
    buildLegend();
    buildFinder();
    hoverTips();
    basemapButtons();
    document.getElementById("play").addEventListener("click", togglePlay);
    refresh();
    document.getElementById("loading").hidden = true;
    // Start with the credits folded away, so they do not cover a phone screen.
    const credits = document.querySelector(".maplibregl-ctrl-attrib");
    credits?.classList.remove("maplibregl-compact-show");
    credits?.removeAttribute("open");
  })
  .catch(err => {
    document.getElementById("loading").textContent = `Could not load the map data (${err.message}).`;
  });
