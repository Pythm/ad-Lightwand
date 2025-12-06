from typing import List
from lightwand_config import LightSpec
from lightwand_lights import Light
from lightwand_lights import MQTTLight
from lightwand_lights import ToggleLight

def build_light(api,
                spec: LightSpec,
                mqtt_namespace: str,
                hass_namespace: str,
                mqtt_plugin,
                adaptive_switch,
                adaptive_sleep_mode,
                night_motion,
                dim_while_motion,
                random_turn_on_delay,
                weather) -> Light:

    light_spec = {
        'lights': spec.lights,
        'light_modes': spec.light_modes,
        'automations': spec.automations,
        'motionlight': spec.motionlights,
        'lux_constraint': spec.lux_constraint,
        'room_lux_constraint': spec.room_lux_constraint,
        'conditions': spec.conditions,
        'keep_on_conditions': spec.keep_on_conditions,
        'HASS_namespace': hass_namespace,
        'night_motion': spec.options.get('night_motion', night_motion) if spec.options else night_motion,
        'dim_while_motion': spec.options.get('dim_while_motion', dim_while_motion) if spec.options else dim_while_motion,
        'random_turn_on_delay': random_turn_on_delay,
        'adaptive_switch': spec.adaptive_switch or adaptive_switch,
        'adaptive_sleep_mode': spec.adaptive_sleep_mode or adaptive_sleep_mode,
        'weather': weather,
    }

    if mqtt_plugin is not None:
        return MQTTLight(api,
            **light_spec,
            MQTT_namespace=mqtt_namespace,
            mqtt_plugin=mqtt_plugin,
        )

    if getattr(spec, 'toggle', None):
        return ToggleLight(api,
            **light_spec,
            toggle=spec.toggle,
            num_dim_steps=spec.num_dim_steps,
            toggle_speed=spec.toggle_speed,
            prewait_toggle=spec.prewait_toggle,
        )

    return Light(api, **light_spec)