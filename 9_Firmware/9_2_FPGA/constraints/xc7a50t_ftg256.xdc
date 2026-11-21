# ============================================================================
# RADAR SYSTEM FPGA CONSTRAINTS — AERIS-10N (50T Production Wrapper)
# ============================================================================
# Device: XC7A50T-2FTG256I (FTG256 package, U42 on MainBoard)
# Top:    radar_system_top_50t (instantiates radar_system_top as u_core)
#
# I/O Bank Voltage Summary (RADAR_Main_Board.sch):
#   Bank 0:  VCCO = 3.3V (Configuration / SPI Flash / JTAG)
#   Bank 14: VCCO = 3.3V (AD9484 LVDS_25 inputs with DIFF_TERM FALSE + external
#            100-ohm resistors R2..R12; adc_pwdn on T5 as LVCMOS33 via R36=830R / R37=1k)
#   Bank 15: VCCO = 3.3V (DAC AD9708, 100/120 MHz clocks, STM32 SPI 3.3V, DIG bus, mixers)
#   Bank 34: VCCO = 1.8V (ADAR1000 beamformer control & 1.8V SPI side)
#   Bank 35: VCCO = 3.3V (FT2232H USB 2.0 245 Synchronous FIFO — 15 signals)
#
# Engineering Gate Notes (Zero-Waiver Policy):
#   - Bank 14 (Investigation #11): 7-Series HR IBUFDS LVDS_25 differential inputs
#     are powered from VCCAUX (1.8V) and operate with VCCO_14 = 3.3V ONLY when
#     internal DIFF_TERM is FALSE. External 100-ohm differential resistors R2..R12
#     provide termination on the PCB; adc_pwdn (T5) uses LVCMOS33 through divider
#     R36=830R / R37=1k, eliminating DRC BIVC-1 and Place 30-372 without waivers.
#   - MRCC Clocks (Investigations #9 & #10 — ECO Candidates [Proposal]):
#     * clk_120m_dac -> D13 (IO_L12P_T1_MRCC_15, P-side MRCC; unmodified PCB routes C13)
#     * ft_clkout    -> D4  (IO_L12P_T1_MRCC_35, P-side MRCC; unmodified PCB routes C4)
#     Configured cleanly on P-side MRCC inputs with ZERO CLOCK_DEDICATED_ROUTE FALSE
#     overrides. Physical BGA escape routing C13->D13 and C4->D4 remains tracked
#     as ECO candidates under Investigations #9 and #10 prior to board manufacture.
# ============================================================================

# ============================================================================
# CONFIGURATION
# ============================================================================
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]

# ============================================================================
# CLOCK CONSTRAINTS
# ============================================================================

# 100 MHz System Clock (AD9523 OUT6 -> FPGA_SYS_CLOCK -> Bank 15 P-side SRCC pin E12)
set_property PACKAGE_PIN E12 [get_ports {clk_100m}]
set_property IOSTANDARD LVCMOS33 [get_ports {clk_100m}]
create_clock -name clk_100m -period 10.000 [get_ports {clk_100m}]
set_input_jitter [get_clocks clk_100m] 0.100

# 120 MHz DAC Clock (AD9523 OUT11 -> FPGA_DAC_CLOCK -> Bank 15 P-side MRCC pin D13)
# NOTE: Unmodified MainBoard schematic/layout connects FPGA_DAC_CLOCK to C13
#       (IO_L12N_T1_MRCC_15). Pin D13 (IO_L12P_T1_MRCC_15) is the clean P-side
#       MRCC assignment evaluated under ECO Candidate Investigation #9.
set_property PACKAGE_PIN D13 [get_ports {clk_120m_dac}]
set_property IOSTANDARD LVCMOS33 [get_ports {clk_120m_dac}]
create_clock -name clk_120m_dac -period 8.333 [get_ports {clk_120m_dac}]
set_input_jitter [get_clocks clk_120m_dac] 0.100

