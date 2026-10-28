-- Named queries used by src/*.py. Each block starts with "-- name: <id>".

-- name: dq_cycle_gaps
-- Every engine should have contiguous cycles 1..N. Counts engines that do not.
SELECT split,
       COUNT(*) AS units,
       SUM(CASE WHEN min_cycle = 1 AND max_cycle = n_rows THEN 0 ELSE 1 END) AS units_with_gaps
FROM (
    SELECT split, unit, MIN(cycle) AS min_cycle, MAX(cycle) AS max_cycle, COUNT(*) AS n_rows
    FROM cycles
    GROUP BY split, unit
)
GROUP BY split;

-- name: dq_sensor_profile
-- Per-channel profile on the training split: nulls, range, variance, distinct values.
-- Channels with zero variance carry no information and are dropped from modelling.
SELECT sensor,
       COUNT(*)                                        AS n,
       SUM(CASE WHEN value IS NULL THEN 1 ELSE 0 END)  AS n_null,
       MIN(value)                                      AS min_value,
       MAX(value)                                      AS max_value,
       AVG(value)                                      AS mean_value,
       AVG(value * value) - AVG(value) * AVG(value)    AS variance,
       COUNT(DISTINCT value)                           AS n_distinct
FROM readings
WHERE split = 'train'
GROUP BY sensor;

-- name: fleet_lifetimes
-- Lifetime of each training engine and its quartile within the fleet.
SELECT unit,
       lifetime,
       NTILE(4) OVER (ORDER BY lifetime) AS lifetime_quartile
FROM unit_lifetime
ORDER BY unit;

-- name: drift_by_life_stage
-- Mean and variance of each channel in ten life-stage bins (0 = first tenth of life,
-- 9 = last tenth), so degradation shows up as a trend across stages.
SELECT r.sensor,
       CAST(10.0 * (t.cycle - 1) / t.lifetime AS INTEGER)    AS stage,
       COUNT(*)                                              AS n,
       AVG(r.value)                                          AS mean_value,
       AVG(r.value * r.value) - AVG(r.value) * AVG(r.value)  AS variance
FROM readings r
JOIN train_rul t ON t.unit = r.unit AND t.cycle = r.cycle
WHERE r.split = 'train'
GROUP BY r.sensor, stage;

-- name: test_fleet_truth
-- Last observed cycle of each test engine and the true RUL at that point.
SELECT l.unit, l.last_cycle, r.rul AS rul_true
FROM (
    SELECT unit, MAX(cycle) AS last_cycle
    FROM cycles
    WHERE split = 'test'
    GROUP BY unit
) l
JOIN test_rul r ON r.unit = l.unit
ORDER BY l.unit;

-- name: train_labels
SELECT unit, cycle, lifetime, rul FROM train_rul;
