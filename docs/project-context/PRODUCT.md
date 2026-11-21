# Технічний паспорт продукту та архітектура `PLFM_RADAR — AERIS-10N Nexus R0.1` (`PRODUCT.md`)

- **Канонічний репозиторій**: [`dscodetesla/PLFM_RADAR`](https://github.com/dscodetesla/PLFM_RADAR) · **Інтеграційна гілка R02**: [`work/r02-integrated-2026-11-21`](https://github.com/dscodetesla/PLFM_RADAR/tree/work/r02-integrated-2026-11-21)
- **Апстрім-джерело**: [`NawfalMotii79/PLFM_RADAR`](https://github.com/NawfalMotii79/PLFM_RADAR) (коміти [`749bd0f8`](https://github.com/NawfalMotii79/PLFM_RADAR/commit/749bd0f86a07a28a86347d8ce9c141e601057c40) та [`62d4c556`](https://github.com/NawfalMotii79/PLFM_RADAR/commit/62d4c556508927a4192acca24422bd16a979c7dc))
- **Поточний статус готовності**: `Draft` | **`NOT_FOR_MANUFACTURE`** | **`NOT_FOR_FLASH`**

## 1. Призначення системи та межі конфігурації `AERIS-10N Nexus R0.1` `[V]`

**`AERIS-10N Nexus R0.1`** — твердотільна когерентна імпульсна радіолокаційна станція X-діапазону (`10.50 ГГц` передавання / `10.38 ГГц` гетеродин приймання, ПЧ `120 МГц`) з кусково-лінійною частотною модуляцією (PLFM), 16-канальним електронним скануванням у площині азимута/кута місця та цифровою узгодженою фільтрацією й допплерівською обробкою (FFT + MTI + CA-CFAR) на ПЛІС.

| Плата у складі `AERIS-10N` | Шари / Стек | Ключова елементна база | Показники паритету `SCH <-> BRD` `[V]` |
| :--- | :---: | :--- | :--- |
| **`MainBoard`** (`RADAR_Main_Board.{sch,brd}`) | `10L` ([Rogers RO4350B](https://www.rogerscorp.com/advanced-electronics-solutions/ro4000-series-laminates/ro4350b-laminates) `0.102 мм` + FR-4) | ПЛІС `U42` ([`XC7A50T-2FTG256I`](https://download.amd.com/adaptive-socs-and-fpgas/developer/adaptive-socs-and-fpgas/package-pinout-files/a7packages/xc7a50tftg256pkg.txt)), МК `STM32F746ZGT6`, АЦП [AD9484](https://www.analog.com/en/products/ad9484.html) (`400 MSPS`), ЦАП [AD9708](https://www.analog.com/en/products/ad9708.html), `4×` [ADAR1000](https://www.analog.com/en/products/adar1000.html), `16×` [ADTR1107](https://www.analog.com/en/products/adtr1107.html), ПЧ [AD8352](https://www.analog.com/en/products/ad8352.html), USB 2.0 FIFO [FT2232H](https://ftdichip.com/products/ft2232hl/) | Ревізія [`62d4c556`](https://github.com/NawfalMotii79/PLFM_RADAR/commit/62d4c556508927a4192acca24422bd16a979c7dc): `791` елемент, `709` CPL, `3453 == 3453` контакти, `1604` отвори `0.15 мм`, `0` КЗ `+5V0_0 <-> GND` |
| **`Frequency Synthesizer`** (`Clocks_Freq_Synth_board.{sch,brd}`) | `6L` (`1+2*3+14*15+16`) | Тактовий генератор [AD9523-1](https://www.analog.com/en/products/ad9523-1.html) (`100/120/400 МГц`) + `2×` НВЧ-синтезатори [ADF4382A](https://www.analog.com/en/products/adf4382a.html) (`10.50 / 10.38 ГГц`, `TIMED` / `EZSYNC`) | `184` елементи, `174` CPL, `619 == 619` контакти, `212` перехідних отворів |
| **`PowerBoard`** (`PowerBoard.{sch,brd}`) | `2L` (`FR-4 1.5 мм, 4 oz Cu`) | Багатоканальні імпульсні перетворювачі та LDO живлення аналогових, цифрових і силових шин PA/LNA | `313` елементів, `276` CPL, `814 == 814` контакти (`X36` відновлено у схемі) |
| **`Patch 8x16`** (`Patch_Anetnna_16_8.{sch,brd}`) | `4L` (`1+2*3+16`) | `16×8 = 128` послідовно живлених патчів із кроком `14.3400 мм` + `16×` SMA [Cinch 142-0731-211](https://www.cinch.com/media/drawings/products/rf-microwave/connectors/dr-CCS-JOHNS-142-0731-211.pdf) | `16` роз'ємів SMA (`J9, J11, J13, J15` вирівняні на `-0.0800 мм`), `64 == 64` контакти `GND` |

> **Поза обсягом `AERIS-10N`**: зовнішні блоки підсилювачів потужності `100 Вт` на [Qorvo QPA2962](https://www.qorvo.com/products/p/QPA2962) та щілинна хвилеводна решітка `32×16` (`DFSWA.dwg`) стосуються виключно далекобійної модифікації `AERIS-10E/X` і в поточний пакет виробництва не входять `[V]`.

## 2. Підсумки верифікованої інтеграції `R02` за підсистемами `[V]`

1. **Підсистема керування ФАР та BIST на МК (`9_Firmware/9_1_Microcontroller`) `[V]`**:
   - Відкориговано полярність `BIAS_EN` (`0x030` Bit 5 = `0` active-low), фізичну адресацію чипів на шині SPI1 (`ADDR1:ADDR0 = {0, 2, 1, 3}`) та 1-базову індексацію каналів `1..4` без затирання `CH1` при записі `CH4`.
   - Запроваджено поправки фази мікросмужкових ліній `ADAR1000_PcbPhaseLut.h` (`6-bit` та `7-bit` на сітці `2.8125°`) і нелінійну матрицю комутації квадрантів `ADAR1..4 <-> ADTR1107_1..16`.
   - Додано вбудовану діагностику `ADAR1000_BIST` із вирівнюванням потужності передавання 16 каналів за детекторами спрямованих відгалужувачів `CPLR_OUT` і контролем струму спокою `Idq` через АЦП `ADS7830` на ізольованій шині `I2C2` (`25/25` хост-тестів `PASS`).
2. **Підсистема цифрової обробки сигналів ПЛІС (`9_Firmware/9_2_FPGA`) `[V]` / `[Proposal]`**:
   - У виробничій обгортці `radar_system_top_50t.v` (`82` скалярні порти, `USB_MODE=1` під `FT2232H`) та файлах обмежень `xc7a50t_ftg256.xdc` + `adc_clk_mmcm.xdc` забезпечено `100%` покриття контактів і стандартів вводу-виводу без жодного зниження серйозності правил DRC (`BIVC-1`, `NSTD-1`, `UCIO-1`, `PLIO-9`).
   - Для Банку 14 (`VCCO_14 = 3.3 В`) задано `DIFF_TERM FALSE` на LVDS-лініях `AD9484` (із зовнішніми термінаторами `100 Ом` `R2..R12`) та `LVCMOS33` на `T5` (`adc_pwdn` через дільник `830 Ом / 1 кОм`).
   - У `xc7a50t_ftg256.xdc` тактові порти `clk_120m_dac` і `ft_clkout` призначені на P-виводи MRCC `D13` та `D4` без `CLOCK_DEDICATED_ROUTE FALSE`; при цьому перенесення трас на платі `C13 -> D13` (`#9`) і `C4 -> D4` (`#10`) зафіксовані суворо як **кандидати ECO `[Proposal]`**, що потребують нативної CAD- і таймінг-верифікації.
3. **Антигалюцинаційні виробничі бар'єри (`tools/manufacturing`) `[V]`**:
   - Автоматичний аудит `audit.py` перевіряє відсутність КЗ `+5V0_0 <-> GND` у `RADAR_Main_Board.brd`, крок `14.3400 мм` і співвісність фідерів у `Patch_Anetnna_16_8.brd`, кардинальність `BOM/CPL` 4 плат, нульову присутність вигаданих назв ревізій та утримує блокування `NOT_FOR_MANUFACTURE / NOT_FOR_FLASH` до виконання свіжого CAM-експорту `G06` і дослідів `#9–#14` (`53/53` модульні тести `PASS`).

## 3. Команди швидкої локальної перевірки (`desk-tyan`)

```bash
# 1. Лінтер Ruff (увесь репозиторій, включно з правилами ISC / T20 / RUF):
uv run ruff check .

# 2. Усі 53 модульні тести виробничого, CAD XML та FPGA XDC гейтів:
python3 -m unittest discover -s tools/manufacturing/tests -v

# 3. Усі 25 C/C++ хост-тестів прошивки STM32F7 (ADAR1000, AGC, BIST, ADF4382A, GPS):
make -C 9_Firmware/9_1_Microcontroller/tests test

# 4. Повна симуляційна регресія RTL ПЛІС (25 тестбенчів Icarus Verilog) + міжрівневі контракти:
(cd 9_Firmware/9_2_FPGA && bash run_regression.sh)
uv run pytest 9_Firmware/9_3_GUI/test_GUI_V65_Tk.py 9_Firmware/9_3_GUI/test_v7.py 9_Firmware/tests/cross_layer/test_cross_layer_contract.py -v
```
