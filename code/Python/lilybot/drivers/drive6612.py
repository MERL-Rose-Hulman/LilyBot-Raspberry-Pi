#!/usr/bin/env python3
"""
Grove I2C Motor Driver (TB6612FNG) – robust CLI for Raspberry Pi
Works with the PyPI package `raspberry-i2c-tb6612fng` across versions.

Examples:
  python3 motor.py test --channel A
  python3 motor.py run B 180 --duration 3 --end brake
  python3 motor.py sweep B --min -255 --max 255 --step 50 --hold 0.2
"""

import argparse, sys, time

# ---------- helpers to cope with API differences across lib versions ----------

def _get(obj, names, default=None):
    """Return the first existing attribute from names on obj, else default."""
    for n in names:
        if hasattr(obj, n):
            return getattr(obj, n)
    return default

def _try_ctor(cls, bus, addr, i2c=None):
    """
    Try multiple constructor signatures until one works.
    Returns (driver, used_signature_str).
    """
    attempts = [
        ((), {}),                # defaults
        ((addr,), {}),           # (address)
        ((), {"i2c_addr": addr}),
        ((), {"address": addr}),
        ((), {"addr": addr}),
    ]

    bus_candidates = []
    if i2c is not None:
        bus_candidates.append(i2c)
    if bus is not None:
        bus_candidates.append(bus)

    for candidate in bus_candidates:
        attempts.extend([
            ((candidate, addr), {}),
            ((), {"bus": candidate, "address": addr}),
            ((), {"bus": candidate, "i2c_addr": addr}),
            ((), {"busnum": candidate, "address": addr}),
            ((), {"i2c_bus": candidate, "i2c_addr": addr}),
            ((), {"i2c_bus_id": candidate, "i2c_addr": addr}),
            ((), {"port": candidate, "address": addr}),
        ])
    last_err = None
    for args, kwargs in attempts:
        try:
            drv = cls(*args, **kwargs)
            return drv, f"{cls.__name__}{args or ''}{(' ' + str(kwargs)) if kwargs else ''}"
        except TypeError as e:
            # wrong keywords/arity → try next
            last_err = e
            continue
        except Exception as e:
            last_err = e
            continue
    raise last_err or RuntimeError("Unable to construct driver (unexpected).")

class _DriverWrapper:
    def __init__(self, bus=1, addr=0x14, *, i2c=None, driver=None, verbose=True):
        # 1) import, but don't mask non-import errors
        try:
            mod = __import__("raspberry_i2c_tb6612fng", fromlist=["*"])
        except Exception as e:
            print("ERROR: Can't import 'raspberry_i2c_tb6612fng'. "
                  "Install inside this venv: pip install raspberry-i2c-tb6612fng", file=sys.stderr)
            raise

        # 2) resolve classes/constants
        self._MotorCls = _get(mod, ["MotorDriverTB6612FNG"])
        if self._MotorCls is None:
            raise ImportError("Package missing MotorDriverTB6612FNG")

        self._Motors = _get(mod, ["TB6612FNGMotors"], default=None)

        # 3) construct driver trying multiple signatures (or reuse provided)
        if driver is None:
            self._drv, used = _try_ctor(self._MotorCls, bus, addr, i2c=i2c)
            if verbose:
                print(f"[driver] created via {used}")
        else:
            self._drv = driver
            if verbose:
                cls_name = driver.__class__.__name__
                print(f"[driver] using provided {cls_name}")

        # 4) resolve channel constants (A/B)
        self._A = self._B = None
        if self._Motors:
            # attempt common enum names
            self._A = _get(self._Motors, ["MOTOR_CHA", "MOTOR_A", "CHA", "A"])
            self._B = _get(self._Motors, ["MOTOR_CHB", "MOTOR_B", "CHB", "B"])
        # fallback to ints if still missing
        if self._A is None: self._A = 0
        if self._B is None: self._B = 1

        # 5) resolve method names
        self._fn_run   = _get(self._drv, ["dc_motor_run"])
        self._fn_stop  = _get(self._drv, ["dc_motor_stop", "dc_motor_coast", "motor_stop", "stop"])
        self._fn_brake = _get(self._drv, ["dc_motor_brake", "dc_motor_break", "motor_brake", "brake"])

        if not callable(self._fn_run):
            raise AttributeError("Driver missing 'dc_motor_run'")

    def _chs(self, s):
        if s.lower() == "both": return ("A","B")
        if s.upper() in ("A","B"): return (s.upper(),)
        raise ValueError("channel must be A, B, or both")

    def _map(self, ch):
        return self._A if ch == "A" else self._B

    def run(self, channel, speed):
        for ch in self._chs(channel):
            self._fn_run(self._map(ch), int(speed))

    def stop(self, channel):
        for ch in self._chs(channel):
            if callable(self._fn_stop):
                self._fn_stop(self._map(ch))
            else:
                # fallback: coast by commanding speed 0
                self._fn_run(self._map(ch), 0)

    def brake(self, channel):
        for ch in self._chs(channel):
            if callable(self._fn_brake):
                self._fn_brake(self._map(ch))
            else:
                # fallback to stop if brake doesn't exist
                self.stop(ch)


