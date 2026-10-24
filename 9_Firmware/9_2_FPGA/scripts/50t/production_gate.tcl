# Native post-route checks; not board validation or manufacturing approval.
proc plfm_require_production_checks {} {
    foreach violation [get_drc_violations -quiet] {
        set severity [get_property SEVERITY $violation]
        if {$severity ni {Error {Critical Warning} Warning Info Advisory}} {
            error "Production blocked: unknown DRC severity '$severity'"
        }
        if {$severity in {Error {Critical Warning}}} {
            error "Production blocked by DRC $violation ($severity)"
        }
    }
    foreach delay_type {max min} {
        set paths [get_timing_paths -quiet -delay_type $delay_type -max_paths 1]
        if {[llength $paths] != 1} {
            error "Production blocked: no $delay_type timing path"
        }
        set slack [get_property SLACK [lindex $paths 0]]
        if {![string is double -strict $slack] || $slack < 0 || abs($slack) == Inf} {
            error "Production blocked: $delay_type slack=$slack ns"
        }
    }
    puts "PLFM_POST_ROUTE_GATE_PASS (DRC and timed setup/hold paths only)"
}
