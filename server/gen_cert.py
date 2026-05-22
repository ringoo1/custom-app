"""Generate a self-signed cert for the H3 test server.

Outputs cert.pem and key.pem in the current directory. The cert covers
localhost, 127.0.0.1, 10.0.2.2 (Android emulator host alias), and h3.local
so the same cert works from curl, the emulator, and a custom hostname.
"""

import argparse
import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def generate(out_dir: Path, extra_ips: list[str]) -> None:
    key = ec.generate_private_key(ec.SECP256R1())

    sans: list[x509.GeneralName] = [
        x509.DNSName("h3.local"),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        x509.IPAddress(ipaddress.IPv4Address("10.0.2.2")),
    ]
    for ip in extra_ips:
        sans.append(x509.IPAddress(ipaddress.ip_address(ip)))

    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "h3-test-server")]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName(sans), critical=False)
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        .sign(key, hashes.SHA256())
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    cert_path = out_dir / "cert.pem"
    key_path = out_dir / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    print(f"wrote {cert_path}")
    print(f"wrote {key_path}")
    print("SAN entries:", ", ".join(str(s.value) for s in sans))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=".", help="output directory")
    parser.add_argument(
        "--ip",
        action="append",
        default=[],
        help="extra IP to include as SAN (repeatable); e.g. your LAN IP",
    )
    args = parser.parse_args()
    generate(Path(args.out), args.ip)
