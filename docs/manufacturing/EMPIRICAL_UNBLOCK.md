# PLFM_RADAR — емпірична ітерація 2

Статус: **NOT_FOR_MANUFACTURE**. Логічну неузгодженість PowerBoard виправлено;
фізичну працездатність і готовність до виробництва ще не підтверджено.
База: `749bd0f86a07a28a86347d8ce9c141e601057c40`, локальна гілка
`fix/hf-manufacturing-audit-20261020`. Зміни не закомічені й не опубліковані.
Scope незмінний: Nexus — Main, Synth, Power, Patch 8×16.

## Конкретні результати

- **Power X36:** додано відсутній part і окремий другий аркуш SCH із двома
  підключеннями: `1 → +5V0_LO`, `2 → GND`. Використано наявний пристрій
  `con-molex/22-23-2021`, його gates `-1/-2`, pin `S` і штатну pad mapping.
  Це відновлення схемного опису вже наявного PCB/BOM. PCB не змінювався.
  Повне порівняння XML після вилучення доданих part/sheet підтвердило незмінність
  решти схеми. Native open/ERC/DRC і візуальний CAD review залишаються OPEN.
- **Звірка SCH↔BRD:** аудит тепер перевіряє кожен збережений зв'язок
  `(reference, pad) → net`, включно з multi-pad pins. Усі чотири плати збігаються:
  Main 3453, Synth 619, Power 814, Patch 64 connected pads. Це логічна
  відповідність XML; вона не доводить безперервність міді, clearance або unrouted=0.
- **Clock blocker:** додано звірку п'яти clock ports XDC з фізичними U42 pads.
  `clk_120m_dac`: XDC **D13**, SCH/BRD **C13**. Помилка тепер відтворюється
  командою, а 50T production build зупиняється до створення/перезапису outputs.
  Призначення pin не підмінено для отримання зеленого результату.
- Виправлення BOM/CPL першої ітерації збережені. Нові перевірки додані до
  існуючого manufacturing workflow; strict лишається fail через clock mismatch.

## Швидкий selftest і докази

З кореня репозиторію, Python 3 без додаткових залежностей:

```bash
python3 -m unittest discover -s tools/manufacturing/tests -v
python3 tools/manufacturing/audit.py --strict --output /tmp/plfm-audit.json
python3 tools/manufacturing/check_fpga_clocks.py
```

| Перевірка | Фактичний результат |
|---|---|
| Manufacturing unittest | 18 passed; нові тести спочатку падали |
| Повний `python3 -m pytest -q` | 228 passed, 9 skipped, 2 warnings, 17 subtests |
| Strict audit | exit 1: одна FPGA_CLOCK_PIN finding; усі 4 board findings порожні |
| Clock CLI | exit 1: C13/D13 |
| Tcl preflight через `tkinter.Tcl()` | Очікувана зупинка на mismatch до Vivado commands |
| MCU/FPGA RTL | Цією ітерацією не змінювались; MCU 24 suite PASS із попередньої ітерації |
| Native EAGLE / Vivado | NOT RUN; не підмінені статичними перевірками |
| Повний CI перед commit | BLOCKED: немає ruff/Icarus/sfw; пакети не встановлювались |

На трьох online Linux-хостах виконано лише read-only PATH preflight:
`sfw`, `ruff`, `iverilog`, `vvp`, `vivado`, `eagle`, `kicad-cli` не знайдені.
Це не повний пошук інсталяцій на дисках. Віддалені файли не змінювались.

Докази: [audit](evidence/iteration2-audit.json),
[X36 delta](evidence/x36-repair.json),
[AMD pin facts](evidence/amd-clock-pin-facts.json),
[verification](evidence/iteration2-verification.json).
JSON input hashes визначають фактичні робочі байти; HEAD сам по собі їх не містить.

## Рішення для прискорення

Не починати новий загальний аудит: наступний критичний результат —
**native перевірена MainBoard ECO**, після неї — factory-approved stackup і fresh CAM.

