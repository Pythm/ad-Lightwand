""" Lightwand by Pythm

    @Pythm / https://github.com/Pythm
"""

__version__ = "2.4.0"

from appdaemon.plugins.hass.hassapi import Hass
import json
import os
from typing import List, Iterable, Set

from translations_lightmodes import translations
from weather_data import OutdoorWeather

from lightwand_utils import _parse_mode_and_room, cancel_timer_handler, cancel_listen_handler
from lightwand_builder import _convert_dict_to_light_spec
from lightwand_factory import build_light
from lightwand_config import LightSpec, Sensor

from lightwand_lights import Light
from lightwand_lights import MQTTLight
from lightwand_lights import ToggleLight

from ast_evaluator import safe_eval_logged

MOTION = ('on', 'open')
NOT_A_STATE = ('unavailable', 'unknown', None)
_legacy_language_warned:bool = False

class Room(Hass):

    def initialize(self):
        # Set first so terminate() works even if initialize stops early
        self.selector_input = None
        self.selector_input_options:list = []
        self._selector_echo:list = []
        self.weather = None
        self.json_storage = None

        self.mqtt = self.get_plugin_api('MQTT')
        # Namespaces for HASS and MQTT
        self.HASS_namespace:str = self.args.get('HASS_namespace', 'default')
        MQTT_namespace:str = self.args.get('MQTT_namespace', 'mqtt')

        self.roomlight:list = []

        # Legacy way of setting translations. The ModeTranslation app is the preferred way.
        if 'language_file' in self.args or 'lightwand_language' in self.args:
            global _legacy_language_warned
            if not _legacy_language_warned:
                _legacy_language_warned = True
                self.log(
                    "language_file and lightwand_language in a room app is deprecated since 2.3.0. "
                    "Move them to the ModeTranslation app (module: mode_translation) and add "
                    "'dependencies' on it. See the Lightwand README, 'Translating or Changing Modes'.",
                    level = 'WARNING'
                )
            try:
                translations.configure(
                    language_file = self.args.get('language_file', None),
                    language = self.args.get('lightwand_language', None)
                )
            except Exception as e:
                self.log(
                    f"Not able to set language_file {self.args.get('language_file', None)} / "
                    f"lightwand_language {self.args.get('lightwand_language', None)}: {e}",
                    level = 'WARNING'
                )

        self.LIGHT_MODE:str = 'none'
        # All known modes that the room can enter
        self.all_modes: Set[str] = {
            translations.automagical,
            translations.away,
            translations.off,
            translations.night,
            translations.custom,
            translations.fire,
            translations.false_alarm,
            translations.wash,
            translations.reset,
        }
        # Mode to apply when the bed is exited. None: automagical
        self.getOutOfBedMode = None
        self.LIGHT_MODE = translations.automagical

        night_motion:bool = False
        dim_while_motion:bool = False
        self.prevent_off_to_normal:bool = False
        self.prevent_night_to_morning:bool = False

        # Options defined in configurations
        self.roomtype = self.args.get('roomtype', 'normal')

        options = self.args.get('options', [])
        opts = set(options)
        if 'exclude_from_custom' in opts or self.roomtype in ('outdoor', 'bedroom'):
            self.all_modes.discard(translations.custom)
            self.all_modes.discard(translations.wash)

        night_motion      = 'night_motion'      in opts or self.roomtype == 'outdoor'
        dim_while_motion  = 'dim_while_motion'  in opts
        take_manual_control = 'take_manual_control' in opts or self.roomtype in ('livingroom', 'kitchen')
        verify_if_executed  = 'verify_if_executed' in opts
        self.prevent_off_to_normal   = 'prevent_off_to_normal' in opts or 'prevent_off_to_automagical' in opts
        self.prevent_night_to_morning = 'prevent_night_to_morning' in opts

        # Bedroom: time window where automagical/reset without room name does not end night
        self.night_lock_start:str = self.args.get('night_lock_start', '10:00:00')
        self.night_lock_end:str = self.args.get('night_lock_end', '05:00:00')

        # Reaction delay to mode
        self.mode_turn_off_delay:int = self.args.get('mode_turn_off_delay', 0)
        self.mode_turn_on_delay:int = self.args.get('mode_turn_on_delay',0)
        self.mode_delay_handler = None
        self._delay_map = {
            translations.away: self.mode_turn_off_delay,
            translations.off: self.mode_turn_off_delay,
            translations.night: self.mode_turn_off_delay,
            translations.automagical: self.mode_turn_on_delay,
            translations.morning: self.mode_turn_on_delay,
        }
        random_turn_on_delay:int = self.args.get('random_turn_on_delay',0)

        # Adaptive Lighting
        adaptive_switch:str = self.args.get('adaptive_switch', None)
        adaptive_sleep_mode:str = self.args.get('adaptive_sleep_mode', None)

        self.active_motion_sensors: Set[str] = set()

        # Presence detection
        self.trackers = [Sensor.from_yaml(item) for item in self.args.get('presence', [])]
        ishome = not self.trackers
        for tracker in self.trackers:
            self.listen_state(self.presence_change, tracker.sensor,
                namespace = self.HASS_namespace,
                tracker = tracker
            )
            if self.get_state(tracker.sensor, namespace = self.HASS_namespace) == 'home':
                ishome = True

        if not ishome:
            self.LIGHT_MODE = translations.away

        # Motion detection
        motion_sensors = [Sensor.from_yaml(item) for item in self.args.get('motion_sensors', [])]
        for sensor in motion_sensors:
            self.listen_state(self.motion_state, sensor.sensor,
                namespace = self.HASS_namespace,
                sensor = sensor
            )

        MQTT_motion_sensors = [Sensor.from_yaml(item) for item in self.args.get('MQTT_motion_sensors', [])]
        for sensor in MQTT_motion_sensors:
            self.mqtt.mqtt_subscribe(sensor.sensor)
            self.mqtt.listen_event(self.MQTT_motion_event, 'MQTT_MESSAGE',
                topic = sensor.sensor,
                namespace = MQTT_namespace,
                sensor = sensor
            )

        self.bed_sensors: list[Sensor] = self._parse_bed_sensors()

        # Weather sensors
        self.weather = OutdoorWeather(
            api = self,
            on_change = self.reactToChange,
            react_blocked = self._mode_delay_running,
            HASS_namespace = self.HASS_namespace,
            MQTT_namespace = MQTT_namespace,
            lux_sensor = self.args.get('OutLux_sensor'),
            lux_sensor_mqtt = self.args.get('OutLuxMQTT'),
            lux_sensor_2 = self.args.get('OutLux_sensor_2'),
            lux_sensor_2_mqtt = self.args.get('OutLuxMQTT_2'),
            room_lux_sensor = self.args.get('RoomLux_sensor'),
            room_lux_sensor_mqtt = self.args.get('RoomLuxMQTT'),
        )

        self.listen_sensors = self.args.get('listen_sensors', [])
        self.mediaplayers:dict = self.args.get('mediaplayers', [])

        for raw in self.args.get('MQTTLights', []):
            if 'enable_light_control' in raw:
                light_control_state = raw.get(str('light_control_state'), 'on')
                if self.get_state(raw['enable_light_control'], namespace = self.HASS_namespace) != light_control_state:
                    continue

            spec = _convert_dict_to_light_spec(raw)
            light = build_light(api = self,
                                spec = spec,
                                mqtt_namespace = MQTT_namespace,
                                hass_namespace = self.HASS_namespace,
                                mqtt_plugin = self.mqtt,
                                adaptive_switch = adaptive_switch,
                                adaptive_sleep_mode = adaptive_sleep_mode,
                                night_motion = night_motion,
                                dim_while_motion = dim_while_motion,
                                take_manual_control = take_manual_control,
                                verify_if_executed = verify_if_executed,
                                random_turn_on_delay = random_turn_on_delay,
                                weather = self.weather)
            self.roomlight.append(light)

        for raw in self.args.get('Lights', []):
            if 'enable_light_control' in raw:
                light_control_state = raw.get(str('light_control_state'), 'on')
                if self.get_state(raw['enable_light_control'], namespace = self.HASS_namespace) != light_control_state:
                    continue

            spec = _convert_dict_to_light_spec(raw)
            light = build_light(api = self,
                                spec = spec,
                                mqtt_namespace = MQTT_namespace,
                                hass_namespace = self.HASS_namespace,
                                mqtt_plugin = None,
                                adaptive_switch = adaptive_switch,
                                adaptive_sleep_mode = adaptive_sleep_mode,
                                night_motion = night_motion,
                                dim_while_motion = dim_while_motion,
                                take_manual_control = take_manual_control,
                                verify_if_executed = verify_if_executed,
                                random_turn_on_delay = random_turn_on_delay,
                                weather = self.weather)
            self.roomlight.append(light)

        for raw in self.args.get('ToggleLights', []):
            if 'enable_light_control' in raw:
                light_control_state = raw.get(str('light_control_state'), 'on')
                if self.get_state(raw['enable_light_control'], namespace = self.HASS_namespace) != light_control_state:
                    continue

            spec = _convert_dict_to_light_spec(raw)
            spec.toggle = raw.get('toggle', 3)
            spec.num_dim_steps = raw.get('num_dim_steps', 3)
            spec.toggle_speed = raw.get('toggle_speed', 1)
            spec.prewait_toggle = raw.get('prewait_toggle', 0)
            light = build_light(api = self,
                                spec = spec,
                                mqtt_namespace = MQTT_namespace,
                                hass_namespace = self.HASS_namespace,
                                mqtt_plugin = None,
                                adaptive_switch = adaptive_switch,
                                adaptive_sleep_mode = adaptive_sleep_mode,
                                night_motion = night_motion,
                                dim_while_motion = dim_while_motion,
                                take_manual_control = False,
                                verify_if_executed = False,
                                random_turn_on_delay = random_turn_on_delay,
                                weather = self.weather)
            self.roomlight.append(light)

        # Makes a list of all valid modes for room
        for light in self.roomlight:
            for mode in light.light_modes:
                if not mode.mode in self.all_modes:
                    self.all_modes.add(mode.mode)
                    modename, roomname = _parse_mode_and_room(mode.mode)
                    if  roomname is not None and roomname != str(self.name):
                        self.log(
                            f"Your mode name: {mode.mode} might get you into trouble. Please do not use mode names with underscore.\n"
                            "You can read more about this change in version 1.4.4 in the documentation. ",
                            level = 'WARNING'
                        )

        self.selector_input = self.args.get('selector_input', None)
        if self.selector_input is not None:
            selector_input_exclude_modes = self.args.get('selector_input_exclude_modes', [])
            self.run_in(self.setup_selector_input, 30, selector_input_exclude_modes = selector_input_exclude_modes)

        # Persistent storage for storing mode and lux data.
        # Written only here (new file) and in terminate() to spare SD cards.
        legacy_storage = None
        if 'json_path' in self.args:
            json_dir = str(self.args['json_path'])
            if not json_dir.endswith(os.sep):
                # Before 2.4.0 the file name was appended without a separator
                legacy_storage = f"{json_dir}{self.name}.json"
        else:
            json_dir = os.path.join(str(self.AD.config_dir), 'persistent', 'lightwand')
        self.json_storage = os.path.join(json_dir, f"{self.name}.json")

        storage = self.json_storage
        if (
            legacy_storage is not None
            and not os.path.exists(self.json_storage)
            and os.path.exists(legacy_storage)
        ):
            storage = legacy_storage
        lightwand_data = self._read_json(storage)
        if lightwand_data is None:
            self._write_json()
        else:
            self._restore_from_json(lightwand_data)
            if storage != self.json_storage:
                self._write_json()

        # Listen sensors for when to update lights
        for sensor in self.listen_sensors:
            self.listen_state(self.state_changed, sensor,
                namespace = self.HASS_namespace
            )

        # Media players for setting mediaplayer mode
        for mediaplayer in self.mediaplayers:
            delay = mediaplayer.get('delay', 0)
            self.listen_state(self.media_on, mediaplayer['mediaplayer'],
                new = 'on',
                old = 'off',
                namespace = self.HASS_namespace,
                mode = mediaplayer['mode']
            )
            self.listen_state(self.media_off, mediaplayer['mediaplayer'],
                new = 'off',
                old = 'on',
                duration = delay,
                namespace = self.HASS_namespace,
                mode = mediaplayer['mode']
            )

        # Verifies your room names
        modename, roomname = _parse_mode_and_room(str(self.name))
        if roomname is not None:
            self.log(
                f"Your app name: {self.name} might get you into trouble. Please do not use names with underscore.\n"
                "You can read more about this change in version 1.4.4 in the documentation.",
                level = 'WARNING'
            )

        # Sets lights at startup
        self.check_mediaplayers_off()

        """ This listens to events fired as MODE_CHANGE with data beeing mode = 'yourmode'
            self.fire_event('MODE_CHANGE', mode = 'normal')
            If you already have implemented someting similar in your Home Assistant setup you can easily change
            MODE_CHANGE in translation.json to receive whatever data you are sending """
        self.listen_event(self.mode_event, translations.MODE_CHANGE,
            namespace = self.HASS_namespace
        )

        # Initialize sensors with correct state:
        for sensor in motion_sensors:
            if self.get_state(sensor.sensor, namespace = self.HASS_namespace) in MOTION:
                motion_data:dict = {'occupancy': True}
                self._process_sensor(sensor, motion_data)


    def _parse_bed_sensors(self):
        raw = self.args.get('bed_sensors', [])
        parsed = []

        for entry in raw:
            if isinstance(entry, str):
                parsed.append(Sensor(sensor=entry))
            elif isinstance(entry, dict):
                parsed.append(Sensor(**entry))
            else:
                self.log(
                    f"bed_sensors entry must be a string or dict, got {type(entry)}: {entry}"
                )

        return parsed

    def setup_selector_input(self, **kwargs):
        """ Setup the selector input for the room mode """

        selector_input_exclude_modes = kwargs.get('selector_input_exclude_modes', [])
        exclude = {translations.fire, translations.false_alarm, translations.reset ,'presence'} | set(selector_input_exclude_modes)
        self.selector_input_options = [m for m in self._ordered_modes() if m not in exclude]

        self.call_service("input_select/set_options",
            entity_id = self.selector_input,
            options = self.selector_input_options,
            namespace = self.HASS_namespace
        )
        self.listen_state(self.mode_update_from_selector, self.selector_input,
            namespace = self.HASS_namespace
        )


        """ End initial setup for Room """

    def _ordered_modes(self) -> list:
        """ all_modes in a stable order: built-in modes first, then the light modes as configured. """

        ordered = [
            translations.automagical,
            translations.away,
            translations.off,
            translations.night,
            translations.custom,
            translations.fire,
            translations.false_alarm,
            translations.wash,
            translations.reset,
        ]
        for light in self.roomlight:
            ordered.extend(mode.mode for mode in light.light_modes)
        modes = [m for m in dict.fromkeys(ordered) if m in self.all_modes]
        return modes + sorted(m for m in self.all_modes if m not in modes)

    def _read_json(self, path:str):
        """ Returns the stored data, or None if there is no usable file. """

        try:
            with open(path, 'r') as json_read:
                lightwand_data = json.load(json_read)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as e:
            self.log(f"Ignoring {path}, not able to read it: {e}", level = 'WARNING')
            return None
        if not isinstance(lightwand_data, dict) or 'mode' not in lightwand_data:
            self.log(f"Ignoring {path}, it has no stored mode: {lightwand_data!r}", level = 'WARNING')
            return None
        return lightwand_data

    def _restore_from_json(self, lightwand_data:dict) -> None:
        mode = lightwand_data['mode']
        # Unknown modes (renamed, translation changed, 'normal' from before 2.1.0) and reset start as automagical
        if not isinstance(mode, str) or mode not in self.all_modes or mode == translations.reset:
            self.log(f"Stored mode {mode!r} is not a mode for {self.name}. Starting in {translations.automagical}", level = 'INFO')
            mode = translations.automagical
        self.LIGHT_MODE = mode

        # Stored lux is only a fallback until an own lux sensor has reported
        if 'lux' in lightwand_data and not self.weather._own_lux_reporting():
            try:
                self.weather.out_lux = float(lightwand_data['lux'])
            except (TypeError, ValueError):
                pass

    def _write_json(self) -> None:
        if getattr(self, 'json_storage', None) is None:
            return
        weather = getattr(self, 'weather', None)
        lightwand_data = {
            'mode' : getattr(self, 'LIGHT_MODE', translations.automagical),
            'lux' : weather.out_lux if weather is not None else None
        }
        tmp_storage = f"{self.json_storage}.tmp"
        try:
            os.makedirs(os.path.dirname(self.json_storage) or '.', exist_ok = True)
            with open(tmp_storage, 'w') as json_write:
                json.dump(lightwand_data, json_write, indent = 4)
            os.replace(tmp_storage, self.json_storage)
        except Exception as e:
            self.log(f"Not able to store to {self.json_storage} : {e}", level = 'WARNING')

    def terminate(self) -> None:
        """ Writes out data to persistent storage before terminating. """

        self._write_json()

        if getattr(self, 'selector_input', None) is not None:
            try:
                self.call_service("input_select/set_options",
                    entity_id = self.selector_input,
                    options = self.LIGHT_MODE,
                    namespace = self.HASS_namespace
                )
            except Exception as e:
                self.log(f"Not able to set options for {self.selector_input} : {e}", level = 'WARNING')

    def mode_event(self, event_name, data, **kwargs) -> None:
        """ New mode events. Updates lights if conditions are met. """

        mode = data.get('mode') if isinstance(data, dict) else None
        if not isinstance(mode, str) or not mode:
            self.log(f"{event_name} without a valid mode: {data}", level = 'DEBUG')
            return

        modename, roomname = _parse_mode_and_room(mode)
        if roomname is not None and roomname != str(self.name):
            return

        if modename == translations.fire:
            # Fire is applied at once, regardless of any block, bed or delay
            self._apply_mode(modename)
            return

        if modename not in self.all_modes:
            if modename == translations.morning:
                modename = translations.automagical
            else:
                return

        if (
            self.LIGHT_MODE == translations.off
            and modename in (translations.automagical, translations.morning)
            and self.prevent_off_to_normal
        ):
            return

        if self.LIGHT_MODE.startswith(translations.night):
            # A full block on automations to take room out of night
            if (
                modename in (translations.morning, translations.automagical)
                and self.prevent_night_to_morning
            ):
                return
            # A block to prevent user or automation to take room out of night unless _roomname is provided
            if (
                modename in (translations.automagical, translations.reset) and
                roomname is None and
                self.roomtype == 'bedroom' and
                self.now_is_between(self.night_lock_start, self.night_lock_end)
            ):
                return
            # Waiting for bedsensors to be empty before ending night
            if (
                not modename.startswith(translations.night)
                and modename != translations.off
                and self._bed_occupied()
            ):
                self._start_bed_wait(modename)
                return

        self._apply_mode(modename)

    def _apply_mode(self, modename:str) -> None:
        """ Sets the room mode from a mode event, with the mode delay if defined. """

        self._cancel_bed_wait()
        cancel_timer_handler(ADapi = self, handler = self.mode_delay_handler)
        self.mode_delay_handler = None

        self.LIGHT_MODE = modename

        delay = self._delay_map.get(modename, 0)
        if delay > 0:
            self.mode_delay_handler = self.run_in(self.set_Mode_with_delay, delay)
            return

        self.reactToChange()

        if modename == translations.reset:
            self.LIGHT_MODE = translations.automagical

        self._set_selector_input()

    def _set_selector_input(self) -> None:
        # Options are empty until setup_selector_input has run
        if self.selector_input is not None and self.LIGHT_MODE in self.selector_input_options:
            # Remember what Lightwand wrote, so the state change it causes is not taken as a user selection
            if not self._selector_echo or self._selector_echo[-1] != self.LIGHT_MODE:
                self._selector_echo.append(self.LIGHT_MODE)
            try:
                self.call_service("input_select/select_option",
                    entity_id = self.selector_input,
                    option = self.LIGHT_MODE,
                    namespace = self.HASS_namespace
                )
            except Exception as e:
                self.log(f"Could not set mode to {self.selector_input}. Error: {e}", level = 'DEBUG')

    def mode_update_from_selector(self, entity, attribute, old, new, kwargs) -> None:
        """ Updates mode based on HA selector update. """

        if new in NOT_A_STATE or not isinstance(new, str):
            self.log(f"Ignoring {new} from {entity}", level = 'DEBUG')
            return
        if new in self._selector_echo:
            # Written by Lightwand. Echoes arrive in the order they were written
            del self._selector_echo[:self._selector_echo.index(new) + 1]
            return
        self._selector_echo.clear()

        modename, roomname = _parse_mode_and_room(new)
        if roomname is not None and roomname != str(self.name):
            return
        if modename not in self.all_modes:
            self.log(f"Ignoring {new} from {entity}: not a mode for {self.name}", level = 'DEBUG')
            return
        if modename == translations.automagical:
            modename = translations.reset
        if modename == self.LIGHT_MODE:
            return

        self._cancel_bed_wait()
        self.LIGHT_MODE = modename
        self.reactToChange()

        if modename == translations.reset:
            self.LIGHT_MODE = translations.automagical

    def set_Mode_with_delay(self, kwargs):
        """ Sets mode with defined delay. """

        cancel_timer_handler(ADapi = self, handler = self.mode_delay_handler)
        self.mode_delay_handler = None

        self.reactToChange()

        if self.LIGHT_MODE == translations.reset:
            self.LIGHT_MODE = translations.automagical

        self._set_selector_input()

        # Motion and presence
    def motion_state(self, entity, attribute, old, new, **kwargs) -> None:
        """ Listens to motion state. """

        sensor: Sensor = kwargs['sensor']
        if new in MOTION:
            motion_data:dict = {'occupancy': True}
        else:
            motion_data:dict = {'occupancy': False}

        self._process_sensor(sensor, motion_data)

    def MQTT_motion_event(self, event_name, data, **kwargs) -> None:
        """ Listens to motion MQTT event.  """

        try:
            motion_data = json.loads(data['payload'])
        except (KeyError, TypeError, ValueError) as e:
            self.log(f"Not able to read motion payload {data}: {e}", level = 'DEBUG')
            return
        if not isinstance(motion_data, dict):
            self.log(f"Motion payload is not a json object: {data}", level = 'DEBUG')
            return
        sensor: Sensor = kwargs['sensor']

        """ Test your MQTT settings. Uncomment line below to get logging when motion detected """
        #self.log(f"Motion detected: {sensor} Motion Data: {motion_data}") # FOR TESTING ONLY

        self._process_sensor(sensor, motion_data)

    def _process_sensor(self, sensor: Sensor, motion_data):
        match motion_data:
            case {'occupancy': True}:
                self._activate(sensor)

            case {'occupancy': False}:
                if sensor.last_state is not False:
                    self._deactivate(sensor)

            case {'value': 8}:
                self._activate(sensor)

            case {'value': 0}:
                if sensor.last_state is not False:
                    self._deactivate(sensor)

            case {'contact': False}:
                self._activate(sensor)

            case {'contact': True}:
                if sensor.last_state is not False:
                    self._deactivate(sensor)

    def _activate(self, sensor: Sensor) -> None:
        constraints_ok = True
        if sensor.constraints is not None:
            constraints_ok = safe_eval_logged(sensor.sensor, sensor.constraints, {'self': self}, self.log)

        if not constraints_ok:
            return

        self.active_motion_sensors.add(sensor.sensor)
        cancel_timer_handler(ADapi = self, handler = sensor.handler)
        sensor.handler = None
        sensor.last_state = True
        self._newMotion()

    def _deactivate(self, sensor: Sensor) -> None:
        cancel_timer_handler(ADapi = self, handler = sensor.handler)
        sensor.handler = None
        sensor.last_state = False
        sensor_delay:int = getattr(sensor, 'delay', 60)
        sensor.handler = self.run_in(self.MotionEnd, sensor_delay, sensor = sensor)

    def _newMotion(self) -> None:
        if not self.check_mediaplayers_off():
            return
        is_night_mode = self.LIGHT_MODE.startswith(translations.night)

        for light in self.roomlight:
            use_motion = self._decide_to_activate_motion(
                light,
                is_night_mode
            )
            if use_motion:
                light.setMotion(lightmode=self.LIGHT_MODE)

    def out_of_bed(self, entity, attribute, old, new, **kwargs) -> None:
        """ Check if all bed sensors are empty and if so change to the pending mode. """

        if self._bed_occupied():
            return
        modename = self.getOutOfBedMode or translations.automagical
        self._cancel_bed_wait()

        self.LIGHT_MODE = modename
        self.reactToChange()

        if self.LIGHT_MODE == translations.reset:
            self.LIGHT_MODE = translations.automagical

        self._set_selector_input()

    def _bed_occupied(self) -> bool:
        """Return True if any bed sensor reports 'on' and its constraints are met."""

        return any(
            self.get_state(sensor.sensor, namespace = self.HASS_namespace) == 'on'
            and safe_eval_logged(sensor.sensor, sensor.constraints, {'self': self}, self.log)
            for sensor in self.bed_sensors
        )

    def _start_bed_wait(self, modename:str) -> None:
        """ Room stays in night until the bed is exited, then applies *modename* (newest wins). """

        self._cancel_bed_wait()
        for sensor in self.bed_sensors:
            sensor.handler = self.listen_state(
                self.out_of_bed,
                sensor.sensor,
                new = 'off',
                duration = sensor.delay,
                namespace = self.HASS_namespace,
                sensor = sensor,
            )
        self.getOutOfBedMode = modename

    def _cancel_bed_wait(self) -> None:
        """ Ends waiting for the bed to be exited and drops the pending mode. """

        for sensor in self.bed_sensors:
            cancel_listen_handler(ADapi = self, handler = sensor.handler)
            sensor.handler = None
        self.getOutOfBedMode = None

    def presence_change(self, entity, attribute, old, new, **kwargs) -> None:
        """ Listens to tracker/person state change. """

        tracker: Sensor = kwargs['tracker']

        # A tracker that drops out (HA restart, glitch) has not left
        if new in NOT_A_STATE:
            return

        if new == 'home':
            constraints_ok = True
            if tracker.constraints is not None:
                constraints_ok = safe_eval_logged(tracker.sensor, tracker.constraints, {'self': self}, self.log)

            if self.LIGHT_MODE in (translations.automagical, translations.away) and self.check_mediaplayers_off():
                self.LIGHT_MODE = translations.automagical
                self._set_selector_input()

            if not constraints_ok or 'presence' not in self.all_modes:
                self.reactToChange()
                return

            else:
                self.active_motion_sensors.add(tracker.sensor)
                cancel_timer_handler(ADapi = self, handler = tracker.handler)
                tracker.handler = None
                for light in self.roomlight:
                    light.setLightMode(lightmode = 'presence')
                tracker_delay:int = getattr(tracker, 'delay', 300)
                tracker.handler = self.run_in(self.MotionEnd, tracker_delay, sensor = tracker)
                return

        elif old == 'home':
            for tracker in self.trackers:
                if self.get_state(tracker.sensor, namespace = self.HASS_namespace) == 'home':
                    self.reactToChange()
                    return
            if self.LIGHT_MODE not in (translations.off, translations.custom):
                self._cancel_bed_wait()
                self.LIGHT_MODE = translations.away
                self.reactToChange()
                self._set_selector_input()
                return

        self.reactToChange()

    def MotionEnd(self, **kwargs) -> None:
        """ Motion / Presence countdown ended. Turns lights back to current mode. """

        sensor: Sensor = kwargs['sensor']
        self.active_motion_sensors.discard(sensor.sensor)
        cancel_timer_handler(ADapi = self, handler = sensor.handler)
        sensor.handler = None
        
        if self.active_motion_sensors:
            return
        # Motion has ended also when a media player is on
        for light in self.roomlight:
            light.motion = False
            light.last_motion_brightness = 0
        if self.check_mediaplayers_off():
            for light in self.roomlight:
                light.setLightMode(lightmode = self.LIGHT_MODE)

    def state_changed(self, entity, attribute, old, new, kwargs) -> None:
        """ Update light settings when state of a HA entity is updated. """

        self.reactToChange()

    def _mode_delay_running(self) -> bool:
        return self.mode_delay_handler is not None and self.timer_running(self.mode_delay_handler)

    def reactToChange(self):
        """ This function is called when a sensor has new values and based upon mode and if motion is detected,
            it will either call 'setMotion' or 'setLightMode' to adjust lights based on the updated sensors. """

        if not self.check_mediaplayers_off():
            return

        is_night_mode = self.LIGHT_MODE.startswith(translations.night)

        for light in self.roomlight:
            use_motion = self._decide_to_activate_motion(
                light,
                is_night_mode
            )
            if use_motion:
                light.setMotion(lightmode=self.LIGHT_MODE)
            else:
                light.setLightMode(lightmode = self.LIGHT_MODE)

    def _decide_to_activate_motion(self,
                                   light,
                                   is_night_mode: bool,
    ) -> bool:
        """ Decide which mode to use for a single light. """

        if is_night_mode and not light.night_motion:
            return False

        if self.LIGHT_MODE in (translations.off, translations.custom):
            return False

        if self.LIGHT_MODE == translations.away and self.roomtype not in ('outdoor', 'hallway'):
            return False

        if self.active_motion_sensors:
            return light.motionlight

        return False

        # Media Player / sensors
    def media_on(self, entity, attribute, old, new, kwargs) -> None:
        if self.LIGHT_MODE == translations.morning:
            self.LIGHT_MODE = translations.automagical
            self._set_selector_input()
        self.check_mediaplayers_off()

    def media_off(self, entity, attribute, old, new, kwargs) -> None:
        self.reactToChange()

    def check_mediaplayers_off(self) -> bool:
        """ Returns true if media player sensors is off or self.LIGHT_DATA != 'normal'/'night'.
            If not it updates lightmode to the first detected media player. """

        if self.LIGHT_MODE in (translations.automagical, translations.reset) or self.LIGHT_MODE.startswith(translations.night):
            for mediaplayer in self.mediaplayers:
                if self.get_state(mediaplayer['mediaplayer'], namespace = self.HASS_namespace) not in ('off', 'idle', 'paused', 'unavailable', 'unknown'):
                    for light in self.roomlight:
                        if ((light.checkConditions(light.conditions) and light.checkLuxConstraints()) or
                            light.current_keep_on_Condition
                        ):
                            force_change = self.LIGHT_MODE == translations.reset
                            light.setLightMode(lightmode = mediaplayer['mode'], force_change = force_change)
                        else:
                            light.turn_off_lights()

                    return False
        return True