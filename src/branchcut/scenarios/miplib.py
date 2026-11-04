"""MIPLIB 2017 instances: download and load from ``data/miplib``."""

from __future__ import annotations

import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from branchcut.core.types import Instance

URL = "https://miplib.zib.de/WebData/instances/{name}.mps.gz"
BENCHMARK_LIST = Path("data/benchmark-v2.test")


def benchmark_names(list_path: str | Path = BENCHMARK_LIST) -> list[str]:
    """Instance names from a MIPLIB ``.test`` list (one ``name.mps.gz`` per line)."""
    lines = Path(list_path).read_text(encoding="utf-8").split()
    return [line.removesuffix(".gz").removesuffix(".mps") for line in lines if line]


def _download(url: str, target: Path) -> None:
    try:
        with urllib.request.urlopen(url, timeout=60) as resp, target.open("wb") as fh:
            shutil.copyfileobj(resp, fh)
    except urllib.error.URLError as exc:
        # python.org builds on macOS ship without CA certificates ("Install Certificates.command")
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc) or shutil.which("curl") is None:
            raise
        subprocess.run(["curl", "-fsSL", "--max-time", "300", "-o", str(target), url], check=True)


def fetch(names, directory: str | Path, overwrite: bool = False, progress=print) -> list[Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for name in names:
        path = directory / f"{name}.mps.gz"
        if path.exists() and not overwrite:
            progress(f"{name}: already present")
        else:
            tmp = path.with_suffix(".part")
            _download(URL.format(name=name), tmp)
            tmp.replace(path)
            progress(f"{name}: downloaded ({path.stat().st_size / 1024:.0f} KiB)")
        paths.append(path)
    return paths


def instance(name: str, directory: str | Path) -> Instance:
    path = Path(directory) / f"{name}.mps.gz"
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing; download it with: python run.py fetch-miplib {name}")
    return Instance(name, "miplib", "miplib2017", str(path))
