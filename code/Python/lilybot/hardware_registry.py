"""Centralised tracker for LilyBot hardware resource allocations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class HardwareReservation:
    """Represents a single reserved hardware resource."""

    role: str
    protocol: str
    owner: str


class HardwareRegistry:
    """Track GPIO pins, I2C addresses, and other shared resources."""

    def __init__(self) -> None:
        self._gpio: Dict[int, HardwareReservation] = {}
        self._i2c: Dict[Tuple[int, int], HardwareReservation] = {}

    # GPIO -----------------------------------------------------------------
    def reserve_gpio(self, pin: int, *, role: str, owner: str, protocol: str = "GPIO") -> None:
        existing = self._gpio.get(pin)
        if existing is not None:
            raise RuntimeError(
                self._conflict_message(
                    resource=f"GPIO pin {pin}",
                    requested=(role, protocol, owner),
                    existing=existing,
                )
            )
        self._gpio[pin] = HardwareReservation(role=role, protocol=protocol, owner=owner)

    def release_gpio(self, pin: int) -> None:
        self._gpio.pop(pin, None)

    def gpio_usage(self) -> Dict[int, HardwareReservation]:
        return dict(self._gpio)

    # I2C ------------------------------------------------------------------
    def reserve_i2c(
        self,
        bus_id: int,
        address: int,
        *,
        role: str,
        owner: str,
        protocol: str = "I2C",
    ) -> None:
        key = (bus_id, address)
        existing = self._i2c.get(key)
        if existing is not None:
            raise RuntimeError(
                self._conflict_message(
                    resource=f"I2C bus {bus_id} address 0x{address:02X}",
                    requested=(role, protocol, owner),
                    existing=existing,
                )
            )
        self._i2c[key] = HardwareReservation(role=role, protocol=protocol, owner=owner)

    def release_i2c(self, bus_id: int, address: int) -> None:
        self._i2c.pop((bus_id, address), None)

    def i2c_usage(self) -> Dict[Tuple[int, int], HardwareReservation]:
        return dict(self._i2c)

    # Snapshot -------------------------------------------------------------
    def snapshot(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Return a shallow copy of all tracked allocations."""
        return {
            "gpio": {str(pin): asdict(reservation) for pin, reservation in self._gpio.items()},
            "i2c": {
                f"{bus}:{address}": asdict(reservation)
                for (bus, address), reservation in self._i2c.items()
            },
        }

    # Helpers --------------------------------------------------------------
    @staticmethod
    def _conflict_message(
        *,
        resource: str,
        requested: Tuple[str, str, str],
        existing: HardwareReservation,
    ) -> str:
        role, protocol, owner = requested
        return (
            f"{resource} already in use by {existing.owner} ({existing.role}, {existing.protocol}). "
            f"Requested by {owner} for {role} via {protocol}."
        )


__all__ = ["HardwareRegistry", "HardwareReservation"]
