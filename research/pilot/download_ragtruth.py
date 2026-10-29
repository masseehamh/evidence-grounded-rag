"""Download the public RAGTruth dataset into a local data directory.

RAGTruth source: https://github.com/ParticleMedia/RAGTruth
This script downloads the upstream repository; it does not modify project code or
commit the dataset into this repository.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


REPOSITORY_URL = "https://github.com/ParticleMedia/RAGTruth.git"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clone the public RAGTruth dataset repository locally."
    )
    parser.add_argument(
        "--destination",
        default="data/external/RAGTruth",
        help="Local destination directory (default: data/external/RAGTruth)",
    )
    args = parser.parse_args()

    destination = Path(args.destination).expanduser().resolve()
    if destination.exists():
        parser.error(
            f"Destination already exists: {destination}. "
            "Choose another --destination or move the existing folder first."
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    command = ["git", "clone", "--depth", "1", REPOSITORY_URL, str(destination)]
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError:
        parser.error("Git was not found. Install Git, reopen your terminal, and retry.")
    except subprocess.CalledProcessError as exc:
        parser.error(f"Dataset download failed (git exited with {exc.returncode}).")

    print(f"RAGTruth downloaded to: {destination}")
    print("Read the upstream README and license before using or redistributing data.")
    print("For this project, start with the QA task and keep the official train/test split.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
