# ==============================================================================
# PLFM_RADAR (AERIS-10N Nexus R0.1) Zero-Waiver Pre-Bitstream Production Gate
# Host: desk-tyan (/home/user/AMDDesignTools/2026.1/Vivado/bin/vivado)
# Target Part: xc7a50tftg256-2
# ==============================================================================

proc plfm_require_production_checks {} {
    puts "INFO: [PLFM_GATE] Enforcing strict zero-waiver production DRC checks..."

    # 1. Enforce Error severity on critical I/O and Bank Voltage DRC rules
    set critical_drcs [list NSTD-1 UCIO-1 BIVC-1 PLIO-9]
    foreach rule $critical_drcs {
        set check_obj [get_drc_checks -quiet $rule]
        if {[llength $check_obj] > 0} {
            set_property SEVERITY {Error} $check_obj
            set_property IS_ENABLED true $check_obj
        }
    }

    # 2. Reject any CLOCK_DEDICATED_ROUTE FALSE overrides on nets
    set cdr_false_nets [get_nets -quiet -filter {CLOCK_DEDICATED_ROUTE == FALSE}]
    if {[llength $cdr_false_nets] > 0} {
        error "ERROR: [PLFM_GATE] Forbidden CLOCK_DEDICATED_ROUTE FALSE detected on nets: $cdr_false_nets"
    }

    # 3. Verify all top-level ports have explicit LOC (PACKAGE_PIN) and IOSTANDARD
    set top_ports [get_ports -quiet *]
    foreach p $top_ports {
        set std [get_property -quiet IOSTANDARD $p]
        set pin [get_property -quiet PACKAGE_PIN $p]
        if {$std eq "" || $std eq "DEFAULT"} {
            error "ERROR: [PLFM_GATE] Violation NSTD-1 on port $p (IOSTANDARD=$std)"
        }
        if {$pin eq ""} {
            error "ERROR: [PLFM_GATE] Violation UCIO-1 on port $p (unconstrained PACKAGE_PIN)"
        }
    }

    puts "INFO: [PLFM_GATE] Pre-bitstream zero-waiver check completed."
}
