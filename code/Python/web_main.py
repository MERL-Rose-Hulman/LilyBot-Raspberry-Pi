#!/usr/bin/env python3
"""Run a simple web UI for controlling LilyBot on a local network."""

from __future__ import annotations

import atexit
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Dict, Optional

from flask import Flask, jsonify, render_template, request

from lilybot import KitDefaults, LilyBotKit

# ---------------------------------------------------------------------------
# Hardware configuration - mirror the classroom defaults used in main.py
# ---------------------------------------------------------------------------
DRIVER = "drv8830"          # Set to "tb6612" if you use that motor driver
I2C_BUS = 1
SONAR_PIN = 5               # GPIO pin (BCM numbering) for the ultrasonic ranger
LED_PIN = 12               # GPIO pin for the Grove LED (e.g. D12 -> 12)
DRV8830_LEFT = 0x65
DRV8830_RIGHT = 0x60
TB6612_ADDR = 0x14
DEFAULTS = KitDefaults(speed=60, duration=1.2, inner_scale=0.4, pause=0.5)


app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))


# Shared LilyBot kit instance --------------------------------------------------
_kit: Optional[LilyBotKit] = None
_kit_lock = Lock()

_demo_thread: Optional[Thread] = None
_demo_stop_event: Optional[Event] = None
_demo_lock = Lock()

AVOID_DISTANCE_CM = 25.0
AVOID_FORWARD_DURATION = 0.35
AVOID_BACKOFF_DURATION = 0.3
AVOID_TURN_DURATION = 0.45
AVOID_BACKOFF_SPEED = 45.0
AVOID_TURN_SPEED = 55.0


def _get_kit() -> LilyBotKit:
    """Create (or reuse) the shared LilyBotKit instance."""
    global _kit
    if _kit is None:
        _kit = LilyBotKit(
            driver=DRIVER,
            bus_id=I2C_BUS,
            sonar_pin=SONAR_PIN,
            led_pin=LED_PIN,
            tb6612_addr=TB6612_ADDR,
            drv8830_left=DRV8830_LEFT,
            drv8830_right=DRV8830_RIGHT,
            defaults=DEFAULTS,
        )
    return _kit


def _close_kit() -> None:
    """Close the shared kit when the process terminates."""
    global _kit
    _stop_demo(wait=True)
    with _kit_lock:
        if _kit is not None:
            try:
                _kit.close()
            finally:
                _kit = None


atexit.register(_close_kit)


def _clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


_ACTION_LABELS: Dict[str, str] = {
    "forward": "Forward",
    "backward": "Backward",
    "pivot_left": "Pivot Left",
    "pivot_right": "Pivot Right",
    "turn_left": "Turn Left",
    "turn_right": "Turn Right",
    "stop": "Stop",
}


def _demo_is_running() -> bool:
    thread = _demo_thread
    return thread is not None and thread.is_alive()


def _stop_demo(*, wait: bool = False) -> bool:
    """Signal the obstacle avoidance demo to stop if it is running."""
    global _demo_thread, _demo_stop_event
    with _demo_lock:
        thread = _demo_thread
        stop_event = _demo_stop_event
        if thread is None or stop_event is None:
            return False
        stop_event.set()
    if wait:
        thread.join(timeout=5.0)
    with _demo_lock:
        _demo_thread = None
        _demo_stop_event = None
    return True


def _run_obstacle_avoidance(stop_event: Event) -> None:
    """Background loop that performs a simple obstacle avoidance routine."""
    try:
        while not stop_event.is_set():
            with _kit_lock:
                kit = _get_kit()
                motors = kit.motors
                distance_component = kit.distance
                display = kit.display if kit.display.available else None
                motors_available = motors.available
                distance = distance_component.read()
                if display:
                    if distance is None:
                        display.set_lines("Avoidance", "Scanning")
                    else:
                        display.set_lines("Avoidance", f"{distance:5.1f} cm")

            if not motors_available:
                break

            if stop_event.is_set():
                break

            if distance is None or distance > AVOID_DISTANCE_CM:
                motors.forward(speed=DEFAULTS.speed, duration=AVOID_FORWARD_DURATION)
            else:
                motors.stop()
                motors.backward(speed=min(DEFAULTS.speed, AVOID_BACKOFF_SPEED), duration=AVOID_BACKOFF_DURATION)
                if stop_event.is_set():
                    break
                motors.pivot_right(speed=min(DEFAULTS.speed, AVOID_TURN_SPEED), duration=AVOID_TURN_DURATION)

            stop_event.wait(0.15)
    finally:
        with _kit_lock:
            if _kit is not None:
                try:
                    if _kit.motors.available:
                        _kit.motors.stop()
                    if _kit.display.available:
                        _kit.display.set_lines("Avoidance", "Stopped")
                except Exception:
                    pass


@app.route("/")
def index():
    """Serve the single-page controller UI."""
    return render_template("index.html", action_labels=_ACTION_LABELS)


@app.route("/api/status")
def api_status():
    """Report hardware availability to the frontend."""
    with _kit_lock:
        kit = _get_kit()
        status = {
            "motors": kit.motors.available,
            "display": kit.display.available,
            "distance": kit.distance.available,
            "led": kit.led.available if hasattr(kit, "led") else False,
            "defaults": {
                "speed": DEFAULTS.speed,
                "duration": DEFAULTS.duration,
                "inner_scale": DEFAULTS.inner_scale,
            },
            "demo_running": _demo_is_running(),
        }
    return jsonify(status)


