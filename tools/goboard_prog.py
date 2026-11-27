"""Programa la flash SPI de la Go Board con el driver FTDI de Windows (D2XX).

Hace lo mismo que `iceprog` (MPSSE en la interfaz A del FT2232H), pero a traves de
ftd2xx.dll, que viene con el driver FTDIBUS. Asi no hace falta cambiar el driver
con Zadig.

Uso:
  python tools/goboard_prog.py --id              lee la firma de la flash (no escribe nada)
  python tools/goboard_prog.py archivo.bin       borra, programa, verifica y reinicia la FPGA
"""
import ctypes
import sys
import time

FT_OK = 0
d2xx = ctypes.WinDLL("ftd2xx.dll")

# Pines del puerto ADBUS (mismo mapeo que iceprog)
CS = 0x10       # ADBUS4: chip select de la flash
CDONE = 0x40    # ADBUS6: la FPGA termino de configurarse
CRESET = 0x80   # ADBUS7: reset de la FPGA (activo en bajo)
DIR = 0x93      # salidas: SCK, MOSI, CS, CRESET


def check(st, what):
    if st != FT_OK:
        raise RuntimeError(f"{what} fallo (FT_STATUS={st})")


class Mpsse:
    def __init__(self):
        n = ctypes.c_ulong()
        check(d2xx.FT_CreateDeviceInfoList(ctypes.byref(n)), "FT_CreateDeviceInfoList")
        idx = None
        for i in range(n.value):
            desc = ctypes.create_string_buffer(64)
            serial = ctypes.create_string_buffer(16)
            flags, typ, dev_id, loc = (ctypes.c_ulong() for _ in range(4))
            h = ctypes.c_void_p()
            d2xx.FT_GetDeviceInfoDetail(i, ctypes.byref(flags), ctypes.byref(typ),
                                        ctypes.byref(dev_id), ctypes.byref(loc),
                                        serial, desc, ctypes.byref(h))
            if desc.value.endswith(b" A") and dev_id.value == 0x04036010:
                idx = i
                break
        if idx is None:
            raise RuntimeError("no encontre la interfaz A del FT2232H (Go Board)")
        self.h = ctypes.c_void_p()
        check(d2xx.FT_Open(idx, ctypes.byref(self.h)), "FT_Open")
        check(d2xx.FT_ResetDevice(self.h), "FT_ResetDevice")
        check(d2xx.FT_SetUSBParameters(self.h, 65536, 65536), "FT_SetUSBParameters")
        check(d2xx.FT_SetLatencyTimer(self.h, 1), "FT_SetLatencyTimer")
        check(d2xx.FT_SetBitMode(self.h, 0x00, 0x00), "FT_SetBitMode reset")
        check(d2xx.FT_SetBitMode(self.h, 0x00, 0x02), "FT_SetBitMode MPSSE")
        time.sleep(0.05)
        d2xx.FT_Purge(self.h, 3)
        # Reloj: 60 MHz / 5 = 12 MHz base, divisor 0 -> 6 MHz (igual que iceprog)
        self.write(bytes([0x8B, 0x86, 0x00, 0x00]))

    def write(self, data):
        done = ctypes.c_ulong()
        check(d2xx.FT_Write(self.h, data, len(data), ctypes.byref(done)), "FT_Write")
        if done.value != len(data):
            raise RuntimeError("FT_Write incompleto")

    def read(self, n):
        buf = ctypes.create_string_buffer(n)
        got = 0
        out = b""
        t0 = time.time()
        while got < n:
            q = ctypes.c_ulong()
            d2xx.FT_GetQueueStatus(self.h, ctypes.byref(q))
            if q.value:
                k = min(q.value, n - got)
                r = ctypes.c_ulong()
                check(d2xx.FT_Read(self.h, buf, k, ctypes.byref(r)), "FT_Read")
                out += buf.raw[:r.value]
                got += r.value
            elif time.time() - t0 > 2:
                raise RuntimeError("timeout leyendo del FTDI")
        return out

    def gpio(self, cs, creset):
        val = (CS if cs else 0) | (CRESET if creset else 0)
        self.write(bytes([0x80, val, DIR]))

    def cdone(self):
        self.write(bytes([0x81, 0x87]))
        return bool(self.read(1)[0] & CDONE)

    def xfer(self, data):
        """Transfiere `data` por SPI (modo 0, MSB primero) con CS bajo y devuelve lo leido."""
        out = b""
        for i in range(0, len(data), 4096):
            chunk = data[i:i + 4096]
            n = len(chunk) - 1
            self.write(bytes([0x31, n & 0xFF, n >> 8]) + chunk + b"\x87")
            out += self.read(len(chunk))
        return out

    def cmd(self, data):
        self.gpio(cs=0, creset=0)
        r = self.xfer(bytes(data))
        self.gpio(cs=1, creset=0)
        return r

    def close(self):
        d2xx.FT_SetBitMode(self.h, 0x00, 0x00)
        d2xx.FT_Close(self.h)


def wait_busy(m):
    while m.cmd([0x05, 0x00])[1] & 0x01:
        time.sleep(0.001)


def main():
    m = Mpsse()
    try:
        m.gpio(cs=1, creset=0)          # FPGA en reset: suelta el bus SPI
        time.sleep(0.1)
        m.cmd([0xFF] * 8)               # sale de modos raros (QPI/continuo)
        # 0xAB despierta la flash y devuelve su firma tras 3 bytes de relleno.
        # La de la Go Board (M25P10, firma 0x10) no implementa 0x9F (JEDEC ID).
        sig = m.cmd([0xAB, 0, 0, 0, 0])[4]
        print(f"firma de la flash: {sig:#04x}")
        if sig in (0x00, 0xFF):
            raise RuntimeError("la flash no responde")

        if sys.argv[1] != "--id":
            img = open(sys.argv[1], "rb").read()
            # Sectores de 32 KB (M25P10). En una flash de 64 KB por sector,
            # borrar en 0 y en 0x8000 borra el mismo sector dos veces: inofensivo.
            nsect = (len(img) + 0x7FFF) // 0x8000
            print(f"{len(img)} bytes, borrando {nsect} sector(es)...")
            for s in range(nsect):
                a = s * 0x8000
                m.cmd([0x06])
                m.cmd([0xD8, a >> 16, (a >> 8) & 0xFF, 0])
                wait_busy(m)
            print("programando...")
            for a in range(0, len(img), 256):
                page = img[a:a + 256]
                m.cmd([0x06])
                m.cmd(bytes([0x02, a >> 16, (a >> 8) & 0xFF, a & 0xFF]) + page)
                wait_busy(m)
            print("verificando...")
            back = m.cmd(bytes([0x03, 0, 0, 0]) + bytes(len(img)))[4:]
            if back != img:
                bad = next(i for i in range(len(img)) if back[i] != img[i])
                raise RuntimeError(f"verificacion fallo en el byte {bad:#x}")
            print("VERIFY OK")

        m.cmd([0xB9])                   # flash en bajo consumo
        m.gpio(cs=1, creset=1)          # suelta el reset: la FPGA lee la flash
        time.sleep(0.25)
        print("CDONE:", "alto (FPGA configurada)" if m.cdone() else "bajo")
    finally:
        m.close()


if __name__ == "__main__":
    main()
