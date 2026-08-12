from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from blueboardClient import BlueBoardClient, discoverBlueBoards
from router import Router, loadBindings


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Connect to an iRig BlueBoard over BLE-MIDI on Windows."
    )
    parser.add_argument(
        "command", choices=("scan", "run"), nargs="?", default="run"
    )
    parser.add_argument("--name", default="BlueBoard", help="Device-name substring")
    parser.add_argument("--address", help="Connect only to this previously discovered device")
    parser.add_argument("--pair", action="store_true", help="Ask Windows to pair before GATT discovery")
    parser.add_argument("--scan-timeout", type=float, default=8.0)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "blueboard.json",
    )
    parser.add_argument("--debug", action="store_true")
    return parser


async def run(args: argparse.Namespace) -> None:
    if args.command == "scan":
        devices = await discoverBlueBoards(args.name, args.scan_timeout)
        if not devices:
            print("No matching BLE device found. Hold C while powering on the BlueBoard, then retry.")
            return
        for device in devices:
            print(f"{device.name or '<unnamed>'}\t{device.address}\tRSSI={device.rssi}")
        return

    router = Router(loadBindings(args.config))
    client = BlueBoardClient(
        router.handleEvent,
        router.releaseAll,
        nameSubstring=args.name,
        address=args.address,
        pair=args.pair,
        scanTimeout=args.scan_timeout,
    )
    await client.run()


def main() -> None:
    args = buildParser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(relativeCreated)09.0fms %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
