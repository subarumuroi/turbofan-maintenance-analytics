-- Schema for NASA C-MAPSS FD001 (turbofan engine run-to-failure simulation).
-- One row per engine ("unit") per operating cycle, in wide form, plus a long
-- form of the same readings that makes per-sensor SQL simple.

DROP TABLE IF EXISTS cycles;
CREATE TABLE cycles (
    split TEXT NOT NULL CHECK (split IN ('train','test')),
    unit  INTEGER NOT NULL,
    cycle INTEGER NOT NULL,
    set1  REAL NOT NULL,
    set2  REAL NOT NULL,
    set3  REAL NOT NULL,
    s1 REAL NOT NULL,
    s2 REAL NOT NULL,
    s3 REAL NOT NULL,
    s4 REAL NOT NULL,
    s5 REAL NOT NULL,
    s6 REAL NOT NULL,
    s7 REAL NOT NULL,
    s8 REAL NOT NULL,
    s9 REAL NOT NULL,
    s10 REAL NOT NULL,
    s11 REAL NOT NULL,
    s12 REAL NOT NULL,
    s13 REAL NOT NULL,
    s14 REAL NOT NULL,
    s15 REAL NOT NULL,
    s16 REAL NOT NULL,
    s17 REAL NOT NULL,
    s18 REAL NOT NULL,
    s19 REAL NOT NULL,
    s20 REAL NOT NULL,
    s21 REAL NOT NULL,
    PRIMARY KEY (split, unit, cycle)
);

DROP TABLE IF EXISTS readings;
CREATE TABLE readings (
    split  TEXT NOT NULL,
    unit   INTEGER NOT NULL,
    cycle  INTEGER NOT NULL,
    sensor TEXT NOT NULL,
    value  REAL NOT NULL
);
CREATE INDEX idx_readings_sensor ON readings (split, sensor);
CREATE INDEX idx_readings_unit   ON readings (split, unit, cycle);

-- True remaining useful life (cycles) at the last observed cycle of each test engine.
DROP TABLE IF EXISTS test_rul;
CREATE TABLE test_rul (
    unit INTEGER PRIMARY KEY,
    rul  INTEGER NOT NULL
);

-- Training engines run to failure, so lifetime = last cycle and RUL = lifetime - cycle.
DROP VIEW IF EXISTS unit_lifetime;
CREATE VIEW unit_lifetime AS
SELECT unit, MAX(cycle) AS lifetime
FROM cycles
WHERE split = 'train'
GROUP BY unit;

DROP VIEW IF EXISTS train_rul;
CREATE VIEW train_rul AS
SELECT c.unit, c.cycle, l.lifetime, l.lifetime - c.cycle AS rul
FROM cycles c
JOIN unit_lifetime l ON l.unit = c.unit
WHERE c.split = 'train';
