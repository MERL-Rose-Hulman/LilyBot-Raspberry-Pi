# LilyBot Architecture & Extension Guide

This guide is aimed at instructors and contributors. It explains how the
LilyBot project is structured and documents the recommended steps for adding
new sensors or actuators.

## Layered Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  Student / Teaching Entry Points: main.py, lilybot/kit.py           │
└───────────────▲─────────────────────────────────────────────────────┘
                │ (Friendly API surface: kit.motors.forward(), etc.)
┌───────────────┴─────────────────────────────────────────────────────┐
│  Core Hardware Abstractions: lilybot/robot.py                       │
│   • Robot manages the shared I2C bus                                │
│   • MotionSystem / DisplaySystem / DistanceSensor                   │
│   • ActionRunner executes scripted motion sequences                  │
└───────────────▲─────────────────────────────────────────────────────┘
                │ (Reuse shared defaults and resilience strategies)
┌───────────────┴─────────────────────────────────────────────────────┐
│  Device Adaptors: lilybot/drivers/drive8830.py,                     │
│                   lilybot/peripherals/lcd.py,                       │
│                   lilybot/peripherals/ultrasonic.py, …              │
│   • Direct interaction with the hardware libraries                   │
│   • Graceful fallbacks when smbus / grove packages are missing       │
└─────────────────────────────────────────────────────────────────────┘
```

### Design Goals

1. **Object-oriented boundaries** – every subsystem owns a clear slice of
   responsibility and collaborates via composition rather than free functions.
2. **Extensibility** – new devices can be added by introducing new classes; the
   student-facing API remains stable.
3. **Friendly fault handling** – when hardware is disconnected during
   development the code prints warnings instead of crashing the app.
4. **Teaching-first API** – `LilyBotKit` emphasises readable, semantic method
   names so beginners focus on robotics concepts rather than plumbing.

## Adding a New Device

Use the following checklist when you introduce a new sensor or actuator (the
example below assumes a temperature sensor):

1. **Confirm hardware requirements**
   - Wire the hardware and validate the communication protocol (I2C, GPIO,
     SPI, UART, etc.).
   - Record any additional Python dependencies and how to install them on the
     classroom Raspberry Pi environment.

2. **Wrap the low-level driver**
  - Create a dedicated module such as
    `code/Developing/lilybot/peripherals/temperature.py`
     with a `TemperatureSensor` class that handles setup, reads data, and
     releases resources.
   - Mirror the patterns in `lilybot/drivers/drive8830.py` and friends so missing dependencies
     raise an informative error only when the driver is actually used.

3. **Optionally surface it through `Robot`**
   - If all consumers should have access, instantiate the new driver inside
     `Robot.__init__` and expose a lightweight helper (for example,
     `self.temperature_sensor`).
   - The helper can unify error handling or provide consistent units.

4. **Expose it via the teaching kit**
   - Subclass `KitComponent` inside `lilybot/kit.py`:

     ```python
     class TemperatureComponent(KitComponent):
         def __init__(self, robot: Robot) -> None:
             super().__init__("temperature")
             self._sensor = robot.temperature_sensor

         def read(self) -> Optional[float]:
             return self._sensor.read() if self._sensor else None
     ```

   - Register the component in `LilyBotKit.__init__` with
     `register_component("temperature", TemperatureComponent(self.robot))`.
   - Students can now call `kit.temperature.read()` in their lessons.

5. **Update docs and demos**
   - Extend `USAGE.md` or add a sample script showing how to import, read from,
     and display values from the new component.
   - Keep the explanation concise and classroom friendly.

6. **Test on hardware**
   - Verify the module on a Raspberry Pi to ensure exception handling and
     resource cleanup behave correctly.
   - Confirm software-only features such as `main.py --list-actions` still run
     on development machines without the hardware libraries installed.

## Key Classes Recap

- **`Robot`** – owns the shared `SMBus` handle, builds the motion, display, and
  distance subsystems, and exposes high-level helpers like `forward()`.
- **`ActionRunner`** – interprets action tuples and triggers the appropriate
  motor or sensor behaviour.
- **`LilyBotKit`** – classroom wrapper that surfaces semantic components such as
  `kit.motors`, `kit.display`, and `kit.distance`, plus helpers like
  `run_actions` and `run_prebuilt_demo`.

Keeping the stack ordered as Device → Robot → Kit allows us to provide a gentle
API for students while still enabling rapid experimentation with new hardware
behind the scenes.
