# Data quality: Bristol City Council tree register

Loaded 28 September 2026, ingest run 1. Source: ArcGIS REST MapServer/32
(Open Government Licence 3.0). Queries: `sql/02_clean.sql` and the `qa` views.

## Load

| Check | Result |
|---|---|
| Records requested (beech, oak, lime, plane, sycamore genera) | 16,451 |
| Records loaded | 16,451, matching the service count |
| Duplicate OBJECTIDs while paging | none |
| Beeches | 985 (805 *Fagus sylvatica*, 144 'Purpurea', 36 other cultivars or genus only) |
| Points outside the Bristol area | none |

## Identifiers change between downloads

Reloaded on 30 September 2026 (ingest run 7), the register returned 56,581
records (the whole register, now loaded so every tree can act as a
neighbour when crowns are split), and **every OBJECTID had changed**: on
28 September they were around 37,812,000; on 30 September they ran from
37,925,039 to 37,981,619. The service had evidently been republished.
OBJECTID is therefore only a row number for one download. **ASSET_ID** is
unique and never null across all 56,581 records, and is used for every join
across downloads. The field sample drawn on 29 September (by a hash of
OBJECTID) is frozen by ASSET_ID in `raw.field_sample_frozen`; all 61 trees
were found again in the new download.

## Parsing

Trunk diameter (DBH), crown height and crown width are stored as text with
the unit inside the value. Of 49,353 measurement strings, every one either
parsed to a number or was an explicit "No Code Allocated". **None needed
manual handling** (`qa.parse_failures` is empty), including the two known
typos, "36 Centrimetres" and "93  Centimetres" (double space). No values
were implausible: no DBH over 3 m, height over 45 m, crown over 40 m or zeros.

## Completeness

| Group | Trees | No DBH | No height | No crown width |
|---|---|---|---|---|
| Lime | 6,672 | 4.9% | 6.6% | 6.7% |
| Sycamore | 3,397 | 8.4% | 3.7% | 3.7% |
| Plane | 2,943 | 4.0% | 3.3% | 3.2% |
| Oak (English and sessile) | 1,797 | 20.0% | 23.1% | 23.9% |
| **Beech** | **985** | **12.7%** | **12.0%** | **13.0%** |

Oak is the weakest-recorded group, so oak comparisons rest on fewer trees.

## Dead trees

**No tree in any group is flagged dead**, in either `DEAD` or `DEAD_FLAG`.
That fits the earlier finding across the whole register (0 of 56,573): dead
trees appear to be removed from the register rather than flagged. The
register therefore cannot show drought mortality directly.

## Trunk sizes are partly estimated

If DBH were measured with a tape, about 10% of values would fall on a
multiple of 10 cm. The register has 15 to 20% in every group. Individual
values are also heavily over-represented:

| Group | Most common DBH values (count) | Share in top five values |
|---|---|---|
| Beech | 6 cm (107), 8 cm (92), 20 cm (58), 32 cm (53), 80 cm (45) | 41% |
| Oak | 6 cm (296), 8 cm (110), 15 cm (81), 10 cm (54), 80 cm (49) | 41% |
| Lime | 6 cm (397), 32 cm (280), 50 cm (267), 41 cm (148), 20 cm (140) | 19% |

The 6 and 8 cm spikes are probably new plantings recorded at nursery size.
The spikes at 20, 32, 50 and 80 cm suggest banded or estimated values.
**Consequence for the analysis:** DBH is used only in broad size classes
(under 20, 20 to 49, 50 to 79, 80 cm and over), never as an exact age.

## Beech size classes

| Size class | Green beech | Purple beech |
|---|---|---|
| Under 20 cm | 308 | 84 |
| 20 to 49 cm | 211 | 17 |
| 50 to 79 cm | 93 | 25 |
| 80 cm and over | 106 | 16 |
| Unknown | 119 | 6 |

240 beeches have a DBH of 50 cm or more. These are the core of the
satellite analysis, subject to the crown size and purity rules in week 2.

## Species grouping

Comparison groups: beech, oak (*Quercus robur* and *petraea* only), lime (all
*Tilia*), plane (all *Platanus*), sycamore (all *Acer pseudoplatanus*).
Excluded from the comparison: evergreen oaks (holm oak and others, 220
trees), other exotic oaks (339) and genus-only oaks (98). Purple-leaved
trees (copper beech, purple sycamore) are flagged, because purple foliage
lowers greenness indices; they are compared against their own baselines.

## The register against the ground (field check, 30 September 2026)

41 sample trees on Clifton and Durdham Downs were visited
(`sql/07_field_check.sql`).

| Check | Result |
|---|---|
| Found at the register point | 40 of 41 |
| Not found | 1: tree 8 (PK30851, a 32 cm beech) |
| Species confirmed | 39 of 40; 1 unsure (tree 10, no leaves to check) |
| Register says live, tree is dead | 1: tree 10 (PK41290) |
| Returns not in the issued sample | none |
| Points moved in the app | none |
| Found trees with a blank score or photo | 1: tree 57, no photo |

**Tree 10 (PK41290)** is recorded as a live 100 cm beech (DEAD_FLAG "N",
crown 14 m wide, 18 m high). On the ground it is a monolith: the crown has
been cut off and giant polypore fruits in a ring around the trunk. The LIDAR
composite still shows its full crown, so both the register and the LIDAR
predate the cut. It is kept in every table and set aside from the drought
comparison (`analysis.field_exclusions`).

**What this suggests for the whole register:** one of 41 visited trees
(2%) is dead but recorded as live. Dead trees seem to leave the register
when they are removed, not when they die (see "Dead trees"), so a tree cut
to a monolith can stay listed as live. A satellite method that finds
sudden, lasting crown loss could flag trees like this for the council to
update.