| Пріоритет / відповідальність | Конкретна дія | Критерій переходу |
|---|---|---|
| 1. CAD + FPGA | Перевірити варіант reroute `FPGA_DAC_CLOCK` C13→D13; одночасно оцінити `FT_CLKOUT` C4→D4. Обидві P-пари в AMD pinout, D13/D4 не мають saved contactref на поточному PCB | Узгоджені SCH/BRD/XDC; native routing, DRC, timing; відсутність contactref не означає доступний фізичний маршрут |
| 1. FPGA + analog | Закрити Bank14 VCCO/DIFF_TERM/adc_pwdn, перевірити 3.3 V rail проти I/O constraints; переглянути наявні BIVC-1/PLIO-9 demotions | Native implementation і electrical review без необґрунтованих waiver |
| 1. CAD | Відкрити відновлену Power SCH+BRD; перевірити X36, cross-sheet nets; закрити XTAL3 geometry/load із NDK drawing | Native ERC/DRC, підписаний footprint review |
| 2. Fabrication engineer | Відправити конкретний per-board stackup/via запит після source freeze; за потреби запитувати можливості процесу раніше, позначаючи draft | Письмове погодження laminate, impedance, 0.15 mm drill process і layer map |
| 2. Toolchain owner | Надати середовище з дозволеним `sfw` та CI/CAD/FPGA tools; виконати повний локальний CI | Вимога CONTRIBUTING виконана; після цього commit/PR у develop з контрольованим перенесенням відмінних CAD |
| 3. CAD + production | Fresh BOM/CPL/Gerber/drill/netlist/drawings, manifest; factory DFM/DFA | Перевірений пакет саме frozen revision, без legacy CAM |
| 4. Lab | Струмообмежений power bring-up → MCU/FPGA → clocks → ADC/DAC → RF на навантаженні → calibration | Raw measurements та межі з ТЗ/datasheets; лише тоді заявляти робочий прототип |

C13→D13 та C4→D4 — **кандидати ECO**, не виконані або схвалені зміни трасування.
Альтернатива зі збереженням N-side clock і недедикованого маршруту потребує
окремого обґрунтування timing/jitter; автоматичне waiver не є рішенням для випуску.
Після фізичного ECO оновити baseline-specific test поточного C13/D13 дефекту,
зберігши негативний fixture, що доводить виявлення mismatch.

Виробничий напрямок лишається PCBWay Advanced/HF custom stackup. Публічний
JLCPCB HF профіль (2 layers, drill ≥0.2 mm, перевірено у першій ітерації) не
підтверджує сумісність цього комплекту. Фабриці нічого не відправлено;
пакет цього звіту — для engineering review, не для запуску виробництва.
Детальні вимоги: [pcbway-requirements.md](pcbway-requirements.md).

## Контроль деградації процесу

Вхідні файли мають SHA256; виправлення X36 обмежене перевіреним delta; кожен
новий клас помилок має негативний тест. Наступна сесія починається з
`docs/project-context/state.json` та цього звіту. Незалежний review виявив і закрив false-pass на альтернативному XDC синтаксисі;
невідомий PACKAGE_PIN синтаксис тепер завершує перевірку помилкою. Аудитор не є
інтерпретатором довільного Tcl. Немає повторних інсталяційних
спроб без `sfw`, змін цільової архітектури, вигаданих вимірювань або перенесення
успіху іншої FPGA-плати на Nexus.

Первинне джерело pin classes: [AMD XC7A50T FTG256 package file](https://download.amd.com/adaptive-socs-and-fpgas/developer/adaptive-socs-and-fpgas/package-pinout-files/a7packages/xc7a50tftg256pkg.txt).
Отриманий файл датований AMD 2013-10-04; його SHA256 зафіксовано в evidence.
Це дані pinout, а не підтвердження маршрутизації конкретного дизайну.
