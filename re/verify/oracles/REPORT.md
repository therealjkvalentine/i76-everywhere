# Oracle report (verify/oracle_run.py --all)

Generated 2026-10-02 12:44. Runs: drive/20261001-211111 (stock20), drive/20261001-211503 (stock20), drive/20261001-212220 (stock20), drive/20261001-212443 (stock60), drive/20261001-212619 (stock60), drive/20261002-090752 (stock20), drive/20261002-091323 (stock20), drive/20261002-091855 (stock20), drive/20261002-092424 (stock20), drive/20261002-093400 (stock20), drive/20261002-094329 (stock20), drive/20261002-095257 (stock20), drive/20261002-100235 (stock20), drive/20261002-101210 (stock20), drive/20261002-102145 (stock20), drive/20261002-103121 (stock20), drive/20261002-103651 (stock20), drive/20261002-104219 (stock20), drive/20261002-104747 (stock20), take-damage/20261002-120608 (stock20). PASS = >= 98% of considered frames within tolerance (verify/tolerances.json). KIND `finding` oracles fit a constant the telemetry does not carry and are never graded PASS.

Nothing here ran the game: every number comes from the recorded `telemetry.csv` of each run (one row per rendered frame, fields per `tools/telemetry/i76tel.h`) and its `manifest.json`.

## Pass/fail table

