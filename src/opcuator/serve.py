from __future__ import annotations

import socket

import uvicorn

from .config import settings


def _local_ip_addresses() -> list[str]:
    addresses: set[str] = {"127.0.0.1"}
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

    return sorted(address for address in addresses if address and not address.startswith("0."))


def _print_startup_banner() -> None:
    port = settings.rest_port
    host = settings.rest_host
    print()
    print("OPCUAtor")
    print("REST bridge for OPC UA")
    print()
    print(f"Listening on: {host}:{port}")
    print("Try one of these URLs:")

    for address in _local_ip_addresses():
        base_url = f"http://{address}:{port}"
        print(f"  {base_url}/health")
        print(f"  {base_url}/config")
        print(f"  {base_url}/endpoints")
        print(f"  {base_url}/namespace?max_depth=2&max_nodes=100")

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
