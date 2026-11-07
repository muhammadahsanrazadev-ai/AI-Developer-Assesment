"""Google Ads search volume and competition for keywords chosen by the keyword agent.

DataForSEO returns the monthly search count and the paid-competition index.
This module never invents either number.
"""

import base64
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SEO_API_MESSAGE = "SEO API not working properly."
REQUEST_TIMEOUT_SECONDS = 30
LIVE_PATH = "/v3/keywords_data/google_ads/search_volume/live"


class SearchVolumeError(Exception):
    """The SEO API could not be used. Callers must not invent volume or difficulty."""

    def __init__(self, message: str = SEO_API_MESSAGE):
        super().__init__(message)


@dataclass(frozen=True)
class KeywordMetrics:
    search_volume: int | None
    competition_index: int | None


def metrics_from_body(body: dict, expected: set[str]) -> dict[str, KeywordMetrics]:
    """Read one live response. Raises SearchVolumeError when the task itself failed."""
    if not isinstance(body, dict) or body.get("status_code") != 20000:
        raise SearchVolumeError(SEO_API_MESSAGE)
    tasks = body.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise SearchVolumeError(SEO_API_MESSAGE)
    if any(not isinstance(task, dict) or task.get("status_code") != 20000 for task in tasks):
        raise SearchVolumeError(SEO_API_MESSAGE)

    found: dict[str, KeywordMetrics] = {}
    for task in tasks:
        result = task.get("result") or []
        if not isinstance(result, list):
            continue
        for item in result:
            if not isinstance(item, dict):
                continue
            keyword = str(item.get("keyword") or "").strip().lower()
            if keyword not in expected:
                continue
            found[keyword] = KeywordMetrics(
                search_volume=_volume(item.get("search_volume")),
                competition_index=_difficulty(item.get("competition_index")),
            )
    return found


class DataForSEOVolumeClient:
    def __init__(self, login: str, password: str, base_url: str,
                 location_code: int, language_code: str):
        if not login or not password:
            raise SearchVolumeError(SEO_API_MESSAGE)
        self._login = login
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._location_code = location_code
        self._language_code = language_code or "en"

    def fetch(self, keywords: list[str | None]) -> dict[str, KeywordMetrics]:
        unique = _unique_keywords(keywords)
        if not unique:
            return {}
        body = self._post(unique)
        return metrics_from_body(body, set(unique))

    def _post(self, keywords: list[str]) -> dict:
        payload = [{
            "keywords": keywords,
            "location_code": self._location_code,
            "language_code": self._language_code,
            "search_partners": False,
        }]
        token = base64.b64encode(f"{self._login}:{self._password}".encode("utf-8")).decode("ascii")
        request = urllib.request.Request(
            f"{self._base_url}{LIVE_PATH}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            logger.warning("DataForSEO request failed: %s", type(exc).__name__)
            raise SearchVolumeError(SEO_API_MESSAGE) from exc
        try:
            body = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("DataForSEO returned a body that was not JSON")
            raise SearchVolumeError(SEO_API_MESSAGE) from exc
        return body


def build_volume_client(app) -> DataForSEOVolumeClient:
    try:
        location_code = int(app.config["DATAFORSEO_LOCATION_CODE"])
    except (TypeError, ValueError) as exc:
        raise SearchVolumeError(SEO_API_MESSAGE) from exc
    return DataForSEOVolumeClient(
        login=app.config.get("DATAFORSEO_LOGIN") or "",
        password=app.config.get("DATAFORSEO_PASSWORD") or "",
        base_url=app.config.get("DATAFORSEO_BASE_URL") or "https://api.dataforseo.com",
        location_code=location_code,
        language_code=app.config.get("DATAFORSEO_LANGUAGE_CODE") or "en",
    )


def _unique_keywords(keywords: list[str | None]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        if keyword and keyword not in seen:
            seen.add(keyword)
            unique.append(keyword)
    return unique


def _whole_number(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _volume(value) -> int | None:
    number = _whole_number(value)
    if number is None or number < 0:
        return None
    return number


def _difficulty(value) -> int | None:
    number = _whole_number(value)
    if number is None or not 0 <= number <= 100:
        return None
    return number