| oracle | run (profile) | lag | frames | considered | skipped | matched | rate | max_abs_err | verdict |
|---|---|---|---|---|---|---|---|---|---|
| engine_rpm | drive/20261001-211111 (stock20) | 0 | 1725 | 1279 | 446 | 1279 | 1.0000 | rpm 0.131256 | **PASS** |
| engine_rpm | drive/20261001-211503 (stock20) | 0 | 1463 | 1218 | 245 | 1218 | 1.0000 | rpm 0.14374 | **PASS** |
| engine_rpm | drive/20261001-212220 (stock20) | 0 | 1463 | 1201 | 262 | 1201 | 1.0000 | rpm 0.144752 | **PASS** |
| engine_rpm | drive/20261001-212443 (stock60) | 0 | 4378 | 3564 | 814 | 3564 | 1.0000 | rpm 0.146819 | **PASS** |
| engine_rpm | drive/20261001-212619 (stock60) | 0 | 4382 | 3583 | 799 | 3583 | 1.0000 | rpm 0.146455 | **PASS** |
| engine_rpm | drive/20261002-090752 (stock20) | 0 | 1463 | 1209 | 254 | 1209 | 1.0000 | rpm 0.148576 | **PASS** |
| engine_rpm | drive/20261002-091323 (stock20) | 0 | 1443 | 1219 | 224 | 1219 | 1.0000 | rpm 0.143286 | **PASS** |
| engine_rpm | drive/20261002-091855 (stock20) | 0 | 1463 | 1218 | 245 | 1218 | 1.0000 | rpm 0.146064 | **PASS** |
| engine_rpm | drive/20261002-092424 (stock20) | 0 | 1463 | 1225 | 238 | 1225 | 1.0000 | rpm 0.146311 | **PASS** |
| engine_rpm | drive/20261002-093400 (stock20) | 0 | 1463 | 1221 | 242 | 1221 | 1.0000 | rpm 0.147056 | **PASS** |
| engine_rpm | drive/20261002-094329 (stock20) | 0 | 1463 | 1194 | 269 | 1194 | 1.0000 | rpm 0.145959 | **PASS** |
| engine_rpm | drive/20261002-095257 (stock20) | 0 | 1463 | 1224 | 239 | 1224 | 1.0000 | rpm 0.145182 | **PASS** |
| engine_rpm | drive/20261002-100235 (stock20) | 0 | 1463 | 1204 | 259 | 1204 | 1.0000 | rpm 0.14549 | **PASS** |
| engine_rpm | drive/20261002-101210 (stock20) | 0 | 1443 | 1196 | 247 | 1196 | 1.0000 | rpm 0.144525 | **PASS** |
| engine_rpm | drive/20261002-102145 (stock20) | 0 | 1443 | 1198 | 245 | 1198 | 1.0000 | rpm 0.143457 | **PASS** |
| engine_rpm | drive/20261002-103121 (stock20) | 0 | 1463 | 1226 | 237 | 1226 | 1.0000 | rpm 0.144657 | **PASS** |
| engine_rpm | drive/20261002-103651 (stock20) | 0 | 1443 | 1204 | 239 | 1204 | 1.0000 | rpm 0.146272 | **PASS** |
| engine_rpm | drive/20261002-104219 (stock20) | 0 | 1463 | 1226 | 237 | 1226 | 1.0000 | rpm 0.144657 | **PASS** |
| engine_rpm | drive/20261002-104747 (stock20) | 0 | 1463 | 1219 | 244 | 1219 | 1.0000 | rpm 0.147772 | **PASS** |
| engine_rpm | take-damage/20261002-120608 (stock20) | 0 | 1723 | 1344 | 379 | 1344 | 1.0000 | rpm 0.136557 | **PASS** |
| engine_gear | drive/20261001-211111 (stock20) | 0 | 1725 | 1724 | 1 | 1721 | 0.9983 | gear 1 | **PASS** |
| engine_gear | drive/20261001-211503 (stock20) | 0 | 1463 | 1462 | 1 | 1458 | 0.9973 | gear 1 | **PASS** |
| engine_gear | drive/20261001-212220 (stock20) | 0 | 1463 | 1462 | 1 | 1459 | 0.9979 | gear 1 | **PASS** |
| engine_gear | drive/20261001-212443 (stock60) | 0 | 4378 | 4377 | 1 | 4372 | 0.9989 | gear 1 | **PASS** |
| engine_gear | drive/20261001-212619 (stock60) | 0 | 4382 | 4381 | 1 | 4372 | 0.9979 | gear 1 | **PASS** |
| engine_gear | drive/20261002-090752 (stock20) | 0 | 1463 | 1462 | 1 | 1459 | 0.9979 | gear 1 | **PASS** |
| engine_gear | drive/20261002-091323 (stock20) | 0 | 1443 | 1442 | 1 | 1432 | 0.9931 | gear 1 | **PASS** |
| engine_gear | drive/20261002-091855 (stock20) | 0 | 1463 | 1462 | 1 | 1459 | 0.9979 | gear 1 | **PASS** |
| engine_gear | drive/20261002-092424 (stock20) | 0 | 1463 | 1462 | 1 | 1459 | 0.9979 | gear 2 | **PASS** |
| engine_gear | drive/20261002-093400 (stock20) | 0 | 1463 | 1462 | 1 | 1458 | 0.9973 | gear 1 | **PASS** |
| engine_gear | drive/20261002-094329 (stock20) | 0 | 1463 | 1462 | 1 | 1459 | 0.9979 | gear 1 | **PASS** |
| engine_gear | drive/20261002-095257 (stock20) | 0 | 1463 | 1462 | 1 | 1459 | 0.9979 | gear 1 | **PASS** |
| engine_gear | drive/20261002-100235 (stock20) | 0 | 1463 | 1462 | 1 | 1459 | 0.9979 | gear 1 | **PASS** |
| engine_gear | drive/20261002-101210 (stock20) | 0 | 1443 | 1442 | 1 | 1439 | 0.9979 | gear 1 | **PASS** |
| engine_gear | drive/20261002-102145 (stock20) | 0 | 1443 | 1442 | 1 | 1439 | 0.9979 | gear 1 | **PASS** |
| engine_gear | drive/20261002-103121 (stock20) | 0 | 1463 | 1462 | 1 | 1459 | 0.9979 | gear 2 | **PASS** |
| engine_gear | drive/20261002-103651 (stock20) | 0 | 1443 | 1442 | 1 | 1439 | 0.9979 | gear 1 | **PASS** |
| engine_gear | drive/20261002-104219 (stock20) | 0 | 1463 | 1462 | 1 | 1459 | 0.9979 | gear 2 | **PASS** |
| engine_gear | drive/20261002-104747 (stock20) | 0 | 1463 | 1462 | 1 | 1458 | 0.9973 | gear 1 | **PASS** |
| engine_gear | take-damage/20261002-120608 (stock20) | 0 | 1723 | 1722 | 1 | 1718 | 0.9977 | gear 1 | **PASS** |
| drive_power | drive/20261001-211111 (stock20) | 0 | 1725 | 0 | 1725 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261001-211503 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261001-212220 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261001-212443 (stock60) | 0 | 4378 | 0 | 4378 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261001-212619 (stock60) | 0 | 4382 | 0 | 4382 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-090752 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-091323 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-091855 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-092424 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-093400 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-094329 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-095257 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-100235 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-101210 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-102145 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-103121 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-103651 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-104219 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | drive/20261002-104747 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | drive_power 0 | **INCONCLUSIVE** |
| drive_power | take-damage/20261002-120608 (stock20) | 0 | 1723 | 1723 | 0 | 1722 | 0.9994 | drive_power 55022.1 | **PASS** |
| brake_effective | drive/20261001-211111 (stock20) | 0 | 1725 | 0 | 1725 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261001-211503 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261001-212220 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261001-212443 (stock60) | 0 | 4378 | 0 | 4378 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261001-212619 (stock60) | 0 | 4382 | 0 | 4382 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-090752 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-091323 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-091855 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-092424 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-093400 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-094329 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-095257 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-100235 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-101210 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-102145 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-103121 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-103651 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-104219 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | drive/20261002-104747 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | brake_effective 0 | **INCONCLUSIVE** |
| brake_effective | take-damage/20261002-120608 (stock20) | 0 | 1723 | 1723 | 0 | 1723 | 1.0000 | brake_effective 2.6243e-06 | **PASS** |
| health_fraction | drive/20261001-211111 (stock20) | 0 | 1725 | 0 | 1725 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261001-211503 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261001-212220 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261001-212443 (stock60) | 0 | 4378 | 0 | 4378 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261001-212619 (stock60) | 0 | 4382 | 0 | 4382 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-090752 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-091323 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-091855 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-092424 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-093400 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-094329 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-095257 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-100235 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-101210 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-102145 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-103121 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-103651 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-104219 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | drive/20261002-104747 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | health_pct 0 | **INCONCLUSIVE** |
| health_fraction | take-damage/20261002-120608 (stock20) | 0 | 1723 | 1723 | 0 | 1723 | 1.0000 | health_pct 1.42109e-14 | **PASS** |
| damage_smoke | drive/20261001-211111 (stock20) | 0 | 1725 | 0 | 1725 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261001-211503 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261001-212220 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261001-212443 (stock60) | 0 | 4378 | 0 | 4378 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261001-212619 (stock60) | 0 | 4382 | 0 | 4382 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-090752 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-091323 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-091855 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-092424 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-093400 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-094329 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-095257 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-100235 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-101210 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-102145 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-103121 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-103651 (stock20) | 0 | 1443 | 0 | 1443 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-104219 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | drive/20261002-104747 (stock20) | 0 | 1463 | 0 | 1463 | 0 | 0.0000 | smoke 0 | **INCONCLUSIVE** |
| damage_smoke | take-damage/20261002-120608 (stock20) | 0 | 1723 | 1723 | 0 | 1723 | 1.0000 | smoke 0 | **PASS** |
| step_count | drive/20261001-211111 (stock20) | 0 | 1725 | 1725 | 0 | 1725 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261001-211503 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261001-212220 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261001-212443 (stock60) | 0 | 4378 | 4378 | 0 | 4378 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261001-212619 (stock60) | 0 | 4382 | 4382 | 0 | 4382 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-090752 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-091323 (stock20) | 0 | 1443 | 1443 | 0 | 1443 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-091855 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-092424 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-093400 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-094329 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-095257 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-100235 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-101210 (stock20) | 0 | 1443 | 1443 | 0 | 1443 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-102145 (stock20) | 0 | 1443 | 1443 | 0 | 1443 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-103121 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-103651 (stock20) | 0 | 1443 | 1443 | 0 | 1443 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-104219 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | drive/20261002-104747 (stock20) | 0 | 1463 | 1463 | 0 | 1463 | 1.0000 | step_count 0 | **PASS** |
| step_count | take-damage/20261002-120608 (stock20) | 0 | 1723 | 1723 | 0 | 1723 | 1.0000 | step_count 0 | **PASS** |

