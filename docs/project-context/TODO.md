# Оперативний список відкритих задач (`TODO.md`)

- **Проєкт**: [`dscodetesla/PLFM_RADAR`](https://github.com/dscodetesla/PLFM_RADAR) (`AERIS-10N Nexus R0.1`)
- **Гілка**: [`work/r02-integrated-2026-11-21`](https://github.com/dscodetesla/PLFM_RADAR/tree/work/r02-integrated-2026-11-21) · **Статус**: `NOT_FOR_MANUFACTURE / NOT_FOR_FLASH`

## Виконано в консолідації `R02` (`2026-11-21`) `[V]`

- [x] Зберегти `100%` чистоту базового дерева `/home/user/projects/PLFM_RADAR-rnd-20261024` на `checkpoint/rnd-2026-10-24` (`a4840b40`, `951` файл) та підняти ізольований `git worktree` `/home/user/projects/PLFM_RADAR-wt-r02-20261121`.
- [x] Інтегрувати пакет **MCU/BIST/PhaseLUT** (`ADAR1000_PcbPhaseLut.h`, `ADAR1000_BIST.{h,cpp}`, виправлення `ADAR1000_Manager.{h,cpp}`, `ADAR1000_AGC.cpp`, `adf4382a_manager.c`, розширений `stm32_hal_mock` і `25` тест-сьютів з `-Werror`).
- [x] Інтегрувати пакет **CAD Short Fix & Patch 8x16 DFM** (`RADAR_Main_Board.brd` ревізії [`62d4c556`](https://github.com/NawfalMotii79/PLFM_RADAR/commit/62d4c556508927a4192acca24422bd16a979c7dc) без КЗ у `(54.620, 136.470)` мм, вирівняні `-0.0800 мм` `Patch_Anetnna_16_8.{brd,mnt}` + `CPL.xlsx`, звіт `CAD_DIFF_62D4C55_AND_PATCH_FIX.md`).
- [x] Інтегрувати пакет **FPGA XDC/TCL & Clock Gate** (`xc7a50t_ftg256.xdc`, `adc_clk_mmcm.xdc`, `build_50t.tcl`, `pre_bitstream_gate.tcl`, `radar_system_top_50t.v`, `check_fpga_clocks.py`, `53/53` модульні тести в `tools/manufacturing/tests`).
- [x] Актуалізувати повний пакет керуючих файлів у `docs/project-context/` (`state.json`, `IDENTITY.md`, `FINDINGS.md`, `PLAN.md`, `TODO.md`, `CHECKLIST.md`, `CHANGELOG.md`, `TASK_MONITOR.md`, `SUBAGENTS.md`, `PRODUCT.md`) із нульовим термінологічним дрейфом.
- [x] Налаштувати автоматичний запуск `.github/workflows/ci-tests.yml` і `.github/workflows/manufacturing-audit.yml` для гілок `work/**` на GitHub Actions.

## Відкриті задачі (Наступні кроки R&D) `[?]` / `[Proposal]`

- [ ] **`[Proposal]` Дослід `#9` (`FPGA_DAC_CLOCK` `120 МГц`)**: перевірити у нативному EAGLE/Fusion фізичне BGA-трасування кандидата ECO `C13 -> D13` (`U42` [`XC7A50T-2FTG256I`](https://download.amd.com/adaptive-socs-and-fpgas/developer/adaptive-socs-and-fpgas/package-pinout-files/a7packages/xc7a50tftg256pkg.txt), Банк 15) та зафіксувати емпіричний вердикт.
- [ ] **`[Proposal]` Дослід `#10` (`FT_CLKOUT` `60 МГц`)**: перевірити у нативному EAGLE/Fusion фізичне BGA-трасування кандидата ECO `C4 -> D4` (Банк 35, синхронний інтерфейс [FT2232H](https://ftdichip.com/products/ft2232hl/)) і запас за часом встановлення/утримання.
- [ ] **`[?]` Дослід `#11` (Електричний аудит Банку 14 та `T5` `adc_pwdn`)**: завершити розрахунок найгіршого випадку для дільника `R36 = 830 Ом / R37 = 1 кОм` на вході `PWDN` АЦП [AD9484](https://www.analog.com/en/products/ad9484.html) (`absmax 2.1 В`) та зовнішніх термінаторів `100 Ом` `R2..R12` при `VCCO_14 = 3.3 В`.
- [ ] **`[?]` Дослід `#12` (Повна нативна збірка `Vivado 2026.1` на `desk-tyan`, залежить від `#9–#11`)**: виконати синтез, розміщення, трасування й перевірку `WNS/WHS >= 0` для `radar_system_top_50t` без жодного зниження серйозності DRC.
- [ ] **`[?]` Дослід `#13` (Нативний ERC/DRC `PowerBoard`)**: валідувати відновлений роз'єм `X36` у рідному середовищі EAGLE/Fusion.
- [ ] **`[?]` Дослід `#14` (`XTAL3` та аудит BOM `MainBoard`)**: узгодити корпус/MPN резонатора `XTAL3` (`3.2×1.5 мм` проти `3.2×2.5 мм`) і закрити відкриті позиції [Issue #175](https://github.com/NawfalMotii79/PLFM_RADAR/issues/175) та [Issue #209](https://github.com/NawfalMotii79/PLFM_RADAR/issues/209).
- [ ] **`[?]` Гейт `G06` / `G08` (Свіжий CAM-експорт і DFM-погодження стеку)**: перегенерувати Gerber/Excellon/CPL для `MainBoard` та `Patch 8x16` у нативному CAD після прийняття всіх ECO перед будь-яким запитом на виробництво плат.
- [ ] **`[?]` Мультимодальне збагачення графа знань (`graphify-out/graph.json`)**: виконати на `desk-tyan` скрипт доповнення базового графа (`4,334` вузли AST коду) вузлами `.sch/.brd/.xdc` та виробничих гейтів `G01–G11`.
