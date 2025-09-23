# LilyBot Quickstart

The `code/Developing/lilybot/` package exposes a high-level API designed for
students who are new to robotics programming. The central entry point is
`LilyBotKit`, which automatically initialises the motors, LCD screen and
ultrasonic sensor. Internally it reuses the lower-level implementations in
`robot.py`, so existing behaviour remains intact while still leaving room for
future hardware extensions.

```python
from lilybot import LilyBotKit

# Instantiate the kit (tweak I2C parameters to match the hardware setup)
kit = LilyBotKit(driver="drv8830", bus_id=1, sonar_pin=5,
                 drv8830_left=0x60, drv8830_right=0x65)

# High level motion helpers
kit.motors.forward(speed=60, duration=1.5)
kit.motors.turn_right(inner_scale=0.3)

# Read the distance and push it to the LCD
value = kit.distance.read_and_display(kit.display)
print("Current distance:", value)

# Play back a scripted sequence (same format as the CLI)
actions = [
    ("forward", [70, 1.2]),
    ("drive", [60, -60, 0.8]),
    ("distance", []),
]
kit.run_actions(actions)

kit.close()
```

## Key Concepts

- `kit.motors`: student-friendly motor controls that wrap `forward`,
  `backward`, `turn_left/right`, `pivot`, `drive`, and `stop`. The default
  speed/duration values can be overridden globally by providing a custom
  `KitDefaults` instance when the kit is created.
- `kit.display`: thin wrapper around the Grove RGB LCD with `set_lines`,
  `write`, `set_color`, and `show_distance` helpers.
- `kit.distance`: ultrasonic helper exposing `read()` and
  `read_and_display()` for easy integration with the display.
- `kit.run_actions(...)`: executes the same action tuples accepted by the
  command-line interface so classroom scripts or notebooks can replay CLI
  experiments verbatim.
- `kit.register_component(...)`: attach your own `KitComponent` subclasses to
  the kit. This keeps the door open for future sensors or actuators.

## Extension Checklist

1. **Add new hardware**: subclass `KitComponent`, implement the desired
   behaviour, then register it with `kit.register_component("your_name", component)`.
2. **Tune defaults**: pass a `KitDefaults` instance into `LilyBotKit(defaults=...)`
   to configure global speed, duration, turn inner-scale, and action pauses.
3. **Reuse CLI scripts**: anything you prototype with `main.py` and the
   `--actions` flag can be run inside Python via `kit.run_actions` without
   rewriting the sequence.

> **Note**: On machines without hardware libraries installed, the scripts in
> `drive8830.py`, `lcd.py`, and `ultrasonic.py` will raise friendly warnings
> only when the code attempts to talk to the device, so features such as
> `--list-actions` remain usable in software-only environments.

Always call `kit.close()` when you finish (or use the `with LilyBotKit(...) as kit:`
context manager) so the shared I2C resources are released cleanly.
