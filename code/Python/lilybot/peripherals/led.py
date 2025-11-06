#!/usr/bin/env python3
"""Minimal Grove Red LED adapter for the LilyBot toolkit."""

from __future__ import annotations

import time
from typing import Optional

try:
    from grove.gpio import GPIO
except ImportError:  # pragma: no cover - allow import on dev machines
    GPIO = None  # type: ignore[assignment]


class GroveLed:
    """Thin wrapper around the Grove digital LED module."""

    def __init__(self, pin: Optional[int] = None, *, gpio: Optional[GPIO] = None) -> None:
        if gpio is None:
            if GPIO is None:
                raise RuntimeError(
                    "grove.gpio module not available. Install Seeed's grove Python libraries on the Raspberry Pi."
                )
            if pin is None:
                raise ValueError("pin must be provided when gpio is None")
            self._gpio = GPIO(pin)
            self.pin = pin
            self._owns_gpio = True
        else:
            self._gpio = gpio
            self.pin = pin if pin is not None else getattr(self._gpio, "pin", None)
            self._owns_gpio = False
        self.off()

    def on(self) -> None:
        self._gpio.write(1)

    def off(self) -> None:
        self._gpio.write(0)

    def blink(self, *, count: int = 3, on_time: float = 0.5, off_time: float = 0.5) -> None:
        """Blink the LED a fixed number of times (blocking helper)."""
        if count <= 0:
            self.off()
            return
        for _ in range(count):
            self.on()
            if on_time > 0:
                time.sleep(on_time)
            self.off()
            if off_time > 0:
                time.sleep(off_time)

    def close(self) -> None:
        try:
            self.off()
        finally:
            if self._owns_gpio and hasattr(self._gpio, "close"):
                try:
                    self._gpio.close()
                except Exception:
                    pass


__all__ = ["GroveLed"]
