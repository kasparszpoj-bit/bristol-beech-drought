# Giant polypore: the per tree test, fixed in advance

Written 28 October 2026, before any 2027 data exists, so later seasons test the model rather than get fitted to it.

The citywide and UK tests (sightings against summer rain, fruiting against autumn rain) are in the separate project [giant-polypore-drought-uk](https://github.com/kasparszpoj-bit/giant-polypore-drought-uk).

## The test: does a tree's stress come before its fungus? (per tree)

- **Model:** `beech-polypore-hazard` (`src/beech/polypore_hazard.py`).
  Discrete-time survival: each analysable register beech, each year from
  2020, until the fungus is first recorded within 15 m of it (records
  located to 30 m or better). Trees first recorded in 2019 are left out,
  as they may have fruited long before.
- **Primary term:** red edge stress in the previous year, against the
  crown's own 2019 to 2024 baseline. Effort: log of all iNaturalist
  records that season. Complementary log-log link, permutation p value.
- **Prediction:** the hazard ratio for previous-year stress is above 1.
- **Result on 28 October 2026:** 7 first appearances in 1,245 tree years
  (9 with the 1 to 3 year mean). Hazard ratio 1.46 per 0.05 of stress
  (95% CI 0.76 to 2.79), permutation p = 0.25. In the predicted direction,
  not significant.
- **Power:** with this spread of stress, about 58 first appearances are
  needed to detect a ratio of 1.46 (5% level, 80% power), about 120 for
  1.3. Bristol adds around 2 to 5 a year from public records, so 2027 and
  2028 alone will not settle Test 2. It needs more trees checked (see
  below), not just more years.
- **Rerun:** every November with the code unchanged.

## What would strengthen it

A September survey of the analysable beeches, recording fungus present or
absent at each base, would give true absences (public records have none)
and more first appearances than chance sightings. The protocol would follow
`docs/field_protocol.md`.