@app.route("/api/move", methods=["POST"])
def api_move():
    """Execute a movement command provided by the web UI."""
    payload = request.get_json(silent=True) or {}
    action = (payload.get("action") or "").strip().lower()
    if action not in _ACTION_LABELS:
        return jsonify({"error": f"Unsupported action '{action}'"}), 400

    if _demo_is_running():
        return jsonify({"error": "Obstacle avoidance demo is running; stop it first."}), 409

    speed = float(payload.get("speed", DEFAULTS.speed))
    duration = float(payload.get("duration", DEFAULTS.duration))
    inner_scale = float(payload.get("inner_scale", DEFAULTS.inner_scale))

    # Clamp to safe ranges similar to the classroom defaults.
    speed = _clamp(speed, 0.0, 100.0)
    duration = max(0.0, duration)
    inner_scale = _clamp(inner_scale, 0.0, 1.0)

    with _kit_lock:
        kit = _get_kit()
        motors = kit.motors
        if not motors.available:
            return jsonify({"error": "Motor driver not detected."}), 503

        label = _ACTION_LABELS[action]
        if kit.display.available:
            kit.display.set_lines(label, f"Speed {speed:>5.1f}%")

        if action == "forward":
            motors.forward(speed=speed, duration=duration)
        elif action == "backward":
            motors.backward(speed=speed, duration=duration)
        elif action == "pivot_left":
            motors.pivot_left(speed=speed, duration=duration)
        elif action == "pivot_right":
            motors.pivot_right(speed=speed, duration=duration)
        elif action == "turn_left":
            motors.turn_left(speed=speed, duration=duration, inner_scale=inner_scale)
        elif action == "turn_right":
            motors.turn_right(speed=speed, duration=duration, inner_scale=inner_scale)
        elif action == "stop":
            motors.stop()
        else:  # pragma: no cover - defensive
            return jsonify({"error": f"Action '{action}' not implemented."}), 400

    return jsonify({"ok": True, "action": action})


@app.route("/api/distance")
def api_distance():
    """Fetch a distance reading and optionally reflect it on the LCD."""
    with _kit_lock:
        kit = _get_kit()
        display = kit.display if kit.display.available else None
        distance = kit.distance.read_and_display(display)
    if distance is None:
        return jsonify({"distance_cm": None, "available": False}), 503
    return jsonify({"distance_cm": round(distance, 2), "available": True})


@app.route("/api/led", methods=["POST"])
def api_led():
    """Control the Grove LED via the web UI."""
    payload = request.get_json(silent=True) or {}
    state = (payload.get("state") or "").strip().lower()
    try:
        count = int(payload.get("count", 3))
    except (TypeError, ValueError):
        return jsonify({"error": "count must be an integer."}), 400
    try:
        on_time = float(payload.get("on_time", 0.3))
        off_time = float(payload.get("off_time", 0.3))
    except (TypeError, ValueError):
        return jsonify({"error": "on_time/off_time must be numbers."}), 400

    count = max(0, count)
    on_time = max(0.0, on_time)
    off_time = max(0.0, off_time)

    with _kit_lock:
        kit = _get_kit()
        led = getattr(kit, "led", None)
        if led is None or not led.available:
            return jsonify({"error": "LED not connected."}), 404
        try:
            if state == "on":
                led.on()
            elif state == "off":
                led.off()
            elif state == "blink":
                led.blink(count=count, on_time=on_time, off_time=off_time)
            else:
                return jsonify({"error": f"Unsupported LED state '{state}'."}), 400
        except Exception as exc:  # pragma: no cover - hardware error path
            return jsonify({"error": f"LED command failed: {exc}"}), 500
    return jsonify({"ok": True, "state": state})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    """Force-stop the motors without waiting for durations to elapse."""
    demo_was_running = _stop_demo(wait=False)
    with _kit_lock:
        kit = _get_kit()
        if not kit.motors.available:
            return jsonify({"error": "Motor driver not detected."}), 503
        kit.motors.stop()
        if kit.display.available:
            kit.display.set_lines("Stopped", "Web controller")
    return jsonify({"ok": True, "demo_stopped": demo_was_running})


@app.route("/api/demo/avoidance", methods=["POST"])
def api_demo_avoidance_start():
    """Run the obstacle avoidance demo in the background."""
    if _demo_is_running():
        return jsonify({"error": "Obstacle avoidance demo already running."}), 409

    with _kit_lock:
        kit = _get_kit()
        if not kit.motors.available:
            return jsonify({"error": "Motor driver not detected."}), 503
        if kit.display.available:
            kit.display.set_lines("Avoidance", "Starting")

    stop_event = Event()
    thread = Thread(target=_run_obstacle_avoidance, args=(stop_event,), name="lilybot-avoidance", daemon=True)
    with _demo_lock:
        global _demo_thread, _demo_stop_event
        _demo_thread = thread
        _demo_stop_event = stop_event
    thread.start()
    return jsonify({"ok": True})


@app.route("/api/demo/avoidance/stop", methods=["POST"])
def api_demo_avoidance_stop():
    """Stop the obstacle avoidance demo if it is running."""
    if not _demo_is_running():
        return jsonify({"ok": False, "message": "Demo was not running."})
    _stop_demo(wait=True)
    with _kit_lock:
        if _kit is not None and _kit.motors.available:
            _kit.motors.stop()
        if _kit is not None and _kit.display.available:
            _kit.display.set_lines("Avoidance", "Stopped")
    return jsonify({"ok": True})


def main() -> None:
    """Start the Flask development server bound to all interfaces."""
    print("Starting LilyBot web controller on http://0.0.0.0:8000 ...")
    app.run(host="0.0.0.0", port=8000, debug=False)


if __name__ == "__main__":
    main()
