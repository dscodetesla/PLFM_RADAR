# PLFM_RADAR: HF manufacturing recovery, 2026-10-20

Оновлення ітерації 2: див. [EMPIRICAL_UNBLOCK.md](EMPIRICAL_UNBLOCK.md).
Наведені нижче результати першої ітерації збережені як історичні; актуальні зміни
X36, clock preflight та результати тестів — у новому звіті.

Статус: **NOT_FOR_MANUFACTURE / Draft**. Поточна ітерація виправляє комплектування
та додає відтворюваний аудит. Робочий фізичний прототип, Quote ready, Fab approved
і PCBA approved цією роботою не підтверджені.

## База і межі

Репозиторій: https://github.com/dscodetesla/PLFM_RADAR

Вхідний main: `749bd0f86a07a28a86347d8ce9c141e601057c40`.
Перевірений develop: `2a9f7161a07c6cde6dc3faa033381d684aac41ab`.
У main відсутні попередні `release/AERIS-10N-Nexus-R0.1` та
`docs/project-context/state.json`; попередні заяви готовності не успадковані.
Серед отриманих 20 гілок немає гілки з цими release-артефактами за назвою;
повний аудит історії кожної гілки/зовнішніх forks не виконаний.
Main і develop мають істотні відмінності CAD і firmware (133 змінені шляхи в diff),
тому ціла альтернативна гілка не переносилась. Зміни підготовлені на main в
окремому worktree `fix/hf-manufacturing-audit-20261020`.

Scope: AERIS-10N Nexus — MainBoard, Frequency Synthesizer, PowerBoard, Patch 8×16,
їхні інтерфейси і перевірки. PA/QPA2962 та Waveguide 32×16 належать Extended;
вони збережені у репозиторії, але не входять у цю закупівлю. Заявлені upstream
дальність 3 km, потужність та steering залишаються вимогами до фізичної перевірки.

## Що реально виправлено

| Файл / об'єкт | Дефект | Зміна | Доказ |
|---|---|---|---|
| Main BOM, A13 | Qty=75, перелік 73 refs | Qty=73 | Підрахунок refs та CAD |
| Main BOM, A15/E15 | Qty=6, 8 entries, дубль C352, відсутній C353 | Qty=8; останній C352 замінено на C353 | C352/C353 існують у SCH/BRD, обидва 0.1uF/C0201 |
| Main CPL | SJ1, U$2, U$3 присутні попри DNP/artwork у BOM | Видалено 3 позиції; решта 709 незмінні | Перевірка кожного рядка проти baseline |
| Patch BOM, A2 | Qty=11, перелік і PCB містять 16 | Qty=16 | 16 унікальних refs у SCH/BRD/BOM/CPL |
| Pipeline | BOM/CPL не перевірялись CI | Read-only audit + unittest + Actions workflow | Тести спочатку відтворили помилки, потім пройшли |
| README | Інструкція одразу замовляти старі outputs | Посилання на статус і блокери | Зміна документації |

MPN у виправлених рядках збережено з чинного BOM, а не схвалено заново.
Корекція кількості не доводить voltage rating, lifecycle, механічну чи RF-сумісність.
Під час експорту XLSX виявлено помилку імпортера порожніх shared strings;
порожні комірки відновлено з джерела. Фінальний побайтовий формат XLSX змінився,
але перевірка значень/формул дозволила тільки перелічені зміни; змінені області
переглянуто візуально. Повна Excel-native перевірка стилів/властивостей не виконана.

## Фактичний профіль плат

Це статичні факти EAGLE XML, не результат native DRC. Значення drill — CAD drill,
не погоджений із виробником діаметр готового отвору.

| Board | PCB elements / physical SCH parts | Шарів міді | CAD layerSetup | Мін. via drill, mm | CPL після змін |
|---|---:|---:|---|---:|---:|
| Main | 791 / 791 | 10 | `(1*2+3*4+5*12+13*14+15*16)` | 0.15 | 709 |
| Synth | 184 / 184 | 6 | `(1+2*3+14*15+16)` | 0.15 | 174 |
| Power | 313 / 312 | 2 | `(1*16)` | 0.15 | 276 |
| Patch 8×16 | 16 / 16 | 4 | `(1+2*3+16)` | 0.6 | 16 |

