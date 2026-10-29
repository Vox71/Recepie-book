"""Download of the Kaggle dataset (credentials come from the environment only).

The dataset licence is not stated, therefore the archive is downloaded next to the
service and never committed: ``.gitignore`` and ``backend/.dockerignore`` exclude
``backend/data/``. Kaggle serves a zip archive over its public API, so the download
needs nothing but the standard library plus the credentials:

    export KAGGLE_USERNAME=...   # https://www.kaggle.com/settings/account
    export KAGGLE_KEY=...
    python -m app.importer --download --destination data/povarenok

Every network call has a timeout (CONTRIBUTION.md §7): a hung Kaggle response must not
block the importer forever.
"""

from __future__ import annotations

import base64
import logging
import os
import shutil
import zipfile
from pathlib import Path
from typing import BinaryIO, Callable
from urllib.request import Request, urlopen

from .povarenok import DatasetError, find_dataset_file

logger = logging.getLogger(__name__)

KAGGLE_DATASET = "rogozinushka/povarenok-recipes"
KAGGLE_ARCHIVE_URL = "https://www.kaggle.com/api/v1/datasets/download/{dataset}"
ARCHIVE_NAME = "povarenok-recipes.zip"
DEFAULT_TIMEOUT_SECONDS = 120
CHUNK_SIZE = 1024 * 1024

Opener = Callable[[Request, int], BinaryIO]


def download_dataset(
    destination: str | Path,
    *,
    dataset: str = KAGGLE_DATASET,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    opener: Opener = urlopen,
) -> Path:
    """Download and unpack ``dataset`` into ``destination``; return the data file.

    ``opener`` is injectable so that the unpacking logic is tested without network.
    """
    username = os.environ.get("KAGGLE_USERNAME", "").strip()
    key = os.environ.get("KAGGLE_KEY", "").strip()
    if not username or not key:
        raise DatasetError(
            "KAGGLE_USERNAME and KAGGLE_KEY must be set to download the dataset "
            "(--dataset PATH works without them)"
        )

    target = Path(destination)
    target.mkdir(parents=True, exist_ok=True)
    archive = target / ARCHIVE_NAME
    request = Request(
        KAGGLE_ARCHIVE_URL.format(dataset=dataset),
        headers={"Authorization": f"Basic {_basic_token(username, key)}"},
    )
    logger.info("Downloading %s to %s (timeout %s s)", dataset, target, timeout)
    try:
        with opener(request, timeout) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output, length=CHUNK_SIZE)
        _unpack(archive, target)
    except OSError as exc:
        raise DatasetError(f"Cannot download the dataset: {exc}") from exc
    finally:
        archive.unlink(missing_ok=True)
    return find_dataset_file(target)


def _basic_token(username: str, key: str) -> str:
    """Build the Basic authentication token of the Kaggle API."""
    return base64.b64encode(f"{username}:{key}".encode()).decode()


def _unpack(archive: Path, target: Path) -> None:
    """Extract the archive, refusing entries that escape ``target`` (zip slip)."""
    resolved_target = target.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.namelist():
            if member.endswith("/"):
                continue
            member_path = (resolved_target / member).resolve()
            if resolved_target not in member_path.parents:
                raise DatasetError(f"Archive entry escapes the destination: {member}")
            bundle.extract(member, resolved_target)
