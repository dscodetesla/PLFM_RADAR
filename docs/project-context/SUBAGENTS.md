# Реєстр інженерних пакетів та декомпозиції субагентів (`SUBAGENTS.md`)

- **Проєкт**: [`dscodetesla/PLFM_RADAR`](https://github.com/dscodetesla/PLFM_RADAR) (`AERIS-10N Nexus R0.1`)
- **Інтегрована гілка**: [`work/r02-integrated-2026-11-21`](https://github.com/dscodetesla/PLFM_RADAR/tree/work/r02-integrated-2026-11-21)

## 1. Консолідовані інженерні потоки `R02` (`2026-11-20 -> 2026-11-21`) `[V]`

| Ідентифікатор потоку | Джерельний коміт верифікації | Зона відповідальності в дереві `PLFM_RADAR` | Підсумковий статус |
| :--- | :--- | :--- | :---: |
| **`SA-R02-MCU`** (`MCU / ADAR1000 / BIST`) | [`cb70cb34`](https://gitlab.com/dscodetesla/plfm-radar-rnd/-/commit/cb70cb34cc64973ba853ca1f1a87660614c26f2e) | `9_Firmware/9_1_Microcontroller/9_1_1_C_Cpp_Libraries/ADAR1000_*`, `adf4382a_manager.c`, `9_Firmware/9_1_Microcontroller/tests/*` | **`INTEGRATED`** `[V]` (`25/25` C/C++ suites `PASS`) |
| **`SA-R02-CAD`** (`MainBoard Short Fix & Patch 8x16 DFM`) | [`ba350989`](https://gitlab.com/dscodetesla/plfm-radar-rnd/-/commit/ba350989af872490d92f6578474fc80ae8964b52) | `RADAR_Main_Board.brd` ([`62d4c556`](https://github.com/NawfalMotii79/PLFM_RADAR/commit/62d4c556508927a4192acca24422bd16a979c7dc)), `Patch_Anetnna_16_8.{brd,mnt}`, `CPL.xlsx`, `docs/manufacturing/CAD_DIFF_62D4C55_AND_PATCH_FIX.md` | **`INTEGRATED`** `[V]` (`SCH <-> BRD` `100%` паритет, `0` КЗ) |
| **`SA-R02-FPGA`** (`50T Zero-Waiver XDC / TCL & Clock Gate`) | [`d73a441b`](https://gitlab.com/dscodetesla/plfm-radar-rnd/-/commit/d73a441b74b9cd4582166d1ea4d8853f68ec45f3) | `xc7a50t_ftg256.xdc`, `adc_clk_mmcm.xdc`, `radar_system_top_50t.v`, `scripts/50t/{build_50t,pre_bitstream_gate}.tcl`, `tools/manufacturing/*` | **`INTEGRATED`** `[V]` (`53/53` Python gate tests `PASS`) |
| **`SA-R02-ORCHESTRATOR`** (`GitHub Full-Tree Consolidation`) | Поточна сесія (`desk-tyan`) | Ізольований worktree `/home/user/projects/PLFM_RADAR-wt-r02-20261121`, `docs/project-context/*`, `.github/workflows/*`, пуш у GitHub | **`COMPLETED`** `[V]` (`0` активних субагентів) |

## 2. Правила делегування для наступної хвилі (`Досліди #9–#14`)

1. **Ізоляція worktree**: кожен паралельний субагент працює у власному каталозі `git worktree` на `desk-tyan` і ніколи не змінює `/home/user/projects/PLFM_RADAR-rnd-20261024`.
2. **Канонічний віддалений сервер**: усі подальші гілки `work/*` та Pull Request створюються безпосередньо у GitHub-репозиторії [`dscodetesla/PLFM_RADAR`](https://github.com/dscodetesla/PLFM_RADAR) під контролем нативних GitHub Actions; проміжний GitLab-проєкт `89041995` не використовується для запису.
3. **Захист термінології та статусу**: жоден субагент не має права знімати прапори `NOT_FOR_MANUFACTURE / NOT_FOR_FLASH` або вводити неіснуючі назви ревізій ECO без нативного CAM-експорту `G06` та успішного звіту `Vivado 2026.1` (`#12`).