791/184/313/16 — кількість елементів CAD, не кількість закуповуваних компонентів:
artwork/DNP/ручний монтаж мають бути явно класифіковані. У всіх чотирьох платах
немає збережених wire layer=19; це **не доказ відсутності unrouted nets**.
Вибіркова автоматизована звірка всіх CPL X/Y із EAGLE element origin не виявила
відхилень понад 0.02 mm. EAGLE origin не гарантує centroid корпусу, а rotation/pin1
і нижній бік ще потребують assembly review.

## GAP і критерії закриття

| ID | Рівень / клас доказу | Проблема | Наступна конкретна дія / критерій |
|---|---|---|---|
| G01 | P0, Documented fact | Power X36 є на PCB, відсутній у packaged SCH. Pad1=`+5V0_LO`, pad2=`GND` | CAD-інтегратор: відновити задум X36, узгодити SCH↔BRD у native EAGLE, повторити ERC/DRC та CAM |
| G02 | P0, Documented fact | `FPGA_DAC_CLOCK`: PCB U42/C13, XDC `clk_120m_dac` D13 | FPGA+CAD: перевірити офіційний FTG256 pinout/clock pin class, actual net, виправити джерело; native synthesis/implementation/timing без прихованих DRC |
| G03 | P0, Open issue | XTAL3: MPN NX3215SA-32.768K-STD-MUS-2, package названий NX3225GD-8MHZ; CAD pads x=±0.9525, dx=1.2954, dy=2.3876 mm | Зіставити геометрію з NDK drawing, CL/drive/startup зі STM32 LSE, потім native footprint/routing review. Назва package сама по собі не доводить несправність |
| G04 | P0, Open issue | Немає доказу узгодженого per-board HF stackup | Отримати матеріал, товщини діелектриків/міді, Dk/Df із методом і частотою, RF reference plane, finish/mask, impedance coupon та допуски для точної ревізії |
| G05 | P0, Documented fact / Open issue | 0.15 mm vias: Main 1604, Synth 212, Power 28 | PCBWay engineering review: drill type, finished diameter, aspect ratio, annular ring, fill/tent і yield; не збільшувати отвори без reroute/DRC |
| G06 | P0, Open issue | Немає native ERC/DRC/CAM-equivalence evidence | Native open, library resolution, ERC, ratsnest/DRC, approved exceptions, fresh CAM, незалежний Gerber/drill viewer і exact archive review |
| G07 | P0, Open issue | Немає повної закупівельної/монтажної специфікації | Кожен MPN/voltage/package/lifecycle/DNP; manual/THT/hybrid список; pin1/rotation; assembly drawing та sourcing confirmation |
| G08 | P0, Open issue | ADC bank VCCO/DIFF_TERM/adc_pwdn і native build не перевірені | Офіційні pinout/electrical docs, фактичні rails і termination, level margins; native build для точної MainBoard. Не переносити успіх TE0713 на цю плату |
| G09 | P1, Open issue | Host MCU tests не є повним STM32 firmware build | Відтворюваний target build/link map, startup/rail/fault sequence, board config, programming procedure; потім контрольований bring-up |
| G10 | P1, Open issue | Немає фізичного RF/system evidence | Послідовність нижче, raw logs/config/instruments; не заявляти дальність, beamforming або калібрування за mock |
| G11 | Gate, Documented fact | Повний локальний CI недоступний | Виконати команди CONTRIBUTING у середовищі з дозволеним `sfw`, ruff, h5py та Icarus; тільки потім commit/PR |

Історичний сигнал про IC1 не підтверджений у цьому main: CAD value і BOM MPN
однакові (`AT93C46A-10SQ-2.7`). Його lifecycle/закупівля все одно не валідувалися.
Роз'єми Patch мають центральний SMD pad і чотири THT ground pads. Не можна
оголосити footprint помилковим лише за текстом «Through Hole» в BOM: креслення
Cinch описує surface-mount signal contact із монтажними ніжками. Потрібен
фактичний механічний fit/reflow/manual-assembly review.

## Виробничий маршрут

Рекомендований напрямок для оцінки: **PCBWay Advanced/HF**, окремий профіль на
кожну плату. Це інженерний вибір для quotation, а не підтверджена пропозиція заводу.
PowerBoard не потрібно автоматично замовляти на HF-ламінаті: його матеріал слід
визначити електричними/тепловими вимогами й погодити окремо.

На актуальній публічній сторінці JLCPCB HF зазначено 2 layers і minimum drill
0.2 mm. Отже, Main/Synth/Patch не відповідають опублікованій кількості шарів,
а CAD 0.15 mm потребує іншого підтвердженого процесу. Не переносити старі 2-layer
тарифи чи загальний текст про multilayer на цей комплект. Доступність custom
multilayer HF у JLCPCB залишається непідтвердженою.

