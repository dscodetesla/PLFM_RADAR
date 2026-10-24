# Read-only native device/pin inventory. Does not load or validate radar RTL/CAD.
# vivado -mode batch -nojournal -nolog -source scripts/50t/probe_50t.tcl
puts "PLFM_VIVADO_VERSION [version -short]"
set target xc7a50tftg256-2
set matches [get_parts -quiet $target]
puts "PLFM_TARGET_MATCH [llength $matches] $matches"
if {[llength $matches] != 1} {error "Missing target device support: $target"}
create_project -in_memory -part $target
link_design -part $target
foreach pin {C13 D13 C4 D4 E12 T5} {
    set object [get_package_pins $pin]
    puts "PLFM_PIN $pin [get_property PIN_FUNC $object] BANK=[get_property BANK $object]"
}
puts PLFM_PIN_PREFLIGHT_COMPLETE
close_project
exit 0
