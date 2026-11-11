"""Cricsheet IPL archive to bronze: one raw JSON document per match.

Cricsheet publishes every IPL match as one zip (about 5 MB), refreshed after each game, so a
run downloads the whole archive and writes only the matches that are new or were revised.
A manifest of content hashes makes that check one read instead of one per match.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import zipfile
from collections.abc import Iterator
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ingestion import landing

ARCHIVE_URL = "https://cricsheet.org/downloads/ipl_json.zip"
SOURCE = "cricsheet"
ENDPOINT = "matches"
# Cricsheet asks for attribution (ODC-By); a contact-free client name is enough for a download.
USER_AGENT = "ipl-cricket-analytics/0.1 (+https://github.com/Emmanuel-Esplin/ipl-cricket-analytics)"

log = logging.getLogger(__name__)


@retry(
    retry=retry_if_exception_type(httpx.TransportError),
    wait=wait_exponential(multiplier=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def download_archive(client: httpx.Client | None = None) -> bytes:
    """The current IPL zip from Cricsheet."""
    own = client is None
    client = client or httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT})
    try:
        response = client.get(ARCHIVE_URL, follow_redirects=True)
        response.raise_for_status()
        return response.content
    finally:
        if own:
            client.close()


def iter_matches(archive: bytes) -> Iterator[tuple[str, bytes]]:
    """(match_id, raw JSON) for every match file in the zip; README and LICENSE are skipped."""
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        for name in sorted(zf.namelist()):
            stem, _, ext = name.rpartition(".")
            if ext == "json" and stem.isdigit():
                yield stem, zf.read(name)


def season_of(match: dict[str, Any]) -> int:
    """Calendar year of the first match day. Cricsheet labels some seasons '2007/08' or
    '2020/21', but every IPL edition is played within one calendar year."""
    return int(match["info"]["dates"][0][:4])


def _manifest_path() -> str:
    return landing.store().path("bronze", SOURCE, "_manifest.json")


def _read_manifest() -> dict[str, str]:
    path = _manifest_path()
    if not landing.store().exists(path):
        return {}
    return json.loads(landing.store().read_bytes(path))


def ingest(archive: bytes | None = None, refresh: bool = False) -> dict[str, int]:
    """Write new or revised matches to bronze. Returns counts of written and unchanged files."""
    archive = archive if archive is not None else download_archive()
    manifest = {} if refresh else _read_manifest()
    written = unchanged = 0
    for match_id, raw in iter_matches(archive):
        digest = hashlib.sha256(raw).hexdigest()
        if manifest.get(match_id) == digest:
            unchanged += 1
            continue
        match = json.loads(raw)
        path = landing.bronze_path(SOURCE, ENDPOINT, season=season_of(match), match_id=match_id)
        landing.write_bronze(path, match, ARCHIVE_URL)
        manifest[match_id] = digest
        written += 1
    # Written last: if the run dies midway, the next one rewrites the same matches.
    landing.store().write_bytes(_manifest_path(), json.dumps(manifest, sort_keys=True).encode())
    log.info("bronze: %d written, %d unchanged", written, unchanged)
    return {"written": written, "unchanged": unchanged}
