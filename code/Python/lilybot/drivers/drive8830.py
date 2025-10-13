#!/usr/bin/env python3
"""Grove Mini I2C Motor Driver (DRV8830) helper functions and CLI."""

import argparse
import sys
import time
from typing import Optional

try:
    from smbus2 import SMBus
except ImportError:  # pragma: no cover - fallback when smbus2 is unavailable
    try:
        from smbus import SMBus  # type: ignore[assignment]
    except ImportError:  # pragma: no cover - development environments without smbus
        SMBus = None  # type: ignore[assignment]

CONTROL_REG = 0x00
FAULT_REG = 0x01

_MODE_STANDBY = 0x00
_MODE_FORWARD = 0x01
_MODE_REVERSE = 0x02
_MODE_BRAKE = 0x03

DEFAULT_ADDRESS = 0x60


def _clamp(value: int, lo: int, hi: int) -> int:
    return lo if value < lo else hi if value > hi else value


class DRV8830:
    """Simple wrapper around the DRV8830 single-channel motor driver."""

    def __init__(self, address: int = DEFAULT_ADDRESS, *, bus: int = 1, i2c: Optional[SMBus] = None):
        if SMBus is None and i2c is None:
            raise RuntimeError(
                "SMBus library not available. Install 'smbus2' or run on Raspberry Pi."
            )
        self.address = address
        if i2c is None:
            self.bus = SMBus(bus)
            self._owns_bus = True
        else:
            self.bus = i2c
            self._owns_bus = False
        self._last_command = 0

    def _write_control(self, magnitude: int, mode: int) -> None:
        magnitude = _clamp(magnitude, 0, 63)
        mode &= 0x03
        value = (magnitude << 2) | mode
        self.bus.write_byte_data(self.address, CONTROL_REG, value)
        self._last_command = value

    def set_speed(self, speed: int) -> None:
        speed = _clamp(int(speed), -100, 100)
        if speed == 0:
            self.standby()
            return
        magnitude = max(1, round(abs(speed) * 63 / 100))
        mode = _MODE_FORWARD if speed > 0 else _MODE_REVERSE
        self._write_control(magnitude, mode)

    def stop(self) -> None:
        self.standby()

    def standby(self) -> None:
        self._write_control(0, _MODE_STANDBY)

    def brake(self) -> None:
        self._write_control(0, _MODE_BRAKE)

    def read_fault(self) -> int:
        """Return the raw fault register value (0 => normal)."""
        return self.bus.read_byte_data(self.address, FAULT_REG)

    def clear_fault(self) -> None:
        """Clear the fault register by writing 0 to the control register."""
        self._write_control(0, _MODE_STANDBY)

    def close(self) -> None:
        if getattr(self, "_owns_bus", False):
            self.bus.close()

    def __enter__(self):  # pragma: no cover - convenience
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - convenience
        self.close()


def get_driver(*, bus: int = 1, address: int = DEFAULT_ADDRESS, i2c: Optional[SMBus] = None) -> DRV8830:
    """Create a DRV8830 instance; callers may reuse the returned driver."""
    return DRV8830(address=address, bus=bus, i2c=i2c)


def run_motor(speed: int, *, driver: Optional[DRV8830] = None, bus: int = 1, address: int = DEFAULT_ADDRESS,
              i2c: Optional[SMBus] = None) -> DRV8830:
    """Run the motor at the specified speed (-100..100). Returns the driver used."""
    drv = driver or get_driver(bus=bus, address=address, i2c=i2c)
    drv.set_speed(speed)
    return drv


def stop_motor(*, driver: Optional[DRV8830] = None, bus: int = 1, address: int = DEFAULT_ADDRESS,
               i2c: Optional[SMBus] = None) -> DRV8830:
    """Stop (coast) the motor. Returns the driver used."""
    drv = driver or get_driver(bus=bus, address=address, i2c=i2c)
    drv.stop()
    return drv


