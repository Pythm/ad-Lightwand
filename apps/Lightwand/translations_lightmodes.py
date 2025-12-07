#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict
from pydantic import BaseModel, ValidationError, Field

from pydantic import BaseModel, Field

class ModeTranslation(BaseModel):
    MODE_CHANGE: str = Field(..., description="Event listen string")

    normal: str = Field(..., description="Normal mode")
    morning: str = Field(..., description="Morning mode")
    night: str = Field(..., description="Night mode")
    away: str = Field(..., description="Away mode")
    fire: str = Field(..., description="Fire mode")

    false_alarm: str = Field(
        ...,
        description="False alarm",
        alias="false_alarm",
    )

    wash: str = Field(..., description="Wash mode")
    reset: str = Field(..., description="Reset mode")
    custom: str = Field(..., description="Custom mode")
    off: str = Field(..., description="Off mode")

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"

class TranslationStore:
    _instance: TranslationStore | None = None

    def __new__(cls, file_path: str | Path | None = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            default_path = Path(__file__).parent / "translations.json"
            cls._instance._file_path = Path(file_path or default_path)
            cls._instance._data: dict[str, ModeTranslation] = {}
            cls._instance._load()
        return cls._instance


    def _load(self) -> None:
        try:
            raw = json.loads(self._file_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RuntimeError(f"Translation file not found: {self._file_path}") from exc

        for lang, block in raw.items():
            try:
                self._data[lang] = ModeTranslation(**block)
            except ValidationError as exc:
                raise RuntimeError(f"Invalid translation block for language '{lang}': {exc}") from exc

    def reload(self) -> None:
        """Call this if the JSON file changes while the server is running."""
        self._data.clear()
        self._load()

    def get(self, lang: str, key: str) -> str:
        try:
            return getattr(self._data[lang], key)
        except KeyError:
            if lang != "en":
                return getattr(self._data["en"], key)
            raise

    def available_languages(self) -> list[str]:
        return list(self._data.keys())

class Translations:
    """
    *A thin façade that*:

    * keeps a pointer to the TranslationStore,
    * remembers the currently selected language,
    * forwards attribute access (e.g. translations.normal) to the
      ModeTranslation instance for that language.
    """

    def __init__(self, file_path: str | Path | None = None):
        self._store = TranslationStore(file_path)
        self._lang: str = "en"

    def set_language(self, lang: str) -> None:
        """Select a language.  Raises if the language is unknown."""
        if lang not in self._store._data:
            raise ValueError(f"Unknown language '{lang}'. Available: {self._store.available_languages()}")
        self._lang = lang

    @property
    def language(self) -> str:
        return self._lang

    @property
    def current(self) -> ModeTranslation:
        """The ModeTranslation instance for the current language."""
        return self._store._data[self._lang]

    def __getattr__(self, name: str):

        return getattr(self.current, name)

    def reload(self) -> None:

        self._store.reload()

    def set_file_path(self, path: str | Path) -> None:
        """ Tell the singleton to read a *different* JSON file. """
        self._store._file_path = Path(path)
        self._store.reload()

translations = Translations()