Деталі: [pcbway-requirements.md](pcbway-requirements.md).

## Перевірки і відтворення

```bash
python3 -m unittest discover -s tools/manufacturing/tests -v
python3 tools/manufacturing/audit.py --output /tmp/plfm-current-audit.json
python3 tools/manufacturing/audit.py --strict --output /tmp/plfm-strict-audit.json
```

Звичайний audit повертає 0, коли звіт успішно побудовано, навіть якщо є findings.
`--strict` повертає 1 за static findings; input failure повертає ненульовий код.
Жоден режим не видає production approval. Поточний strict має залишатися червоним
через G01. Автоматичний job перевіряє інвентаризаційні регресії; manual dispatch
додатково виконує strict gate. Це не обхід native/factory gates.

Докази: [baseline](evidence/baseline-audit.json),
[після виправлень](evidence/current-audit.json),
[точні зміни XLSX](evidence/workbook-changes.json),
[verification](evidence/verification.json).
`source_commit` у JSON — Git HEAD; фактичні робочі байти визначають input SHA256.
Після коміту або зміни inputs створити новий звіт; історичний звіт не переписувати
як доказ для іншої ревізії.

MCU host: 24 executable suites пройшли, 0 failed, із mock HAL. Вбудований GPS suite
містить 51 assertion/test case; це не додаткові 51 hardware tests. Повний Python discovery після змін: 220 passed, 9 skipped, 2 warnings.
Native EAGLE, Vivado, ARM compiler, Icarus, ruff та h5py відсутні у цьому середовищі.
Початковий preflight не знаходив pytest; повторний фактичний запуск його знайшов.
Пропуски залишаються видимими; це не безумовний full-CI PASS.
`sfw` також відсутній; обов'язковий локальний full-CI gate CONTRIBUTING не виконано.
Тому commit, push і PR не зроблені. Гілка поки лише локальна.

## Послідовність до робочого прототипу

1. Закрити G01–G03/G08 у первинних CAD/XDC та native builds. Узгодити stackup G04–G05.
2. Fresh exports із frozen source: SCH PDF, BOM, CPL, netlist, Gerber, PTH/NPTH drill,
   outline, layer map, fab/assembly drawings. Звірити checksum manifest і ZIP.
3. Quote review та factory DFM/DFA для точної ревізії. Не подавати цей review bundle
   як production ZIP. Замовлення/оплата не виконувалися.
4. На отриманих платах: візуальна інспекція/shorts → живлення з обмеженням струму →
   rails/sequence → MCU/FPGA/JTAG/USB → reference/PLL → ADC/DAC digital → один RF
   канал на навантаженні → amplitude/phase усіх каналів → calibration/target tests.
5. Для кожного кроку до запуску записати конкретні допустимі межі з ТЗ/datasheets,
   прилади, fixture і stop criteria. Невідомі межі залишити OPEN, не вигадувати.

## Самовдосконалення процесу

Кожна підтверджена помилка комплектування тепер має regression check.
Незалежний review також спричинив перевірки missing fitted CPL, порожнього CPL,
обов’язкових колонок і скінченних числових значень. Наявність SMD pad вимагає
CPL, крім explicit DNP; майбутній ручний монтаж потребує явної зміни цього контракту. CI завжди
зберігає звіт із вхідними хешами, а ручний strict запуск показує незакриті CAD
розбіжності. Нові hardware defects спочатку записуються в GAP із джерелом і
критерієм закриття, потім виправляються одним CAD-інтегратором. Наступна ітерація
починається з G01 і G02, а не з повторного написання загального плану.

## Первинні зовнішні джерела

Перевірено 2026-10-20, Europe/Kyiv. Публічні capability pages не є approval замовлення.

- PCBWay HF: https://www.pcbway.com/pcb_prototype/What_is_High_Frequency__HF__PCB_.html
- PCBWay Advanced: https://www.pcbway.com/advanced-pcb-capabilities.html
- PCBWay assembly input: https://www.pcbway.com/smt_ordering_guide.html
- JLCPCB HF current offering: https://jlcpcb.com/pcb-fabrication/high-frequency-pcb
- NDK NX3215SA: https://www.ndk.com/images/products/catalog/c_NX3215SA_e.pdf
- Cinch drawing: https://www.cinch.com/media/drawings/products/rf-microwave/connectors/dr-CCS-JOHNS-142-0731-211.pdf
