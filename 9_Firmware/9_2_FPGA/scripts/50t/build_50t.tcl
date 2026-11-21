################################################################################
# build_50t.tcl — XC7A50T Zero-Waiver Production Gate Build
# Builds the AERIS-10N design targeting XC7A50T-2FTG256I (radar_system_top_50t)
#
# Usage:
#   cd 9_Firmware/9_2_FPGA
#   vivado -mode batch -source scripts/50t/build_50t.tcl 2>&1 | tee build_50t/vivado.log
################################################################################

set project_name        "aeris10_radar_50t"
set script_dir          [file dirname [file normalize [info script]]]
set project_root        [file normalize [file join $script_dir "../.."]]
set repo_root           [file normalize [file join $project_root "../.."]]
set project_dir         [file join $project_root "build_50t"]
set rtl_dir             $project_root
set fpga_part           "xc7a50tftg256-2"
set top_module          "radar_system_top_50t"
set evidence_gate_tcl   [file join $repo_root "docs" "manufacturing" "evidence" "production_gate.tcl"]
set local_gate_tcl      [file join $script_dir "production_gate.tcl"]
set pre_bit_gate_tcl    [file join $script_dir "pre_bitstream_gate.tcl"]

# Verify exact native Artix-7 target part installation before creating outputs.
if {[llength [get_parts -quiet $fpga_part]] != 1} {
    error "Production FPGA part unavailable: $fpga_part; install Artix-7 device support"
}

puts "================================================================"
puts "  AERIS-10N — XC7A50T Zero-Waiver Build"
puts "  Target:    $fpga_part"
puts "  Project:   $project_dir"
puts "================================================================"

if {![file exists $evidence_gate_tcl]} {
    error "CRITICAL: Missing zero-waiver gate script: $evidence_gate_tcl"
}

file mkdir $project_dir
set report_dir [file join $project_dir "reports_50t"]
file mkdir $report_dir
set bit_dir [file join $project_dir "bitstream"]
file mkdir $bit_dir

create_project $project_name $project_dir -part $fpga_part -force

# Add ALL RTL files in the project root (avoid stale/dev tops)
set skip_patterns {*_te0712_* *_te0713_*}
foreach f [glob -directory $rtl_dir *.v] {
    set skip 0
    foreach pat $skip_patterns {
        if {[string match $pat [file tail $f]]} { set skip 1; break }
    }
    if {!$skip} {
        add_files -norecurse $f
        puts "  Added: [file tail $f]"
    }
}

set_property top $top_module [current_fileset]
set_property verilog_define {FFT_XPM_BRAM} [current_fileset]

# Constraints — 50T XDC + MMCM supplement (zero DRC severity waivers)
add_files -fileset constrs_1 -norecurse [file join $project_root "constraints" "xc7a50t_ftg256.xdc"]
add_files -fileset constrs_1 -norecurse [file join $project_root "constraints" "adc_clk_mmcm.xdc"]

# ===== SYNTHESIS =====
set synth_start [clock seconds]
launch_runs synth_1 -jobs 8
wait_on_run synth_1
set synth_elapsed [expr {[clock seconds] - $synth_start}]
set synth_status [get_property STATUS [get_runs synth_1]]
puts "  Synthesis status: $synth_status"
puts "  Synthesis time:   ${synth_elapsed}s"

if {![string match "*Complete*" $synth_status]} {
    puts "CRITICAL: SYNTHESIS FAILED: $synth_status"
    close_project
    exit 1
}

open_run synth_1
report_timing_summary -file "${report_dir}/01_timing_post_synth.rpt"
report_utilization -file "${report_dir}/01_utilization_post_synth.rpt"

# ===== IMPLEMENTATION (strict native DRC & dedicated MRCC routing) =====
set impl_start [clock seconds]

opt_design -directive Explore
place_design -directive ExtraNetDelay_high
phys_opt_design -directive AggressiveExplore
route_design -directive AggressiveExplore
phys_opt_design -directive AggressiveExplore
phys_opt_design -directive AggressiveExplore

set impl_elapsed [expr {[clock seconds] - $impl_start}]
puts "  Implementation time: ${impl_elapsed}s"

# ===== REPORTS & PRE-BITSTREAM PRODUCTION GATE =====
report_timing_summary -file "${report_dir}/02_timing_summary.rpt"
report_utilization -file "${report_dir}/04_utilization.rpt"
report_drc -file "${report_dir}/06_drc.rpt"
report_io -file "${report_dir}/07_io.rpt"

# Enforce zero-waiver port/clock checks, native DRC check, and post-route slack checks
source $evidence_gate_tcl
plfm_require_production_checks
if {[file exists $pre_bit_gate_tcl]} {
    source $pre_bit_gate_tcl
    plfm_require_post_route_checks
}
if {[file exists $local_gate_tcl]} {
    source $local_gate_tcl
    plfm_require_production_checks
}

# ===== BITSTREAM =====
set bit_start [clock seconds]
set dst_bit [file join $bit_dir "radar_system_top_50t.bit"]
write_bitstream -force $dst_bit
set bit_elapsed [expr {[clock seconds] - $bit_start}]
if {[file exists $dst_bit]} {
    puts "  Bitstream: $dst_bit ([expr {[file size $dst_bit] / 1024}] KB)"
} else {
    error "CRITICAL: Bitstream not generated at $dst_bit"
}

puts "================================================================"
puts "  XC7A50T Zero-Waiver Build Complete"
puts "  Synth:  ${synth_elapsed}s"
puts "  Impl:   ${impl_elapsed}s"
puts "  Bit:    ${bit_elapsed}s"
set wns_val "N/A"
set whs_val "N/A"
catch {set wns_val [get_property STATS.WNS [current_design]]}
catch {set whs_val [get_property STATS.WHS [current_design]]}
puts "  WNS:    $wns_val ns"
puts "  WHS:    $whs_val ns"
puts "================================================================"

close_project
exit 0