## engine_rpm

engine_rpm: gear + speed -> rpm on grounded, geared, engine-running frames (subsystems/engine.md, Model).

- INPUTS: `gear, speed, flags, gear_lever`; OUTPUTS: `rpm`; LAG 0; KIND pass
- Spec constants used: `850` = rpm offset (engine.md Model); `126.81` = rpm per m/s per unit ratio (engine.md Model); `R` = {3.0 reverse, -, 1.67, 0.96, 0.67} at 0x4f8640 (engine.md Model); `1050` = idle / neutral rpm (engine.md Model); `flags 0x1 / 0x2 / 0x4 / 0x8 / 0x20` = engine running / skid / airborne / starting / destroyed (i76tel.h, ent+0x454) - used only to skip free-rev frames
- drive/20261001-211111: considered 1279 of 1725 frames (skipped: skidding (flag 0x2): free-rev branch 212, engine off (flag 0x1 clear) 139, airborne (flag 0x4): free-rev branch 94, destroyed (flag 0x20) 1); matched 1279 (1.0000); PASS.
- drive/20261001-211503: considered 1218 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 245); matched 1218 (1.0000); PASS.
- drive/20261001-212220: considered 1201 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 262); matched 1201 (1.0000); PASS.
- drive/20261001-212443: considered 3564 of 4378 frames (skipped: skidding (flag 0x2): free-rev branch 814); matched 3564 (1.0000); PASS.
- drive/20261001-212619: considered 3583 of 4382 frames (skipped: skidding (flag 0x2): free-rev branch 799); matched 3583 (1.0000); PASS.
- drive/20261002-090752: considered 1209 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 254); matched 1209 (1.0000); PASS.
- drive/20261002-091323: considered 1219 of 1443 frames (skipped: skidding (flag 0x2): free-rev branch 224); matched 1219 (1.0000); PASS.
- drive/20261002-091855: considered 1218 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 245); matched 1218 (1.0000); PASS.
- drive/20261002-092424: considered 1225 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 238); matched 1225 (1.0000); PASS.
- drive/20261002-093400: considered 1221 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 242); matched 1221 (1.0000); PASS.
- drive/20261002-094329: considered 1194 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 269); matched 1194 (1.0000); PASS.
- drive/20261002-095257: considered 1224 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 239); matched 1224 (1.0000); PASS.
- drive/20261002-100235: considered 1204 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 259); matched 1204 (1.0000); PASS.
- drive/20261002-101210: considered 1196 of 1443 frames (skipped: skidding (flag 0x2): free-rev branch 247); matched 1196 (1.0000); PASS.
- drive/20261002-102145: considered 1198 of 1443 frames (skipped: skidding (flag 0x2): free-rev branch 245); matched 1198 (1.0000); PASS.
- drive/20261002-103121: considered 1226 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 237); matched 1226 (1.0000); PASS.
- drive/20261002-103651: considered 1204 of 1443 frames (skipped: skidding (flag 0x2): free-rev branch 239); matched 1204 (1.0000); PASS.
- drive/20261002-104219: considered 1226 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 237); matched 1226 (1.0000); PASS.
- drive/20261002-104747: considered 1219 of 1463 frames (skipped: skidding (flag 0x2): free-rev branch 244); matched 1219 (1.0000); PASS.
- take-damage/20261002-120608: considered 1344 of 1723 frames (skipped: skidding (flag 0x2): free-rev branch 357, airborne (flag 0x4): free-rev branch 22); matched 1344 (1.0000); PASS.
- What this does and does not prove: A PASS supports the geared rpm equation and the ratio table on the frames the drive runs reach (reverse, 1st, 2nd, 3rd, idle; speeds 0..45 m/s). It does not test the free-rev branch, the engine-off value or the gear decision itself (engine_gear does that). The idle 1050 is tested only as a constant on gear-1 frames.

## engine_gear

engine_gear: previous gear + this frame's speed, throttle, direction, lever -> this frame's gear (engine.md, Automatic gearbox).

- INPUTS: `gear@prev, speed, throttle, gear_dir, gear_lever, flags, step_count, speed@prev, throttle@prev`; OUTPUTS: `gear`; LAG 0; KIND pass
- Spec constants used: `62 / 106` = full-throttle upshift km/h (engine.md Automatic gearbox); `60 / 98` = full-throttle kickdown km/h (engine.md); `25 / 40` = closed-throttle upshift km/h (engine.md); `12 / 31` = closed-throttle downshift km/h (engine.md); `0.0625` = closed-throttle boundary (engine.md); `0.002` = idle <-> 1st throttle test (engine.md, 0x46a518 / 0x46a2f1); `0.5 km/h` = 1st -> idle speed test (engine.md, 0x46a2f1); `3.6` = m/s -> km/h unit conversion only
- drive/20261001-211111: considered 1724 of 1725 frames (skipped: no previous frame 1); matched 1721 (0.9983); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261001-211503: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1458 (0.9973); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261001-212220: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1459 (0.9979); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261001-212443: considered 4377 of 4378 frames (skipped: no previous frame 1); matched 4372 (0.9989); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261001-212619: considered 4381 of 4382 frames (skipped: no previous frame 1); matched 4372 (0.9979); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261002-090752: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1459 (0.9979); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261002-091323: considered 1442 of 1443 frames (skipped: no previous frame 1); matched 1432 (0.9931); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261002-091855: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1459 (0.9979); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261002-092424: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1459 (0.9979); PASS.
  - worst frame: 41 t=2.2 flags=0x81001 {gear@prev=2, speed=17.0431, throttle=-0.0623547, gear_dir=1, gear_lever=3, flags=0x81001, step_count=2, speed@prev=16.8344, throttle@prev=0.661518} -> expected {gear=2} / got {gear=4}
