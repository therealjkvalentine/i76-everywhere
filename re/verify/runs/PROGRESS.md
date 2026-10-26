# Phase 1 census progress (run_phase1.py; one line per batch x scenario; `ok` lines are skipped on restart)

| batch | scenario | run id | status | per_frame | per_substep | per_event | init_only | never | irregular | not_hooked | live frames | fired | anomalies |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| batch-001 | drive | 20261002-090752 | ok | 30 | 16 | 14 | 4 | 81 | 4 | 1 | 908 | 1548881 | check FAIL gear_in [3, 4] gear 1 |
| batch-001 | fire-each | 20261002-091038 | ok | 27 | 20 | 11 | 3 | 84 | 4 | 1 | 905 | 1584392 |  |
| batch-002 | drive | 20261002-091323 | ok | 32 | 5 | 4 | 4 | 104 | 0 | 1 | 888 | 11850005 | check FAIL gear_in [3, 4] gear 1 |
| batch-002 | fire-each | 20261002-091610 | ok | 28 | 9 | 13 | 4 | 94 | 1 | 1 | 903 | 13982822 |  |
| batch-003 | drive | 20261002-091855 | ok | 34 | 3 | 18 | 2 | 91 | 2 | 0 | 889 | 29218498 | check FAIL gear_in [3, 4] gear 1 |
| batch-003 | fire-each | 20261002-092141 | ok | 31 | 7 | 28 | 1 | 79 | 4 | 0 | 888 | 29242727 |  |
| batch-004 | drive | 20261002-092424 | ok | 18 | 2 | 34 | 2 | 91 | 3 | 0 | 888 | 150246022 | check FAIL gear_in [3, 4] gear 1 |
| batch-004 | fire-each | 20261002-092709 | ok | 18 | 3 | 39 | 2 | 87 | 1 | 0 | 889 | 148102584 |  |
| batch-004 | melee | 20261002-092952 | ok | 15 | 2 | 44 | 0 | 84 | 5 | 0 | 2408 | 10098805 | WM_CLOSE ignored for 10 s, killed |
| batch-005 | drive | 20261002-093400 | ok | 25 | 0 | 15 | 4 | 103 | 3 | 0 | 889 | 3681546 | check FAIL gear_in [3, 4] gear 1 |
| batch-005 | fire-each | 20261002-093646 | ok | 27 | 0 | 13 | 6 | 103 | 1 | 0 | 888 | 3510014 |  |
| batch-005 | melee | 20261002-093930 | ok | 19 | 0 | 57 | 0 | 59 | 15 | 0 | 1586 | 1826242 | player wrecked at frame 1989 (101 frames excluded) |
| batch-006 | drive | 20261002-094329 | ok | 31 | 0 | 3 | 15 | 95 | 6 | 0 | 908 | 957953 | check FAIL gear_in [3, 4] gear 1 |
| batch-006 | fire-each | 20261002-094613 | ok | 34 | 0 | 3 | 16 | 95 | 2 | 0 | 907 | 1009778 |  |
| batch-006 | melee | 20261002-094857 | ok | 25 | 0 | 7 | 0 | 84 | 34 | 0 | 498 | 229808 | player wrecked at frame 902 (101 frames excluded) |
| batch-007 | drive | 20261002-095257 | ok | 17 | 0 | 25 | 3 | 100 | 5 | 0 | 888 | 22254307 | check FAIL speed_gt 5.0 speed 4.951316833496094; check FAIL gear_in [3, 4] gear 1 |
| batch-007 | fire-each | 20261002-095543 | ok | 18 | 0 | 19 | 5 | 105 | 3 | 0 | 888 | 22366092 |  |
| batch-007 | melee | 20261002-095826 | ok | 11 | 0 | 16 | 0 | 99 | 24 | 0 | 2410 | 5349862 | WM_CLOSE ignored for 10 s, killed |
| batch-008 | drive | 20261002-100235 | ok | 37 | 0 | 13 | 10 | 87 | 3 | 0 | 905 | 126629931 | check FAIL gear_in [3, 4] gear 1 |
| batch-008 | fire-each | 20261002-100519 | ok | 35 | 0 | 12 | 17 | 81 | 5 | 0 | 888 | 127019938 |  |
| batch-008 | melee | 20261002-100802 | ok | 31 | 0 | 23 | 0 | 90 | 6 | 0 | 2409 | 7103966 | WM_CLOSE ignored for 10 s, killed |
| batch-009 | drive | 20261002-101210 | ok | 18 | 0 | 18 | 13 | 86 | 15 | 0 | 889 | 64946057 | check FAIL gear_in [3, 4] gear 1 |
| batch-009 | fire-each | 20261002-101455 | ok | 19 | 0 | 21 | 13 | 86 | 11 | 0 | 889 | 63865416 |  |
| batch-009 | melee | 20261002-101738 | ok | 16 | 0 | 17 | 0 | 112 | 5 | 0 | 2409 | 2406888 | WM_CLOSE ignored for 10 s, killed |
| batch-010 | drive | 20261002-102145 | ok | 14 | 0 | 2 | 2 | 111 | 21 | 0 | 889 | 140429594 | check FAIL speed_gt 5.0 speed 4.611964225769043; check FAIL gear_in [3, 4] gear 1 |
| batch-010 | fire-each | 20261002-102430 | ok | 14 | 0 | 2 | 2 | 111 | 21 | 0 | 889 | 138749093 |  |
| batch-010 | melee | 20261002-102713 | ok | 13 | 0 | 2 | 0 | 135 | 0 | 0 | 2408 | 48851 | WM_CLOSE ignored for 10 s, killed |
| batch-011 | drive | 20261002-103121 | ok | 9 | 0 | 3 | 10 | 125 | 3 | 0 | 888 | 135781 | check FAIL gear_in [3, 4] gear 1 |
| batch-011 | fire-each | 20261002-103406 | ok | 9 | 0 | 3 | 10 | 125 | 3 | 0 | 887 | 135780 |  |
| batch-012 | drive | 20261002-103651 | ok | 5 | 4 | 5 | 3 | 132 | 1 | 0 | 889 | 99159 | check FAIL gear_in [3, 4] gear 1 |
| batch-012 | fire-each | 20261002-103935 | ok | 4 | 6 | 2 | 4 | 133 | 1 | 0 | 888 | 93855 |  |
| batch-013 | drive | 20261002-104219 | ok | 21 | 4 | 15 | 4 | 97 | 3 | 6 | 888 | 18515554 | check FAIL gear_in [3, 4] gear 1 |
| batch-013 | fire-each | 20261002-104504 | ok | 22 | 4 | 15 | 4 | 97 | 2 | 6 | 888 | 18977830 |  |
| batch-014 | drive | 20261002-104747 | ok | 9 | 1 | 3 | 0 | 30 | 4 | 2 | 888 | 53043736 | check FAIL gear_in [3, 4] gear 1 |
| batch-014 | fire-each | 20261002-105032 | ok | 9 | 2 | 3 | 0 | 30 | 3 | 2 | 888 | 53635756 |  |
| batch-014 | melee | 20261002-105315 | ok | 8 | 1 | 5 | 0 | 34 | 1 | 0 | 2409 | 2410201 | WM_CLOSE ignored for 10 s, killed |

