"""Read-only client-side lookup of stable protocol codes."""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType


class LocalizationError(ValueError):
    pass


class LocalizationCatalog:
    def __init__(self, locale_directory: str | Path):
        directory = Path(locale_directory)
        catalogs = {}
        for path in directory.glob("*.json"):
            try:
                values = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise LocalizationError(f"Cannot load locale {path.name}") from exc
            if not isinstance(values, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in values.items()
            ):
                raise LocalizationError(f"Locale {path.name} must map strings to strings")
            catalogs[path.stem] = MappingProxyType(dict(values))
        if not catalogs:
            raise LocalizationError("No locale files found")
        self._catalogs = MappingProxyType(catalogs)

    @property
    def languages(self) -> tuple[str, ...]:
        return tuple(sorted(self._catalogs))

    def text(self, language: str, code: str) -> str:
        try:
            return self._catalogs[language][code]
        except KeyError as exc:
            raise LocalizationError(
                f"Missing translation for {language}:{code}"
            ) from exc