- drive/20261002-093400: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1458 (0.9973); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261002-094329: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1459 (0.9979); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261002-095257: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1459 (0.9979); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261002-100235: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1459 (0.9979); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261002-101210: considered 1442 of 1443 frames (skipped: no previous frame 1); matched 1439 (0.9979); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261002-102145: considered 1442 of 1443 frames (skipped: no previous frame 1); matched 1439 (0.9979); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261002-103121: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1459 (0.9979); PASS.
  - worst frame: 41 t=2.2 flags=0x81001 {gear@prev=2, speed=17.0427, throttle=-0.0617123, gear_dir=1, gear_lever=3, flags=0x81001, step_count=2, speed@prev=16.8341, throttle@prev=0.661011} -> expected {gear=2} / got {gear=4}
- drive/20261002-103651: considered 1442 of 1443 frames (skipped: no previous frame 1); matched 1439 (0.9979); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- drive/20261002-104219: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1459 (0.9979); PASS.
  - worst frame: 41 t=2.2 flags=0x81001 {gear@prev=2, speed=17.0427, throttle=-0.0617123, gear_dir=1, gear_lever=3, flags=0x81001, step_count=2, speed@prev=16.8341, throttle@prev=0.661011} -> expected {gear=2} / got {gear=4}
- drive/20261002-104747: considered 1462 of 1463 frames (skipped: no previous frame 1); matched 1458 (0.9973); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- take-damage/20261002-120608: considered 1722 of 1723 frames (skipped: no previous frame 1); matched 1718 (0.9977); PASS.
  - worst frame: 1 t=0.2 flags=0xa1001 {gear@prev=1, speed=0, throttle=0.218728, gear_dir=1, gear_lever=3, flags=0xa1001, step_count=5, speed@prev=0, throttle@prev=0} -> expected {gear=1} / got {gear=2}
- Variant readings (match rate per run, default first):
  - drive/20261001-211111: default 0.9983; gearbox runs while skidding 0.9368; prev-frame speed/throttle 0.9948; prev-frame throttle only 0.9994; one shift per frame 0.9971
  - drive/20261001-211503: default 0.9973; gearbox runs while skidding 0.8427; prev-frame speed/throttle 0.9945; prev-frame throttle only 1.0000; one shift per frame 0.9973
  - drive/20261001-212220: default 0.9979; gearbox runs while skidding 0.8338; prev-frame speed/throttle 0.9938; prev-frame throttle only 0.9993; one shift per frame 0.9979
  - drive/20261001-212443: default 0.9989; gearbox runs while skidding 0.8236; prev-frame speed/throttle 0.9977; prev-frame throttle only 0.9998; one shift per frame 0.9989
  - drive/20261001-212619: default 0.9979; gearbox runs while skidding 0.8265; prev-frame speed/throttle 0.9973; prev-frame throttle only 0.9998; one shift per frame 0.9979
  - drive/20261002-090752: default 0.9979; gearbox runs while skidding 0.8393; prev-frame speed/throttle 0.9938; prev-frame throttle only 0.9993; one shift per frame 0.9979
  - drive/20261002-091323: default 0.9931; gearbox runs while skidding 0.8530; prev-frame speed/throttle 0.9903; prev-frame throttle only 0.9958; one shift per frame 0.9924
  - drive/20261002-091855: default 0.9979; gearbox runs while skidding 0.8454; prev-frame speed/throttle 0.9938; prev-frame throttle only 0.9993; one shift per frame 0.9973
  - drive/20261002-092424: default 0.9979; gearbox runs while skidding 0.8488; prev-frame speed/throttle 0.9938; prev-frame throttle only 0.9993; one shift per frame 0.9979
  - drive/20261002-093400: default 0.9973; gearbox runs while skidding 0.8475; prev-frame speed/throttle 0.9945; prev-frame throttle only 1.0000; one shift per frame 0.9973
  - drive/20261002-094329: default 0.9979; gearbox runs while skidding 0.8249; prev-frame speed/throttle 0.9932; prev-frame throttle only 0.9993; one shift per frame 0.9979
  - drive/20261002-095257: default 0.9979; gearbox runs while skidding 0.8475; prev-frame speed/throttle 0.9938; prev-frame throttle only 0.9993; one shift per frame 0.9973
  - drive/20261002-100235: default 0.9979; gearbox runs while skidding 0.8365; prev-frame speed/throttle 0.9938; prev-frame throttle only 0.9993; one shift per frame 0.9979
  - drive/20261002-101210: default 0.9979; gearbox runs while skidding 0.8412; prev-frame speed/throttle 0.9938; prev-frame throttle only 0.9993; one shift per frame 0.9979
  - drive/20261002-102145: default 0.9979; gearbox runs while skidding 0.8433; prev-frame speed/throttle 0.9938; prev-frame throttle only 0.9993; one shift per frame 0.9979
  - drive/20261002-103121: default 0.9979; gearbox runs while skidding 0.8495; prev-frame speed/throttle 0.9938; prev-frame throttle only 0.9993; one shift per frame 0.9979
  - drive/20261002-103651: default 0.9979; gearbox runs while skidding 0.8474; prev-frame speed/throttle 0.9938; prev-frame throttle only 0.9993; one shift per frame 0.9979
  - drive/20261002-104219: default 0.9979; gearbox runs while skidding 0.8495; prev-frame speed/throttle 0.9938; prev-frame throttle only 0.9993; one shift per frame 0.9979
  - drive/20261002-104747: default 0.9973; gearbox runs while skidding 0.8454; prev-frame speed/throttle 0.9945; prev-frame throttle only 1.0000; one shift per frame 0.9973
  - take-damage/20261002-120608: default 0.9977; gearbox runs while skidding 0.8531; prev-frame speed/throttle 0.9954; prev-frame throttle only 0.9988; one shift per frame 0.9965