<!-- run_phase1.py finished 2026-10-02T10:57:24; sandbox {"i76_pids": [], "lock": false, "dll_md5": "54f2de9da2beacb1b66a697eaf0d9ea1", "pretest": false} -->

## Pass `early` (run_phase1.py --pass early: Frida hooks before WinMain's first instruction; mission-idle = t01 direct boot, menu-idle = shell main menu)

| batch | scenario | pass | run id | status | per_frame | per_substep | per_event | init_only | menu_only | never | irregular | not_hooked | live frames | fired | attach s | anomalies |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| batch-001 | mission-idle | early | 20261002-111350 | ok | 27 | 21 | 8 | 35 | 0 | 56 | 2 | 1 | 908 | 1560196 | 0.67/1.04 |  |
| batch-002 | mission-idle | early | 20261002-111535 | ok | 30 | 7 | 4 | 26 | 0 | 82 | 0 | 1 | 888 | 3311981 | 0.66/1.03 |  |
| batch-003 | mission-idle | early | 20261002-111719 | ok | 31 | 7 | 3 | 32 | 0 | 76 | 1 | 0 | 889 | 7999951 | 0.66/1.02 |  |
| batch-004 | mission-idle | early | 20261002-111903 | ok | 16 | 6 | 30 | 27 | 0 | 70 | 1 | 0 | 907 | 152214690 | 0.73/1.09 |  |
| batch-004 | menu-idle | early | 20261002-112049 | ok | 0 | 0 | 0 | 0 | 0 | 150 | 0 | 0 | 0 | 0 | 0.66/1.04 | VOID census (no hook fired) |
| batch-005 | mission-idle | early | 20261002-112214 | ok | 27 | 0 | 11 | 11 | 0 | 100 | 1 | 0 | 889 | 3509264 | 0.67/1.04 |  |
| batch-005 | menu-idle | early | 20261002-112400 | ok | 0 | 0 | 0 | 2 | 0 | 148 | 0 | 0 | 0 | 2 | 0.65/1.03 |  |
| batch-006 | mission-idle | early | 20261002-112525 | ok | 34 | 0 | 2 | 42 | 0 | 69 | 3 | 0 | 908 | 1024679 | 0.66/1.03 |  |
| batch-006 | menu-idle | early | 20261002-112710 | ok | 0 | 0 | 0 | 24 | 0 | 126 | 0 | 0 | 0 | 881 | 0.71/1.1 |  |
| batch-007 | mission-idle | early | 20261002-112835 | ok | 18 | 0 | 1 | 41 | 0 | 87 | 3 | 0 | 908 | 22496843 | 0.69/1.11 |  |
| batch-007 | menu-idle | early | 20261002-113019 | ok | 0 | 0 | 0 | 10 | 0 | 140 | 0 | 0 | 0 | 434 | 0.66/1.03 |  |
| batch-008 | mission-idle | early | 20261002-113144 | ok | 37 | 0 | 2 | 43 | 0 | 65 | 3 | 0 | 904 | 126824598 | 0.88/1.43 |  |
| batch-008 | menu-idle | early | 20261002-113331 | ok | 0 | 0 | 0 | 8 | 0 | 142 | 0 | 0 | 0 | 16031577 | 0.87/1.26 |  |
| batch-009 | mission-idle | early | 20261002-113456 | ok | 19 | 0 | 17 | 29 | 0 | 74 | 11 | 0 | 887 | 13012368 | 0.67/1.03 |  |
| batch-009 | menu-idle | early | 20261002-113642 | ok | 0 | 0 | 0 | 21 | 4 | 125 | 0 | 0 | 0 | 36389290 | 0.69/1.06 |  |
| batch-010 | mission-idle | early | 20261002-113808 | ok | 14 | 0 | 0 | 26 | 0 | 89 | 21 | 0 | 902 | 24857358 | 0.71/1.27 |  |
| batch-010 | menu-idle | early | 20261002-113954 | ok | 0 | 0 | 0 | 8 | 0 | 142 | 0 | 0 | 0 | 8965831 | 2.31/2.77 |  |
| batch-011 | mission-idle | early | 20261002-114123 | ok | 9 | 0 | 3 | 22 | 0 | 113 | 3 | 0 | 902 | 137610 | 1.03/1.44 |  |
| batch-012 | mission-idle | early | 20261002-114309 | ok | 4 | 6 | 2 | 64 | 0 | 74 | 0 | 0 | 898 | 98947 | 0.81/1.23 |  |
| batch-013 | mission-idle | early | 20261002-114455 | ok | 22 | 4 | 11 | 57 | 0 | 48 | 2 | 6 | 904 | 20151456 | 0.96/1.35 |  |
| batch-014 | mission-idle | early | 20261002-114640 | ok | 9 | 2 | 2 | 14 | 0 | 17 | 3 | 2 | 907 | 42774318 | 0.69/0.85 |  |
| batch-014 | menu-idle | early | 20261002-114825 | ok | 0 | 0 | 0 | 11 | 0 | 36 | 0 | 2 | 0 | 6249 | 1.03/1.21 |  |

<!-- run_phase1.py --pass early finished 2026-10-02T11:49:53; sandbox {"i76_pids": [], "lock": false, "dll_md5": "54f2de9da2beacb1b66a697eaf0d9ea1", "pretest": false} -->
