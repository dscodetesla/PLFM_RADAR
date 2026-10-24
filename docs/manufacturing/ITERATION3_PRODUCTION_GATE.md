# Ітерація 3 — production FPGA gate та доступний native target

Дата: 2026-10-20, Europe/Kyiv. База `b00c6b5e9a2b6a08130bfa1ded342fe60a9f78e2`,
гілка `integration/workbench-2026-10-20`. **NOT_FOR_MANUFACTURE / NOT_FOR_FLASH.**
Scope: Nexus Main + Synth + Power + Patch 8×16; CAD/RTL не змінено цією ітерацією.

## Виправлений дефект pipeline (pending review/commit)

`build_50t.tcl` знижував BIVC-1, PLIO-9, NSTD-1 та UCIO-1 до Warning,
додавав blanket CLOCK_DEDICATED_ROUTE FALSE для FT clock і викликав
write_bitstream до фінальних DRC/timing reports. Відсутній bitstream давав лише Warning.

У поточному working tree: native part check до створення outputs; вилучені ці
послаблення; report_drc/report_timing_summary перед write_bitstream; production_gate.tcl
відхиляє Error/Critical Warning, невідомий severity, відсутні timing paths,
нечисловий/нескінченний або негативний setup/hold slack. Missing bitstream є error.
Це обмежений build gate: він не доводить timing coverage, CDC, RF або board compatibility.
Нативна перевірка unconstrained paths, pulse width, CDC, Bank14 та всі ECO залишаються OPEN.
Видалення blanket waivers може виявити додаткові реальні помилки після clock ECO;
їх треба виправляти у джерелах, а не повертати demotions.

## Емпіричне розблокування інструментів

- X99MG: Vivado 2025.2, 1274 parts, Artix-7 matches=0. Конкретний target unavailable;
  запуск create_project для xc7a50tftg256-2 завершився exit 1.
- desk-tyan: `/home/user/AMDDesignTools/2026.1/Vivado/bin/vivado`,
  5893 parts, exact target match=1. In-memory link_design і package-pin inventory PASS, exit 0.
- Нативна база Vivado підтвердила C13=IO_L12N_T1_MRCC_15,
  D13=IO_L12P_T1_MRCC_15, C4=IO_L12N_T1_MRCC_35,
  D4=IO_L12P_T1_MRCC_35, E12=IO_L13P_T2_MRCC_15,
  T5=IO_L23N_T3_A02_D18_14. Це класи контактів, не routing/timing proof.
- Окрема synthetic 1-FF design synthesis на exact part PASS. Native report_drc
  повернув NSTD-1 та UCIO-1 як Critical Warning; SEVERITY доступний на drc_violation.
  Це тест API/середовища, не synthesis радара.
- Репозиторій у `/home/user/gdrive_local/project/PLFM_RADAR` на desk-tyan
  фактично main + багато dirty files. Не перезаписаний і не переключений.

Відтворення inventory: з `9_Firmware/9_2_FPGA` виконати
`/home/user/AMDDesignTools/2026.1/Vivado/bin/vivado -mode batch -nojournal -nolog -source scripts/50t/probe_50t.tcl`.
Probe не завантажує radar sources й не створює manufacturing approval.

## Перевірки

- Manufacturing unittest: 21/21 PASS, включно з negative DRC/setup/hold/missing-path cases.
- Python discovery: 231 passed, 9 skipped, 2 warnings, 26 subtests (див. фактичний log).
- MCU host/mock: 24 suite PASS, 0 fail; compiler signedness warning залишається.
- Strict static manufacturing audit: exit 1, очікуваний C13/D13 mismatch лишається видимим.
- git diff --check: PASS.
- Native negative gate: у Vivado 2026.1 новий gate відхилив NSTD-1#1 Critical Warning;
  PLFM_NATIVE_DRC_REJECTION_PASS, exit 0 тестового harness. Bitstream не створювався.
- Full local CI: NOT COMPLETE — ruff та Icarus відсутні; sfw відсутній,
  пакетів не встановлювали. За CONTRIBUTING зміни не комічені/не pushed.
- Full radar native synthesis/place/route, native EAGLE ERC/DRC та fresh CAM: NOT RUN.

## Наступний критичний результат

Один узгоджений native CAD ECO для clock contacts та Bank14, з SCH↔BRD↔XDC
відповідністю й electrical review. Не переносити branch XDC C13 workaround без timing/jitter
доказу. Після ECO: full radar native build на desk-tyan, тоді fresh per-board exports
і factory-approved stackup/DFM. Не генерувати production ZIP з поточних legacy CAM.

PCBWay Advanced/HF лишається кандидатом маршруту quotation; JLCPCB custom multilayer
HF не підтверджено. Нових звернень до фабрик або замовлень не виконували.

## Самовдосконалення

Availability gate тепер перевіряє exact FPGA part, не лише наявність команди Vivado.
Production script не перетворює electrical/pin DRC на Warning за замовчуванням.
Нові negative tests захищають від хибного bitstream acceptance. Tool facts прив'язані
до конкретного хоста/версії; hardware readiness не підвищено.

Первинний API reference: https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/get_timing_paths
