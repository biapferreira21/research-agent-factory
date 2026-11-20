"""Build a shareable, credential-free Agent Factory starter kit."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "distribution"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    if wheel.suffix != ".whl":
        raise ValueError("Expected a wheel file")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = "research-agent-factory-kit"
    wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    with ZipFile(output, "w", ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(TEMPLATES.iterdir()):
            if path.is_file() and not path.is_symlink():
                archive.write(path, f"{prefix}/{path.name}")
        archive.write(ROOT / "SDK.md", f"{prefix}/SDK.md")
        archive.write(ROOT / "SECURITY.md", f"{prefix}/SECURITY.md")
        archive.write(wheel, f"{prefix}/packages/{wheel.name}")
        archive.writestr(f"{prefix}/SHA256SUMS.txt", f"{wheel_hash}  packages/{wheel.name}\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
