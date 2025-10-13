#!/usr/bin/env python3
"""LilyBot 入门示例：依次调用核心功能，帮助学生熟悉机器人编程。"""

from __future__ import annotations

from time import sleep
from typing import Optional

from lilybot import KitDefaults, LilyBotKit

# ---------------------------------------------------------------------------
# Hardware defaults for the classroom rig. Adjust these as required for your
# robot build before running the lesson script.
# ---------------------------------------------------------------------------
DRIVER = "drv8830"          # 也可改为 "tb6612"
I2C_BUS = 1
SONAR_PIN = 5               # Grove 超声波模块插入的 GPIO 引脚（例：D5 → 5）
DRV8830_LEFT = 0x65         # 左轮驱动板 I2C 地址
DRV8830_RIGHT = 0x60        # 右轮驱动板 I2C 地址
TB6612_ADDR = 0x14          # TB6612 驱动板地址（当 DRIVER="tb6612" 时生效）
DEFAULTS = KitDefaults(speed=60, duration=1.2, inner_scale=0.4, pause=0.5)


def show_header(kit: LilyBotKit) -> None:
    """Display a welcome banner on the LCD (or console fallback)."""
    print("=== LilyBot Intro Demo ===")
    if kit.display.available:
        kit.display.set_lines("Hello LilyBot!", "Let's explore")
        sleep(1.5)
        kit.display.set_lines("Ready to move", "Watch the wheels")
    else:
        print("[info] LCD is not connected; falling back to console messages only.")


def check_distance(kit: LilyBotKit, note: str) -> Optional[float]:
    """Fetch a distance reading and display it using the available channels."""
    distance = kit.distance.read_and_display(kit.display if kit.display.available else None)
    if distance is None:
        print(f"[{note}] Distance unavailable (sensor missing or invalid reading).")
    else:
        print(f"[{note}] Distance = {distance:.1f} cm")
    return distance


def demo_motions(kit: LilyBotKit) -> None:
    """Demonstrate the basic motion primitives in a safe, sequential order."""
    motors = kit.motors
    if not motors.available:
        print("[warn] Motor driver not detected; skipping the movement showcase.")
        return

    print("→ Forward")
    motors.forward()

    print("→ Backward")
    motors.backward()

    print("→ Pivot left")
    motors.pivot_left()

    print("→ Pivot right")
    motors.pivot_right()

    print("→ Turning left with inner wheel scaling")
    motors.turn_left(inner_scale=0.5)

    print("→ Turning right with inner wheel scaling")
    motors.turn_right(inner_scale=0.5)

    print("→ Differential drive demo (left forward, right reverse)")
    motors.drive(60, -60, duration=1.0)

    print("→ Stop")
    motors.stop()


def demo_action_sequence(kit: LilyBotKit) -> None:
    """Showcase the scripted action pipeline shared with the CLI."""
    # The action tuples use the same format as the command-line interface.
    script = [
        ("forward", [70, 1.2]),
        ("pivot_left", [60, 1.0]),
        ("distance", []),
        ("drive", [50, -50, 0.8]),
        ("stop", []),
    ]
    print("→ Executing scripted action sequence", script)
    kit.run_actions(script)


def main() -> None:
    print("Initialising LilyBot – ensure power and sensors are connected…")
    with LilyBotKit(
        driver=DRIVER,
        bus_id=I2C_BUS,
        sonar_pin=SONAR_PIN,
        tb6612_addr=TB6612_ADDR,
        drv8830_left=DRV8830_LEFT,
        drv8830_right=DRV8830_RIGHT,
        defaults=DEFAULTS,
    ) as kit:
        show_header(kit)

        check_distance(kit, "Start Distance")
        demo_motions(kit)
        check_distance(kit, "End Distance")

        demo_action_sequence(kit)

        if kit.display.available:
            kit.display.set_lines("Lesson", "Completed")
        print("Demo finished – feel free to tweak the parameters or add new actions!")


if __name__ == "__main__":
    main()
