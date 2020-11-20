from migen import *

from litex.soc.integration.soc_core import *
from litex.soc.integration.builder import *
from litex.soc.cores.uart import RS232PHY, UART
from litex.soc.cores.gpio import GPIOIn, GPIOOut
from litex.soc.cores import spi_flash

from litex.soc.interconnect import csr, csr_bus
from litex.soc.interconnect import wishbone as wb

from util import *
from wishbone_debug_bus import *
from wishbone_uart import *
from cpu import *
from jtag import *

class SoC(GenericSoC):
    def csr_address_map(self, name, memory):
        return {
            "leds": 0x00,
            "btns": 0x10,
            "cpu_disable": 0x20,
            "flash0": 0x100
        }[name]

    def wb_address_map(self, name):
        # Format: (check_fn, translate_fn)
        return {
            "iram": (lambda x: (x >= 0x1000_0000) & (x < 0x2000_0000), lambda x: (x - 0x1000_0000) >> 2),
            "dram": (lambda x: (x >= 0x4000_0000) & (x < 0x5000_0000), lambda x: (x - 0x4000_0000) >> 2),

            "csr": (lambda x: (x >= 0x8000_0000) & (x < 0x8000_1000), lambda x: x - 0x8000_0000),
            "uart": (lambda x: (x >= 0x8000_1000) & (x < 0x8000_2000), lambda x: x - 0x8000_1000),
            "flash0": (lambda x: (x >= 0x9000_0000) & (x < 0x9F00_0000), lambda x: x - 0x9000_0000)
        }[name]

    def __init__(self, platform, sys_clk_freq=25e6):
        sys_clk_freq = int(sys_clk_freq)
        super().__init__(
            platform, sys_clk_freq,
            data_width=32, adr_width=32,
            csr_delay_register=True,
            wishbone_delay_register=False,
            crossbar=True
        )

        self.submodules.crg = CRG(platform.request("sys_clk"), platform.request("sys_rst"))

        #led = platform.request("led")
        #self.add_csr_periph(GPIOOut(led), "leds")

        btn = platform.request("btn")
        self.add_csr_periph(GPIOIn(btn), "btns")
        #0x100000B7,0x30008093,0xDEADC137,0xEEF10113,0x0020A023,0x12345137,0x67810113,0x0020A223,0xABCDB137,0xBCD10113,0x0020A423,     
        self.add_wb_slave(wb.SRAM(512, init=[0x00000113, 0x40000237, 0x00020213, 0x800001B7, 0x00018193, 0xFFF14113, 0x0021A023, 0x009890B7, 0x68008093, 0xFFF08093, 0x00122023, 0xFE104CE3, 0xFE5FF06F, 0x80000137, 0x00010113, 0x00212023], bus=wb.Interface(data_width=32, adr_width=32)), "iram")
        self.add_wb_slave(wb.SRAM(512, init=[0xDEADBEEF], bus=wb.Interface(data_width=32, adr_width=32)), "dram")

        self.submodules.wbdbgbus = WishboneDebugBus(platform.request("uart0"), sys_clk_freq, baud=115200)
        cycle_counter = CycleCounter(self.wbdbgbus.bus, max=255)
        self.add_wb_master(cycle_counter, "debugbus")
        #self.comb += led.eq(cycle_counter.counter)

        cpu = CPU()
        #self.submodules.instr_convert = instr_convert = WBP2WBC(bus_in=cpu.instr_bus)
        #self.submodules.data_convert = data_convert = WBP2WBC(bus_in=cpu.data_bus)
        #self.add_wb_master(cpu, "cpu_ibus", bus=cpu.instr_bus)
        #self.add_wb_master(None, "cpu_dbus", bus=cpu.data_bus)

        self.add_csr_periph(GPIOOut(cpu.disable), "cpu_disable")

        self.add_wb_slave(spi_flash.SpiFlashDualQuad(platform.request("flash"), dummy=6, div=2, with_bitbang=True, endianness="big"), "flash0")

        jtag_regs = {
            0: 32, # ID
            1: 32, # ID
            2: 32, # ID
            3: 32, # LED
            4: 32  # BTN
        }
        #self.submodules.jtag = JTAGTAP(platform.request("jtag"), jtag_regs, ir_width=10, sync_ffs=2)

        """print(self.jtag.regs)
        self.comb += self.jtag.regs[0].read_data.eq(0xDEADBEEF)
        self.comb += self.jtag.regs[1].read_data.eq(0xDEADBEEF)
        self.comb += self.jtag.regs[2].read_data.eq(0xDEADBEEF)
        self.comb += self.jtag.regs[3].read_data.eq(led)
        self.comb += self.jtag.regs[4].read_data.eq(btn)

        self.sync += If(self.jtag.regs[3].write_valid, led.eq(self.jtag.regs[3].write_data))"""

        #self.add_wb_slave(WishboneUART(platform.request("serial1"), sys_clk_freq, baud=115200, fifo_depth=4, bus=wb.Interface(data_width=8, adr_width=16)), "uart")
        #self.add_csr_periph(UART(phy=RS232PHY(platform.request("serial1"), sys_clk_freq, baudrate=115200), tx_fifo_depth=4, rx_fifo_depth=4, rx_fifo_rx_we=False), "uart")

        self.generate_bus()

    @classmethod
    def get_io(cls):
        if getattr(cls, "io", None) is None:
            cls.io = [
                ("sys_clk", 0, Pins(1)),
                ("sys_rst", 0, Pins(1)),

                ("uart0", 0,
                    Subsignal("tx", Pins(1)),
                    Subsignal("rx", Pins(1)),
                ),

                ("led", 0, Pins(8)),
                ("btn", 0, Pins(6)),

                ("flash", 0,
                    Subsignal("dq", Pins(4)),
                    Subsignal("clk", Pins(1)),
                    Subsignal("cs_n", Pins(1)),
                ),

                ("jtag", 0,
                    Subsignal("tck", Pins(1)),
                    Subsignal("tms", Pins(1)),
                    Subsignal("tdo", Pins(1)),
                    Subsignal("tdi", Pins(1)),
                ),
            ]

        return cls.io

