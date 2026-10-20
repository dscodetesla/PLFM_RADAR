# PLFM_RADAR workbench

Приватний архів проміжних результатів PLFM_RADAR / AERIS-10N Nexus.
Статус інженерного комплекту: **NOT_FOR_MANUFACTURE**.

## Поточний checkpoint

- [Звіт і план прискорення](reports/EMPIRICAL_UNBLOCK.md)
- [Вимоги до виробництва](reports/pcbway-requirements.md)
- [Початковий GAP](reports/HF_HANDOFF.md)
- [Стан вихідної робочої гілки](source-state.json)
- [Пакет v2: cumulative patch, виправлені BOM/CPL, докази](checkpoints/2026-10-20/PLFM_RADAR_HF_Review_20261020_v2.zip)
- [Пакет v1](checkpoints/2026-10-20/PLFM_RADAR_HF_Review_20261020.zip)

Вихідний проєкт: https://github.com/dscodetesla/PLFM_RADAR
Source baseline: 749bd0f86a07a28a86347d8ce9c141e601057c40.
Архівний commit тут не означає commit/merge вихідного коду чи проходження його full-CI gate.
Заяви «не опубліковано» в історичних звітах стосуються часу створення checkpoint.

## Правила збереження

Зберігати нові результати датованими checkpoint, не перезаписувати попередні ZIP.
Кожен checkpoint містить статус, source revision, перевірки, обмеження та SHA256.
Не завантажувати credentials, API tokens, приватні ключі або неперевірені build outputs.
Scope: MainBoard, Synthesizer, PowerBoard, Patch 8×16. Native ERC/DRC, clock ECO,
погодження stackup і фізичний bring-up залишаються відкритими.

## Усі робочі зміни

`working-changes/` містить змінені та нові файли з робочої копії вихідного
проєкту, включно з CAD, BOM/CPL, аудиторами, тестами, планом, CI YAML і журналами
перевірок. Це частковий overlay на вказаний baseline, не самостійна build tree.
CI YAML збережено як артефакт усередині overlay і тут автоматично не виконується.
Cumulative patch міститься у ZIP v2. Вихідний репозиторій не змінено.
