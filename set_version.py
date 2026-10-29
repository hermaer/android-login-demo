"""Bump the app version and Android build_number together.

Usage from project root: python set_version.py 0.3.0
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def set_version(value: str) -> int:
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError("Version must be x.y.z (example: 0.3.0).")
    project_file = ROOT / "pyproject.toml"
    config_file = ROOT / "src" / "update_config.py"
    project = project_file.read_text(encoding="utf-8")
    config = config_file.read_text(encoding="utf-8")

    pattern_project = r'(?m)^version = "\d+\.\d+\.\d+"$'
    pattern_config = r'(?m)^APP_VERSION = "\d+\.\d+\.\d+"$'
    pattern_build = r'(?m)^build_number = (\d+)(\s*(?:#.*)?)$'

    match = re.search(pattern_build, project)
    if (
        not match
        or len(re.findall(pattern_project, project)) != 1
        or len(re.findall(pattern_config, config)) != 1
    ):
        raise ValueError("Could not locate version fields in project files.")
    current = re.search(r'^APP_VERSION = "(.*)"$', config, re.M).group(1)
    if tuple(map(int, value.split('.'))) <= tuple(map(int, current.split('.'))):
        raise ValueError(f"Version must be higher than {current}.")
    new_build = int(match.group(1)) + 1
    project = re.sub(pattern_project, f'version = "{value}"', project)
    project = re.sub(pattern_build, lambda m: f"build_number = {new_build}{m.group(2)}", project)
    config = re.sub(pattern_config, f'APP_VERSION = "{value}"', config)
    project_file.write_text(project, encoding="utf-8")
    config_file.write_text(config, encoding="utf-8")
    return new_build


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python set_version.py 0.3.0")
        sys.exit(2)
    try:
        build = set_version(sys.argv[1])
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)
    print(f"Version updated to {sys.argv[1]}, Android build number: {build}.")
