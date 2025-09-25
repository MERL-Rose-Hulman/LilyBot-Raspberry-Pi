#!/usr/bin/env python3
"""Core robot orchestration and action sequencing for LilyBot."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple, Union

# SMBus is required for I2C access on the Raspberry Pi. During local
# development the dependency may be missing, so we attempt a graceful
# fallback that leaves `SMBus` as ``None``.
try:
    from smbus2 import SMBus
except ImportError:  # pragma: no cover - fallback when smbus2 is missing
    try:
        from smbus import SMBus  # type: ignore[assignment]
    except ImportError:  # pragma: no cover - developer machines without SMBus
        SMBus = None  # type: ignore[assignment]

from .drivers.drive6612 import get_controller
from .drivers.drive8830 import get_driver
from .peripherals.lcd import GroveRGBLCD
from .peripherals.ultrasonic import GroveUltrasonicRanger


DEFAULT_SPEED = 60.0
DEFAULT_DURATION = 1.2
DEFAULT_INNER_SCALE = 0.4
DEFAULT_PAUSE = 0.5

# Supported action identifiers. Keeping the list centralised ensures the CLI,
# action runner, and educational kit stay in sync.
_ACTION_NAMES = (
    "forward",
    "backward",
    "pivot_left",
    "pivot_right",
    "turn_left",
    "turn_right",
    "drive",
    "stop",
    "distance",
)


def _clamp_pct(value: float) -> float:
    return -100.0 if value < -100.0 else 100.0 if value > 100.0 else value


@dataclass
class ActionDefaults:
    speed: float = DEFAULT_SPEED
    duration: float = DEFAULT_DURATION
    inner_scale: float = DEFAULT_INNER_SCALE
    pause: float = DEFAULT_PAUSE


@dataclass
class ActionSpec:
    """Represents a single action with optional parameters."""

    name: str
    params: Tuple[float, ...] = ()

    @classmethod
    def from_tuple(cls, item: Tuple[str, Sequence[float]]) -> "ActionSpec":
        name, params = item
        return cls(name, tuple(params))

    @classmethod
    def ensure(cls, item: Union["ActionSpec", Tuple[str, Sequence[float]]]) -> "ActionSpec":
        """Accept either an ActionSpec or a raw tuple and normalise it."""
        if isinstance(item, ActionSpec):
            return item
        if isinstance(item, tuple) and len(item) == 2:
            return cls.from_tuple(item)
        raise TypeError(f"Unsupported action spec type: {type(item)!r}")


class MotionSystem:
    """High-level control over the differential drive subsystem."""

    def __init__(self, controller=None, drv8830_pair: Optional[Tuple[object, object]] = None) -> None:
        self._controller = controller
        self._drv8830_pair = drv8830_pair

    @property
    def available(self) -> bool:
        return self._controller is not None or self._drv8830_pair is not None

    def drive(self, left_pct: float, right_pct: float) -> None:
        if not self.available:
            return  # No driver detected → silently ignore to keep lessons flowing
        if self._controller is not None:
            left_val = int(round(_clamp_pct(left_pct) * 255 / 100))
            right_val = int(round(_clamp_pct(right_pct) * 255 / 100))
            self._controller.run("A", left_val)
            self._controller.run("B", right_val)
        else:
            left_drv, right_drv = self._drv8830_pair  # type: ignore[misc]
            left_drv.set_speed(int(round(_clamp_pct(left_pct))))
            right_drv.set_speed(int(round(_clamp_pct(right_pct))))

    def stop(self) -> None:
        if not self.available:
            return
        if self._controller is not None:
            self._controller.stop("both")
        else:
            left_drv, right_drv = self._drv8830_pair  # type: ignore[misc]
            left_drv.stop()
            right_drv.stop()

    def timed_drive(self, left_pct: float, right_pct: float, duration: float) -> None:
        self.drive(left_pct, right_pct)
        if duration > 0:
            time.sleep(duration)
            self.stop()

    def forward(self, speed: float, duration: float) -> None:
        self.timed_drive(speed, speed, duration)

    def backward(self, speed: float, duration: float) -> None:
        self.timed_drive(-speed, -speed, duration)

    def pivot_left(self, speed: float, duration: float) -> None:
        self.timed_drive(-speed, speed, duration)

    def pivot_right(self, speed: float, duration: float) -> None:
        self.timed_drive(speed, -speed, duration)

    def turn_left(self, speed: float, duration: float, inner_scale: float) -> None:
        # The inner wheel runs slower than the outer wheel to produce a smooth arc
        self.timed_drive(speed * inner_scale, speed, duration)

    def turn_right(self, speed: float, duration: float, inner_scale: float) -> None:
        self.timed_drive(speed, speed * inner_scale, duration)

    def close(self) -> None:
        # Drivers share the SMBus owned by Robot; ensure motors stop safely
        try:
            self.stop()
        except Exception:
            pass


class DisplaySystem:
    def __init__(self, lcd: Optional[GroveRGBLCD]) -> None:
        self._lcd = lcd

    @property
    def available(self) -> bool:
        return self._lcd is not None

    def write(self, text: str) -> None:
        if self._lcd is None:
            return
        self._lcd.write(text)

    def set_lines(self, line1: str, line2: str = "") -> None:
        if self._lcd is None:
            return
        self._lcd.clear()
        self._lcd.print_line(line1[:16], 0)
        if line2:
            self._lcd.print_line(line2[:16], 1)

    def set_color(self, name: str) -> None:
        if self._lcd is None:
            return
        self._lcd.set_color(name)

    def show_distance(self, distance: Optional[float], status: str = "Distance") -> None:
        if self._lcd is None:
            return
        if distance is None:
            line1 = "Dist: ----"
        else:
            line1 = f"Dist: {distance:5.1f} cm"
        self.set_lines(line1, status[:16])

    def close(self) -> None:
        if self._lcd is not None:
            self._lcd.close()


class DistanceSensor:
    def __init__(self, sensor: Optional[GroveUltrasonicRanger]) -> None:
        self._sensor = sensor

    @property
    def available(self) -> bool:
        return self._sensor is not None

    def read(self) -> Optional[float]:
        if self._sensor is None:
            return None
        try:
            return float(self._sensor.get_distance())
        except Exception as exc:  # pragma: no cover - hardware error path
            print(f"[warn] Ultrasonic read failed: {exc}", file=sys.stderr)
            return None


class Robot:
    """Aggregates motion, display, and sensors on a shared I2C bus."""

    def __init__(
        self,
        *,
        driver: str = "tb6612",
        bus_id: int = 1,
        sonar_pin: int,
        tb6612_addr: int = 0x14,
        drv8830_left: int = 0x60,
        drv8830_right: int = 0x61,
    ) -> None:
        if SMBus is None:
            raise RuntimeError(
                "SMBus library not available. Install 'smbus2' or run on Raspberry Pi."
            )

        self.bus = SMBus(bus_id)

        # LCD -----------------------------------------------------------------
        try:
            self.lcd = GroveRGBLCD(i2c=self.bus)
            self.lcd_present = True
        except OSError as exc:
            print(f"[warn] LCD init failed ({exc}); continuing without LCD", file=sys.stderr)
            self.lcd = None
            self.lcd_present = False

        # Wrap the LCD in a light-weight system that can absorb missing hardware
        self.display = DisplaySystem(self.lcd)

        # Ultrasonic ----------------------------------------------------------
        try:
            self.sonar = GroveUltrasonicRanger(sonar_pin)
            self.sonar_present = True
        except Exception as exc:
            print(f"[warn] Ultrasonic init failed ({exc}); distance readings disabled", file=sys.stderr)
            self.sonar = None
            self.sonar_present = False

        self.distance_sensor = DistanceSensor(self.sonar)

        # Motors --------------------------------------------------------------
        motion: MotionSystem
        if driver == "tb6612":
            try:
                controller = get_controller(bus=bus_id, address=tb6612_addr, i2c=self.bus, verbose=False)
                motion = MotionSystem(controller=controller)
            except OSError as exc:
                print(f"[warn] TB6612 controller unavailable ({exc}); motors disabled", file=sys.stderr)
                motion = MotionSystem()
        elif driver == "drv8830":
            left_drv = right_drv = None
            try:
                left_drv = get_driver(bus=bus_id, address=drv8830_left, i2c=self.bus)
                right_drv = get_driver(bus=bus_id, address=drv8830_right, i2c=self.bus)
                motion = MotionSystem(drv8830_pair=(left_drv, right_drv))
            except OSError as exc:
                print(f"[warn] DRV8830 drivers unavailable ({exc}); motors disabled", file=sys.stderr)
                if left_drv is not None:
                    left_drv.close()
                if right_drv is not None:
                    right_drv.close()
                motion = MotionSystem()
        else:
            raise ValueError(f"Unsupported driver '{driver}'")

        self.motion = motion
        self.motors_present = self.motion.available

    # ------------------------------------------------------------------
    def drive(self, left_pct: float, right_pct: float) -> None:
        self.motion.drive(left_pct, right_pct)

    def stop(self) -> None:
        self.motion.stop()

    def forward(self, speed: float, duration: float) -> None:
        self.motion.forward(speed, duration)

    def backward(self, speed: float, duration: float) -> None:
        self.motion.backward(speed, duration)

    def pivot_left(self, speed: float, duration: float) -> None:
        self.motion.pivot_left(speed, duration)

    def pivot_right(self, speed: float, duration: float) -> None:
        self.motion.pivot_right(speed, duration)

    def turn_left(self, speed: float, duration: float, *, inner_scale: float) -> None:
        self.motion.turn_left(speed, duration, inner_scale)

    def turn_right(self, speed: float, duration: float, *, inner_scale: float) -> None:
        self.motion.turn_right(speed, duration, inner_scale)

    def read_distance(self) -> Optional[float]:
        return self.distance_sensor.read()

    def display_distance(self, distance: Optional[float], status: str = "Distance") -> None:
        self.display.show_distance(distance, status)

    def close(self) -> None:
        try:
            self.motion.close()
        finally:
            try:
                self.display.close()
            finally:
                self.bus.close()


class ActionRunner:
    """Executes high-level action sequences against a robot."""

    available_actions = list(_ACTION_NAMES)

    def __init__(self, robot: Robot, defaults: Optional[ActionDefaults] = None) -> None:
        self.robot = robot
        self.defaults = defaults or ActionDefaults()

    def run(
        self,
        actions: Sequence[Union[ActionSpec, Tuple[str, Sequence[float]]]],
        *,
        default_speed: Optional[float] = None,
        default_duration: Optional[float] = None,
        default_inner_scale: Optional[float] = None,
        pause: Optional[float] = None,
    ) -> None:
        if not actions:
            return

        # Merge per-call overrides with the runner defaults so lesson code stays concise.
        defaults = ActionDefaults(
            speed=self.defaults.speed if default_speed is None else default_speed,
            duration=self.defaults.duration if default_duration is None else default_duration,
            inner_scale=self.defaults.inner_scale if default_inner_scale is None else default_inner_scale,
            pause=self.defaults.pause if pause is None else pause,
        )

        if not self.robot.motors_present:
            print("[warn] Motors not available; movement actions will be skipped", file=sys.stderr)

        for item in actions:
            spec = ActionSpec.ensure(item)
            name = spec.name.lower().strip()
            if name not in _ACTION_NAMES:
                raise ValueError(
                    f"Unsupported action '{name}'. Available actions: {', '.join(_ACTION_NAMES)}"
                )

            params = list(spec.params)
            if name == "distance":
                distance = self.robot.read_distance()
                self.robot.display_distance(distance, "Distance")
                if distance is not None:
                    print(f"[distance] {distance:.2f} cm")
                else:
                    print("[distance] ----")
            else:
                label = name.replace("_", " ").title()
                distance = self.robot.read_distance()
                self.robot.display_distance(distance, label)
                if distance is not None:
                    print(f"[{name}] distance={distance:.2f} cm")
                else:
                    print(f"[{name}] distance=----")
                self._perform_motion(name, params, defaults)

            if defaults.pause > 0:
                time.sleep(defaults.pause)

    # ------------------------------------------------------------------
    def _perform_motion(self, name: str, params: List[float], defaults: ActionDefaults) -> None:
        motion = self.robot.motion
        if not motion.available:
            return  # Nothing to do when the drivetrain is absent or failed to initialise

        if name == "forward":
            speed = params[0] if len(params) > 0 else defaults.speed
            duration = params[1] if len(params) > 1 else defaults.duration
            print(f"[forward] speed={speed:.2f}% duration={duration:.2f}s")
            motion.forward(speed, duration)
        elif name == "backward":
            speed = params[0] if len(params) > 0 else defaults.speed
            duration = params[1] if len(params) > 1 else defaults.duration
            print(f"[backward] speed={speed:.2f}% duration={duration:.2f}s")
            motion.backward(speed, duration)
        elif name == "pivot_left":
            speed = params[0] if len(params) > 0 else defaults.speed
            duration = params[1] if len(params) > 1 else defaults.duration
            print(f"[pivot_left] speed={speed:.2f}% duration={duration:.2f}s")
            motion.pivot_left(speed, duration)
        elif name == "pivot_right":
            speed = params[0] if len(params) > 0 else defaults.speed
            duration = params[1] if len(params) > 1 else defaults.duration
            print(f"[pivot_right] speed={speed:.2f}% duration={duration:.2f}s")
            motion.pivot_right(speed, duration)
        elif name == "turn_left":
            speed = params[0] if len(params) > 0 else defaults.speed
            duration = params[1] if len(params) > 1 else defaults.duration
            inner = params[2] if len(params) > 2 else defaults.inner_scale
            print(f"[turn_left] speed={speed:.2f}% duration={duration:.2f}s inner={inner:.2f}")
            motion.turn_left(speed, duration, inner_scale=inner)
        elif name == "turn_right":
            speed = params[0] if len(params) > 0 else defaults.speed
            duration = params[1] if len(params) > 1 else defaults.duration
            inner = params[2] if len(params) > 2 else defaults.inner_scale
            print(f"[turn_right] speed={speed:.2f}% duration={duration:.2f}s inner={inner:.2f}")
            motion.turn_right(speed, duration, inner_scale=inner)
        elif name == "drive":
            left = params[0] if len(params) > 0 else defaults.speed
            right = params[1] if len(params) > 1 else defaults.speed
            duration = params[2] if len(params) > 2 else defaults.duration
            print(f"[drive] left={left:.2f}% right={right:.2f}% duration={duration:.2f}s")
            motion.timed_drive(left, right, duration)
        elif name == "stop":
            print("[stop]")
            motion.stop()
        else:
            raise ValueError(f"Unhandled action '{name}'")


# ---------------------------------------------------------------------------
# Backward-compatible helper functions


def build_robot(
    *,
    driver: str = "tb6612",
    bus_id: int = 1,
    sonar_pin: int,
    tb6612_addr: int = 0x14,
    drv8830_left: int = 0x60,
    drv8830_right: int = 0x61,
) -> Robot:
    return Robot(
        driver=driver,
        bus_id=bus_id,
        sonar_pin=sonar_pin,
        tb6612_addr=tb6612_addr,
        drv8830_left=drv8830_left,
        drv8830_right=drv8830_right,
    )


def available_actions() -> List[str]:
    return list(_ACTION_NAMES)


def execute_actions(
    robot: Robot,
    actions: Sequence[Tuple[str, Sequence[float]]],
    *,
    default_speed: float = DEFAULT_SPEED,
    default_duration: float = DEFAULT_DURATION,
    default_inner_scale: float = DEFAULT_INNER_SCALE,
    pause: float = DEFAULT_PAUSE,
) -> None:
    runner = ActionRunner(robot, ActionDefaults())
    runner.run(
        actions,
        default_speed=default_speed,
        default_duration=default_duration,
        default_inner_scale=default_inner_scale,
        pause=pause,
    )


def run_demo(
    robot: Robot,
    speed: float,
    duration: float,
    *,
    inner_scale: float = DEFAULT_INNER_SCALE,
    pause: float = DEFAULT_PAUSE,
) -> None:
    sequence = [
        ("forward", [speed, duration]),
        ("backward", [speed, duration]),
        ("pivot_left", [speed, duration]),
        ("pivot_right", [speed, duration]),
        ("turn_left", [speed, duration, inner_scale]),
        ("turn_right", [speed, duration, inner_scale]),
    ]
    execute_actions(
        robot,
        sequence,
        default_speed=speed,
        default_duration=duration,
        default_inner_scale=inner_scale,
        pause=pause,
    )


__all__ = [
    "Robot",
    "MotionSystem",
    "DisplaySystem",
    "DistanceSensor",
    "ActionDefaults",
    "ActionSpec",
    "ActionRunner",
    "build_robot",
    "available_actions",
    "execute_actions",
    "run_demo",
    "DEFAULT_SPEED",
    "DEFAULT_DURATION",
    "DEFAULT_INNER_SCALE",
    "DEFAULT_PAUSE",
]
