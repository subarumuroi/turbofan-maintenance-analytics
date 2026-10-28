WITH base AS (
    SELECT split, unit,
        AVG(s9) AS b_s9,
        AVG(s11) AS b_s11,
        AVG(s4) AS b_s4,
        AVG(s12) AS b_s12,
        AVG(s7) AS b_s7,
        AVG(s15) AS b_s15,
        AVG(s14) AS b_s14,
        AVG(s20) AS b_s20,
        AVG(s21) AS b_s21,
        AVG(s17) AS b_s17,
        AVG(s2) AS b_s2,
        AVG(s3) AS b_s3,
        AVG(s13) AS b_s13,
        AVG(s8) AS b_s8
    FROM cycles
    WHERE cycle <= 20
    GROUP BY split, unit
)
SELECT c.split, c.unit, c.cycle,
    AVG(c.s9) OVER w10 - b.b_s9 AS s9_d10,
    AVG(c.s9) OVER w30 - b.b_s9 AS s9_d30,
    AVG(c.s11) OVER w10 - b.b_s11 AS s11_d10,
    AVG(c.s11) OVER w30 - b.b_s11 AS s11_d30,
    AVG(c.s4) OVER w10 - b.b_s4 AS s4_d10,
    AVG(c.s4) OVER w30 - b.b_s4 AS s4_d30,
    AVG(c.s12) OVER w10 - b.b_s12 AS s12_d10,
    AVG(c.s12) OVER w30 - b.b_s12 AS s12_d30,
    AVG(c.s7) OVER w10 - b.b_s7 AS s7_d10,
    AVG(c.s7) OVER w30 - b.b_s7 AS s7_d30,
    AVG(c.s15) OVER w10 - b.b_s15 AS s15_d10,
    AVG(c.s15) OVER w30 - b.b_s15 AS s15_d30,
    AVG(c.s14) OVER w10 - b.b_s14 AS s14_d10,
    AVG(c.s14) OVER w30 - b.b_s14 AS s14_d30,
    AVG(c.s20) OVER w10 - b.b_s20 AS s20_d10,
    AVG(c.s20) OVER w30 - b.b_s20 AS s20_d30,
    AVG(c.s21) OVER w10 - b.b_s21 AS s21_d10,
    AVG(c.s21) OVER w30 - b.b_s21 AS s21_d30,
    AVG(c.s17) OVER w10 - b.b_s17 AS s17_d10,
    AVG(c.s17) OVER w30 - b.b_s17 AS s17_d30,
    AVG(c.s2) OVER w10 - b.b_s2 AS s2_d10,
    AVG(c.s2) OVER w30 - b.b_s2 AS s2_d30,
    AVG(c.s3) OVER w10 - b.b_s3 AS s3_d10,
    AVG(c.s3) OVER w30 - b.b_s3 AS s3_d30,
    AVG(c.s13) OVER w10 - b.b_s13 AS s13_d10,
    AVG(c.s13) OVER w30 - b.b_s13 AS s13_d30,
    AVG(c.s8) OVER w10 - b.b_s8 AS s8_d10,
    AVG(c.s8) OVER w30 - b.b_s8 AS s8_d30
FROM cycles c
JOIN base b ON b.split = c.split AND b.unit = c.unit
WINDOW
    w10 AS (PARTITION BY c.split, c.unit ORDER BY c.cycle ROWS BETWEEN 9 PRECEDING AND CURRENT ROW),
    w30 AS (PARTITION BY c.split, c.unit ORDER BY c.cycle ROWS BETWEEN 29 PRECEDING AND CURRENT ROW)
ORDER BY c.split, c.unit, c.cycle;