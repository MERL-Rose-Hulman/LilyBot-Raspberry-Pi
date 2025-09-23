#!/usr/bin/env python3
"""Command-line demo entry point for LilyBot."""

import argparse
from typing import List, Optional

from robot import build_robot, run_demo


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
    robot = build_robot(
        driver=args.driver,
        bus_id=args.bus,
        sonar_pin=args.sonar_pin,
        tb6612_addr=args.tb6612_addr,
        drv8830_left=args.drv8830_left,
        drv8830_right=args.drv8830_right,
    )

    try:
        run_demo(robot, args.speed, args.duration)
    except KeyboardInterrupt:
        print("\n[abort] Ctrl-C")
    finally:
        robot.close()


if __name__ == "__main__":
    main()
