"""SEC EDGAR client: declared User-Agent, at most 1 request/second, every response cached."""

import json
import os
import pathlib
import time

import httpx

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
MIN_INTERVAL = 1.0


class Edgar:
    def __init__(self, cache: pathlib.Path, http: httpx.Client | None = None) -> None:
        self.cache, self.http, self._last = cache, http or httpx.Client(timeout=60), 0.0

    def get(self, url: str, name: str) -> bytes:
        """Cached bytes for `name`; on a miss fetches `url` with SEC_USER_AGENT from the env."""
        path = self.cache / name
        if path.exists():
            return path.read_bytes()
        agent = os.environ.get("SEC_USER_AGENT")
        if not agent:
            raise RuntimeError("SEC_USER_AGENT is not set (load .env into the shell first)")
        time.sleep(max(0.0, self._last + MIN_INTERVAL - time.monotonic()))
        r = self.http.get(url, headers={"User-Agent": agent})
        self._last = time.monotonic()
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.content)
        return r.content

    def submissions(self, cik: int) -> dict:
        return json.loads(self.get(SUBMISSIONS.format(cik=cik), f"submissions_CIK{cik:010d}.json"))

    def companyfacts(self, cik: int) -> dict:
        return json.loads(
            self.get(COMPANYFACTS.format(cik=cik), f"companyfacts_CIK{cik:010d}.json")
        )

    def document(self, cik: int, accession: str, doc: str) -> bytes:
        acc = accession.replace("-", "")
        return self.get(ARCHIVE.format(cik=cik, acc=acc, doc=doc), f"docs/{accession}_{doc}")