- What this does and does not prove: A PASS supports the shift-threshold table on the throttle regimes the drive runs cover (full, closed, braking, some partial) and the reverse / idle rules, within one frame: every residual mismatch is a 0.0625 crossing where the live shift lands one frame off. Frames where the gear held because the car was skidding (the 1 -> 2 shift at 32 km/h after a wheelspin start, which also explains engine.md's "unexplained 1 -> 2 at 28 km/h") are predicted by the hold reading, which the spec does not state: the 7-17 point gap between the default and the 'gearbox runs while skidding' variant is a finding about the engine's branch order, not a confirmation of spec text. The sub-frame order of two shifts in one multi-substep frame is approximated with the end-of-frame speed.

## drive_power

drive_power: rpm, ENGN power and the engine health factor -> eng+0x10 drive power (engine.md, Power).

- INPUTS: `rpm, engine_hp, engine_hp_max, engine_power, proxy_frame`; OUTPUTS: `drive_power`; LAG 0; KIND pass
- Spec constants used: `7000` = rpm at which power is zero (engine.md Power); `3500` = peak rpm and the 3500^2 divisor (engine.md Power); `0.4` = offline player health floor (engine.md Power, 0x469fb0 / 0x4be268)
- drive/20261001-211111: considered 0 of 1725 frames (skipped: columns missing (telemetry v1): engine_power 1725); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-211503: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212220: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212443: considered 0 of 4378 frames (skipped: columns missing (telemetry v1): engine_power 4378); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212619: considered 0 of 4382 frames (skipped: columns missing (telemetry v1): engine_power 4382); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-090752: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-091323: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): engine_power 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-091855: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-092424: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-093400: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-094329: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-095257: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-100235: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-101210: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): engine_power 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-102145: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): engine_power 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-103121: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-103651: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): engine_power 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-104219: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-104747: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): engine_power 1463); matched 0 (0.0000); INCONCLUSIVE.
- take-damage/20261002-120608: considered 1723 of 1723 frames (skipped: none); matched 1722 (0.9994); PASS.
  - summary: engine_power (P) values = [193960], engine_hp changes (frame, from, to, on a hit frame) = [(1067, 1200, 600, False)], engine damage events (hp drop on a hit frame) = 0, player impact frames = 15
  - worst frame: 0 t=0 flags=0x81001 {rpm=1050, engine_hp=1200, engine_hp_max=1200, engine_power=0x2f5a8, proxy_frame=0} -> expected {drive_power=43897.5} / got {drive_power=98919.6}
- Variant readings (match rate per run, default first):
  - drive/20261001-211111: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261001-211503: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261001-212220: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261001-212443: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261001-212619: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-090752: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-091323: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-091855: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-092424: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-093400: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-094329: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-095257: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-100235: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-101210: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-102145: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-103121: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-103651: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-104219: default 0.0000; f = hp/max every frame 0.0000
  - drive/20261002-104747: default 0.0000; f = hp/max every frame 0.0000
  - take-damage/20261002-120608: default 0.9994; f = hp/max every frame 0.6187
- What this does and does not prove: A PASS supports eng+0x10 = P x f x rpm x (7000 - rpm) / 3500^2 with P read from eng+0x14 (no fitted constant any more: P = 193960 is the Piranha's ENGN power, data/VEHICLES.md) on every frame of the drive and take-damage runs, and that f is event-driven (the poke left the curve unchanged). It does not prove the value of the floor 0.4 nor the hp factor itself, since no engine damage event occurred in any run; a hit that damages the engine (or an AI's fire on it) is still needed for those two constants.

## brake_effective

brake_effective: brake hp and the vehicle mass -> brake+0x10 effective strength with the single-player 2300/m rule (engine.md, Brakes).

- INPUTS: `brake_hp, brake_hp_max, mass`; OUTPUTS: `brake_effective`; LAG 0; KIND pass
- Spec constants used: `0.2` = brake hp floor (engine.md Brakes); `2300` = single-player brake strength numerator, 0x4bd144 (engine.md Brakes, physics.md)
- drive/20261001-211111: considered 0 of 1725 frames (skipped: columns missing (telemetry v1): mass 1725); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-211503: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212220: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212443: considered 0 of 4378 frames (skipped: columns missing (telemetry v1): mass 4378); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212619: considered 0 of 4382 frames (skipped: columns missing (telemetry v1): mass 4382); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-090752: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-091323: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): mass 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-091855: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-092424: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-093400: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-094329: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-095257: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-100235: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-101210: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): mass 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-102145: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): mass 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-103121: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-103651: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): mass 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-104219: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-104747: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): mass 1463); matched 0 (0.0000); INCONCLUSIVE.
- take-damage/20261002-120608: considered 1723 of 1723 frames (skipped: none); matched 1723 (1.0000); PASS.
  - summary: mass values = [1951], distinct brake_hp/max values seen = 1, brake_effective values = [1.17888]
- What this does and does not prove: A PASS supports the single-player rule brake+0x10 = 2300 / m with m read from ent+0xa4 (1951 kg) on every frame of the drive and take-damage runs: 1.17888 to the CSV's six digits, which a BRAK-file strength (1.0-2.0 stock) would not give. It does not prove the hp factor or the 0.2 floor (brake hp never left its max).

## health_fraction

health_fraction: armour, chassis and core components -> object_HealthFraction, compared with the telemetry's health_pct (damage.md).

- INPUTS: `armour_0, armour_1, armour_2, armour_3, armour_max_0, armour_max_1, armour_max_2, armour_max_3, chassis_0, chassis_1, chassis_2, chassis_3, chassis_max_0, chassis_max_1, chassis_max_2, chassis_max_3, engine_hp, engine_hp_max, susp_hp, susp_hp_max, brake_hp, brake_hp_max`; OUTPUTS: `health_pct`; LAG 0; KIND pass
- Spec constants used: `0.9999` = core-component intact test (damage.md Damage smoke, 0x4bc62c); `28 / 72` = scaled branch 28 + 72 x r, 0x4bc634 / 0x4bc630 (damage.md); `0.02 / 100` = all-three-dead return (damage.md, 0x4bc624); `100` = the x100 of the unscaled branch under I76_FIX_HEALTH_PCT (damage.md Opt-in fix)
- drive/20261001-211111: considered 0 of 1725 frames (skipped: columns missing (telemetry v1): health_pct 1725); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-211503: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212220: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212443: considered 0 of 4378 frames (skipped: columns missing (telemetry v1): health_pct 4378); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212619: considered 0 of 4382 frames (skipped: columns missing (telemetry v1): health_pct 4382); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-090752: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-091323: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): health_pct 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-091855: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-092424: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-093400: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-094329: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-095257: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-100235: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-101210: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): health_pct 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-102145: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): health_pct 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-103121: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-103651: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): health_pct 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-104219: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-104747: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- take-damage/20261002-120608: considered 1723 of 1723 frames (skipped: none); matched 1723 (1.0000); PASS.
  - summary: predicted min = 0.5, predicted max = 100, observed health_pct min = 0.5, observed health_pct max = 100, frames in the scaled branch = 1067, frames in the unscaled branch = 656, frames with health_pct < 75 = 729, I76_FIX_HEALTH_PCT = F
