# Data source

NASA Prognostics Center of Excellence, Turbofan Engine Degradation Simulation Data Set (C-MAPSS),
subset FD001: `train_FD001.txt`, `test_FD001.txt`, `RUL_FD001.txt`.

Reference: A. Saxena, K. Goebel, D. Simon and N. Eklund, "Damage propagation modeling for aircraft engine
run-to-failure simulation", International Conference on Prognostics and Health Management, 2008.

The three files in `raw/` were copied from a public GitHub repository that mirrors the dataset. If you are
publishing this project, replace them with files downloaded from NASA's data portal and confirm the
current terms of use there. Columns: unit, cycle, 3 operating settings, 21 sensor channels (no header, space separated).