# ADC DCO Clock (400 MHz LVDS — AD9523 OUT5 -> AD9484 -> FPGA Bank 14 P-side MRCC N14/P14)
# External 100-ohm termination resistor R2 is populated on PCB; DIFF_TERM must be
# FALSE because Bank 14 VCCO = 3.3V (7-Series internal DIFF_TERM requires VCCO = 2.5V).
set_property PACKAGE_PIN N14 [get_ports {adc_dco_p}]
set_property PACKAGE_PIN P14 [get_ports {adc_dco_n}]
set_property IOSTANDARD LVDS_25 [get_ports {adc_dco_p}]
set_property IOSTANDARD LVDS_25 [get_ports {adc_dco_n}]
set_property DIFF_TERM FALSE [get_ports {adc_dco_p}]
set_property DIFF_TERM FALSE [get_ports {adc_dco_n}]
create_clock -name adc_dco_p -period 2.500 [get_ports {adc_dco_p}]
set_input_jitter [get_clocks adc_dco_p] 0.050

# FT2232H 60 MHz CLKOUT (245 Synchronous FIFO mode -> Bank 35 P-side MRCC pin D4)
# NOTE: Unmodified MainBoard schematic/layout connects FT_CLKOUT to C4
#       (IO_L12N_T1_MRCC_35). Pin D4 (IO_L12P_T1_MRCC_35) is the clean P-side
#       MRCC assignment evaluated under ECO Candidate Investigation #10 (no waivers).
set_property PACKAGE_PIN D4 [get_ports {ft_clkout}]
set_property IOSTANDARD LVCMOS33 [get_ports {ft_clkout}]
create_clock -name ft_clkout -period 16.667 [get_ports {ft_clkout}]
set_input_jitter [get_clocks ft_clkout] 0.200

# ============================================================================
# RESET (Active-Low — DIG_4: STM32 PD12 -> FPGA Bank 15 pin E15)
# ============================================================================
set_property PACKAGE_PIN E15 [get_ports {reset_n}]
set_property IOSTANDARD LVCMOS33 [get_ports {reset_n}]
set_property PULLUP true [get_ports {reset_n}]

