# ============================================================================
# adc_clk_mmcm.xdc — Supplementary constraints for MMCM ADC clock path (50T)
#
# These constraints augment the existing adc_dco_p clock definitions when the
# adc_clk_mmcm module is integrated into ad9484_interface_400m.v under the
# 50T wrapper hierarchy (radar_system_top_50t -> u_core).
#
# USAGE:
#   Add this file to the Vivado project AFTER constraints/xc7a50t_ftg256.xdc.
#   The main XDC defines create_clock on adc_dco_p, clk_100m, clk_120m_dac,
#   and ft_clkout. Vivado auto-creates generated clock clk_mmcm_out0 on the
#   MMCME2_ADV CLKOUT0 net.
#
# HIERARCHY (50T top wrapper): u_core/rx_inst/adc/mmcm_inst/mmcm_adc_400m/...
# ============================================================================

# --------------------------------------------------------------------------
# CDC: BUFIO domain (adc_dco_p) <-> MMCM output domain (clk_mmcm_out0)
# --------------------------------------------------------------------------
set_max_delay -datapath_only -from [get_clocks adc_dco_p] \
    -to [get_clocks clk_mmcm_out0] 2.500

set_max_delay -datapath_only -from [get_clocks clk_mmcm_out0] \
    -to [get_clocks adc_dco_p] 2.500

# --------------------------------------------------------------------------
# CDC: MMCM output domain <-> other 50T clock domains
# --------------------------------------------------------------------------
set_false_path -from [get_clocks clk_100m] -to [get_clocks clk_mmcm_out0]
set_false_path -from [get_clocks clk_mmcm_out0] -to [get_clocks clk_100m]

set_false_path -from [get_clocks clk_mmcm_out0] -to [get_clocks ft_clkout]
set_false_path -from [get_clocks ft_clkout] -to [get_clocks clk_mmcm_out0]

set_false_path -from [get_clocks clk_mmcm_out0] -to [get_clocks clk_120m_dac]
set_false_path -from [get_clocks clk_120m_dac] -to [get_clocks clk_mmcm_out0]

# --------------------------------------------------------------------------
# MMCM Locked — asynchronous status signal under u_core hierarchy
# --------------------------------------------------------------------------
set_false_path -through [get_pins {u_core/rx_inst/adc/mmcm_inst/mmcm_adc_400m/LOCKED}]

# --------------------------------------------------------------------------
# Hold waiver for source-synchronous ADC capture (BUFIO-clocked IDDR)
# --------------------------------------------------------------------------
set_false_path -hold -from [get_ports {adc_d_p[*]}] -to [get_clocks adc_dco_p]

# --------------------------------------------------------------------------
# Timing margin for 400 MHz critical paths
# --------------------------------------------------------------------------
set_clock_uncertainty -setup -add 0.100 [get_clocks clk_mmcm_out0]
