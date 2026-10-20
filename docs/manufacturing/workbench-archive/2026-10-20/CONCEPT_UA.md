# PLFM_RADAR / AERIS-10N Nexus: концепт та архітектура

Відкрита модульна платформа активного імпульсного ЛЧМ-радара з аналоговим
формуванням променя та цифровою обробкою у FPGA. Цілі: оцінка дальності,
радіальної швидкості та напрямку на об’єкти за відбитим сигналом.

Контур Nexus: MainBoard, Frequency Synthesizer, PowerBoard, Patch Array 8×16.
MainBoard: XC7A50T FTG256, STM32F746, AD9484 ADC, AD9708 DAC, LTC5552 mixers,
4× ADAR1000 та 16× ADTR1107. Синхронізація: AD9523-1, гетеродини ADF4382.
ПК/GUI підключається до фізичної 50T-плати через FT2232H USB2.0.

TX: FPGA chirp → DAC → перетворення частоти → RF beamformer/front-end → антена.
RX: антена → front-end/beamformer → перетворення частоти → ADC → FPGA DSP → GUI.
FPGA: DDC I/Q, децимація/фільтри, pulse compression, Doppler FFT, MTI/CFAR.
MCU: живлення, периферія, RF sequencing; GPS/IMU і механічне обертання —
додаткові функції ширшого задуму. 8×16 випромінювачів не означають 128 ADC.

10.5 GHz, 3 km, ±45° steering та 360° механічний огляд — заявлені цілі upstream,
а не підтверджені нашими фізичними вимірюваннями характеристики.
Extended PA/waveguide і альтернативні XC7A200T/FT601 targets не входять до
поточного виробничого комплекту. Найближча мета: живлення, clocks, ADC/DAC,
контрольне відбиття, потім калібрування та вимірювання. NOT_FOR_MANUFACTURE.

Основа опису: README та radar_system_top_50t.v baseline
749bd0f86a07a28a86347d8ce9c141e601057c40; результати перевірок — reports/.