def brake_motor(*, driver: Optional[DRV8830] = None, bus: int = 1, address: int = DEFAULT_ADDRESS,
                i2c: Optional[SMBus] = None) -> DRV8830:
    """Apply an electronic brake. Returns the driver used."""
    drv = driver or get_driver(bus=bus, address=address, i2c=i2c)
    drv.brake()
    return drv


def standby_motor(*, driver: Optional[DRV8830] = None, bus: int = 1, address: int = DEFAULT_ADDRESS,
                  i2c: Optional[SMBus] = None) -> DRV8830:
    """Put the driver into standby. Returns the driver used."""
    drv = driver or get_driver(bus=bus, address=address, i2c=i2c)
    drv.standby()
    return drv


def _format_fault(value: int) -> str:
    if value == 0:
        return "OK"
    bits = []
    if value & 0x80:
        bits.append("FAULT")
    if value & 0x10:
        bits.append("OT (over-temp)")
    if value & 0x08:
        bits.append("UVLO (undervoltage)")
    if value & 0x04:
        bits.append("OCP (over-current)")
    if value & 0x02:
        bits.append("ILIMIT")
    return ", ".join(bits) if bits else f"0x{value:02X}"


# ----------------------------------- CLI helpers -----------------------------------

def cmd_run(args):
    drv = get_driver(bus=args.bus, address=args.address)
    print(f"[run] speed={args.speed} addr=0x{args.address:02X} bus={args.bus}")
    try:
        drv.set_speed(args.speed)
        if args.duration > 0:
            time.sleep(args.duration)
            {"coast": drv.stop, "brake": drv.brake, "standby": drv.standby}[args.end]()
    finally:
        drv.close()


def cmd_stop(args):
    drv = get_driver(bus=args.bus, address=args.address)
    print(f"[stop] addr=0x{args.address:02X} bus={args.bus}")
    try:
        drv.stop()
    finally:
        drv.close()


def cmd_brake(args):
    drv = get_driver(bus=args.bus, address=args.address)
    print(f"[brake] addr=0x{args.address:02X} bus={args.bus}")
    try:
        drv.brake()
    finally:
        drv.close()


def cmd_standby(args):
    drv = get_driver(bus=args.bus, address=args.address)
    print(f"[standby] addr=0x{args.address:02X} bus={args.bus}")
    try:
        drv.standby()
    finally:
        drv.close()


def cmd_fault(args):
    drv = get_driver(bus=args.bus, address=args.address)
    try:
        status = drv.read_fault()
        print(f"[fault] 0x{status:02X} -> {_format_fault(status)}")
    finally:
        drv.close()


def cmd_clear(args):
    drv = get_driver(bus=args.bus, address=args.address)
    try:
        drv.clear_fault()
        print("[clear] fault register cleared")
    finally:
        drv.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CLI for Grove Mini I2C Motor Driver (DRV8830)")
    p.add_argument("--bus", type=int, default=1, help="I2C bus number (default 1)")
    p.add_argument("--address", type=lambda x: int(x, 0), default=DEFAULT_ADDRESS,
                   help="I2C address in hex (default 0x60)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run", help="Run the motor at a given speed")
    s.add_argument("speed", type=int, help="Speed -100..100 (sign controls direction)")
    s.add_argument("--duration", type=float, default=0.0, help="Optional time in seconds to hold speed")
    s.add_argument("--end", choices=["coast", "brake", "standby"], default="coast",
                   help="Action after --duration elapses")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("stop", help="Coast/stop the motor")
    s.set_defaults(func=cmd_stop)

    s = sub.add_parser("brake", help="Apply brake")
    s.set_defaults(func=cmd_brake)

    s = sub.add_parser("standby", help="Enter standby mode")
    s.set_defaults(func=cmd_standby)

    s = sub.add_parser("fault", help="Read fault register")
    s.set_defaults(func=cmd_fault)

    s = sub.add_parser("clear", help="Clear fault register")
    s.set_defaults(func=cmd_clear)

    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n[abort] Ctrl-C")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
