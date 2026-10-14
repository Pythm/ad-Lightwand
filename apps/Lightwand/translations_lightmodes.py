#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict
from pydantic import BaseModel, ValidationError, Field, root_validator

class ModeTranslation(BaseModel):
    MODE_CHANGE: str = Field(..., description="Event listen string")

    automagical: str = Field(..., description="Automagical mode")
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

    @property
    def normal(self) -> str: # read‑only, backward compatibility
        return self.automagical

    class Config:
        allow_population_by_field_name = True
        extra = "ignore"

    # ----------  Accept an old "normal" key ----------
    @root_validator(pre=True)
    def _map_old_normal(cls, values):
        """
        If the JSON contains "normal" (the old key), move it to the new
        field name `automagical`.  
        New JSON that already uses "automagical" is unaffected.
        """
        if "normal" in values and "automagical" not in values:
            values["automagical"] = values.pop("normal")
        return values

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
        """ Reads the JSON file into a new dict and swaps it in only when the
            whole file is valid, so a bad file never leaves the store empty. """
        try:
            raw = json.loads(self._file_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RuntimeError(f"Translation file not found: {self._file_path}") from exc

        loaded: dict[str, ModeTranslation] = {}
        for lang, block in raw.items():
            try:
                loaded[lang] = ModeTranslation(**block)
            except ValidationError as exc:
                raise RuntimeError(f"Invalid translation block for language '{lang}': {exc}") from exc
        self._data = loaded

    def reload(self) -> None:
        """Call this if the JSON file changes while the server is running."""
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
    * forwards attribute access (e.g. translations.automagical) to the
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
        """ Tell the singleton to read a *different* JSON file.
            If the file is missing or invalid the previous file stays active. """
        old_path = self._store._file_path
        self._store._file_path = Path(path)
        try:
            self._store.reload()
        except Exception:
            self._store._file_path = old_path
            raise
        if self._lang not in self._store._data:
            self._lang = "en"

    def configure(self, language_file: str | Path | None = None, language: str | None = None) -> None:
        """ Used by the ModeTranslation app (and legacy Lightwand room args).
            Applies the file first and then the language. A bad file does not stop
            the language from being applied. Raises the first error after trying both. """
        first_error: Exception | None = None
        if language_file:
            try:
                self.set_file_path(language_file)
            except Exception as exc:
                first_error = exc
        if language:
            try:
                self.set_language(language)
            except Exception as exc:
                first_error = first_error or exc
        if first_error is not None:
            raise first_error

translations = Translations()