# Giant polypore cases in Bristol

Phase 2, step 2. Real cases of giant polypore (*Meripilus giganteus*) on
Bristol trees, matched to the council register, to test whether infected
trees show the garden tree's satellite signal. First search 26 October 2026.

## Sources searched

| Source | What it gave |
|---|---|
| News (Bristol Live via SWNS, Bristol24/7) | One case: the Victoria Square copper beech, fully documented |
| iNaturalist API, 12 km of the centre | 72 records, 2019 to 2026, most with GPS accuracy under 20 m |
| NBN Atlas, 12 km of the centre | 67 records, 1955 to 2025, but only to 100 m or 1 km grid and mostly Ashton Court or Leigh Woods; no use for single trees |
| FixMyStreet Bristol | St Andrews Park (ref 10102007, logged 2 Oct); web search finds other "fungus at base" reports but none naming the species. Needs a location-based sweep, not a text search |
| Facebook | Not searchable without a login. Bristol247's post (the screenshot) is the only one found |
| Bristol Tree Forum | Nothing on this fungus in search results |

Raw downloads and the matched table: `data/polypore/` (not committed;
iNaturalist records carry their observers' licences, so publish counts and
tree IDs, not the photos or observer names).

## Case 1: Victoria Square copper beech (fell 24 to 25 October 2026)

- **The tree:** copper beech planted about 1860, Victoria Square, Clifton.
  Saved from felling in the 1920s by the architect Eveline Drew Blacker,
  and again in 2017 after a campaign by residents and a local tree group.
- **The fungus:** found in 2017. Static load tests by external consultants
  in 2017, 2020, 2022 and 2025 showed stability declining since 2020. The
  council said it had produced "smaller and fewer leaves" over the last two
  summers. Felling announced about 21 October 2026.
- **The fall:** Storm Boelo brought it down the weekend of 24 to 25 October,
  damaging a low wall and the path. Nobody hurt.
- **Register match:** iNaturalist records of the fungus at Victoria Square
  in 2019, 2021, 2022, 2024 (three), 2025 and 2026. Five sit 7 to 8 m from
  **PK00066794** (copper beech, 108 cm trunk, 25 m tall, canopy share
  0.86). The park's other large copper beech, PK00066768, has no records
  near it. **To confirm:** that PK00066794 is the tree that fell (a visit,
  or the news photos against the park layout).
- **What the satellite says (greenness, ground removed):**

  | Year | PK00066794 | Rank of 195 beeches | PK00066768 (neighbour) |
  |---|---|---|---|
  | 2024 | −0.047 | | −0.011 |
  | 2025 | −0.101 | 6th lowest | −0.050 |
  | 2026 | −0.165 | 9th lowest | −0.098 |

  A steady three-year slide, already in the bottom 3% in 2025, the year
  before the drought peak. That matches the council's own account of the
  crown. It is the strongest case so far that root rot shows on Sentinel-2
  before a tree fails.

## Case 2: St Andrews Park beech, PK31500

Already logged (2 October 2026). iNaturalist adds independent records at
its base on 30 September 2024 (4 m away, "fungus at base of Beech tree")
and 19 October 2026 (2 m). So the fungus was fruiting at least two years
ago. Satellite: a drop in every year from 2022, rank 52 of 195 in 2026.
A second record on 17 September 2026 is 14 m from PK31512, a neighbouring
beech, to check on the ground.

## Other register beeches with records within 10 m

| Tree | Site | Records (years) | 2026 rank of 195 |
|---|---|---|---|
| PK00216254 | Eastville Park | 2019 (three), 2025, 2026 | 93 |
| PK30099 | Eastville Park | 2026 (two) | to check |
| PK30095 | Eastville Park | 2023 | to check |
| PK39651 (copper) | Eastville Park | 2026 ("growing on beech roots") | to check |
| PK00068436 (copper) | Mall Gardens, Clifton | 2026 | to check |
| PK00070452 (copper) | Park Place Park, Clifton | 2023, 2024, 2026 | not analysable (canopy share too low) |

Eastville Park is a hotspot: about 15 records over seven years. PK00216254
has fruited since at least 2019 with only mild drops, a useful counter case:
a tree can carry the fungus for years without a strong crown signal.

## Not register trees

About 40 records are more than 20 m from any register beech: private
gardens, the University (Royal Fort, Tyndalls Park), Goldney, Ashton Court,
Tyntesfield, Blaise, Stoke Park, Abbots Leigh. Useful for counts, not for
the satellite test. None is within 700 m of the garden tree.

## Next

1. Confirm which Victoria Square tree fell, and record the fall date.
2. Rank every matched tree for 2024 to 2026, not just 2026.
3. Test the matched trees as a group against all analysable beeches.
4. FixMyStreet sweep by location for "Tree in poor health" reports near
   register beeches.
5. Visit Eastville Park and the Clifton copper beeches to check the records.
