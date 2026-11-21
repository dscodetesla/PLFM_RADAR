# Паспорт ідентичності та меж проєкту `PLFM_RADAR` (`IDENTITY.md`)

- **Проєкт**: `PLFM_RADAR` — когерентна імпульсна ЛЧМ (PLFM) радіолокаційна платформа X-діапазону (`10.5 ГГц`) з цифровою обробкою на ПЛІС і фазованою антенною решіткою.
- **Канонічна цільова конфігурація**: **`AERIS-10N Nexus R0.1`** (4-платний базовий радіолокаційний комплект малої дальності до `10 км`) `[V]`.
- **Канонічний GitHub-репозиторій (`951+` файлів)**: [`dscodetesla/PLFM_RADAR`](https://github.com/dscodetesla/PLFM_RADAR) (`origin = https://github.com/dscodetesla/PLFM_RADAR.git`) `[V]`.
- **Апстрім-референс**: [`NawfalMotii79/PLFM_RADAR`](https://github.com/NawfalMotii79/PLFM_RADAR) (базовий коміт [`749bd0f8`](https://github.com/NawfalMotii79/PLFM_RADAR/commit/749bd0f86a07a28a86347d8ce9c141e601057c40), жовтневе виправлення `MainBoard.brd` [`62d4c556`](https://github.com/NawfalMotii79/PLFM_RADAR/commit/62d4c556508927a4192acca24422bd16a979c7dc)) `[V]`.
- **Еталонний інженерний хост верифікації**: `desk-tyan` (`739c694f-0965-4c21-82d3-4320f81b5ae0`, `2× Xeon E5-2680 v4`, `AMD Vivado 2026.1` за шляхом `/home/user/AMDDesignTools/2026.1/Vivado/bin/vivado` з нативною підтримкою кристала [`XC7A50T-2FTG256I`](https://download.amd.com/adaptive-socs-and-fpgas/developer/adaptive-socs-and-fpgas/package-pinout-files/a7packages/xc7a50tftg256pkg.txt)) `[V]`.
- **Статус готовності**: `Draft` | **`NOT_FOR_MANUFACTURE`** | **`NOT_FOR_FLASH`** до закриття дослідів `#9–#14` та свіжого нативного CAM-експорту `G06` `[V]`.

## 1. Ізоляція робочих дерев та гілок на `desk-tyan` `[V]`

| Робоче дерево / Ресурс | Гілка / SHA | Роль та режим доступу |
| :--- | :--- | :--- |
| `/home/user/projects/PLFM_RADAR-rnd-20261024` | [`checkpoint/rnd-2026-10-24`](https://github.com/dscodetesla/PLFM_RADAR/tree/checkpoint/rnd-2026-10-24) @ `a4840b40` | Незмінний 951-файловий R&D-архів (`100%` чисте робоче дерево, модифікації заборонені) `[V]` |
| `/home/user/projects/PLFM_RADAR-wt-r02-20261121` | [`work/r02-integrated-2026-11-21`](https://github.com/dscodetesla/PLFM_RADAR/tree/work/r02-integrated-2026-11-21) | Ізольований `git worktree` консолідації 3 верифікованих пакетів `R02` поверх повного 951-файлового дерева та нативних GitHub Actions `[V]` |
| [GitLab `dscodetesla/plfm-radar-rnd`](https://gitlab.com/dscodetesla/plfm-radar-rnd) (`ID: 89041995`) | `cb70cb34`, `ba350989`, `d73a441b` | Історичне read-only джерело часткових пакетних гілок (21–79 файлів); нові записи не виконуються `[V]` |

## 2. Затверджений апаратний обсяг `AERIS-10N Nexus R0.1` (`4` плати) `[V]`

1. **`MainBoard`** (`RADAR_Main_Board.{sch,brd}`, ревізія плати [`62d4c556`](https://github.com/NawfalMotii79/PLFM_RADAR/commit/62d4c556508927a4192acca24422bd16a979c7dc)): 10-шаровий ВЧ-гібрид ([Rogers RO4350B](https://www.rogerscorp.com/advanced-electronics-solutions/ro4000-series-laminates/ro4350b-laminates) `0.102 мм` + FR-4), `791` елемент CAD, `709` позицій монтажу CPL, `3453` підключені площадки (`100%` збіг `SCH <-> BRD`), `4353` перехідних отвори (`1604` із мін. свердлом `0.15 мм`), ПЛІС `U42` (`XC7A50T-2FTG256I`), МК `STM32F746ZGT6`, АЦП [Analog Devices AD9484](https://www.analog.com/en/products/ad9484.html), ЦАП [AD9708](https://www.analog.com/en/products/ad9708.html), 4× формувачі променя [ADAR1000](https://www.analog.com/en/products/adar1000.html) + 16× ВЧ-модулі T/R [ADTR1107](https://www.analog.com/en/products/adtr1107.html), міст USB 2.0 FIFO [FTDI FT2232H](https://ftdichip.com/products/ft2232hl/).
2. **`Frequency Synthesizer`** (`Clocks_Freq_Synth_board.{sch,brd}`): 6-шаровий гібрид (`1+2*3+14*15+16`), `184` елементи CAD, `174` позиції CPL, `619` підключених площадок, тактовий розподільник [AD9523-1](https://www.analog.com/en/products/ad9523-1.html) та 2× НВЧ-синтезатори гетеродина [ADF4382A](https://www.analog.com/en/products/adf4382a.html) (`10.50 ГГц` TX / `10.38 ГГц` RX).
3. **`PowerBoard`** (`PowerBoard.{sch,brd}`): 2-шарова силова плата FR-4 (`1.5 мм`, мідь `4 oz`), `313` елементів CAD, `276` позицій CPL, `814` підключених площадок (відновлено роз'єм `X36` Molex `22-23-2021` у схемі).
4. **`Patch 8x16 Antenna Array`** (`Patch_Anetnna_16_8.{sch,brd}`): 4-шарова мікросмужкова ФАР (`1+2*3+16`), `16` лінійних підрешіток по `8` елементів із рівномірним кроком `14.3400 мм` та `16` роз'ємів SMA [Cinch 142-0731-211](https://www.cinch.com/media/drawings/products/rf-microwave/connectors/dr-CCS-JOHNS-142-0731-211.pdf) (`64/64` корпусні контакти `GND`).

**Виключено з обсягу `AERIS-10N Nexus R0.1`** (належать розширеній конфігурації `AERIS-10E/X` `35–50 км`): зовнішні 100-ватні GaN-підсилювачі потужності [Qorvo QPA2962](https://www.qorvo.com/products/p/QPA2962) та хвилеводна щілинна антена `32×16` (`DFSWA.dwg`) `[V]`.

## 3. Епістемічні правила та заборона термінологічного дрейфу `[V]`

- **`[V]` (Verified Fact)**: факт, безпосередньо підтверджений парсингом XML/RTL/C++/Python-файлів репозиторію, контрольними сумами SHA-256 та логами виконання компіляторів/тестів/Vivado на `desk-tyan`.
- **`[Proposal]` (Engineering Candidate)**: інженерна пропозиція зміни плати (зокрема кандидати ECO перетрасування тактових входів `C13 -> D13` у досліді `#9` та `C4 -> D4` у досліді `#10`), яка **не є затвердженою чи виконаною зміною друкованої плати** до фізичної перевірки BGA-виходу у нативному CAD та замикання часових обмежень.
- **`[?]` (Open Blocker)**: відкрита перевірка (нативний CAM-експорт Gerber/Excellon `G06`, ERC/DRC у EAGLE/Fusion `#13`, звірка кварцу `XTAL3` `#14`, повний прогін імплементації Vivado `#12`), до завершення якої діє жорстке блокування **`NOT_FOR_MANUFACTURE / NOT_FOR_FLASH`**.
- **Нульовий дрейф назв ревізій**: вигадування неіснуючих проміжних назв ревізій плати до офіційного затвердження ECO суворо заборонене і автоматично перевіряється сканером `scan_forbidden_terminology()` у `tools/manufacturing/audit.py`.
