#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def build_parser() -> argparse.ArgumentParser:
    hostname = socket.gethostname()
    parser = argparse.ArgumentParser(
        description="Generate an OPC UA client certificate for OPCUAtor.",
    )
    parser.add_argument("--out-dir", default="certs", help="Output directory.")
    parser.add_argument("--name", default="opcuator-client", help="Output file prefix.")
    parser.add_argument("--common-name", default="OPCUAtor", help="Certificate common name.")
    parser.add_argument(
        "--app-uri",
        default=f"urn:{hostname}:OPCUAtor",
        help="OPC UA application URI stored as a URI subjectAltName.",
    )
    parser.add_argument(
        "--dns",
        action="append",
        default=[hostname],
        help="DNS subjectAltName. Can be passed multiple times.",
    )
    parser.add_argument(
        "--ip",
        action="append",
        default=[],
        help="IP subjectAltName. Can be passed multiple times.",
    )
    parser.add_argument("--days", type=int, default=3650, help="Certificate validity in days.")
    parser.add_argument("--key-size", type=int, default=2048, help="RSA key size.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    key_path = out_dir / f"{args.name}-key.pem"
    cert_pem_path = out_dir / f"{args.name}.pem"
    cert_der_path = out_dir / f"{args.name}.der"

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=args.key_size,
    )

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, args.common_name),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OPCUAtor"),
        ],
    )

    alt_names: list[x509.GeneralName] = [x509.UniformResourceIdentifier(args.app_uri)]
    alt_names.extend(x509.DNSName(item) for item in args.dns if item)
    for item in args.ip:
        if item:
            alt_names.append(x509.IPAddress(ipaddress.ip_address(item)))

    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=args.days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=True,
                data_encipherment=True,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .sign(private_key, hashes.SHA256())
    )

    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )
    cert_pem_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    cert_der_path.write_bytes(certificate.public_bytes(serialization.Encoding.DER))

    key_path.chmod(0o600)

    print(f"Private key: {key_path}")
    print(f"Client certificate PEM: {cert_pem_path}")
    print(f"Client certificate DER for server trust store: {cert_der_path}")
    print(f"Application URI: {args.app_uri}")
    print()
    print("Copy this public DER certificate to the OPC UA server trusted directory:")
    print(f"  {cert_der_path}")


if __name__ == "__main__":
    main()
