from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Literal, Optional, Union
from pydantic import BaseModel, Field, root_validator, ConfigDict

State = Literal['turn_off', 'turn_on', 'adjust', 'lux_controlled', 'manual', 'pass', 'none', 'adaptive']

def filter_none(d: dict) -> dict:
    """Return a new dict that contains only the keys with non-None values."""

    return {k: v for k, v in d.items() if v is not None}

class Sensor(BaseModel):
    sensor: str
    delay: int = 0
    constraints: Optional[str] = None
    handler: Any | None = None

    @classmethod
    def from_yaml(cls, d: Mapping[str, Any]) -> "Sensor":
        d = dict(d)
        if "motion_sensor" in d:
            d["sensor"] = d.pop("motion_sensor")
        if "tracker" in d:
            d["sensor"] = d.pop("tracker")
        if "motion_constraints" in d:
            d["constraints"] = d.pop("motion_constraints")
        if "tracker_constraints" in d:
            d["constraints"] = d.pop("tracker_constraints")
        return cls(**d)

@dataclass
class LightMode:
    mode: Optional[str] = None
    offset: int = 0
    state: State = 'none'
    light_data: Optional[Dict[str, Any]] = None
    automations: Optional[List[Automation]] = None
    original_automations: Optional[List[Automation]] = None
    toggle: Optional[int] = None
    max_brightness_pct: Optional[int] = None
    min_brightness_pct: Optional[int] = None
    noMotion: bool = False

    def _get_from_light_data(self, *keys: str) -> Any:
        if not self.light_data:
            return None
        for k in keys:
            if k in self.light_data:
                return self.light_data[k]
        return None

    def _set_to_light_data(self, value: Any, *keys: str) -> None:
        if self.light_data is None:
            self.light_data = {}
        for k in keys:
            if k in self.light_data:
                self.light_data[k] = value
                return
        self.light_data[keys[0]] = value

    @property
    def brightness(self) -> Optional[int]:
        raw = self._get_from_light_data("brightness", "value")
        return int(raw) if raw is not None else None

    @brightness.setter
    def brightness(self, value: int) -> None:
        self._set_to_light_data(value, "brightness", "value")

    def brightness_kwargs(self) -> dict:
        """Return a dict with only the brightness settings that are set."""

        return filter_none({
            'max_brightness': self.max_brightness_pct,
            'min_brightness': self.min_brightness_pct,
        })

    def resolve_brightness_to_255(self) -> int:
        """ Helper to convert a brightness into a comparable 0-255 integer. """

        if self.state == 'adaptive' and self.max_brightness_pct is not None:
            return int((self.max_brightness_pct / 100.0) * 255)

        if self.brightness is not None:
            return self.brightness

        return 0

@dataclass(init=False)
class Automation:
    time: str = '00:00:00'
    orLater: Optional[str] = None
    stoptime: str = '00:00:00'
    dimrate: Optional[int] = None
    fixed: bool = False

    light_mode: LightMode = field(default_factory=LightMode, init=False)

    def __init__(self, **kwargs):
        # split into automation‑ and light‑mode‑keywords
        auto_kwargs, lm_kwargs = {}, {}
        for k, v in kwargs.items():
            if k in Automation.__dataclass_fields__:
                auto_kwargs[k] = v
            else:
                lm_kwargs[k] = v

        object.__setattr__(self, 'time', auto_kwargs.get('time', '00:00:00'))
        object.__setattr__(self, 'orLater', auto_kwargs.get('orLater'))
        object.__setattr__(self, 'stoptime', auto_kwargs.get('stoptime', '00:00:00'))
        object.__setattr__(self, 'dimrate', auto_kwargs.get('dimrate'))
        object.__setattr__(self, 'fixed', auto_kwargs.get('fixed', False))

        self.light_mode = LightMode(**lm_kwargs)

@dataclass
class LightSpec:
    lights: List[str]
    automations: List[Automation] = field(default_factory=list)
    motionlights: Optional[Union[List[Automation], LightMode]] = None
    light_modes: Optional[List[LightMode]] = None
    lux_constraint: Optional[float] = None
    room_lux_constraint: Optional[float] = None
    conditions: Optional[List[str]] = None
    keep_on_conditions: Optional[List[str]] = None
    options: Optional[List[str]] = None   # exclude_from_custom, night_motion, dim_while_motion
    adaptive_switch: Optional[str] = None
    adaptive_sleep_mode: Optional[str] = None