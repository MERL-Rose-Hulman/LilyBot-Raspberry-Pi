#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Grove LCD RGB Backlight driver (Raspberry Pi + Grove Pi Hat)
- Text controller: HD44780-compatible @ 0x3E
- Backlight (auto-detect):
    * V5: SGM31323 @ 0x30
    * V4: PCA963x  @ 0x60..0x67
If no backlight chip found, degrade to text-only safely.

Usage:
    python3 grove_rgb_lcd.py
"""

from time import sleep
from typing import Optional

try:
    from smbus2 import SMBus
except ImportError:
    from smbus import SMBus


# --------------------- LCD (text) constants ---------------------
LCD_ADDR = 0x3E
LCD_CMD  = 0x80
LCD_DATA = 0x40

CMD_CLEAR_DISPLAY   = 0x01
CMD_RETURN_HOME     = 0x02
CMD_ENTRY_MODE_SET  = 0x04
CMD_DISPLAY_CONTROL = 0x08
CMD_FUNCTION_SET    = 0x20
CMD_SET_DDRAM_ADDR  = 0x80

ENTRY_LEFT   = 0x02
DISPLAY_ON   = 0x04
CURSOR_ON    = 0x02
BLINK_ON     = 0x01

FUNC_2LINE = 0x08
FUNC_5x8   = 0x00

ROW_OFFSETS = [0x00, 0x40, 0x14, 0x54]  # 16x2/20x4 常见排布


# --------------------- Backlight chips --------------------------
# V4: PCA963x（Seeed早期版本）——地址 0x60..0x67
PCA_ADDRS = list(range(0x60, 0x68))
PCA_MODE1, PCA_MODE2, PCA_LEDOUT = 0x00, 0x01, 0x08
PCA_BLUE, PCA_GREEN, PCA_RED = 0x02, 0x03, 0x04  # 注意顺序：B,G,R

# V5: SGM31323（Seeed V5 版本）——固定地址 0x30
SGM_ADDR = 0x30
SGM_REG0 = 0x00  # 设备状态/睡眠（默认即可）
SGM_REG4 = 0x04  # 通道路由/开关（设为常亮）
SGM_REG6 = 0x06  # CH1（映射 R）
SGM_REG7 = 0x07  # CH2（映射 G）
SGM_REG8 = 0x08  # CH3（映射 B）


def _i2c_probe(bus: SMBus, addr: int, reg: int = 0x00) -> bool:
    try:
        bus.read_byte_data(addr, reg)
        return True
    except OSError:
        return False


class _Backlight:
    def set_rgb(self, r: int, g: int, b: int) -> None: ...
    def close(self) -> None: ...


class _BacklightPCA963x(_Backlight):
    def __init__(self, bus: SMBus, addr: int):
        self.bus, self.addr = bus, addr
        # 正常模式、推挽输出、3通道PWM
        bus.write_byte_data(addr, PCA_MODE1, 0x00)
        bus.write_byte_data(addr, PCA_MODE2, 0x20)
        bus.write_byte_data(addr, PCA_LEDOUT, 0xAA)
        self.set_rgb(255, 255, 255)

    def set_rgb(self, r: int, g: int, b: int) -> None:
        r = 0 if r < 0 else 255 if r > 255 else r
        g = 0 if g < 0 else 255 if g > 255 else g
        b = 0 if b < 0 else 255 if b > 255 else b
        self.bus.write_byte_data(self.addr, PCA_RED,   r)
        self.bus.write_byte_data(self.addr, PCA_GREEN, g)
        self.bus.write_byte_data(self.addr, PCA_BLUE,  b)

    def close(self) -> None:
        self.set_rgb(0, 0, 0)


class _BacklightSGM31323(_Backlight):
    def __init__(self, bus: SMBus, addr: int = SGM_ADDR):
        self.bus, self.addr = bus, addr
        # 通道常亮（不开启渐变/路由），三通道全部启用
        # 0x3F: D1/D2/D3 enable + 常亮；其余位保持默认
        self.bus.write_byte_data(addr, SGM_REG4, 0x3F)
        self.set_rgb(255, 255, 255)

    def set_rgb(self, r: int, g: int, b: int) -> None:
        r = 0 if r < 0 else 255 if r > 255 else r
        g = 0 if g < 0 else 255 if g > 255 else g
        b = 0 if b < 0 else 255 if b > 255 else b
        # 直接写三通道电流/亮度寄存器
        self.bus.write_byte_data(self.addr, SGM_REG6, r)  # R
        self.bus.write_byte_data(self.addr, SGM_REG7, g)  # G
        self.bus.write_byte_data(self.addr, SGM_REG8, b)  # B

    def close(self) -> None:
        self.set_rgb(0, 0, 0)


# --------------------- Main LCD class ---------------------------
class GroveRGBLCD:
    def __init__(
        self,
        bus: int = 1,
        cols: int = 16,
        rows: int = 2,
        text_only: bool = False,
        rgb_addr: Optional[int] = None,
        i2c: Optional[SMBus] = None,
    ):
        """
        text_only=True    -> 禁用背光访问（只用文字）
        rgb_addr=<int>    -> 强制使用该地址作为背光（跳过自动识别）
        rgb_addr=None     -> 先探测 0x30(V5)，再扫 0x60..0x67(V4)，否则降级
        i2c=<SMBus>       -> 使用外部初始化好的 I2C 总线对象（不自动关闭）
        """
        if i2c is None:
            self.bus = SMBus(bus)
            self._owns_bus = True
        else:
            self.bus = i2c
            self._owns_bus = False
        self.cols, self.rows = cols, rows
        self._bl: Optional[_Backlight] = None

        # 初始化文字 LCD
        self._init_lcd()

        # 初始化背光（可选）
        if not text_only:
            self._init_backlight(rgb_addr)

    # ---------- LCD low-level ----------
    def _cmd(self, c: int) -> None:
        self.bus.write_byte_data(LCD_ADDR, LCD_CMD, c)

    def _dat(self, d: int) -> None:
        self.bus.write_byte_data(LCD_ADDR, LCD_DATA, d & 0xFF)

    def _init_lcd(self) -> None:
        sleep(0.05)
        self._cmd(CMD_FUNCTION_SET | FUNC_2LINE | FUNC_5x8)
        self._cmd(CMD_DISPLAY_CONTROL | DISPLAY_ON)
        self.clear()
        self._cmd(CMD_ENTRY_MODE_SET | ENTRY_LEFT)
        sleep(0.002)

    # ---------- Backlight detect/init ----------
    def _init_backlight(self, rgb_addr: Optional[int]) -> None:
        # 优先：V5 固定地址 0x30
        if rgb_addr is None:
            if _i2c_probe(self.bus, SGM_ADDR, SGM_REG0):
                try:
                    self._bl = _BacklightSGM31323(self.bus, SGM_ADDR)
                    return
                except OSError:
                    self._bl = None
            # 其次：扫 V4 0x60..0x67
            for cand in PCA_ADDRS:
                if _i2c_probe(self.bus, cand, PCA_MODE1):
                    try:
                        self._bl = _BacklightPCA963x(self.bus, cand)
                        return
                    except OSError:
                        continue
            self._bl = None  # 找不到，降级
        else:
            # 强制地址：先尝试按 V5 再按 V4
            try:
                if _i2c_probe(self.bus, rgb_addr, SGM_REG0):
                    self._bl = _BacklightSGM31323(self.bus, rgb_addr)
                    return
            except OSError:
                pass
            try:
                if _i2c_probe(self.bus, rgb_addr, PCA_MODE1):
                    self._bl = _BacklightPCA963x(self.bus, rgb_addr)
                    return
            except OSError:
                pass
            self._bl = None  # 强制地址但不可用 → 降级

    # ---------- Text API ----------
    def clear(self) -> None:
        self._cmd(CMD_CLEAR_DISPLAY)
        sleep(0.002)

    def home(self) -> None:
        self._cmd(CMD_RETURN_HOME)
        sleep(0.002)

    def set_cursor(self, col: int, row: int) -> None:
        row = max(0, min(self.rows - 1, row))
        base = ROW_OFFSETS[row if row < len(ROW_OFFSETS) else 0]
        self._cmd(CMD_SET_DDRAM_ADDR | (base + max(0, min(self.cols - 1, col))))

    def write(self, s: str) -> None:
        col, row = 0, 0
        for ch in s:
            if ch == '\n':
                row = min(self.rows - 1, row + 1)
                col = 0
                self.set_cursor(0, row)
                continue
            self._dat(ord(ch))
            col += 1
            if col >= self.cols and row + 1 < self.rows:
                row += 1
                col = 0
                self.set_cursor(0, row)

    def print_line(self, s: str, row: int = 0, align: str = "left") -> None:
        s = s[:self.cols]
        if align == "center":
            pad = max(0, (self.cols - len(s)) // 2)
            s = " " * pad + s
        elif align == "right":
            pad = max(0, self.cols - len(s))
            s = " " * (pad - len(s)) + s
        self.set_cursor(0, row)
        self.write(s.ljust(self.cols))

    def display(self, on: bool = True, cursor: bool = False, blink: bool = False) -> None:
        flags = (DISPLAY_ON if on else 0) | (CURSOR_ON if cursor else 0) | (BLINK_ON if blink else 0)
        self._cmd(CMD_DISPLAY_CONTROL | flags)

    # ---------- Backlight API ----------
    def set_rgb(self, r: int, g: int, b: int) -> None:
        if not self._bl:
            return
        try:
            self._bl.set_rgb(r, g, b)
        except OSError:
            # 运行中掉线，静默降级
            self._bl = None

    def set_color(self, name: str) -> None:
        presets = {
            "white":  (255, 255, 255),
            "red":    (255, 0, 0),
            "green":  (0, 255, 0),
            "blue":   (0, 0, 255),
            "yellow": (255, 255, 0),
            "cyan":   (0, 255, 255),
            "magenta":(255, 0, 255),
            "orange": (255, 128, 0),
            "purple": (128, 0, 255),
            "pink":   (255, 64, 128),
            "off":    (0, 0, 0),
        }
        self.set_rgb(*presets.get(name.lower(), presets["white"]))

    # ---------- Cleanup ----------
    def close(self) -> None:
        try:
            if self._bl:
                self._bl.close()
        finally:
            if getattr(self, "_owns_bus", False):
                self.bus.close()


# --------------------- Demo ---------------------
if __name__ == "__main__":
    lcd = GroveRGBLCD(cols=16, rows=2)  # 自动识别 V5(0x30)/V4(0x60-0x67)/仅文字
    try:
        lcd.clear()
        lcd.print_line("Grove LCD RGB", 0, "center")
        lcd.print_line("Auto-detect BL", 1, "center")
        sleep(1.2)

        # 演示变色（若无背光芯片，下面调用会被静默忽略）
        for c in ["cyan", "magenta", "yellow", "white", "off"]:
            lcd.set_color(c)
            lcd.print_line(f"Color: {c:>7}", 1, "center")
            sleep(0.6)

        # 游标/闪烁演示（与背光无关）
        lcd.display(on=True, cursor=True, blink=True)
        lcd.set_cursor(0, 1)
        lcd.write("Typing...")
        sleep(1.2)
        lcd.display(on=True, cursor=False, blink=False)

        # 换行演示
        lcd.clear()
        lcd.write("Line1\nLine2 via \\n")
        sleep(1.2)
    finally:
        lcd.close()