class MotorController(_DriverWrapper):
    """Public alias for code that wants to reuse the driver wrapper."""
    pass


def get_controller(*, bus=1, address=0x14, i2c=None, driver=None, verbose=False):
    """Return a MotorController suitable for reuse across calls."""
    return MotorController(bus=bus, addr=address, i2c=i2c, driver=driver, verbose=verbose)


def run_motor(channel, speed, *, controller=None, bus=1, address=0x14, i2c=None, driver=None, verbose=False):
    """Run a channel at the requested speed and return the controller used."""
    ctrl = controller or get_controller(bus=bus, address=address, i2c=i2c, driver=driver, verbose=verbose)
    ctrl.run(channel, speed)
    return ctrl


def stop_motor(channel, *, controller=None, bus=1, address=0x14, i2c=None, driver=None, verbose=False):
    """Coast/stop a channel and return the controller used."""
    ctrl = controller or get_controller(bus=bus, address=address, i2c=i2c, driver=driver, verbose=verbose)
    ctrl.stop(channel)
    return ctrl


def brake_motor(channel, *, controller=None, bus=1, address=0x14, i2c=None, driver=None, verbose=False):
    """Hard brake a channel and return the controller used."""
    ctrl = controller or get_controller(bus=bus, address=address, i2c=i2c, driver=driver, verbose=verbose)
    ctrl.brake(channel)
    return ctrl

# --------------------------------- commands ----------------------------------

def cmd_run(a):
    d = get_controller(bus=a.bus, address=a.address, verbose=True)
    if a.speed == 0:
        d.stop(a.channel); return
    print(f"[run] ch={a.channel} speed={a.speed} bus={a.bus} addr=0x{a.address:02X}")
    d.run(a.channel, a.speed)
    if a.duration > 0:
        time.sleep(a.duration)
        {"leave": lambda: None, "stop": d.stop, "brake": d.brake}[a.end](a.channel)

def cmd_stop(a):
    d = get_controller(bus=a.bus, address=a.address, verbose=True)
    print(f"[stop] ch={a.channel}")
    d.stop(a.channel)

def cmd_brake(a):
    d = get_controller(bus=a.bus, address=a.address, verbose=True)
    print(f"[brake] ch={a.channel}")
    d.brake(a.channel)

def cmd_test(a):
    d = get_controller(bus=a.bus, address=a.address, verbose=True)
    ch, fwd, rev = a.channel, a.speed, -abs(a.speed)
    print(f"[test] ch={ch} fwd={fwd} rev={rev} t={a.time}s")
    d.run(ch, fwd); time.sleep(a.time)
    d.brake(ch);    time.sleep(0.2)
    d.run(ch, rev); time.sleep(a.time)
    d.stop(ch)

def cmd_sweep(a):
    d = get_controller(bus=a.bus, address=a.address, verbose=True)
    def sweep(lo, hi, st):
        s = lo
        while (st > 0 and s <= hi) or (st < 0 and s >= hi):
            print(f"[sweep] {s}")
            d.run(a.channel, s)
            time.sleep(a.hold)
            s += st
    sweep(a.min, a.max, abs(a.step))
    time.sleep(a.hold)
    sweep(a.max, a.min, -abs(a.step))
    d.stop(a.channel)

# ----------------------------------- main ------------------------------------

def main():
    p = argparse.ArgumentParser(description="CLI for Grove I2C Motor Driver (TB6612FNG)")
    p.add_argument("--bus", type=int, default=1, help="I2C bus number (default 1)")
    p.add_argument("--address", type=lambda x: int(x, 0), default=0x14, help="I2C address (e.g., 0x14)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run", help="Run motor at a given speed")
    s.add_argument("channel", choices=["A","B","both"])
    s.add_argument("speed", type=int)
    s.add_argument("--duration", type=float, default=0.0)
    s.add_argument("--end", choices=["leave","stop","brake"], default="stop")
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("stop", help="Coast/stop")
    s.add_argument("channel", choices=["A","B","both"])
    s.set_defaults(func=cmd_stop)

    s = sub.add_parser("brake", help="Hard brake")
    s.add_argument("channel", choices=["A","B","both"])
    s.set_defaults(func=cmd_brake)

    s = sub.add_parser("test", help="Forward+reverse sanity test")
    s.add_argument("--channel", choices=["A","B","both"], default="A")
    s.add_argument("--speed", type=int, default=200)
    s.add_argument("--time", type=float, default=1.5)
    s.set_defaults(func=cmd_test)

    s = sub.add_parser("sweep", help="Sweep speeds for tuning")
    s.add_argument("channel", choices=["A","B","both"])
    s.add_argument("--min", type=int, default=-255)
    s.add_argument("--max", type=int, default=255)
    s.add_argument("--step", type=int, default=25)
    s.add_argument("--hold", type=float, default=0.15)
    s.set_defaults(func=cmd_sweep)

    a = p.parse_args()
    try:
        a.func(a)
    except KeyboardInterrupt:
        print("\n[abort] Ctrl-C")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__":
    main()
