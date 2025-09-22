#!/usr/bin/env python3
"""Demo script showing how to drive LilyBot motors and LCD/ultrasonic combo."""

import argparse
import sys
import time
from typing import Callable, List, Optional, Tuple

try:
    from smbus2 import SMBus
except ImportError:  # pragma: no cover - fallback when smbus2 is missing
    from smbus import SMBus  # type: ignore[assignment]

from drive6612 import get_controller
from drive8830 import get_driver
from lcd import GroveRGBLCD
from ultrasonic import GroveUltrasonicRanger


def _clamp_pct(value: float) -> float:
    return -100.0 if value < -100.0 else 100.0 if value > 100.0 else value


class _TB6612Adapter:
    def __init__(self, controller):
        self.controller = controller

    def drive(self, left_pct: float, right_pct: float) -> None:
        left = int(round(_clamp_pct(left_pct) * 255 / 100))
        right = int(round(_clamp_pct(right_pct) * 255 / 100))
        self.controller.run("A", left)
        self.controller.run("B", right)

    def stop(self) -> None:
        self.controller.stop("both")

    def close(self) -> None:  # pragma: no cover - nothing to release explicitly
        pass


class _DRV8830Adapter:
    def __init__(self, left_motor, right_motor):
        self.left = left_motor
        self.right = right_motor

    def drive(self, left_pct: float, right_pct: float) -> None:
        self.left.set_speed(_clamp_pct(left_pct))
        self.right.set_speed(_clamp_pct(right_pct))

    def stop(self) -> None:
        self.left.stop()
        self.right.stop()

    def close(self) -> None:
        self.left.close()
        self.right.close()


class Robot:
    def __init__(
        self,
        *,
        driver: str,
        bus_id: int,
        sonar_pin: int,
        tb6612_addr: int,
        drv8830_left: int,
        drv8830_right: int,
    ) -> None:
        self.bus = SMBus(bus_id)
        self.lcd = GroveRGBLCD(i2c=self.bus)
        self.sonar = GroveUltrasonicRanger(sonar_pin)

        if driver == "tb6612":
            controller = get_controller(bus=bus_id, address=tb6612_addr, i2c=self.bus, verbose=False)
            self.motion = _TB6612Adapter(controller)
        elif driver == "drv8830":
            left = get_driver(bus=bus_id, address=drv8830_left, i2c=self.bus)
            right = get_driver(bus=bus_id, address=drv8830_right, i2c=self.bus)
            self.motion = _DRV8830Adapter(left, right)
        else:
            raise ValueError(f"Unsupported driver '{driver}'")

    # --------------- motion helpers ---------------
    def drive(self, left_pct: float, right_pct: float) -> None:
        self.motion.drive(left_pct, right_pct)

    def stop(self) -> None:
        self.motion.stop()

    def forward(self, speed: float, duration: float) -> None:
        self.drive(speed, speed)
        time.sleep(duration)
        self.stop()

    def backward(self, speed: float, duration: float) -> None:
        self.drive(-speed, -speed)
        time.sleep(duration)
        self.stop()

    def pivot_left(self, speed: float, duration: float) -> None:
        self.drive(-speed, speed)
        time.sleep(duration)
        self.stop()

    def pivot_right(self, speed: float, duration: float) -> None:
        self.drive(speed, -speed)
        time.sleep(duration)
        self.stop()

    def turn_left(self, speed: float, duration: float, inner_scale: float = 0.4) -> None:
        self.drive(speed * inner_scale, speed)
        time.sleep(duration)
        self.stop()

    def turn_right(self, speed: float, duration: float, inner_scale: float = 0.4) -> None:
        self.drive(speed, speed * inner_scale)
        time.sleep(duration)
        self.stop()

    # --------------- sensors / UI ---------------
    def read_distance(self) -> Optional[float]:
        try:
            return float(self.sonar.get_distance())
        except Exception as exc:  # pragma: no cover - hardware error path
            print(f"Ultrasonic read failed: {exc}", file=sys.stderr)
            return None

    def display_distance(self, distance: Optional[float], status: str) -> None:
        if distance is None:
            line1 = "Dist: ----"
        else:
            line1 = f"Dist: {distance:5.1f} cm"
        self.lcd.print_line(line1, row=0)
        self.lcd.print_line(status[:16], row=1)

    def close(self) -> None:
        try:
            self.stop()
        finally:
            try:
                self.lcd.close()
            finally:
                try:
                    self.motion.close()
                finally:
                    self.bus.close()


def _run_demo(robot: Robot, speed: float, duration: float) -> None:
    steps: List[Tuple[str, Callable[[], None]]] = [
        ("Forward", lambda: robot.forward(speed, duration)),
        ("Backward", lambda: robot.backward(speed, duration)),
        ("Pivot Left", lambda: robot.pivot_left(speed, duration)),
        ("Pivot Right", lambda: robot.pivot_right(speed, duration)),
        ("Turn Left", lambda: robot.turn_left(speed, duration)),
        ("Turn Right", lambda: robot.turn_right(speed, duration)),
    ]

    for label, action in steps:
        distance = robot.read_distance()
        robot.display_distance(distance, label)
        action()
        time.sleep(0.5)


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LilyBot movement demo using Grove drivers")
    parser.add_argument("--driver", choices=["tb6612", "drv8830"], default="tb6612",
                        help="Motor driver to use")
    parser.add_argument("--bus", type=int, default=1, help="I2C bus number")
    parser.add_argument("--sonar-pin", type=int, required=True, help="GPIO pin for the ultrasonic ranger")
    parser.add_argument("--tb6612-addr", type=lambda x: int(x, 0), default=0x14,
                        help="I2C address for TB6612 driver (default 0x14)")
    parser.add_argument("--drv8830-left", type=lambda x: int(x, 0), default=0x60,
                        help="Left motor DRV8830 address (default 0x60)")
    parser.add_argument("--drv8830-right", type=lambda x: int(x, 0), default=0x61,
                        help="Right motor DRV8830 address (default 0x61)")
    parser.add_argument("--speed", type=float, default=60.0,
                        help="Base speed percentage (-100..100, default 60)")
    parser.add_argument("--duration", type=float, default=1.2,
                        help="Seconds to hold each motion step")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = _parse_args(argv)
    robot = Robot(
        driver=args.driver,
        bus_id=args.bus,
        sonar_pin=args.sonar_pin,
        tb6612_addr=args.tb6612_addr,
        drv8830_left=args.drv8830_left,
        drv8830_right=args.drv8830_right,
    )

    try:
        _run_demo(robot, args.speed, args.duration)
    except KeyboardInterrupt:
        print("\n[abort] Ctrl-C")
    finally:
        robot.close()


if __name__ == "__main__":
    main()
