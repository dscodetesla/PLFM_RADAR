# Журнал інженерних змін проєкту `PLFM_RADAR` (`CHANGELOG.md`)

- **Канонічний репозиторій**: [`dscodetesla/PLFM_RADAR`](https://github.com/dscodetesla/PLFM_RADAR) (`AERIS-10N Nexus R0.1`)
- **Поточний статус**: `Draft` | `NOT_FOR_MANUFACTURE` | `NOT_FOR_FLASH`

## `2026-11-21` — Консолідація пакетів `R02` у канонічний GitHub-репозиторій (`work/r02-integrated-2026-11-21`) `[V]`

- **Ізоляція гілки та повного 951-файлового дерева**: створено ізольований `git worktree` `/home/user/projects/PLFM_RADAR-wt-r02-20261121` на гілці [`work/r02-integrated-2026-11-21`](https://github.com/dscodetesla/PLFM_RADAR/tree/work/r02-integrated-2026-11-21) від архівного чекпойнта [`checkpoint/rnd-2026-10-24` @ `a4840b40`](https://github.com/dscodetesla/PLFM_RADAR/commit/a4840b40f7d517669fc556e179da79f4877ced2f) на хості `desk-tyan` зі збереженням 100% чистоти базового робочого дерева `/home/user/projects/PLFM_RADAR-rnd-20261024`.
- **Пакет MCU / BIST / PhaseLUT** (перенесено з верифікованого коміту [`cb70cb34`](https://gitlab.com/dscodetesla/plfm-radar-rnd/-/commit/cb70cb34cc64973ba853ca1f1a87660614c26f2e)):
  - Додано таблиці фазової компенсації ВЧ-трас `10.5 ГГц` на підкладці [Rogers RO4350B](https://www.rogerscorp.com/advanced-electronics-solutions/ro4000-series-laminates/ro4350b-laminates) та нелінійну карту квадрантів `ADAR1..4 <-> ADTR1107_1..16` у `ADAR1000_PcbPhaseLut.h`.
  - Додано модуль замкненого самотестування та вирівнювання потужності 16 каналів `ADAR1000_BIST.{h,cpp}` через детектори [ADTR1107](https://www.analog.com/en/products/adtr1107.html) `CPLR_OUT -> DET1..4` і шину телеметрії `I2C2`.
  - Усунено помилки `BIAS_EN` active-low (`0x030` Bit 5), апаратних адрес SPI `{0, 2, 1, 3}` та індексації `CH4` у `ADAR1000_Manager.{h,cpp}` і переповнення `uint8_t` у `ADAR1000_AGC.cpp`; кількість хост-тестів МК доведено до `25/25` під `-Wall -Wextra -Werror`.
- **Пакет CAD Short Fix & Patch 8x16 DFM** (перенесено з [`ba350989`](https://gitlab.com/dscodetesla/plfm-radar-rnd/-/commit/ba350989af872490d92f6578474fc80ae8964b52)):
  - Синхронізовано `RADAR_Main_Board.brd` із апстрім-ревізією [`62d4c556`](https://github.com/NawfalMotii79/PLFM_RADAR/commit/62d4c556508927a4192acca24422bd16a979c7dc) (`EAGLE 7.6.0`), що усуває міжшарове КЗ `+5V0_0 <-> GND` у точці `(54.620, 136.470)` мм біля підсилювача ПЧ `U8` ([AD8352](https://www.analog.com/en/products/ad8352.html)) / `C353`.
  - Вирівняно роз'єми SMA `J9, J11, J13, J15` на `-0.0800 мм` у `Patch_Anetnna_16_8.brd`, `Patch_Anetnna_16_8.mnt` та `CPL.xlsx` до рівномірного кроку ФАР `14.3400 мм`; додано звіт `docs/manufacturing/CAD_DIFF_62D4C55_AND_PATCH_FIX.md`.
- **Пакет FPGA XDC/TCL & Clock Gate** (перенесено з [`d73a441b`](https://gitlab.com/dscodetesla/plfm-radar-rnd/-/commit/d73a441b74b9cd4582166d1ea4d8853f68ec45f3)):
  - Оновлено `xc7a50t_ftg256.xdc`, `adc_clk_mmcm.xdc`, `radar_system_top_50t.v`, `build_50t.tcl` та додано `pre_bitstream_gate.tcl`: усунено примусове зниження критичності `BIVC-1/NSTD-1/UCIO-1/PLIO-9`, вилучено `CLOCK_DEDICATED_ROUTE FALSE`, виставлено `DIFF_TERM FALSE` + `LVCMOS33` (`T5`) у Банку 14 і зафіксовано чисті P-виводи MRCC (`D13`, `D4`) як кандидати ECO `[Proposal]` у дослідах `#9` та `#10`.
  - Об'єднано `tools/manufacturing/audit.py` та `check_fpga_clocks.py` із розширенням пакету модульних тестів до `53/53 PASS`.
- **Управління контекстом і CI**: створено повний комплект живих керуючих файлів у `docs/project-context/` та додано тригери `work/**` у `.github/workflows/ci-tests.yml` і `.github/workflows/manufacturing-audit.yml`.

## `2026-10-20 .. 2026-10-24` — R&D Ітерації `#1–#8` (`checkpoint/rnd-2026-10-24` @ `a4840b40`) `[V]`

- Аудит і виправлення кардинальності BOM/CPL для 4 плат `AERIS-10N Nexus`, вилучення `SJ1 (DNP)` із монтажної відомості, відновлення роз'єму `X36` у схемі `PowerBoard.sch`, верифікація нативної підтримки [`XC7A50T-2FTG256I`](https://download.amd.com/adaptive-socs-and-fpgas/developer/adaptive-socs-and-fpgas/package-pinout-files/a7packages/xc7a50tftg256pkg.txt) у `Vivado 2026.1` на `desk-tyan` і створення архівної гілки [`checkpoint/rnd-2026-10-24`](https://github.com/dscodetesla/PLFM_RADAR/tree/checkpoint/rnd-2026-10-24).
