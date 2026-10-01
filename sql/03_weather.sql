-- 03_weather.sql
-- Met Office monthly station data, for the drought context.
--
-- Bristol has no station in the Met Office historic series, so two
-- stations either side of it are used: Yeovilton (about 50 km south) and
-- Cardiff Bute Park (about 40 km west). The most recent months are marked
-- "Provisional" by the Met Office and may be revised.

CREATE TABLE IF NOT EXISTS raw.met_station_monthly (
    station        text    NOT NULL,
    year           integer NOT NULL,
    month          integer NOT NULL CHECK (month BETWEEN 1 AND 12),
    tmax_c         numeric,
    tmin_c         numeric,
    air_frost_days integer,
    rain_mm        numeric,
    sun_hours      numeric,
    estimated      boolean NOT NULL,  -- any value marked * by the Met Office
    provisional    boolean NOT NULL,
    raw_line       text    NOT NULL,
    run_id         integer NOT NULL REFERENCES qa.ingest_log (run_id),
    PRIMARY KEY (station, year, month)
);

-- Summer (June to August) totals. A summer counts only when all three
-- months have rainfall.
CREATE OR REPLACE VIEW analysis.summer_rain AS
SELECT
    station,
    year,
    sum(rain_mm)                      AS jja_rain_mm,
    round(avg(tmax_c), 1)             AS jja_mean_tmax_c,
    bool_or(provisional)              AS provisional,
    count(rain_mm) = 3                AS complete
FROM raw.met_station_monthly
WHERE month IN (6, 7, 8)
GROUP BY station, year;

-- The 1991 to 2020 climate normal for summer rainfall, per station.
CREATE OR REPLACE VIEW analysis.summer_rain_normal AS
SELECT station, round(avg(jja_rain_mm), 1) AS normal_jja_rain_mm, count(*) AS n_years
FROM analysis.summer_rain
WHERE complete AND year BETWEEN 1991 AND 2020
GROUP BY station;

-- Every complete summer ranked from driest (1) within each station's record,
-- with the share of the normal.
CREATE OR REPLACE VIEW analysis.summer_rain_ranked AS
SELECT
    s.station,
    s.year,
    s.jja_rain_mm,
    s.jja_mean_tmax_c,
    s.provisional,
    round(100 * s.jja_rain_mm / n.normal_jja_rain_mm) AS pct_of_normal,
    rank() OVER (PARTITION BY s.station ORDER BY s.jja_rain_mm)  AS dry_rank,
    count(*) OVER (PARTITION BY s.station)                       AS n_summers
FROM analysis.summer_rain s
JOIN analysis.summer_rain_normal n USING (station)
WHERE s.complete;

-- Growing season climate per year: the drought context used in figure F1.
-- Growing season rain is March to August (spring recharge plus summer);
-- heat is the June to August mean of monthly maximum temperatures.
-- Only years with all months present are ranked.
CREATE OR REPLACE VIEW analysis.season_climate AS
WITH s AS (
    SELECT
        station,
        year,
        sum(rain_mm)   FILTER (WHERE month BETWEEN 3 AND 8) AS mar_aug_rain_mm,
        count(rain_mm) FILTER (WHERE month BETWEEN 3 AND 8) AS n_rain_months,
        sum(rain_mm)   FILTER (WHERE month BETWEEN 3 AND 5) AS spring_rain_mm,
        max(rain_mm)   FILTER (WHERE month = 7)             AS july_rain_mm,
        round(avg(tmax_c) FILTER (WHERE month BETWEEN 6 AND 8), 2) AS jja_mean_tmax_c,
        count(tmax_c)  FILTER (WHERE month BETWEEN 6 AND 8) AS n_tmax_months,
        bool_or(provisional)                                AS provisional
    FROM raw.met_station_monthly
    GROUP BY station, year
)
SELECT
    station, year, mar_aug_rain_mm, spring_rain_mm, july_rain_mm,
    jja_mean_tmax_c, provisional,
    rank() OVER (PARTITION BY station ORDER BY mar_aug_rain_mm)      AS dry_rank_mar_aug,
    rank() OVER (PARTITION BY station ORDER BY july_rain_mm)         AS dry_rank_july,
    rank() OVER (PARTITION BY station ORDER BY jja_mean_tmax_c DESC) AS hot_rank_summer,
    count(*) OVER (PARTITION BY station)                             AS n_years
FROM s
WHERE n_rain_months = 6 AND n_tmax_months = 3;
