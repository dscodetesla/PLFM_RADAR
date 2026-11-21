# Інженерний план розблокування та порядок дослідів (`PLAN.md`)

- **Проєкт**: [`dscodetesla/PLFM_RADAR`](https://github.com/dscodetesla/PLFM_RADAR) — `AERIS-10N Nexus R0.1`
- **Поточний етап**: Консолідована інтеграційна гілка [`work/r02-integrated-2026-11-21`](https://github.com/dscodetesla/PLFM_RADAR/tree/work/r02-integrated-2026-11-21) (`NOT_FOR_MANUFACTURE / NOT_FOR_FLASH`)

## 1. Завершені етапи (`Ітерації #1–#8` + Консолідація `R02`) `[V]`

1. **`[V]` Ітерації `#1–#8` (`checkpoint/rnd-2026-10-24` @ [`a4840b40`](https://github.com/dscodetesla/PLFM_RADAR/commit/a4840b40f7d517669fc556e179da79f4877ced2f))**: виправлення кардинальності BOM і DNP у CPL 4 плат, відновлення `X36` у схемі `PowerBoard.sch`, базовий 21-тестовий аудит `SCH <-> BRD`, емпіричне розблокування `AMD Vivado 2026.1` на `desk-tyan` (`xc7a50tftg256-2`).
2. **`[V]` Інтеграція `R02` (`work/r02-integrated-2026-11-21`)**:
   - Накладено пакет прошивки МК (`ADAR1000_PcbPhaseLut.h`, `ADAR1000_BIST.{h,cpp}`, виправлення Bug 1–4 у `ADAR1000_Manager` та `ADAR1000_AGC`, `25/25` хост-тестів C/C++ з `-Werror`).
   - Накладено пакет CAD (`RADAR_Main_Board.brd` ревізії [`62d4c556`](https://github.com/NawfalMotii79/PLFM_RADAR/commit/62d4c556508927a4192acca24422bd16a979c7dc) без КЗ `+5V0_0 <-> GND` у `(54.620, 136.470)` мм та вирівняні `-0.0800 мм` `Patch_Anetnna_16_8.{brd,mnt}` + `CPL.xlsx`).
   - Накладено пакет ПЛІС (`xc7a50t_ftg256.xdc`, `adc_clk_mmcm.xdc`, `build_50t.tcl`, `pre_bitstream_gate.tcl`, `radar_system_top_50t.v`, розширений гейт `check_fpga_clocks.py`, `53/53` модульні тести у `tools/manufacturing/tests`).

## 2. Обов'язковий граф залежностей відкритих дослідів (`#9–#14`) `[?]` / `[Proposal]`

Згідно з верифікованим правилом послідовності (`sequence_valid == true` у `state.json`), подальші R&D-роботи виконуються суворо у три потоки без передчасного замовлення плат чи прошивання кристалів:

### Потік A — Перша хвиля (виконується ПЕРШОЮ перед збіркою бітстріму `#12`)

- **Дослід `#9` (`FPGA_DAC_CLOCK`, `120 МГц`) `[Proposal / ?]`**:
  Перевірити в нативному Autodesk EAGLE / Fusion Electronics можливість чистого виведення BGA-траси під `U42` ([`XC7A50T-2FTG256I`](https://download.amd.com/adaptive-socs-and-fpgas/developer/adaptive-socs-and-fpgas/package-pinout-files/a7packages/xc7a50tftg256pkg.txt)) з поточного контакту `C13` (`IO_L12N_T1_MRCC_15`) на P-сторону `D13` (`IO_L12P_T1_MRCC_15`) із дотриманням імпедансу `50 Ом` і зазорів `0.10 мм`, або оцінити альтернативний варіант тактування без маскування DRC.
- **Дослід `#10` (`FT_CLKOUT`, `60 МГц` [FT2232H](https://ftdichip.com/products/ft2232hl/)) `[Proposal / ?]`**:
  Незалежно перевірити фізичну трасованість кандидата ECO `C4 -> D4` (`IO_L12N_T1_MRCC_35 -> IO_L12P_T1_MRCC_35` у Банку 35) з урахуванням наявних перехідних отворів та полігонів під корпусом BGA `FTG256` і перевірити запас за часом встановлення/утримання синхронного FIFO `60 МГц`.
- **Дослід `#11` (Електричний знак-оф Банку 14 ПЛІС та [AD9484](https://www.analog.com/en/products/ad9484.html)) `[?]`**:
  Виконати повний розрахунок найгіршого випадку (номінали, допуски резисторів `R36 = 830 Ом` / `R37 = 1 кОм`, розкид `VCCO_14 = 3.3 В ±5%`, струм витоку входу `PWDN` АЦП `AD9484` при абсолютній межі `AVDD + 0.3 В = 2.1 В` та синфазна напруга LVDS на `R2..R12`), щоб закрити електричне погодження перед фінальною фіксацією схеми.

### Потік B — Друга хвиля (виконується ТІЛЬКИ ПІСЛЯ закриття `#9, #10, #11`)

- **Дослід `#12` (Повна нативна імплементація Vivado 2026.1 на `desk-tyan`) `[?]`**:
  Запустити повний цикл `synth_1 -> opt_design -> place_design -> phys_opt_design -> route_design` через `9_Firmware/9_2_FPGA/scripts/50t/build_50t.tcl` під контролем `production_gate.tcl` та `pre_bitstream_gate.tcl` (`WNS >= 0`, `WHS >= 0`, `0` помилок/критичних попереджень DRC). Будь-яке виявлене порушення таймінгу або CDC ізолювати в окремий інженерний запис без повернення `SEVERITY {Warning}`.

### Потік C — Незалежні паралельні роботи (`#13, #14`) та Фінальний виробничий гейт (`G06`)

- **Дослід `#13` (Нативна перевірка `PowerBoard` `X36`) `[?]`**: виконати нативний ERC/DRC у EAGLE/Fusion для перевірки відновленого роз'єму `X36` (`+5V0_LO / GND`).
- **Дослід `#14` (Узгодження `XTAL3` та позицій BOM `MainBoard`) `[?]`**: усунути невідповідність корпусу кварцу `32.768 кГц` `XTAL3` (`NX3215SA` `3.2×1.5 мм` у BOM проти посадкового місця `NX3225GD` `3.2×2.5 мм` на платі) та перевірити зауваження [Issue #175](https://github.com/NawfalMotii79/PLFM_RADAR/issues/175) і [Issue #209](https://github.com/NawfalMotii79/PLFM_RADAR/issues/209).
- **Фінальний CAM-гейт `G06` / `G08` `[?]`**: лише після затвердження єдиного узгодженого пакету змін у `.sch/.brd` виконати свіжий експорт Gerber X2, Excellon drill, BOM і CPL для всіх змінених плат, узгодити стек гібридних підкладок із виробником ([PCBWay High-Frequency](https://www.pcbway.com/pcb_prototype/High_Frequency_PCB.html)) і зняти блокування `NOT_FOR_MANUFACTURE`.
