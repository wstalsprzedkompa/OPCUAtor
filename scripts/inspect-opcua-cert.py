#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from datetime import timezone
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import ExtensionOID


def load_certificate(path: Path) -> x509.Certificate:
    data = path.read_bytes()
    try:
        return x509.load_der_x509_certificate(data)
    except ValueError:
        return x509.load_pem_x509_certificate(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect an OPC UA client certificate.")
    parser.add_argument("certificate", help="Certificate path, PEM or DER.")
    args = parser.parse_args()

    path = Path(args.certificate)
    data = path.read_bytes()
    certificate = load_certificate(path)

    print(f"File: {path}")
    print(f"SHA256 hex: {hashlib.sha256(data).hexdigest()}")
    print(f"Subject: {certificate.subject.rfc4514_string()}")
    print(f"Issuer: {certificate.issuer.rfc4514_string()}")
    print(f"Serial: {certificate.serial_number}")
    print(f"Valid from: {_certificate_time(certificate, 'not_valid_before').isoformat()}")
    print(f"Valid until: {_certificate_time(certificate, 'not_valid_after').isoformat()}")

    try:
        san = certificate.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    except x509.ExtensionNotFound:
        print("Subject Alternative Names: none")
        return

    uris = san.get_values_for_type(x509.UniformResourceIdentifier)
    dns_names = san.get_values_for_type(x509.DNSName)
    ip_addresses = san.get_values_for_type(x509.IPAddress)

    print("Application URI values:")
    for value in uris:
        print(f"  {value}")

    print("DNS names:")
    for value in dns_names:
        print(f"  {value}")

    print("IP addresses:")
    for value in ip_addresses:
        print(f"  {value}")


def _certificate_time(certificate: x509.Certificate, field: str):
    utc_field = f"{field}_utc"
    if hasattr(certificate, utc_field):
        return getattr(certificate, utc_field)
    value = getattr(certificate, field)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


if __name__ == "__main__":
    main()