# ============================================================================
# TRANSMITTER INTERFACE (DAC AD9708 — Bank 15, VCCO=3.3V)
# ============================================================================
set_property PACKAGE_PIN A14 [get_ports {dac_data[0]}]
set_property PACKAGE_PIN A13 [get_ports {dac_data[1]}]
set_property PACKAGE_PIN A12 [get_ports {dac_data[2]}]
set_property PACKAGE_PIN B11 [get_ports {dac_data[3]}]
set_property PACKAGE_PIN B10 [get_ports {dac_data[4]}]
set_property PACKAGE_PIN A10 [get_ports {dac_data[5]}]
set_property PACKAGE_PIN A9  [get_ports {dac_data[6]}]
set_property PACKAGE_PIN A8  [get_ports {dac_data[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {dac_data[*]}]
set_property SLEW FAST [get_ports {dac_data[*]}]
set_property DRIVE 8 [get_ports {dac_data[*]}]

# DAC Sleep Control — DAC_SLEEP net
set_property PACKAGE_PIN A15 [get_ports {dac_sleep}]
set_property IOSTANDARD LVCMOS33 [get_ports {dac_sleep}]

# RF Switch Control — M3S_VCTRL net
set_property PACKAGE_PIN G15 [get_ports {fpga_rf_switch}]
set_property IOSTANDARD LVCMOS33 [get_ports {fpga_rf_switch}]

# Mixer Enables — MIX_RX_EN, MIX_TX_EN nets
set_property PACKAGE_PIN D11 [get_ports {rx_mixer_en}]
set_property PACKAGE_PIN C11 [get_ports {tx_mixer_en}]
set_property IOSTANDARD LVCMOS33 [get_ports {rx_mixer_en}]
set_property IOSTANDARD LVCMOS33 [get_ports {tx_mixer_en}]

# ============================================================================
# ADAR1000 BEAMFORMER CONTROL (Bank 34, VCCO=1.8V)
# ============================================================================
set_property PACKAGE_PIN P3 [get_ports {adar_tx_load_1}]
set_property PACKAGE_PIN T4 [get_ports {adar_tx_load_2}]
set_property PACKAGE_PIN R3 [get_ports {adar_tx_load_3}]
set_property PACKAGE_PIN R2 [get_ports {adar_tx_load_4}]

set_property PACKAGE_PIN M5 [get_ports {adar_rx_load_1}]
set_property PACKAGE_PIN T2 [get_ports {adar_rx_load_2}]
set_property PACKAGE_PIN R1 [get_ports {adar_rx_load_3}]
set_property PACKAGE_PIN N4 [get_ports {adar_rx_load_4}]
set_property IOSTANDARD LVCMOS18 [get_ports {adar_*_load_*}]

set_property PACKAGE_PIN N2 [get_ports {adar_tr_1}]
set_property PACKAGE_PIN N1 [get_ports {adar_tr_2}]
set_property PACKAGE_PIN P1 [get_ports {adar_tr_3}]
set_property PACKAGE_PIN P4 [get_ports {adar_tr_4}]
set_property IOSTANDARD LVCMOS18 [get_ports {adar_tr_*}]

# ============================================================================
# LEVEL SHIFTER SPI INTERFACE (STM32 <-> ADAR1000)
# ============================================================================

# 3.3V Side (from STM32, Bank 15, VCCO=3.3V)
set_property PACKAGE_PIN J16 [get_ports {stm32_sclk_3v3}]
set_property PACKAGE_PIN H13 [get_ports {stm32_mosi_3v3}]
set_property PACKAGE_PIN G14 [get_ports {stm32_miso_3v3}]
set_property PACKAGE_PIN F14 [get_ports {stm32_cs_adar1_3v3}]
set_property PACKAGE_PIN H16 [get_ports {stm32_cs_adar2_3v3}]
set_property PACKAGE_PIN G16 [get_ports {stm32_cs_adar3_3v3}]
set_property PACKAGE_PIN J15 [get_ports {stm32_cs_adar4_3v3}]
set_property IOSTANDARD LVCMOS33 [get_ports {stm32_*_3v3}]

# 1.8V Side (to ADAR1000, Bank 34, VCCO=1.8V)
set_property PACKAGE_PIN P5 [get_ports {stm32_sclk_1v8}]
set_property PACKAGE_PIN M1 [get_ports {stm32_mosi_1v8}]
set_property PACKAGE_PIN N3 [get_ports {stm32_miso_1v8}]
set_property PACKAGE_PIN L5 [get_ports {stm32_cs_adar1_1v8}]
set_property PACKAGE_PIN L4 [get_ports {stm32_cs_adar2_1v8}]
set_property PACKAGE_PIN M4 [get_ports {stm32_cs_adar3_1v8}]
set_property PACKAGE_PIN M2 [get_ports {stm32_cs_adar4_1v8}]
set_property IOSTANDARD LVCMOS18 [get_ports {stm32_*_1v8}]

# ============================================================================
# STM32 CONTROL INTERFACE (DIG bus, Bank 15, VCCO=3.3V)
# ============================================================================
set_property PACKAGE_PIN F13 [get_ports {stm32_new_chirp}]       ;# DIG_0 (PD8)
set_property PACKAGE_PIN E16 [get_ports {stm32_new_elevation}]   ;# DIG_1 (PD9)
set_property PACKAGE_PIN D16 [get_ports {stm32_new_azimuth}]     ;# DIG_2 (PD10)
set_property PACKAGE_PIN F15 [get_ports {stm32_mixers_enable}]   ;# DIG_3 (PD11)
set_property IOSTANDARD LVCMOS33 [get_ports {stm32_new_*}]
set_property IOSTANDARD LVCMOS33 [get_ports {stm32_mixers_enable}]

# DIG_5 = H11, DIG_6 = G12, DIG_7 = H12 — FPGA -> STM32 status outputs
set_property PACKAGE_PIN H11 [get_ports {gpio_dig5}]
set_property PACKAGE_PIN G12 [get_ports {gpio_dig6}]
set_property PACKAGE_PIN H12 [get_ports {gpio_dig7}]
set_property IOSTANDARD LVCMOS33 [get_ports {gpio_dig*}]
set_property DRIVE 8 [get_ports {gpio_dig*}]
set_property SLEW SLOW [get_ports {gpio_dig*}]

# ============================================================================
# ADC INTERFACE (AD9484 LVDS — Bank 14, VCCO=3.3V)
# ============================================================================

# ADC Data (8-bit LVDS pairs from AD9484; external 100-ohm terminators R3..R12 on PCB)
set_property PACKAGE_PIN P15 [get_ports {adc_d_p[0]}]
set_property PACKAGE_PIN P16 [get_ports {adc_d_n[0]}]
set_property PACKAGE_PIN R15 [get_ports {adc_d_p[1]}]
set_property PACKAGE_PIN R16 [get_ports {adc_d_n[1]}]
set_property PACKAGE_PIN T14 [get_ports {adc_d_p[2]}]
set_property PACKAGE_PIN T15 [get_ports {adc_d_n[2]}]
set_property PACKAGE_PIN R13 [get_ports {adc_d_p[3]}]
set_property PACKAGE_PIN T13 [get_ports {adc_d_n[3]}]
set_property PACKAGE_PIN R10 [get_ports {adc_d_p[4]}]
set_property PACKAGE_PIN R11 [get_ports {adc_d_n[4]}]
set_property PACKAGE_PIN T9  [get_ports {adc_d_p[5]}]
set_property PACKAGE_PIN T10 [get_ports {adc_d_n[5]}]
set_property PACKAGE_PIN T7  [get_ports {adc_d_p[6]}]
set_property PACKAGE_PIN T8  [get_ports {adc_d_n[6]}]
set_property PACKAGE_PIN R6  [get_ports {adc_d_p[7]}]
set_property PACKAGE_PIN R7  [get_ports {adc_d_n[7]}]

# ADC Power Down — ADC_PWRD net on T5 (Bank 14 VCCO=3.3V, drives AD9484 PWDN
# via external resistor divider R36=830R / R37=1k -> ~1.80V at 1.8V absmax domain)
set_property PACKAGE_PIN T5 [get_ports {adc_pwdn}]
set_property IOSTANDARD LVCMOS33 [get_ports {adc_pwdn}]

# LVDS_25 inputs with internal DIFF_TERM disabled (external 100-ohm R2..R12 fitted)
set_property IOSTANDARD LVDS_25 [get_ports {adc_d_p[*]}]
set_property IOSTANDARD LVDS_25 [get_ports {adc_d_n[*]}]
set_property DIFF_TERM FALSE [get_ports {adc_d_p[*]}]
set_property DIFF_TERM FALSE [get_ports {adc_d_n[*]}]

# Source-synchronous DDR input delays relative to adc_dco_p
set_input_delay -clock [get_clocks adc_dco_p] -max 1.000 [get_ports {adc_d_p[*]}]
set_input_delay -clock [get_clocks adc_dco_p] -min 0.200 [get_ports {adc_d_p[*]}]
set_input_delay -clock [get_clocks adc_dco_p] -max 1.000 -clock_fall [get_ports {adc_d_p[*]}] -add_delay
set_input_delay -clock [get_clocks adc_dco_p] -min 0.200 -clock_fall [get_ports {adc_d_p[*]}] -add_delay

# ============================================================================
# FT2232H USB 2.0 INTERFACE (Bank 35, VCCO=3.3V)
# ============================================================================
# FT2232H (U6) Channel A in 245 Synchronous FIFO mode (60 MHz, period = 16.667 ns).

# 8-bit bidirectional data bus (ADBUS0..ADBUS7)
set_property PACKAGE_PIN K1 [get_ports {ft_data[0]}]   ;# ADBUS0 -> IO_L22P_T3_35
set_property PACKAGE_PIN J3 [get_ports {ft_data[1]}]   ;# ADBUS1 -> IO_L21P_T3_DQS_35
set_property PACKAGE_PIN H3 [get_ports {ft_data[2]}]   ;# ADBUS2 -> IO_L21N_T3_DQS_35
set_property PACKAGE_PIN G4 [get_ports {ft_data[3]}]   ;# ADBUS3 -> IO_L16N_T2_35
set_property PACKAGE_PIN F2 [get_ports {ft_data[4]}]   ;# ADBUS4 -> IO_L15P_T2_DQS_35
set_property PACKAGE_PIN D1 [get_ports {ft_data[5]}]   ;# ADBUS5 -> IO_L10N_T1_AD15N_35
set_property PACKAGE_PIN C3 [get_ports {ft_data[6]}]   ;# ADBUS6 -> IO_L7P_T1_AD6P_35
set_property PACKAGE_PIN C1 [get_ports {ft_data[7]}]   ;# ADBUS7 -> IO_L9P_T1_DQS_AD7P_35
set_property IOSTANDARD LVCMOS33 [get_ports {ft_data[*]}]

# Control signals (active low where noted)
set_property PACKAGE_PIN A2 [get_ports {ft_rxf_n}]     ;# ACBUS0 -> IO_L8N_T1_AD14N_35
set_property PACKAGE_PIN B2 [get_ports {ft_txe_n}]     ;# ACBUS1 -> IO_L8P_T1_AD14P_35
set_property PACKAGE_PIN A3 [get_ports {ft_rd_n}]      ;# ACBUS2 -> IO_L4N_T0_35
set_property PACKAGE_PIN A4 [get_ports {ft_wr_n}]      ;# ACBUS3 -> IO_L3N_T0_DQS_AD5N_35
set_property PACKAGE_PIN A5 [get_ports {ft_siwu}]      ;# ACBUS4 -> IO_L3P_T0_DQS_AD5P_35
set_property PACKAGE_PIN B7 [get_ports {ft_oe_n}]      ;# ACBUS6 -> IO_L1P_T0_AD4P_35
set_property IOSTANDARD LVCMOS33 [get_ports {ft_rxf_n}]
set_property IOSTANDARD LVCMOS33 [get_ports {ft_txe_n}]
set_property IOSTANDARD LVCMOS33 [get_ports {ft_rd_n}]
set_property IOSTANDARD LVCMOS33 [get_ports {ft_wr_n}]
set_property IOSTANDARD LVCMOS33 [get_ports {ft_siwu}]
set_property IOSTANDARD LVCMOS33 [get_ports {ft_oe_n}]

# Output buffer drive and slew rate for FT2232H signals
set_property SLEW FAST [get_ports {ft_rd_n}]
set_property SLEW FAST [get_ports {ft_wr_n}]
set_property SLEW FAST [get_ports {ft_oe_n}]
set_property SLEW FAST [get_ports {ft_siwu}]
set_property SLEW FAST [get_ports {ft_data[*]}]
set_property DRIVE 8 [get_ports {ft_rd_n}]
set_property DRIVE 8 [get_ports {ft_wr_n}]
set_property DRIVE 8 [get_ports {ft_oe_n}]
set_property DRIVE 8 [get_ports {ft_siwu}]
set_property DRIVE 8 [get_ports {ft_data[*]}]

# --------------------------------------------------------------------------
# FT2232H Source-Synchronous Timing Constraints (DS_FT2232H Table 4.10)
# --------------------------------------------------------------------------
# FPGA Read Path (FT2232H drives data/flags after CLKOUT edge, t3_max = 9.667 ns):
#   - Input delay max = 9.667 ns, min = 0.000 ns
#
# FPGA Write Path (FPGA drives data/control to FT2232H, sampled on CLKOUT rising):
#   - FT2232H datasheet setup time t5 (ADBUS/RD#/WR#/OE#/SIWU# to CLKOUT) = 3.500 ns
#   - FT2232H datasheet hold time  t6 = 0.000 ns
#   - set_output_delay -max = t_su = 3.500 ns, -min = -t_hd = 0.000 ns
# --------------------------------------------------------------------------

# Input delays: FT2232H -> FPGA (data bus and FIFO flags)
set_input_delay -clock [get_clocks ft_clkout] -max 9.667 [get_ports {ft_data[*]}]
set_input_delay -clock [get_clocks ft_clkout] -min 0.000 [get_ports {ft_data[*]}]
set_input_delay -clock [get_clocks ft_clkout] -max 9.667 [get_ports {ft_rxf_n}]
set_input_delay -clock [get_clocks ft_clkout] -min 0.000 [get_ports {ft_rxf_n}]
set_input_delay -clock [get_clocks ft_clkout] -max 9.667 [get_ports {ft_txe_n}]
set_input_delay -clock [get_clocks ft_clkout] -min 0.000 [get_ports {ft_txe_n}]

# Output delays: FPGA -> FT2232H (datasheet t_su = 3.500 ns, t_hd = 0.000 ns)
set_output_delay -clock [get_clocks ft_clkout] -max 3.500 [get_ports {ft_data[*]}]
set_output_delay -clock [get_clocks ft_clkout] -min 0.000 [get_ports {ft_data[*]}]
set_output_delay -clock [get_clocks ft_clkout] -max 3.500 [get_ports {ft_rd_n}]
set_output_delay -clock [get_clocks ft_clkout] -min 0.000 [get_ports {ft_rd_n}]
set_output_delay -clock [get_clocks ft_clkout] -max 3.500 [get_ports {ft_wr_n}]
set_output_delay -clock [get_clocks ft_clkout] -min 0.000 [get_ports {ft_wr_n}]
set_output_delay -clock [get_clocks ft_clkout] -max 3.500 [get_ports {ft_oe_n}]
set_output_delay -clock [get_clocks ft_clkout] -min 0.000 [get_ports {ft_oe_n}]
set_output_delay -clock [get_clocks ft_clkout] -max 3.500 [get_ports {ft_siwu}]
set_output_delay -clock [get_clocks ft_clkout] -min 0.000 [get_ports {ft_siwu}]

# ============================================================================
# TIMING EXCEPTIONS
# ============================================================================

# False paths for asynchronous STM32 control signals (edge-synchronized in RTL)
set_false_path -from [get_ports {stm32_new_*}]
set_false_path -from [get_ports {stm32_mixers_enable}]

# Async reset recovery/removal false paths across u_core reset synchronizers
# Covers u_core/reset_sync_reg[*], u_core/reset_sync_120m_reg[*], and
# u_core/reset_sync_ft601_reg[*] inside radar_system_top_50t -> u_core.
set_false_path -from [get_cells {u_core/reset_sync*_reg[*]}] -to [get_pins -filter {REF_PIN_NAME == CLR} -of_objects [get_cells -hierarchical -filter {PRIMITIVE_TYPE =~ REGISTER.*.*}]]

# Clock Domain Crossing false paths (handled by explicit CDC modules in RTL)
set_false_path -from [get_clocks clk_100m] -to [get_clocks adc_dco_p]
set_false_path -from [get_clocks adc_dco_p] -to [get_clocks clk_100m]

set_false_path -from [get_clocks clk_100m] -to [get_clocks clk_120m_dac]
set_false_path -from [get_clocks clk_120m_dac] -to [get_clocks clk_100m]

set_false_path -from [get_clocks clk_100m] -to [get_clocks ft_clkout]
set_false_path -from [get_clocks ft_clkout] -to [get_clocks clk_100m]

set_false_path -from [get_clocks clk_120m_dac] -to [get_clocks ft_clkout]
set_false_path -from [get_clocks ft_clkout] -to [get_clocks clk_120m_dac]

# ============================================================================
# PHYSICAL CONSTRAINTS
# ============================================================================
set_property BITSTREAM.CONFIG.UNUSEDPIN Pullup [current_design]
