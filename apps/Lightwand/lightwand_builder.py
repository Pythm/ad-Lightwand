from typing import Any, Dict
from lightwand_config import LightSpec, Automation, LightProperties, LightMode
import copy

def automation_from_obj(obj: Any) -> Automation:
    if isinstance(obj, str):
        return Automation(state=obj)
    if isinstance(obj, dict):
        return Automation(**obj)
    raise ValueError(f"Unsupported automation entry: {obj!r}")

def _build_light_properties(d: dict) -> LightProperties:
    data = d.copy()
    return LightProperties(**data)

def _build_light_mode(d: dict) -> LightMode:
    data = d.copy()
    mode_name: str = data.pop('mode', 'none')
    noMotion: bool = data.pop('noMotion', False)
    automs: Optional[List[Automation]] = None
    light_properties: Optional[LightProperties] = None
    if 'automations' in data:
        raw_automs = data.pop('automations')
        if raw_automs:
            automs = [automation_from_obj(a) for a in raw_automs]
        else:
            automs = None
    elif data:
        light_properties = LightProperties(**data)
    else:
        light_properties = LightProperties()
    lm = LightMode(
        mode=mode_name,
        noMotion=noMotion,
        light_properties=light_properties,
        automations=automs,
        original_automations=copy.deepcopy(automs) if automs else None
    )
    return lm

def _convert_dict_to_light_spec(d: dict) -> LightSpec:
    base: dict[str, Any] = {
        k: v for k, v in d.items()
        if k not in (
            'automations',
            'motionlights',
            'light_modes',
            'motion_sensors',
            'options',
            'enable_light_control',
            'light_control_state',
            'toggle',
            'num_dim_steps',
            'toggle_speed',
            'prewait_toggle',
        )
    }
    # --- 1. Automations (time‑based list) ---
    if 'automations' in d:
        base['automations'] = [automation_from_obj(a) for a in d['automations']]
    else:
        base['automations'] = None
    # --- 2. Motion Lights (could be a list of Automations or a LightProperties) ---
    if 'motionlights' in d:
        ml_raw = d['motionlights']
        if isinstance(ml_raw, list):
            base['motionlights'] = [automation_from_obj(a) for a in ml_raw]
        elif isinstance(ml_raw, dict):
            base['motionlights'] = _build_light_properties(ml_raw)
        else:
            base['motionlights'] = LightProperties()
    else:
        base['motionlights'] = None
    # --- 3. Light Modes (named modes) ---
    if 'light_modes' in d:
        base['light_modes'] = [_build_light_mode(m) for m in d['light_modes']]
    else:
        base['light_modes'] = None

    if 'options' in d:
        opt = d['options']
        if isinstance(opt, list):
            opt = {k: True for k in opt}
        base['options'] = opt

    return LightSpec(**base)