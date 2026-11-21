# Монітор виконання задач та CI-гейтів (`TASK_MONITOR.md`)

- **Проєкт**: [`dscodetesla/PLFM_RADAR`](https://github.com/dscodetesla/PLFM_RADAR) (`AERIS-10N Nexus R0.1`)
- **Вузол виконання**: `desk-tyan` (`739c694f-0965-4c21-82d3-4320f81b5ae0`)
- **Робочий worktree**: `/home/user/projects/PLFM_RADAR-wt-r02-20261121` (гілка [`work/r02-integrated-2026-11-21`](https://github.com/dscodetesla/PLFM_RADAR/tree/work/r02-integrated-2026-11-21))

## 1. Зведена матриця конвеєрів верифікації

| Підсистема / Конвеєр | Команда перевірки | Очікуваний / Фактичний поріг | Статус |
| :--- | :--- | :--- | :---: |
| **Лінтер Python (`Ruff`)** | `uv run ruff check .` | `0` помилок по всьому дереву (вкл. правила `E, F, B, RUF, SIM, PIE, T20, ARG, ERA, A, BLE, RET, ISC, TCH, UP, C4, PERF`) | **`PASS`** `[V]` |
| **Модульні тести виробництва, CAD та XDC** | `python3 -m unittest discover -s tools/manufacturing/tests -v` | `53 / 53` тестів `OK` (`test_audit`, `test_clock_contract`, `test_connectivity`, `test_inventory`, `test_production_gate`, `test_manufacturing_audit`, `test_fpga_xdc_and_clocks`) | **`PASS`** `[V]` |
| **Тести GUI та міжрівневих контрактів** | `uv run pytest 9_Firmware/9_3_GUI/test_GUI_V65_Tk.py 9_Firmware/9_3_GUI/test_v7.py 9_Firmware/tests/cross_layer/test_cross_layer_contract.py` | Усі тести протоколів Python <-> Verilog <-> C проходять без регресій | **`PASS`** `[V]` |
| **Хост-тести прошивки МК (`STM32F7`)** | `make -C 9_Firmware/9_1_Microcontroller/tests test` | `25 / 25` бінарних сьютів `PASS` (`C11` + `C++17`, `-Wall -Wextra -Werror`) | **`PASS`** `[V]` |
| **Симуляційна регресія RTL ПЛІС** | `cd 9_Firmware/9_2_FPGA && bash run_regression.sh` | `25` тестбенчів Icarus Verilog проходять без помилок (цифрова верифікація, не заміна Vivado P&R) | **`PASS`** `[V]` |
| **Суворий виробничий гейт (`--strict`)** | `python3 tools/manufacturing/audit.py --strict` | Повертає код `1` (`NOT_FOR_MANUFACTURE`), доки відкриті блокери `G06` та `G08–G11` | **`EXPECTED BLOCK`** `[V]` |
| **GitHub Actions CI (`ci-tests.yml` + `manufacturing-audit.yml`)** | `gh run list --repo dscodetesla/PLFM_RADAR --branch work/r02-integrated-2026-11-21` | Автоматичний запуск і проходження всіх джобів у хмарному середовищі GitHub | **`ACTIVE`** `[V]` |

## 2. Активні фонові процеси та заплановані монітори

- **Довготривалі процеси на `desk-tyan`**: `0` активних демонів збірки (нативна імплементація `Vivado 2026.1` заблокована графом залежностей до завершення дослідів `#9, #10, #11`).
- **Захист еталонного дерева**: `/home/user/projects/PLFM_RADAR-rnd-20261024` залишається зафіксованим на `a4840b40` без жодних локальних змін.