- Variant readings (match rate per run, default first):
  - drive/20261001-211111: default 0.0000; x100 fix reading 0.0000
  - drive/20261001-211503: default 0.0000; x100 fix reading 0.0000
  - drive/20261001-212220: default 0.0000; x100 fix reading 0.0000
  - drive/20261001-212443: default 0.0000; x100 fix reading 0.0000
  - drive/20261001-212619: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-090752: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-091323: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-091855: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-092424: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-093400: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-094329: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-095257: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-100235: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-101210: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-102145: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-103121: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-103651: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-104219: default 0.0000; x100 fix reading 0.0000
  - drive/20261002-104747: default 0.0000; x100 fix reading 0.0000
  - take-damage/20261002-120608: default 1.0000; x100 fix reading 0.6193
- What this does and does not prove: A PASS supports the two branches the runs reach: the scaled 28 + 72 x r value (drive runs: chassis wear; take-damage: armour side 0 poked to 80/800 -> 35.2) and the unscaled stock value once a core component is below 99.99% (take-damage: engine 600/1200 -> 0.5, with I76_FIX_HEALTH_PCT off). It does not test the x100 fix (no run has it on), the all-dead return, or the clamp of r below 0 (a side at 0 hp was not reached). The variant 'x100 fix reading' is expected to FAIL on a stock run exactly on the unscaled-branch frames: that failure is what shows the stock bug is live.

## damage_smoke

damage_smoke: health_pct -> the damage-smoke emitter flag ent+0x454 bit 0x100 (damage.md, entity_UpdateDamageSmoke 0x466ca0).

- INPUTS: `health_pct`; OUTPUTS: `smoke`; LAG 0; KIND pass
- Spec constants used: `0.01` = value -> f (damage.md, 0x463f53); `0.75` = smoke threshold on f (damage.md, 0x466ca4 = 0x4be1e8); `1.0` = the f < 1.0 gate on the UpdateDamageSmoke call (damage.md, 0x463f65); `0x100` = smoke emitter flag bit (damage.md, i76tel.h)
- drive/20261001-211111: considered 0 of 1725 frames (skipped: columns missing (telemetry v1): health_pct 1725); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-211503: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212220: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212443: considered 0 of 4378 frames (skipped: columns missing (telemetry v1): health_pct 4378); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261001-212619: considered 0 of 4382 frames (skipped: columns missing (telemetry v1): health_pct 4382); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-090752: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-091323: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): health_pct 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-091855: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-092424: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-093400: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-094329: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-095257: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-100235: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-101210: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): health_pct 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-102145: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): health_pct 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-103121: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-103651: considered 0 of 1443 frames (skipped: columns missing (telemetry v1): health_pct 1443); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-104219: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- drive/20261002-104747: considered 0 of 1463 frames (skipped: columns missing (telemetry v1): health_pct 1463); matched 0 (0.0000); INCONCLUSIVE.
- take-damage/20261002-120608: considered 1723 of 1723 frames (skipped: none); matched 1723 (1.0000); PASS.
  - `smoke` observed true on 729 frames, predicted true on 729
  - summary: frames with flag 0x100 = 729, frames with health_pct x 0.01 < 0.75 = 729, flag transitions (frame, to, health_pct) = [(994, 'set', 35.2)], health_pct min = 0.5
- What this does and does not prove: A PASS supports the 0.75 threshold on object_HealthFraction x 0.01 and the bit's same-frame behaviour over the frames the runs reach: drive runs never cross it (one-sided), the take-damage run crosses it once (76.0 -> 35.2 at the armour poke) and stays below through the unscaled-branch frames (0.5). It says nothing about the smoke rate levels or the removal on repair.

## step_count

step_count: the frame's physics dt -> number of player-vehicle substeps, per the run's step mode (physics.md, framerate.md).

- INPUTS: `sim_dt`; OUTPUTS: `step_count`; LAG 0; KIND pass
- Spec constants used: `20` = stepper rate (physics.md entity_TickVehicle / simclock_StepperBegin 0x49cc20; framerate.md floor(dt x 20) + 1)
- drive/20261001-211111: considered 1725 of 1725 frames (skipped: none); matched 1725 (1.0000); PASS.
- drive/20261001-211503: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- drive/20261001-212220: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- drive/20261001-212443: considered 4378 of 4378 frames (skipped: none); matched 4378 (1.0000); PASS.
- drive/20261001-212619: considered 4382 of 4382 frames (skipped: none); matched 4382 (1.0000); PASS.
- drive/20261002-090752: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- drive/20261002-091323: considered 1443 of 1443 frames (skipped: none); matched 1443 (1.0000); PASS.
- drive/20261002-091855: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- drive/20261002-092424: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- drive/20261002-093400: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- drive/20261002-094329: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- drive/20261002-095257: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- drive/20261002-100235: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- drive/20261002-101210: considered 1443 of 1443 frames (skipped: none); matched 1443 (1.0000); PASS.
- drive/20261002-102145: considered 1443 of 1443 frames (skipped: none); matched 1443 (1.0000); PASS.
- drive/20261002-103121: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- drive/20261002-103651: considered 1443 of 1443 frames (skipped: none); matched 1443 (1.0000); PASS.
- drive/20261002-104219: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- drive/20261002-104747: considered 1463 of 1463 frames (skipped: none); matched 1463 (1.0000); PASS.
- take-damage/20261002-120608: considered 1723 of 1723 frames (skipped: none); matched 1723 (1.0000); PASS.
- What this does and does not prove: On stock-mode runs (every run so far) a PASS here is a tautology: the proxy's step_count IS floor(sim_dt x 20) + 1 (strlkproxy.c:2011), so the oracle confirms only that the telemetry's sim_dt and step_count columns are consistent with each other. The stepper rule itself is supported by the census, not by this oracle: physics_StepVehicle and the per-substep functions read 1 or 2 calls per vehicle per frame at stock20 in proportion to this very formula (README 'Per-substep multipliers'). A fixed-step run (I76_FIXED_STEP) would make the field a real count and this oracle a test. It does not test the 20-step cap or non-player vehicles.

