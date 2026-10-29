import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from update_config import APP_VERSION
from updater import UpdateCheckError, fetch_latest_release, is_newer, parse_release, version_key

OWNER = "someone"
REPO = "mobile-app"


def release_payload(version="v0.3.0", file_name="app-release.apk"):
    return {
        "tag_name": version,
        "name": "New version",
        "body": "Added a new feature",
        "draft": False,
        "prerelease": False,
        "html_url": f"https://github.com/{OWNER}/{REPO}/releases/tag/{version}",
        "assets": [
            {
                "name": file_name,
                "state": "uploaded",
                "browser_download_url": (
                    f"https://github.com/{OWNER}/{REPO}/releases/download/"
                    f"{version}/{file_name}"
                ),
            }
        ],
    }


class MockResponse:
    def __init__(self, data):
        self.buffer = io.BytesIO(json.dumps(data).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size=-1):
        return self.buffer.read(size)


class UpdaterTests(unittest.TestCase):
    def test_semantic_version_comparison_not_lexical(self):
        self.assertTrue(is_newer("v0.10.0", "0.9.9"))
        self.assertFalse(is_newer("v0.2.0", "0.2.0"))
        self.assertFalse(is_newer("0.1.9", "0.2.0"))
        self.assertEqual(version_key("V12.4.7"), (12, 4, 7))
        with self.assertRaises(ValueError):
            version_key("release-0.5.0")

    def test_valid_release_and_apk(self):
        result = parse_release(release_payload(), OWNER, REPO)
        self.assertEqual(result.version, "0.3.0")
        self.assertTrue(result.apk_url.endswith("/app-release.apk"))

    def test_prevent_untrusted_download(self):
        payload = release_payload()
        payload["assets"][0]["browser_download_url"] = "https://evil.invalid/payload.apk"
        self.assertIsNone(parse_release(payload, OWNER, REPO).apk_url)

    def test_multiple_splits_fallback_to_release_page(self):
        payload = release_payload(file_name="app-arm64.apk")
        payload["assets"].append({
            "name": "app-x86.apk",
            "browser_download_url": f"https://github.com/{OWNER}/{REPO}/releases/download/v0.3.0/app-x86.apk",
        })
        self.assertIsNone(parse_release(payload, OWNER, REPO).apk_url)

    def test_multiple_with_universal_selects_universal(self):
        payload = release_payload(file_name="app-arm64.apk")
        payload["assets"].append({
            "name": "app-universal.apk",
            "browser_download_url": f"https://github.com/{OWNER}/{REPO}/releases/download/v0.3.0/app-universal.apk",
        })
        self.assertTrue(parse_release(payload, OWNER, REPO).apk_url.endswith("app-universal.apk"))

    def test_async_safe_network_check_has_timeout(self):
        def fake(request, timeout):
            self.assertEqual(timeout, 10)
            self.assertEqual(request.get_full_url(), "https://api.github.com/repos/someone/mobile-app/releases/latest")
            return MockResponse(release_payload())

        result = fetch_latest_release(OWNER, REPO, opener=fake)
        self.assertEqual(result.version, "0.3.0")

    def test_no_release_is_friendly(self):
        def fake(request, timeout):
            raise HTTPError(request.full_url, 404, "Missing", {}, None)
        with self.assertRaisesRegex(UpdateCheckError, "Release"):
            fetch_latest_release(OWNER, REPO, opener=fake)

    def test_connection_error(self):
        def fake(request, timeout):
            raise URLError("unreachable")
        with self.assertRaisesRegex(UpdateCheckError, "интернет"):
            fetch_latest_release(OWNER, REPO, opener=fake)

    def test_version_matches_project(self):
        import tomllib
        data = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(APP_VERSION, data["project"]["version"])
        self.assertGreaterEqual(data["tool"]["flet"]["build_number"], 2)


if __name__ == "__main__":
    unittest.main()
