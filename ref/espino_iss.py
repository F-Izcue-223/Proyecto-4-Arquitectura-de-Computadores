"""Simulador de instrucciones del Espino Core (RV32E) con el modelo de ciclos del RTL.

Sirve para medir trade.s tick a tick (IC, ciclos, CPI) en miles de ticks, que en
iverilog tardarian horas. El modelo de ciclos sale de leer el RTL y se comprueba
contra la simulacion del RTL (sim/tb_trade.v): los dos tienen que dar el mismo
numero de ciclos en cada tick.

Ciclos por instruccion en el Espino (rtl/espino_core):
  - 1 ciclo de espera del banco de registros (BRAM de lectura sincronica) + 1 de
    ejecucion: 2 ciclos para ALU, LUI, AUIPC, store y branch no tomado.
  - load: +1 ciclo (la memoria de datos tambien es sincronica) = 3.
  - branch tomado, JAL, JALR: +1 burbuja (la instruccion ya pedida se descarta) = 3.
  - mul8 (variante ESPINO_MUL8): 2 + una vuelta por bit del multiplicador hasta el
    ultimo 1 (minimo 1), ver rtl/espino_core/espino_mul8.v.
En el core base los shifts se ejecutan como ADD (espino_alu.v los tiene comentados);
con ESPINO_SHIFTER son shifts de verdad, en 2 ciclos.
"""

SPI_BASE, PER_BASE = 0x80010000, 0x80000000
MASK = 0xFFFFFFFF


def sext(x, bits):
    return x - (1 << bits) if x >> (bits - 1) & 1 else x


class Variante:
    def __init__(self, shifter=False, mul8=False):
        self.shifter, self.mul8 = shifter, mul8


class Espino:
    def __init__(self, hexfile, variante=Variante(), words=512):
        self.mem = bytearray(4 * words)
        with open(hexfile) as f:
            for i, line in enumerate(x for x in f.read().split()):
                self.mem[4 * i:4 * i + 4] = int(line, 16).to_bytes(4, 'little')
        self.v = variante
        self.x = [0] * 16
        self.pc = 0
        self.ciclos = 0
        self.ic = 0
        # SPI esclavo
        self.nuevo = 0          # STATUS bit 0
        self.precio = 0
        self.decision = 0       # registro DECISION (tx_hold)
        self.sent = 0           # lo que la maestra ejecuto en la ultima transaccion
        self.escrituras_decision = []
        # perifericos
        self.display, self.leds = 0, 0
        self.ultima_lectura = None   # direccion del ultimo load MMIO, para el corredor
        self.bloqueado = False       # el ultimo paso fue una lectura bloqueante (no conto)
        self.perfil = None           # {pc: ciclos} si se pide perfil
        self.bytes = 0               # bytes leidos y escritos (RAM y MMIO), para el roofline

    # --- memoria y MMIO ---------------------------------------------------
    def load(self, addr, size, signed):
        self.bytes += size
        if addr & 0x80000000:
            self.ultima_lectura = addr
            if addr & 0x10000:                      # SPI
                off = addr & 0xFC
                if off == 0:
                    val = self.nuevo                # cs_active = 0 entre transacciones
                elif off == 4:
                    val, self.nuevo = self.precio, 0
                elif off == 12:                     # NUEVO: {precio nuevo, 0, precio}
                    val, self.nuevo = (self.nuevo << 31) | self.precio, 0
                else:
                    val = 0
            else:                                   # perifericos
                off = addr & 0xFC
                val = self.ciclos if off == 12 else 0
            return val & MASK
        a = addr & (len(self.mem) - 1)
        val = int.from_bytes(self.mem[a:a + size], 'little')
        return (sext(val, 8 * size) & MASK) if signed else val

    def store(self, addr, size, val):
        self.bytes += size
        if addr & 0x80000000:
            off = addr & 0xFC
            if addr & 0x10000:
                if off == 8:
                    self.decision = val & 0xFF
                    self.escrituras_decision.append((self.ciclos, self.decision))
            else:
                if off == 0:
                    self.display = val & 0xFF
                elif off == 4:
                    self.leds = val & 0xF
            return
        a = addr & (len(self.mem) - 1)
        self.mem[a:a + size] = (val & ((1 << (8 * size)) - 1)).to_bytes(size, 'little')

    # --- una instruccion ----------------------------------------------------
    def paso(self):
        w = int.from_bytes(self.mem[self.pc & 0x7FC:(self.pc & 0x7FC) + 4], 'little')
        op, rd, f3 = w & 0x7F, (w >> 7) & 0xF, (w >> 12) & 7
        rs1, rs2, f7 = (w >> 15) & 0xF, (w >> 20) & 0xF, w >> 25
        a, b = self.x[rs1], self.x[rs2]
        imm_i = sext(w >> 20, 12)
        npc = (self.pc + 4) & MASK
        c = 2
        res = None
        if op == 0x37:                                  # LUI
            res = w & 0xFFFFF000
        elif op == 0x17:                                # AUIPC
            res = (self.pc + (w & 0xFFFFF000)) & MASK
        elif op == 0x6F:                                # JAL
            off = sext(((w >> 31) << 20) | (((w >> 12) & 0xFF) << 12) | (((w >> 20) & 1) << 11)
                       | (((w >> 21) & 0x3FF) << 1), 21)
            res, npc, c = npc, (self.pc + off) & MASK, 3
        elif op == 0x67:                                # JALR
            res, npc, c = npc, (a + imm_i) & MASK & ~1, 3
        elif op == 0x63:                                # branches
            off = sext(((w >> 31) << 12) | (((w >> 7) & 1) << 11) | (((w >> 25) & 0x3F) << 5)
                       | (((w >> 8) & 0xF) << 1), 13)
            sa, sb = sext(a, 32), sext(b, 32)
            tomado = {0: a == b, 1: a != b, 4: sa < sb, 5: sa >= sb, 6: a < b, 7: a >= b}[f3]
            if tomado:
                npc, c = (self.pc + off) & MASK, 3
        elif op == 0x03:                                # loads
            size, signed = {0: (1, True), 1: (2, True), 2: (4, False), 4: (1, False), 5: (2, False)}[f3]
            addr = (a + imm_i) & MASK
            if addr == SPI_BASE + 12 and not self.nuevo:
                # lectura bloqueante de NUEVO: el load espera al precio (no avanza el pc).
                # El corredor ve esta lectura como "volvio a esperar" y entrega el precio.
                self.ultima_lectura = addr
                self.bloqueado = True
                return
            res = self.load(addr, size, signed)
            c = 3
        elif op == 0x23:                                # stores
            imm_s = sext(((w >> 25) << 5) | ((w >> 7) & 0x1F), 12)
            self.store((a + imm_s) & MASK, {0: 1, 1: 2, 2: 4}[f3], b)
        elif op in (0x13, 0x33):                        # OP-IMM / OP
            bb = imm_i & MASK if op == 0x13 else b
            sub = op == 0x33 and f7 & 0x20
            sh = bb & 31
            if f3 == 0:
                res = a - bb if sub else a + bb
            elif f3 == 1:
                res = (a << sh) if self.v.shifter else a + bb
            elif f3 == 2:
                res = int(sext(a, 32) < sext(bb, 32))
            elif f3 == 3:
                res = int(a < bb)
            elif f3 == 4:
                res = a ^ bb
            elif f3 == 5:
                if not self.v.shifter:
                    res = a + bb
                elif f7 & 0x20:
                    res = sext(a, 32) >> sh
                else:
                    res = a >> sh
            elif f3 == 6:
                res = a | bb
            else:
                res = a & bb
            res &= MASK
        elif op == 0x0B and self.v.mul8:                # mul8 (custom-0)
            m = b & 0xFF
            res = (a * m) & MASK
            c = 2 + max(1, m.bit_length())
        elif op in (0x0F, 0x73):                        # FENCE, ECALL/EBREAK: no hacen nada
            pass
        else:
            raise RuntimeError(f'instruccion ilegal {w:08x} en pc={self.pc:#x}')
        if res is not None and rd:
            self.x[rd] = res
        if self.perfil is not None:
            self.perfil[self.pc] = self.perfil.get(self.pc, 0) + c
        self.pc = npc
        self.ciclos += c
        self.ic += 1
        return w


