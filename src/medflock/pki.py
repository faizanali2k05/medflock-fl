"""Short-lived loopback certificates support transport tests, never hospital enrollment."""

import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def node_identity(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    private_path, public_path = directory / "node.key", directory / "node.pub"
    if private_path.exists() or public_path.exists():
        raise ValueError("Refusing to overwrite an existing node identity")
    key = ec.generate_private_key(ec.SECP384R1())
    private_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.OpenSSH,
            serialization.NoEncryption(),
        )
    )
    private_path.chmod(0o600)
    public_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
        )
    )
    return private_path, public_path


def loopback_pki(directory, clients=3):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    now = datetime.now(timezone.utc)
    ca_key, server_key = (
        ec.generate_private_key(ec.SECP384R1()),
        ec.generate_private_key(ec.SECP384R1()),
    )
    issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "MedFlock local test CA")])
    ca = (
        x509.CertificateBuilder()
        .subject_name(issuer)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    server = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(issuer)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )
    (directory / "ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    (directory / "server.pem").write_bytes(server.public_bytes(serialization.Encoding.PEM))
    (directory / "server.key").write_bytes(
        server_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    (directory / "server.key").chmod(0o600)
    for index in range(clients):
        node_identity(directory / f"node-{index}")
    return directory
