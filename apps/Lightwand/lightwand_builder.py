from typing import Any, Dict
from lightwand_config import LightSpec, Automation, LightMode

def automation_from_obj(obj: Any) -> Automation:

    if isinstance(obj, str):
        return Automation(state=obj)
    if isinstance(obj, dict):
        return Automation(**obj)

    raise ValueError(f"Unsupported automation entry: {obj!r}")


def _build_light_mode(d: dict, default_name: str = 'none') -> LightMode:
    data = d.copy()
    if 'mode' not in data:
        data['mode'] = default_name
    if 'automations' in data:
        raw_automs = data.pop('automations')
        if raw_automs:
            data['automations'] = [automation_from_obj(a) for a in raw_automs]
        else:
            data['automations'] = None
    return LightMode(**data)


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

    # --- 2. Motion Lights (could be a list of Automations or a LightMode) ---
    if 'motionlights' in d:
        ml_raw = d['motionlights']
        if isinstance(ml_raw, list):
            base['motionlights'] = [automation_from_obj(a) for a in ml_raw]
        elif isinstance(ml_raw, dict):
            base['motionlights'] = _build_light_mode(ml_raw, default_name='motion')
        else:
            base['motionlights'] = LightMode(mode='motion')
    else:
        base['motionlights'] = None

    # --- 3. Light Modes (named modes) ---
    if 'light_modes' in d:
        base['light_modes'] = [_build_light_mode(m) for m in d['light_modes']]
    else:
        base['light_modes'] = None

    if 'options' in d:
        base['options'] = d['options']

    return LightSpec(**base)