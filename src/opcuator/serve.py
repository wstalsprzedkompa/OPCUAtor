from __future__ import annotations

import socket
import sys

import uvicorn

from .config import settings

LOGO = r"""
   ____  ____   ____ _   _    _  _
  / __ \|  _ \ / ___| | | |  / \| |_ ___  _ __
 | |  | | |_) | |   | | | | / _ \ __/ _ \| '__|
 | |__| |  __/| |___| |_| |/ ___ \ || (_) | |
  \____/|_|    \____|\___//_/   \_\__\___/|_|
"""


class Color:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def _local_ip_addresses() -> list[str]:
    addresses: set[str] = set()
    hostname = socket.gethostname()

    try:
        addresses.add(socket.gethostbyname(hostname))
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            addresses.add(probe.getsockname()[0])
    except OSError:
        pass

    return sorted(
        address
        for address in addresses
        if address and not address.startswith("0.") and not address.startswith("127.")
    )


def _colors_enabled() -> bool:
    return sys.stdout.isatty()


def _color(text: str, color: str) -> str:
    if not _colors_enabled():
        return text
    return f"{color}{text}{Color.RESET}"


def _print_startup_banner() -> None:
    port = settings.rest_port
    host = settings.rest_host
    print()
    print(_color(LOGO.rstrip(), Color.CYAN))
    print(_color("OPCUAtor", Color.BOLD))
    print(_color("REST client for OPC UA", Color.GREEN))
    print()
    print(f"{_color('Listening on:', Color.YELLOW)} {host}:{port}")
    print(f"{_color('Persistent OPC UA connection:', Color.YELLOW)} {settings.opcua_persistent_connection}")
    print(_color("Try one of these URLs:", Color.YELLOW))

    addresses = _local_ip_addresses()
    if not addresses:
        print("  No non-loopback IPv4 address detected.")
        print("  Bind address is still shown above; use the machine IP reachable from your network.")

    for address in addresses:
        base_url = f"http://{address}:{port}"
        print(_color(f"  {base_url}/health", Color.DIM))
        print(f"  {base_url}/connection")
        print(f"  {base_url}/config")
        print(f"  {base_url}/endpoints")
        print(f"  {base_url}/Browse?max_depth=2&max_nodes=100")
        print(f"  {base_url}/Browse/Tree?max_depth=4&max_nodes=500")
        print(f"  {base_url}/Browse/Text?max_depth=4&max_nodes=500")

    print()


def main() -> None:
    _print_startup_banner()
    uvicorn.run(
        "opcuator.main:app",
        host=settings.rest_host,
        port=settings.rest_port,
    )


if __name__ == "__main__":
    main()
