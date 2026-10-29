"""Small GitHub Releases update checker. No third-party HTTP dependency.

Only public GitHub Releases are supported; checking is read-only. Installation is
performed by Android's standard package installer after the user downloads the
APK using their browser. Python source code is never executed from the network.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

_REPOSITORY_PART = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$", re.IGNORECASE)
_MAX_RESPONSE = 1_000_000


class UpdateCheckError(Exception):
    """A user-friendly error while reading a release feed."""


@dataclass(frozen=True)
class LatestRelease:
    version: str
    title: str
    description: str
    page_url: str
    apk_url: str | None


def version_key(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Недопустимый номер версии: {value!r} (ожидается x.y.z)")
    return tuple(int(v) for v in match.groups())


def is_newer(remote: str, local: str) -> bool:
    return version_key(remote) > version_key(local)


def validate_repository(owner: str, repo: str) -> None:
    if not (_REPOSITORY_PART.fullmatch(owner) and _REPOSITORY_PART.fullmatch(repo)):
        raise UpdateCheckError("Укажите GitHub-логин и название репозитория в src/update_config.py.")
    if owner.lower() in {"your-username", "your-github-username", "change-me"}:
        raise UpdateCheckError("Укажите свой GitHub-логин в src/update_config.py.")


def _trusted_release_url(value: object, owner: str, repo: str) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        return False
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        return False
    repo_prefix = f"/{owner}/{repo}/releases/".lower()
    return parsed.path.lower().startswith(repo_prefix)


def parse_release(data: object, owner: str, repo: str) -> LatestRelease:
    validate_repository(owner, repo)
    if not isinstance(data, dict):
        raise UpdateCheckError("GitHub вернул неожиданный ответ.")
    tag = data.get("tag_name")
    if not isinstance(tag, str):
        raise UpdateCheckError("У выпуска отсутствует тег версии, например v0.3.0.")
    try:
        version_key(tag)
    except ValueError as exc:
        raise UpdateCheckError("Тег выпуска должен быть вида v0.3.0.") from exc

    if data.get("draft") or data.get("prerelease"):
        raise UpdateCheckError("Последний выпуск не является стабильным.")

    page_url = data.get("html_url", "")
    if not _trusted_release_url(page_url, owner, repo):
        raise UpdateCheckError("GitHub вернул некорректную ссылку на выпуск.")

    assets = data.get("assets")
    if not isinstance(assets, list):
        raise UpdateCheckError("В ответе GitHub нет списка файлов выпуска.")

    apks: list[tuple[str, str]] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name", "")
        url = asset.get("browser_download_url")
        if (
            isinstance(name, str)
            and name.lower().endswith(".apk")
            and _trusted_release_url(url, owner, repo)
            and "/releases/download/" in url.lower()
            and asset.get("state", "uploaded") == "uploaded"
        ):
            apks.append((name.lower(), url))

    # A single universal APK is expected. Never guess a phone's CPU architecture.
    universal = [url for name, url in apks if "universal" in name]
    apk_url = (universal[0] if len(universal) == 1 else None)
    if apk_url is None and len(apks) == 1:
        apk_url = apks[0][1]

    title = data.get("name")
    if not isinstance(title, str) or not title.strip():
        title = tag
    body = data.get("body")
    if not isinstance(body, str):
        body = ""
    # Avoid very large and control-character-filled release notes in the UI.
    body = "".join(ch for ch in body[:1200] if ch.isprintable() or ch in "\n\t")
    return LatestRelease(
        version=tag.removeprefix("v").removeprefix("V"),
        title=title[:100],
        description=body.strip()[:800],
        page_url=page_url,
        apk_url=apk_url,
    )


def fetch_latest_release(owner: str, repo: str, *, opener=None) -> LatestRelease:
    """Fetch the latest stable public GitHub release using a short timeout."""
    validate_repository(owner, repo)
    api_url = (
        "https://api.github.com/repos/"
        f"{quote(owner, safe='')}/{quote(repo, safe='')}/releases/latest"
    )
    request = Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "SimpleCabinet-UpdateChecker",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    open_connection = opener or urlopen
    try:
        with open_connection(request, timeout=10) as response:
            content = response.read(_MAX_RESPONSE + 1)
    except HTTPError as exc:
        if exc.code == 404:
            raise UpdateCheckError(
                "В GitHub пока нет опубликованного Release или репозиторий не является публичным."
            ) from exc
        if exc.code == 403:
            raise UpdateCheckError("GitHub временно ограничил запросы. Повторите позже.") from exc
        raise UpdateCheckError(f"Ошибка GitHub: HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise UpdateCheckError("Не удалось подключиться к GitHub. Проверьте интернет.") from exc

    if len(content) > _MAX_RESPONSE:
        raise UpdateCheckError("Ответ GitHub слишком большой.")
    try:
        return parse_release(json.loads(content.decode("utf-8")), owner, repo)
    except (ValueError, UnicodeError) as exc:
        raise UpdateCheckError("Не удалось прочитать ответ GitHub.") from exc