def correr(hexfile, precios, variante=Variante(), max_ciclos_tick=10**6, perfil=False):
    """Corre trade.hex sobre la serie. La maestra ideal: cada precio llega en cuanto
    el programa vuelve a esperar, y SENT = DECISION al empezar la transaccion.

    Devuelve (decisiones, medidas por tick). Medidas = (IC, ciclos) desde que el
    programa lee PRICE hasta que vuelve a leer STATUS (el tick completo, contando
    la ultima escritura de DECISION).
    """
    cpu = Espino(hexfile, variante)
    decisiones, medidas = [], []
    for p in precios:
        cpu.sent = cpu.decision                 # la maestra latchea DECISION al bajar CS
        cpu.precio, cpu.nuevo = p, 1
        # correr hasta que lea PRICE (consume el precio)
        while cpu.nuevo:
            cpu.paso()
            if cpu.ciclos > 10**9:
                raise RuntimeError('el programa no lee el precio')
        c0, i0, b0 = cpu.ciclos, cpu.ic, cpu.bytes
        if perfil and cpu.perfil is None and len(medidas) == 1:
            cpu.perfil = {}             # el tick 0 (llenar el buffer) no entra al perfil
        # correr hasta que vuelva a leer STATUS
        cpu.ultima_lectura = None
        while True:
            cpu.paso()
            if cpu.ultima_lectura in (SPI_BASE, SPI_BASE + 12):
                if cpu.bloqueado:
                    # lectura bloqueante: el lw que espera todavia no se conto
                    medidas.append((cpu.ic - i0, cpu.ciclos - c0, cpu.bytes - b0))
                    cpu.bloqueado = False
                else:
                    # no contar el lw de la espera siguiente (STATUS o NUEVO)
                    medidas.append((cpu.ic - i0 - 1, cpu.ciclos - c0 - 3, cpu.bytes - b0 - 4))
                break
            if cpu.ciclos - c0 > max_ciclos_tick:
                raise RuntimeError('tick demasiado largo')
        decisiones.append(cpu.decision)
    return decisiones, medidas, cpu
