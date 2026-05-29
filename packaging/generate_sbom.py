from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a CycloneDX SBOM from pinned requirements."
    )
    parser.add_argument(
        "--output",
        default="packaging/sbom.xml",
        help="Path for the generated SBOM file. The file extension controls the output format.",
    )
    args = parser.parse_args()

    command = [
        "cyclonedx-py",
        "requirements",
        "packaging/requirements-pinned.txt",
        "-o",
        args.output,
    ]

    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as exc:
        print(
            "cyclonedx-py is not installed. Install cyclonedx-bom before generating the SBOM.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    print(f"SBOM generated at {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
