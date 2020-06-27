VERILOG_TOP=top.sv
CONSTRAINTS_FILE=constraints.lpf
FORMAL_FILE=formal.sby

REMOTE_MACHINE=anish@anish-MBP.local

YOSYS_FLAGS=
NEXTPNR_FLAGS=
ECPPACK_FLAGS=--compress
TARGET=

COCOTB_SIM=verilator

JSON_FILE=build/synthesis.json
CONFIG_FILE=build/pnr_out.config
BITSTREAM_FILE=build/bitstream.bit

VERILOG_SOURCES=$(wildcard *.v) $(wildcard *.sv) $(wildcard **/*.v) $(wildcard **/*.sv)
PYTHON_SOURCES=$(wildcard *.py) $(wildcard **/*.py)

###############################################
# ULX3S Synthesis, P&R, bitstream
###############################################

# Run synthesis
.PHONY: yosys
yosys: $(JSON_FILE)
$(JSON_FILE): $(VERILOG_SOURCES)
	mkdir -p build
	yosys $(YOSYS_FLAGS) -p 'synth_ecp5 -json $(JSON_FILE)' $(VERILOG_TOP) > build/yosys.log

# Run place-and-route
.PHONY: nextpnr
nextpnr: $(CONFIG_FILE)
$(CONFIG_FILE): $(JSON_FILE) $(CONSTRINTS_FILE)
	nextpnr-ecp5 $(NEXTPNR_FLAGS) --85k --json $(JSON_FILE) --lpf $(CONSTRAINTS_FILE) --textcfg $(CONFIG_FILE) 2> build/nextpnr.log

# Create binary bitstream
.PHONY: ecppack
ecppack: $(BITSTREAM_FILE)
$(BITSTREAM_FILE): $(CONFIG_FILE)
	ecppack $(ECPPACK_FLAGS) $(CONFIG_FILE) $(BITSTREAM_FILE)


###############################################
# ULX3S Flashing
###############################################

# Program the FPGA from the binary bitstream
.PHONY: prog
prog: $(BITSTREAM_FILE)
	ujprog $(BITSTREAM_FILE)

.PHONY: prog-remote
prog-remote: $(BITSTREAM_FILE)
	cat $(BITSTREAM_FILE) | ssh $(REMOTE_MACHINE) 'fujprog'

# Reset the FPGA and clear the config SRAM
.PHONY: reset
reset:
	@echo -e "STATE IDLE;\nSTATE RESET;\nSTATE IDLE;\n\nSIR 8 TDI (C6);\nSDR 8 TDI (00);\nRUNTEST IDLE 2 TCK;\n\nSIR 8 TDI (0e);\nSDR 8 TDI (01);\nRUNTEST IDLE 32 TCK 1.00E-01 SEC;\n" > /tmp/clear-ulx3s.svf;
	ujprog /tmp/clear-ulx3s.svf

.PHONY: reset-remote
reset-remote:
	@ssh $(REMOTE_MACHINE) 'echo -e "STATE IDLE;\nSTATE RESET;\nSTATE IDLE;\n\nSIR 8 TDI (C6);\nSDR 8 TDI (00);\nRUNTEST IDLE 2 TCK;\n\nSIR 8 TDI (0e);\nSDR 8 TDI (01);\nRUNTEST IDLE 32 TCK 1.00E-01 SEC;\n" > /tmp/clear-ulx3s.svf && fujprog /tmp/clear-ulx3s.svf'


###############################################
# Verilator Test-Running
###############################################

.PHONY: test
test: $(VERILOG_SOURCES) $(PYTHON_SOURCES)
	-rm -r sim_build/
	SIM=$(COCOTB_SIM) COCOTB_REDUCED_LOG_FMT=1 VERILATOR_TRACE=1 python3 test.py $(TARGET)

###############################################
# Formal Verification
###############################################

.PHONY: formal
formal: $(VERILOG_SOURCES) $(FORMAL_FILE)
	sby -f $(FORMAL_FILE) $(TARGET)

###############################################
# Misc utilities
###############################################

.PHONY: clean
clean:
	-rm -r build/
	-rm -r sim_build/
	-rm -r __pycache__/
	-rm -r formal/
	-rm -r formal_*/
