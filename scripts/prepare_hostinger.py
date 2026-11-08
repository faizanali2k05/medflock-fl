"""Create an isolated deployment bundle locally; never connect to or alter a VPS."""

import argparse
import json
import re
import secrets
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, default=Path("runtime/deployment/hostinger"))
    args = parser.parse_args()
    if not re.fullmatch(
        r"registry\.gitlab\.com/mashhood0x7e-group/medflock-fl:(?:[a-f0-9]{40})", args.image
    ):
        raise ValueError("Use a full tested commit tag from the MedFlock registry")
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError(
            "Output is not empty; preserve existing credentials and choose a new directory"
        )
    args.output.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parents[1] / "deploy/hostinger"
    for path in source.iterdir():
        if path.is_file():
            shutil.copyfile(path, args.output / path.name)
    password = secrets.token_urlsafe(32)
    (args.output / ".env").write_text(
        f"MEDFLOCK_IMAGE={args.image}\nMEDFLOCK_API_KEY={secrets.token_urlsafe(40)}\n"
        f"MEDFLOCK_DB_PASSWORD={password}\nPOSTGRES_ADMIN_PASSWORD={secrets.token_urlsafe(32)}\n"
        "MEDFLOCK_PORT=18088\nMEDFLOCK_ALLOWED_HOSTS=localhost,127.0.0.1\n"
    )
    (args.output / ".env").chmod(0o600)
    (args.output / "deployment-status.json").write_text(
        json.dumps(
            {
                "status": "prepared_not_deployed",
                "target": "Hostinger KVM 4",
                "image": args.image,
                "required_before_deployment": [
                    "SSH access and host-key verification",
                    "Read-only capacity/port preflight",
                    "Dedicated hostname and existing proxy review",
                    "Backup destination",
                ],
                "hospital_status": "no hospital pilot authorization supplied",
            },
            indent=2,
        )
    )
    print(f"Prepared {args.output}; private credentials were not printed")


if __name__ == "__main__":
    main()
