""" Lightwand by Pythm

    @Pythm / https://github.com/Pythm
"""

__version__ = "2.0.0"

from appdaemon.plugins.hass.hassapi import Hass
import json
import os
from typing import List, Iterable, Set

from translations_lightmodes import translations
from weather_data import LightwandWeather

from lightwand_utils import _parse_mode_and_room
from lightwand_builder import _convert_dict_to_light_spec
from lightwand_factory import build_light
from lightwand_config import LightSpec, MotionSensor, TrackerSensor

from lightwand_lights import Light
from lightwand_lights import MQTTLight
from lightwand_lights import ToggleLight

from ast_evaluator import safe_eval

MOTION = ('on', 'open')

class Room(Hass):

    def initialize(self):
        self.mqtt = self.get_plugin_api("MQTT")
        # Namespaces for HASS and MQTT
        HASS_namespace:str = self.args.get('HASS_namespace', 'default')
        MQTT_namespace:str = self.args.get('MQTT_namespace', 'mqtt')

        self.roomlight:list = []

        if 'language_file' in self.args:
            language_file = self.args['language_file']
            translations.set_file_path(language_file)
        if 'lightwand_language' in self.args:
            user_lang = self.args['lightwand_language']
            translations.set_language(user_lang)

        self.LIGHT_MODE:str = 'none'
        # All known modes that the room can enter
        self.all_modes: Set[str] = {
            translations.normal,
            translations.away,
            translations.off,
            translations.night,
            translations.custom,
            translations.fire,
            translations.false_alarm,
            translations.wash,
            translations.reset,
        }
        self.getOutOfBedMode:str = translations.normal

        night_motion:bool = False
        dim_while_motion:bool = False
        self.prevent_off_to_normal:bool = False
        self.prevent_night_to_morning:bool = False

        # Options defined in configurations
        if 'options' in self.args:
            if 'exclude_from_custom' in self.args['options']:
                self.all_modes.discard(translations.custom)
                self.all_modes.discard(translations.wash)
            night_motion = 'night_motion' in self.args['options']
            dim_while_motion = 'dim_while_motion' in self.args['options']
            self.prevent_off_to_normal = 'prevent_off_to_normal' in self.args['options']
            self.prevent_night_to_morning = 'prevent_night_to_morning' in self.args['options']

        self.mode_turn_off_delay:int = self.args.get('mode_turn_off_delay', 0)
        self.mode_turn_on_delay:int = self.args.get('mode_turn_on_delay',0)
        self.mode_delay_handler = None
        random_turn_on_delay:int = self.args.get('random_turn_on_delay',0)

        adaptive_switch:str = self.args.get('adaptive_switch', None)
        adaptive_sleep_mode:str = self.args.get('adaptive_sleep_mode', None)

        # Presence detection
        raw_presence = self.args.get('presence', [])
        self.presence: List[TrackerSensor] = [
            TrackerSensor(**item) for item in raw_presence
        ]
        self.trackerhandle = None
        ishome = False
        for tracker in self.presence:
            self.listen_state(self.presence_change, tracker.tracker,
                namespace = HASS_namespace,
                tracker = tracker
            )
            if self.get_state(tracker.tracker) == 'home':
                ishome = True

        if not ishome:
            self.LIGHT_MODE = translations.away

        # Motion detection
        self.motion_handler = None
        self.active_motion_sensors: Set[str] = set()

        raw_motion = self.args.get('motion_sensors', [])
        motion_sensors: List[MotionSensor] = [
            MotionSensor(**item) for item in raw_motion
        ]
        for sensor in motion_sensors:
            self.listen_state(self.motion_state, sensor.motion_sensor,
                namespace = HASS_namespace,
                sensor = sensor
            )

        raw_motion = self.args.get('MQTT_motion_sensors', [])
        MQTT_motion_sensors: List[MotionSensor] = [
            MotionSensor(**item) for item in raw_motion
        ]
        for sensor in MQTT_motion_sensors:
            self.mqtt.mqtt_subscribe(sensor.motion_sensor)
            self.mqtt.listen_event(self.MQTT_motion_event, "MQTT_MESSAGE",
                topic = sensor.motion_sensor,
                namespace = MQTT_namespace,
                sensor = sensor
            )

        # Weather sensors
        self.weather = LightwandWeather(
            api = self,
            HASS_namespace = HASS_namespace,
            MQTT_namespace = MQTT_namespace,
            lux_sensor = self.args.get('OutLux_sensor'),
            lux_sensor_mqtt = self.args.get('OutLuxMQTT'),
            lux_sensor_2 = self.args.get('OutLux_sensor_2'),
            lux_sensor_2_mqtt = self.args.get('OutLuxMQTT_2'),
            room_lux_sensor = self.args.get('RoomLux_sensor'),
            room_lux_sensor_mqtt = self.args.get('RoomLuxMQTT'),
        )

        self.bed_sensors:list = self.args.get('bed_sensors', [])
        self.listen_sensors = self.args.get('listen_sensors', [])
        self.mediaplayers:dict = self.args.get('mediaplayers', [])

        for raw in self.args.get('MQTTLights', []):
            if 'enable_light_control' in raw:
                if self.get_state(raw['enable_light_control']) == 'off':
                    continue

            spec = _convert_dict_to_light_spec(raw)
            spec.mqtt_topic = raw.get('mqtt_topic', True)
            light = build_light(self,
                                spec,
                                MQTT_namespace,
                                HASS_namespace,
                                self.mqtt,
                                adaptive_switch,
                                adaptive_sleep_mode,
                                night_motion,
                                dim_while_motion,
                                random_turn_on_delay,
                                self.weather)
            self.roomlight.append(light)

        for raw in self.args.get('Lights', []):
            if 'enable_light_control' in raw:
                if self.get_state(raw['enable_light_control']) == 'off':
                    continue

            spec = _convert_dict_to_light_spec(raw)
            light = build_light(self,
                                spec,
                                MQTT_namespace,
                                HASS_namespace,
                                self.mqtt,
                                adaptive_switch,
                                adaptive_sleep_mode,
                                night_motion,
                                dim_while_motion,
                                random_turn_on_delay,
                                self.weather)
            self.roomlight.append(light)

        for raw in self.args.get('ToggleLights', []):
            if 'enable_light_control' in raw:
                if self.get_state(raw['enable_light_control']) == 'off':
                    continue

            spec = _convert_dict_to_light_spec(raw)
            spec.toggle = raw.get('toggle', 3)
            spec.num_dim_steps = raw.get('num_dim_steps', 3)
            spec.toggle_speed = raw.get('toggle_speed', 1)
            spec.prewait_toggle = raw.get('prewait_toggle', 0)
            light = build_light(self,
                                spec,
                                MQTT_namespace,
                                HASS_namespace,
                                self.mqtt,
                                adaptive_switch,
                                adaptive_sleep_mode,
                                night_motion,
                                dim_while_motion,
                                random_turn_on_delay,
                                self.weather)
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

        self.usePersistentStorage:bool = False

        self.selector_input = self.args.get("selector_input", None)
        if self.selector_input is not None:
            self.listen_state(self.mode_update_from_selector, self.selector_input,
                namespace = HASS_namespace
            )
            self.LIGHT_MODE = self.get_state(self.selector_input, namespace = HASS_namespace)

            input_select_state = self.get_state(self.selector_input, attribute="all")
            current_options = input_select_state["attributes"].get("options", [])
            self.selector_input_options = list(current_options)
            
            valid_modes = [m for m in self.all_modes if m not in ("fire", "false-alarm")]

            if current_options != valid_modes:
                self.call_service("input_select/set_options",
                    entity_id = self.selector_input,
                    options = self.selector_input_options,
                    namespace = HASS_namespace
                )

        else:
            # Persistent storage for storing mode and lux data
            self.usePersistentStorage = True
            if 'json_path' in self.args:
                self.json_storage = self.args['json_path']
            else:
                self.json_storage:str = f"{self.AD.config_dir}/persistent/lightwand/"
                if not os.path.exists(self.json_storage):
                    os.makedirs(self.json_storage)
            self.json_storage += f"{self.name}.json"
            lightwand_data:dict = {}
            try:
                with open(self.json_storage, 'r') as json_read:
                    lightwand_data = json.load(json_read)
            except FileNotFoundError:
                lightwand_data = {"mode" : translations.normal,}
                with open(self.json_storage, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)

            self.LIGHT_MODE = lightwand_data['mode']

        # Listen sensors for when to update lights
        for sensor in self.listen_sensors:
            self.listen_state(self.state_changed, sensor,
                namespace = HASS_namespace
            )

        # Media players for setting mediaplayer mode
        for mediaplayer in self.mediaplayers:
            delay = mediaplayer.get('delay', 0)
            self.listen_state(self.media_on, mediaplayer['mediaplayer'],
                new = 'on',
                old = 'off',
                namespace = HASS_namespace,
                mode = mediaplayer['mode']
            )
            self.listen_state(self.media_off, mediaplayer['mediaplayer'],
                new = 'off',
                old = 'on',
                duration = delay,
                namespace = HASS_namespace,
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
            MODE_CHANGE in translation.json to receive whatever data you are sending            
        """
        self.listen_event(self.mode_event, translations.MODE_CHANGE,
            namespace = HASS_namespace
        )

        """ End initial setup for Room """

    def terminate(self) -> None:
        """ Writes out data to persistent storage before terminating. """

        if self.usePersistentStorage:
            try:
                #with open(self.json_storage, 'r') as json_read:
                #    lightwand_data = json.load(json_read)

                #lightwand_data.update(
                #    {"mode" : self.LIGHT_MODE}
                #)
                lightwand_data: dict = {"mode" : self.LIGHT_MODE}
                with open(self.json_storage, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)
            except FileNotFoundError:
                lightwand_data = {"mode" : self.LIGHT_MODE}
                with open(self.json_storage, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)

    def mode_event(self, event_name, data, **kwargs) -> None:
        """ New mode events. Updates lights if conditions are met. """

        modename, roomname = _parse_mode_and_room(data['mode'])
        if roomname is not None and roomname != str(self.name):
            return

        if (
            self.LIGHT_MODE == translations.off
            and modename == translations.normal
            and self.prevent_off_to_normal
        ):
            return

        if modename not in self.all_modes:
            if modename == translations.morning:
                modename = translations.normal
            else:
                return

        # Check if old light mode is night and bed is occupied.
        if self.LIGHT_MODE.startswith(translations.night):
            if (
                modename in (translations.morning, translations.normal)
                and self.prevent_night_to_morning
            ):
                return
            if modename not in (translations.night, translations.off, translations.reset):
                if self._bed_occupied():
                    for bed_sensor in self.bed_sensors:
                        if self.get_state(bed_sensor) == 'on':
                            self._listen_out_of_bed(bed_sensor)
                    return

        self.LIGHT_MODE = modename

        if self.mode_turn_off_delay > 0:
            delay_map = {
                translations.away: self.mode_turn_off_delay,
                translations.off: self.mode_turn_off_delay,
                translations.night: self.mode_turn_off_delay,
                translations.normal: self.mode_turn_on_delay,
                translations.morning: self.mode_turn_on_delay,
            }

            delay = delay_map.get(modename, 0)
            if delay:
                self.mode_delay_handler = self.run_in(self.set_Mode_with_delay, self.mode_turn_off_delay)
                return

        self.reactToChange()

        if modename == translations.reset:
            self.LIGHT_MODE = translations.normal

        self._set_selector_input()

    def _set_selector_input(self) -> None:
        if self.selector_input is not None and self.LIGHT_MODE in self.selector_input_options:
            try:
                self.call_service("input_select/select_option",
                    entity_id = self.selector_input,
                    option = self.LIGHT_MODE,
                    namespace = self.namespace
                )
            except Exception as e:
                self.log(f"Could not set mode to {self.selector_input}. Error: {e}", level = 'DEBUG')

    def mode_update_from_selector(self, entity, attribute, old, new, kwargs) -> None:
        """ Updates mode based on HA selector update. """

        modename, roomname = _parse_mode_and_room(new)
        if roomname is not None and roomname != str(self.name):
            return
        if modename == self.LIGHT_MODE:
            return
        if modename in self.all_modes:
            self.LIGHT_MODE = modename
            self.reactToChange()

        if modename == translations.reset:
            self.LIGHT_MODE = translations.normal

    def set_Mode_with_delay(self, kwargs):
        """ Sets mode with defined delay. """

        if self.mode_delay_handler is not None:
            if self.timer_running(self.mode_delay_handler):
                try:
                    self.cancel_timer(self.mode_delay_handler)
                except Exception:
                    self.log(f"Could not stop dim timer for {entity}.", level = 'DEBUG')
            self.mode_delay_handler = None

        self.reactToChange()

        if self.LIGHT_MODE in (translations.normal, translations.reset):
            self.LIGHT_MODE = translations.normal

        # Motion and presence
    def motion_state(self, entity, attribute, old, new, kwargs) -> None:
        """ Listens to motion state. """

        sensor: MotionSensor = kwargs['sensor']
        if new in MOTION:
            motion_data:dict = {'occupancy': True}
        else:
            motion_data:dict = {'occupancy': False}

        self._process_sensor(sensor, motion_data)

    def MQTT_motion_event(self, event_name, data, **kwargs) -> None:
        """ Listens to motion MQTT event.  """

        motion_data = json.loads(data['payload'])
        sensor: MotionSensor = kwargs['sensor']

        """ Test your MQTT settings. Uncomment line below to get logging when motion detected """
        #self.log(f"Motion detected: {sensor} Motion Data: {motion_data}") # FOR TESTING ONLY

        self._process_sensor(sensor, motion_data)

    def _process_sensor(self, sensor: MotionSensor, motion_data):

        match motion_data:
            case {"occupancy": True}:
                self._activate(sensor)

            case {"occupancy": False}:
                self._deactivate(sensor)

            case {"value": 8}:
                self._activate(sensor)

            case {"value": 0}:
                self._deactivate(sensor)

            case {"contact": False}:
                self._activate(sensor)

            case {"contact": True}:
                self._deactivate(sensor)

    def _activate(self, sensor: MotionSensor) -> None:
        """Mark the sensor as active, call newMotion. """

        constraints_ok = True
        if sensor.motion_constraints is not None:
            try:
                constraints_ok = safe_eval(sensor.motion_constraints, {"self": self})
            except Exception as exc:
                self.log(f"Constraint eval error for {sensor.motion_sensor}: {exc}", level="INFO")
                return

        if not constraints_ok:
            return

        self.active_motion_sensors.add(sensor.motion_sensor)
        self._newMotion()

    def _deactivate(self, sensor: MotionSensor) -> None:
        """Mark the sensor as inactive, call oldMotion. """

        self.active_motion_sensors.discard(sensor.motion_sensor)
        self._oldMotion(sensor=sensor)

    def _newMotion(self) -> None:
        if self.motion_handler is not None and self.timer_running(self.motion_handler):
            try:
                self.cancel_timer(self.motion_handler)
            except Exception as e:
                pass
            self.motion_handler = None

        if not self.check_mediaplayers_off():
            return
        is_night_mode = self.LIGHT_MODE.startswith(translations.night)

        for light in self.roomlight:
            use_motion = self._decide_if_motion(
                light,
                is_night_mode,
                True
            )
            if use_motion:
                light.setMotion(lightmode=self.LIGHT_MODE)

    def _oldMotion(self, sensor) -> None:
        if not self.active_motion_sensors:
            return

        if self.trackerhandle is not None and self.timer_running(self.trackerhandle):
            try:
                self.cancel_timer(self.trackerhandle)
            except Exception as e:
                self.log(f"Was not able to stop timer for {tracker.tracker}: {e}", level = 'DEBUG')
            self.trackerhandle = None
        if self.motion_handler is not None and self.timer_running(self.motion_handler):
            try:
                self.cancel_timer(self.motion_handler)
            except Exception as e:
                self.log(f"Was not able to stop timer for {sensor.motion_sensor}: {e}", level = 'DEBUG')
        sensor_delay:int = getattr(sensor, 'delay', 60)
        self.motion_handler = self.run_in(self.MotionEnd, sensor_delay)

    def out_of_bed(self, entity, attribute, old, new, kwargs) -> None:
        """ Check if all bed sensors are empty and if so change to current mode. """

        if self._bed_occupied():
            return
        self.LIGHT_MODE = self.getOutOfBedMode
        self.reactToChange()

    def _bed_occupied(self) -> bool:
        """Return True if any bed sensor reports 'on'."""
        return any(self.get_state(sensor) == 'on' for sensor in self.bed_sensors)

    def _listen_out_of_bed(self, sensor: str) -> None:
        """Set a delayed callback that will fire when a bed is vacated."""
        self.listen_state(
            self.out_of_bed,
            sensor,
            new='off',
            oneshot=True,
        )

    def presence_change(self, entity, attribute, old, new, kwargs) -> None:
        """ Listens to tracker/person state change. """

        tracker: TrackerSensor = kwargs['tracker']

        if new == 'home':
            constraints_ok = True
            if tracker.tracker_constraints is not None:
                try:
                    constraints_ok = safe_eval(tracker.tracker_constraints, {"self": self})
                except Exception as exc:
                    self.log(f"Constraint eval error for {tracker.tracker}: {exc}", level="INFO")
                    return

            if not constraints_ok:
                if self.LIGHT_MODE == translations.away:
                    self.LIGHT_MODE = translations.normal
                    self.reactToChange()
                return

            if self.LIGHT_MODE in (translations.normal, translations.away) and self.check_mediaplayers_off():
                self.LIGHT_MODE = translations.normal

                if self.trackerhandle is not None and self.timer_running(self.trackerhandle):
                    try:
                        self.cancel_timer(self.trackerhandle)
                    except Exception as e:
                        self.log(f"Was not able to stop timer for {tracker.tracker}: {e}", level = 'DEBUG')
                    self.trackerhandle = None

                if 'presence' in self.all_modes:
                    for light in self.roomlight:
                        light.setLightMode(lightmode = 'presence')
                else:
                    self._newMotion()
                tracker_delay:int = getattr(tracker, 'delay', 300)
                self.trackerhandle = self.run_in(self.MotionEnd, tracker_delay)
                return

        elif old == 'home':
            for tracker in self.presence:
                if self.get_state(tracker.tracker) == 'home':
                    self.reactToChange()
                    return
            self.LIGHT_MODE = translations.away

        for light in self.roomlight:
            light.setLightMode(lightmode = self.LIGHT_MODE)

    def MotionEnd(self, kwargs) -> None:
        """ Motion / Presence countdown ended. Turns lights back to current mode. """

        if self.check_mediaplayers_off():
            for light in self.roomlight:
                light.motion = False
                light.last_motion_brightness = 0
                light.setLightMode(lightmode = self.LIGHT_MODE)

    def state_changed(self, entity, attribute, old, new, kwargs) -> None:
        """ Update light settings when state of a HA entity is updated. """

        self.reactToChange()

    def reactToChange(self):
        """ This function is called when a sensor has new values and based upon mode and if motion is detected,
            it will either call 'setMotion' or 'setLightMode' to adjust lights based on the updated sensors. """

        if not self.check_mediaplayers_off():
            return

        motion_active = (
            self.active_motion_sensors
            or (self.motion_handler is not None and self.timer_running(self.motion_handler))
        )
        is_night_mode = self.LIGHT_MODE.startswith(translations.night)

        for light in self.roomlight:
            use_motion = self._decide_if_motion(
                light,
                is_night_mode,
                motion_active
            )
            if use_motion:
                light.setMotion(lightmode=self.LIGHT_MODE)
            else:
                light.setLightMode(lightmode = self.LIGHT_MODE)

    def _decide_if_motion(
        self,
        light,
        is_night_mode: bool,
        motion_active: bool,
    ) -> bool:
        """ Decide which mode to use for a single light. """

        if is_night_mode and not light.night_motion:
            return False

        if self.LIGHT_MODE in (translations.off, translations.custom):
            return False

        if motion_active:
            return light.motionlight

        return False

        # Media Player / sensors
    def media_on(self, entity, attribute, old, new, kwargs) -> None:
        if self.LIGHT_MODE == translations.morning:
            self.LIGHT_MODE = translations.normal
        self.check_mediaplayers_off()

    def media_off(self, entity, attribute, old, new, kwargs) -> None:
        self.reactToChange()

    def check_mediaplayers_off(self) -> bool:
        """ Returns true if media player sensors is off or self.LIGHT_DATA != 'normal'/'night'.
            If not it updates lightmode to the first detected media player. """

        if (
            self.LIGHT_MODE in (translations.normal, translations.reset)
            or self.LIGHT_MODE.startswith(translations.night)
        ):
            for mediaplayer in self.mediaplayers:
                if self.get_state(mediaplayer['mediaplayer']) == 'on':
                    for light in self.roomlight:
                        if ((light.checkConditions(light.conditions) and light.checkLuxConstraints()) or
                            light.current_keep_on_Condition
                        ):
                            light.setLightMode(lightmode = mediaplayer['mode'])
                        else:
                            light.turn_off_lights()
                            
                    return False
        return True