## Spec gaps

Constants or branches the oracles needed that the cited spec does not name, and branches the recorded runs never exercise.

- **engine_rpm**: engine.md gives no rpm for an engine that is off, starting or destroyed; those frames are skipped, not predicted.
- **engine_rpm**: The free-rev branch (skid / airborne / P-N) is path-dependent (eases at 2 x dt toward 1050 + 4950 x throttle, cap 6000) and is not modelled here; a stateful oracle over consecutive free-rev frames would need the per-substep dt.
- **engine_gear**: engine.md gives thresholds for full and closed throttle only; the oracle treats every throttle >= 0.0625 as the full set (the interpolated ShiftCurveTest never passes). Partial-throttle frames (0.0625..0.99) are 120-383 per run.
- **engine_gear**: engine.md does not say whether the gearbox runs in the free-rev branch (skid / airborne). Default here: it does not (gear holds); VARIANT 'gearbox runs while skidding' is the other reading. The data decides (see report).
- **engine_gear**: engine.md does not say what gear follows reverse when gear_dir returns to +1; assumed idle (g 1); the runs show 0 -> 1 at 0-0.8 km/h, consistent.
- **engine_gear**: The 1st -> idle rule (throttle < 0.002 and v < 0.5 km/h) is only ever reached through the contact model's rest snap: braking from 4-5 km/h the velocity goes to exactly (0, 0, 0) in one frame and the gear drops to 1 on that frame (e.g. run 211111 idx 630 -> 631, run 212443 idx 1864 -> 1865). physics.md names no rest-snap speed; the snap happens from 1.1-1.5 m/s at both 20 and 60 fps. The 0.5 km/h figure itself is therefore untested.
- **engine_gear**: Which frame's throttle the gearbox sees at a 0.0625 crossing is undecidable from frame-level telemetry: the residual mismatches (3-9 per run under the default, 0-1 under 'prev-frame throttle only') are all such crossings and the live shift lands within one frame either way. A per-substep trace of ent+0xe4 would settle it.
- **engine_gear**: Two single-frame throttle blips to 0.085 / 0.096 in 3rd gear at 61 km/h (run 212443 idx 1246, run 212619 idx 323) produced no kickdown under either reading, although the full-throttle set (kickdown below 98 km/h) applies above 0.0625 as the spec reads; a sustained 0.59 did kick down (run 212619). Either the kickdown's throttle test is higher than 0.0625 or it needs more than one substep; engine.md does not say.
- **engine_gear**: Frame 41 -> 42 of run 211111 shifts 2 -> 4 inside one step_count = 2 frame: two shifts in two substeps, as the 'one gear per substep' rule allows; the 'one shift per frame' variant loses exactly those frames.
- **engine_gear**: Frame 1 of every run (sim_time 0.2, the clamped 0.2 s load frame, step_count 5, flag 0x20000 set only there) keeps gear 1 although throttle = 0.219 > 0.002 and frame 0 reports speed 0 while the car is already at 61 km/h: a load-frame artefact (frame 0's telemetry is stale), one frame per run, counted as a mismatch.
- **drive_power**: engine.md states f = max(hp/max, floor) but not when it is recomputed; the catalogue (tunables.json) says 'at the next engine damage event' (eng+0x18 is written by physics_EngineApplyDamage 0x469fb0). The default reading takes an engine damage event as 'engine_hp decreased on a player IMPACT frame'; the take-damage run has no such event (the engine lost hp only through the trainer), so the floor 0.4 and the hp factor are still not exercised live.
- **drive_power**: Frame 0 of every run (sim_time 0, stale load-frame telemetry) carries drive_power 43897.5 at rpm 1050, 0.444 x the curve (implied P x f = 86073): one mismatch per run; engine.md's 'first engine update' in physics_InitEntity may run before the ENGN power is set.
- **drive_power**: Whether the engine damage handler also runs on surface (random) damage that hits the engine is untested: the take-damage run's surface ticks only took chassis.
- **brake_effective**: brake_hp stays at brake_hp_max in every run so far (the take-damage hits took chassis and armour only), so the max(hp/max, 0.2) factor and its floor are not exercised; only the 2300 / m point is. A run that damages the brakes (an AI's fire, or a trainer poke of brake hp followed by a brake hit) is needed.
- **brake_effective**: Whether brake+0x10 is rewritten on the brake damage event only (like eng+0x18) or on every frame cannot be told while hp never changes.
- **brake_effective**: The network / multi-melee branch (BRAK strength multiplied instead of replaced) is outside the sandbox scenarios.
- **health_fraction**: damage.md does not mention the final clamp: whatever the branch, the return is clamped to [0, 100] at 0x40b6f0..0x40b714 (fcom 0x4bc620 = 100.0, fcom 0x4bc61c = 0.0). Found live by verify/poke.py: with the offset poked from -28 to -40 (28 + 72 x 1 -> 112) health_pct stayed at 100. The oracle applies the clamp; it is a code constant the spec should name (it also caps the 'all three dead -> 100' return and any mod that raises the span).
- **health_fraction**: damage.md does not say what HealthFraction returns while a core component sits between 0.02 and 0.9999 with the others intact beyond 'the smallest live component ratio'; the oracle takes min over the three ratios, which the take-damage run (engine 600/1200 -> 0.5) confirms for one point.
- **health_fraction**: The all-three-dead branch (100) is not exercised: no run destroys engine, suspension and brakes together.
- **health_fraction**: Whether the unscaled branch's 'live' qualifier drops dead components (< 0.02) from the min is untested (none died).
- **damage_smoke**: damage.md says UpdateDamageSmoke is reached from entity_DamageAndKill 'after a hit'; the census shows it running every substep (entity_ApplyRandomDamage -> DamageAndKill with zero damage, presumably), which is what makes the flag same-frame with health_pct. The spec should say 'every substep while f < 1.0'.
- **damage_smoke**: The emitter's rate levels (0.6 -> 0.5, 0.4 -> 1.0) and the back-panel position are not in the telemetry; the bit alone is graded.
- **damage_smoke**: The remove path (f back above 0.75 -> emitter removed, 0x466dbe) is not exercised: no run repairs a smoking car.
- **step_count**: INSTRUMENT, not game (found by the poke runner 2026-10-02): in stock mode the proxy does not count substeps, it computes step_count = floor(sim_dt x 20) + 1 itself (music-fix/strlkproxy.c:2011); only under I76_FIXED_STEP is the field the accumulator's real count (g_step_acc). So on stock20 / stock60 runs this oracle checks the proxy's formula against the same formula: a tautology, and its PASS says nothing about entity_TickVehicle. Setting the 0.05 s substep immediate to 0.025 live left step_count on the stock formula. The game-side observable is a per-frame count of physics_StepVehicle calls (the census's per_substep series does exactly that: 1 and 2 steps per frame at stock20).
- **step_count**: i76tel.h says the stock count is 'capped at 20'; neither physics.md nor framerate.md names the cap, so it is not applied here. It cannot matter on these runs (the clamped dt tops out at 0.2 s -> 5 steps).
- **step_count**: The fixed-step accumulator's exact rule (carry, rounding) is not written in framerate.md; the accumulator here is the plain reading. No drive run uses I76_FIXED_STEP, so that branch is untested.
- **step_count**: Which dt the stepper sees (sim_dt 0x4fe420 vs dt 0x4fe428) cannot be told apart on these runs: the two columns are equal on every frame.

## Claims these oracles now support

Names and fields whose equation claim the matching oracle exercises on these runs. A `finding` oracle supports the *shape* of the equation only; the fitted constant is reported, not proved from the spec.

| oracle | verdicts | name / field | what the match supports |
|---|---|---|---|
| engine_rpm | PASS | physics_UpdateEngine 0x46a320 | geared rpm equation 850 + 126.81 x R[g] x v and idle 1050 reproduce eng+0x1c on every grounded geared frame |
| engine_rpm | PASS | 0x4f8640 gear ratio table | R = 3.0 / 1.67 / 0.96 / 0.67 for gears 0 / 2 / 3 / 4 |
| engine_rpm | PASS | eng+0x1c rpm, eng+0x08 gear, ent+0xac speed | the three telemetry fields are the quantities the equation relates (same-frame) |
| engine_rpm | PASS | ent+0x454 bits 0x2 / 0x4 | skid / airborne frames are exactly the ones that leave the equation (skipped here, visible in engine_gear's variants) |
| engine_gear | PASS | physics_UpdateEngine 0x46a320 (upshift) | upshifts at 62 / 106 km/h full throttle, 25 / 40 closed; idle -> 1st above 0.002 throttle |
| engine_gear | PASS | physics_AutoDownshift 0x46a140 | kickdown below 60 / 98 km/h full throttle, 12 / 31 closed |
| engine_gear | PASS | 0.0625 closed-throttle rule | the two threshold sets switch at throttle 0.0625 (braking counts as closed) |
| engine_gear | PASS | ent+0xe8 gear_dir, ent+0x104 gear_lever | reverse direction forces gear 0; lever P/N forces gear 1 |
| engine_gear | PASS | ent+0xe4 throttle_applied, ent+0xac speed | the inputs the gearbox reads, same frame |
| drive_power | INCONCLUSIVE, PASS | physics_UpdateEngine 0x46a320 (power curve) | eng+0x10 = eng+0x14 x f x rpm x (7000 - rpm) / 3500^2 on every frame, P read live |
| drive_power | INCONCLUSIVE, PASS | eng+0x14 engine_power | the telemetry field is the P of the power curve (193960 = Piranha ENGN power, data/VEHICLES.md) |
| drive_power | INCONCLUSIVE, PASS | eng+0x18 engine health factor | event-driven: a trainer write of eng+0x00 to 50% did not change the curve (f stayed 1.0) |
| brake_effective | INCONCLUSIVE, PASS | physics_BrakeSetStrength 0x46a890 / 0x4bd144 = 2300 | offline brake+0x10 = 2300 / m with m = ent+0xa4 read live (1951 kg Piranha), no fit |
| brake_effective | INCONCLUSIVE, PASS | ent+0xa4 mass (v2) | the telemetry field is the mass the brake rule divides by (and brake accel = brake+0x10 x throttle x 8) |
| brake_effective | INCONCLUSIVE, PASS | brake+0x10 brake_effective | the effective strength; constant while brake hp is full |
| health_fraction | INCONCLUSIVE, PASS | object_HealthFraction 0x40b450 | 28 + 72 x min side ratio while engine / suspension / brakes are intact; the unscaled 0..1 component ratio (stock bug) once one is below 0.9999, value-for-value against health_pct |
| health_fraction | INCONCLUSIVE, PASS | 0x4bc630 / 0x4bc634 = 72 / -28 | the scaled branch's span and offset reproduce health_pct on every intact-core frame |
| health_fraction | INCONCLUSIVE, PASS | 0x4bc62c = 0.9999 | the branch switch: engine 600/1200 (take-damage) moves health_pct from the 28 + 72 x r value to 0.5 |
| health_fraction | INCONCLUSIVE, PASS | health_pct telemetry field (v2) | the proxy's game-thread object_HealthFraction call reads the same fields the spec names |
| damage_smoke | INCONCLUSIVE, PASS | entity_UpdateDamageSmoke 0x466ca0 | sets ent+0x454 bit 0x100 on the frame object_HealthFraction x 0.01 drops below 0.75 and keeps it while below |
| damage_smoke | INCONCLUSIVE, PASS | 0x4be1e8 = 0.75 (dual use) | the smoke threshold: 76.0 no smoke, 35.2 smoke (take-damage) |
| damage_smoke | INCONCLUSIVE, PASS | ent+0x454 bit 0x100 | the bit is the emitter's presence; it follows health_pct within the same frame |
| step_count | PASS | step_count telemetry field (stock mode) | consistent with sim_dt under floor(sim_dt x 20) + 1 - the proxy's own formula, not a count (tautology; see GAPS) |
| step_count | PASS | simclock_sim_dt 0x4fe420 | the dt the proxy's formula uses (indistinguishable from 0x4fe428 here) |

