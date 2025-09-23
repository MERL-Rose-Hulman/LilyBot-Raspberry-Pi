"""High-level toolkit for teaching LilyBot robotics programming."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from robot import (
    DEFAULT_DURATION,
    DEFAULT_INNER_SCALE,
    DEFAULT_PAUSE,
    DEFAULT_SPEED,
    Robot,
    available_actions,
    build_robot,
    execute_actions,
    run_demo,
)


@dataclass
class KitDefaults:
    """Container for the default movement timings used across the lesson helpers."""

    speed: float = DEFAULT_SPEED
    duration: float = DEFAULT_DURATION
    inner_scale: float = DEFAULT_INNER_SCALE
    pause: float = DEFAULT_PAUSE


class KitComponent:
    """Base class for every teaching component exposed on ``LilyBotKit``."""

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    @property
    def available(self) -> bool:
        """Return whether the underlying hardware is available."""
        return True

    def close(self) -> None:
        """Release resources if necessary (default: no-op)."""
        return None


class MotorComponent(KitComponent):
    """Friendly wrapper around the Robot motor helpers."""

    def __init__(self, robot: Robot, defaults: KitDefaults) -> None:
        super().__init__("motors")
        self._robot = robot
        self._defaults = defaults

    # Utilities -----------------------------------------------------------------
    def _ensure_available(self) -> None:
        if not self.available:
            raise RuntimeError("Motor driver not available or not detected.")

    @property
    def available(self) -> bool:  # type: ignore[override]
        return self._robot.motors_present

    # Basic motions --------------------------------------------------------------
    def stop(self) -> None:
        if not self.available:
            return  # Stay silent in classrooms where the driver board is absent
        self._robot.stop()

    def drive(self, left_percent: float, right_percent: float, duration: Optional[float] = None) -> None:
        """Drive both wheels with raw percentages; optional timed duration."""
        self._ensure_available()
        duration = self._defaults.duration if duration is None else duration
        self._robot.drive(left_percent, right_percent)
        if duration > 0:
            from time import sleep

            sleep(duration)
        self._robot.stop()

    def forward(self, speed: Optional[float] = None, duration: Optional[float] = None) -> None:
        self._ensure_available()
        speed = self._defaults.speed if speed is None else speed
        duration = self._defaults.duration if duration is None else duration
        self._robot.forward(speed, duration)

    def backward(self, speed: Optional[float] = None, duration: Optional[float] = None) -> None:
        self._ensure_available()
        speed = self._defaults.speed if speed is None else speed
        duration = self._defaults.duration if duration is None else duration
        self._robot.backward(speed, duration)

    def pivot_left(self, speed: Optional[float] = None, duration: Optional[float] = None) -> None:
        self._ensure_available()
        speed = self._defaults.speed if speed is None else speed
        duration = self._defaults.duration if duration is None else duration
        self._robot.pivot_left(speed, duration)

    def pivot_right(self, speed: Optional[float] = None, duration: Optional[float] = None) -> None:
        self._ensure_available()
        speed = self._defaults.speed if speed is None else speed
        duration = self._defaults.duration if duration is None else duration
        self._robot.pivot_right(speed, duration)

    def turn_left(
        self,
        speed: Optional[float] = None,
        duration: Optional[float] = None,
        inner_scale: Optional[float] = None,
    ) -> None:
        self._ensure_available()
        speed = self._defaults.speed if speed is None else speed
        duration = self._defaults.duration if duration is None else duration
        inner_scale = self._defaults.inner_scale if inner_scale is None else inner_scale
        self._robot.turn_left(speed, duration, inner_scale=inner_scale)

    def turn_right(
        self,
        speed: Optional[float] = None,
        duration: Optional[float] = None,
        inner_scale: Optional[float] = None,
    ) -> None:
        self._ensure_available()
        speed = self._defaults.speed if speed is None else speed
        duration = self._defaults.duration if duration is None else duration
        inner_scale = self._defaults.inner_scale if inner_scale is None else inner_scale
        self._robot.turn_right(speed, duration, inner_scale=inner_scale)


class DisplayComponent(KitComponent):
    """Simple wrapper around the Grove RGB LCD."""

    def __init__(self, robot: Robot) -> None:
        super().__init__("display")
        self._robot = robot

    @property
    def available(self) -> bool:  # type: ignore[override]
        return getattr(self._robot, "lcd_present", False)

    def write(self, text: str) -> None:
        if not self.available:
            return  # Reuse the graceful degradation pattern from the robot layer
        self._robot.lcd.write(text)

    def set_lines(self, line1: str, line2: str = "") -> None:
        if not self.available:
            return
        self._robot.lcd.clear()
        self._robot.lcd.print_line(line1[:16], 0)
        if line2:
            self._robot.lcd.print_line(line2[:16], 1)

    def set_color(self, name: str) -> None:
        if not self.available:
            return
        self._robot.lcd.set_color(name)

    def show_distance(self, distance: Optional[float], status: str = "Distance") -> None:
        if not self.available:
            return
        self._robot.display_distance(distance, status)


class DistanceComponent(KitComponent):
    """Helper for the ultrasonic distance sensor."""

    def __init__(self, robot: Robot) -> None:
        super().__init__("distance")
        self._robot = robot

    @property
    def available(self) -> bool:  # type: ignore[override]
        return getattr(self._robot, "sonar_present", False)

    def read(self) -> Optional[float]:
        if not self.available:
            return None
        return self._robot.read_distance()

    def read_and_display(self, display: Optional[DisplayComponent] = None) -> Optional[float]:
        distance = self.read()
        if display is not None:
            display.show_distance(distance)
        return distance


class LilyBotKit:
    """Co-ordinates all robot components for lesson-friendly scripting."""

    def __init__(
        self,
        *,
        driver: str = "tb6612",
        bus_id: int = 1,
        sonar_pin: Optional[int] = None,
        tb6612_addr: int = 0x14,
        drv8830_left: int = 0x60,
        drv8830_right: int = 0x61,
        defaults: Optional[KitDefaults] = None,
    ) -> None:
        if sonar_pin is None:
            raise ValueError("sonar_pin must be provided to initialise the kit")

        self.defaults = defaults or KitDefaults()
        self.robot = build_robot(
            driver=driver,
            bus_id=bus_id,
            sonar_pin=sonar_pin,
            tb6612_addr=tb6612_addr,
            drv8830_left=drv8830_left,
            drv8830_right=drv8830_right,
        )

        # Components are stored in a registry so lessons can iterate or extend them.
        self._components: Dict[str, KitComponent] = {}

        # Core components -------------------------------------------------------
        self.motors = MotorComponent(self.robot, self.defaults)
        self.display = DisplayComponent(self.robot)
        self.distance = DistanceComponent(self.robot)

        self.register_component("motors", self.motors)
        self.register_component("display", self.display)
        self.register_component("distance", self.distance)

    # -------------------------------------------------------------------------
    def register_component(self, name: str, component: KitComponent) -> None:
        """Expose a new component both in the registry and as an attribute."""
        self._components[name] = component
        setattr(self, name, component)

    @property
    def components(self) -> Dict[str, KitComponent]:
        return dict(self._components)

    def list_actions(self) -> List[str]:
        return available_actions()

    def run_prebuilt_demo(self) -> None:
        """Replay the same demonstration sequence used by the CLI demo."""
        run_demo(
            self.robot,
            self.defaults.speed,
            self.defaults.duration,
            inner_scale=self.defaults.inner_scale,
            pause=self.defaults.pause,
        )

    def run_actions(
        self,
        actions: Sequence[Tuple[str, Sequence[float]]],
        *,
        default_speed: Optional[float] = None,
        default_duration: Optional[float] = None,
        default_inner_scale: Optional[float] = None,
        pause: Optional[float] = None,
    ) -> None:
        defaults = self.defaults
        execute_actions(
            self.robot,
            actions,
            default_speed=defaults.speed if default_speed is None else default_speed,
            default_duration=defaults.duration if default_duration is None else default_duration,
            default_inner_scale=defaults.inner_scale if default_inner_scale is None else default_inner_scale,
            pause=defaults.pause if pause is None else pause,
        )

    # Context management -------------------------------------------------------
    def close(self) -> None:
        for component in self._components.values():
            try:
                component.close()
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[warn] failed to close component {component.name}: {exc}")
        self.robot.close()

    def __enter__(self) -> "LilyBotKit":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


__all__ = [
    "KitDefaults",
    "KitComponent",
    "MotorComponent",
    "DisplayComponent",
    "DistanceComponent",
    "LilyBotKit",
]
