# Чекліст інженерних та виробничих гейтів `G01–G11` (`CHECKLIST.md`)

- **Проєкт**: [`dscodetesla/PLFM_RADAR`](https://github.com/dscodetesla/PLFM_RADAR) (`AERIS-10N Nexus R0.1`)
- **Гілка**: [`work/r02-integrated-2026-11-21`](https://github.com/dscodetesla/PLFM_RADAR/tree/work/r02-integrated-2026-11-21)
- **Інтегральний вердикт**: **`NOT_FOR_MANUFACTURE / NOT_FOR_FLASH`** (`6 / 11` гейтів `PASS`, `5` блокувальних гейтів відкриті)

## 1. Статус гейтів готовності (`state.json` <-> `audit.py --strict`)

| Код гейту | Опис перевірки | Статус | Доказ / Блокер |
| :--- | :--- | :---: | :--- |
| **`G00`** | Гігієна термінології та граф залежностей дослідів (`[9,10,11] -> [12]`, `[13,14]`) | **`PASS`** `[V]` | `scan_forbidden_terminology() == []`, `sequence_valid == true` |
| **`G01`** | Фіксація меж конфігурації `AERIS-10N Nexus R0.1` (`4` плати; виключення `QPA2962` і `DFSWA.dwg`) | **`PASS`** `[V]` | Зафіксовано в `state.json`, `IDENTITY.md` та `PRODUCT.md` |
| **`G02`** | Кардинальність `BOM <-> CPL <-> CAD` та фільтрація `DNP` для всіх 4 плат | **`PASS`** `[V]` | `test_inventory.py` та `test_audit.py` (`main=791/709`, `synth=184/174`, `power=313/276`, `patch=16/16`) |
| **`G03`** | Побайтовий та геометричний XML-паритет `SCH <-> BRD`, усунення КЗ `MainBoard` (`62d4c556`) та кроку `Patch 8x16` (`14.34 мм`) | **`PASS`** `[V]` | `test_connectivity.py` + `test_22` + `test_23` (`3453==3453`, `619==619`, `814==814`, `64==64`, `0` КЗ) |
| **`G04`** | Повний пакет тестів Python (`pytest`, `unittest`), міжрівневих контрактів та лінтера `ruff check .` | **`PASS`** `[V]` | Усі тести GUI, міжрівневих контрактів і `53/53` виробничих тестів + `0` зауважень `ruff` (вкл. `ISC`) |
| **`G05`** | Хост-верифікація прошивки МК `STM32F7` (`C11` / `C++17` з `-Wall -Wextra -Werror`) | **`PASS`** `[V]` | `25/25` бінарних наборів у `9_Firmware/9_1_Microcontroller/tests` (вкл. `ADAR1000_BIST` та `AGC`) |
| **`G06`** | Свіжий нативний CAM-експорт Gerber/Excellon для всіх оновлених плат (`MainBoard`, `Patch 8x16`) | **`BLOCKED`** `[?]` | Наявні Gerber-файли створені до ревізії [`62d4c556`](https://github.com/NawfalMotii79/PLFM_RADAR/commit/62d4c556508927a4192acca24422bd16a979c7dc) та вирівнювання `J9..J15`; потрібна регенерація в EAGLE/Fusion |
| **`G07`** | Скрипти пре-бітстрімного контролю `production_gate.tcl` + `pre_bitstream_gate.tcl` + `build_50t.tcl` без waivers | **`PASS`** `[V]` | `test_production_gate.py` + `test_fpga_xdc_and_clocks.py` + нативний негативний тест у `Vivado 2026.1` |
| **`G08`** | Актуальність архіву `Gerber_Main_Board` відносно `RADAR_Main_Board.brd` та закриття `#14` (`XTAL3`) | **`BLOCKED`** `[?]` | `gerber_stale: true`; очікує закриття дослідів `#9–#11`, `#14` і нативного CAM-експорту |
| **`G09`** | Фізична узгодженість тактових контактів `U42` (`C13 -> D13` `120 МГц`, `C4 -> D4` `60 МГц`) між платою та XDC | **`BLOCKED`** `[Proposal]` | Відкриті кандидати ECO у дослідах `#9` та `#10` (`check_fpga_clocks.py --require-pcb-match` повертає `1`) |
| **`G10`** | Допусковий електричний аудит Банку 14 (`VCCO = 3.3 В`, `AD9484` `LVDS_25`, дільник `T5` `adc_pwdn`) | **`BLOCKED`** `[?]` | Обмеження в XDC (`DIFF_TERM FALSE` + `LVCMOS33`) внесені `[V]`, очікується розрахунковий знак-оф досліду `#11` |
| **`G11`** | Повна нативна збірка `Vivado 2026.1` (`synth -> place -> route -> timing -> bitstream`) для `xc7a50tftg256-2` | **`BLOCKED`** `[?]` | Дослід `#12` (виконується виключно після закриття `#9, #10, #11`) |

## 2. Контрольний список безпеки гілок та CI

- [x] Базовий чекпойнт `/home/user/projects/PLFM_RADAR-rnd-20261024` (`checkpoint/rnd-2026-10-24` @ `a4840b40`) залишається 100% чистим (`git status --short` порожній).
- [x] Жодних секретів, токенів або локальних тимчасових артефактів збірки (`*.o`, `build_50t/`, `__pycache__/`) у комітах немає.
- [x] Обидва воркфлоу GitHub Actions (`ci-tests.yml` та `manufacturing-audit.yml`) активні для гілки `work/r02-integrated-2026-11-21`.
