""" Lightwand by Pythm

    @Pythm / https://github.com/Pythm
"""

__version__ = "2.0.0"

from appdaemon.plugins.hass.hassapi import Hass
#from datetime import timedelta
import json
#import csv
import os
from typing import List, Iterable, Set

from translations_lightmodes import translations
from weather_data import LightwandWeather

from lightwand_utils import split_around_underscore
from lightwand_builder import _convert_dict_to_light_spec
from lightwand_factory import build_light
from lightwand_config import LightSpec, MotionSensor

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

        self.LIGHT_MODE:str = 'None'
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

        self.exclude_from_custom:bool = self.args.get('exclude_from_custom', False)
        night_motion:bool = False
        dim_while_motion:bool = False
        self.prevent_off_to_normal:bool = False
        self.prevent_night_to_morning:bool = False

        # Options defined in configurations
        if 'options' in self.args:
            self.exclude_from_custom = 'exclude_from_custom' in self.args['options']
            night_motion = 'night_motion' in self.args['options'] ##
            dim_while_motion = 'dim_while_motion' in self.args['options'] ##
            self.prevent_off_to_normal = 'prevent_off_to_normal' in self.args['options']
            self.prevent_night_to_morning = 'prevent_night_to_morning' in self.args['options']

        self.mode_turn_off_delay:int = self.args.get('mode_turn_off_delay', 0)
        self.mode_turn_on_delay:int = self.args.get('mode_turn_on_delay',0)
        self.mode_delay_handler = None
        random_turn_on_delay:int = self.args.get('random_turn_on_delay',0)

        self.mediaplayers:dict = self.args.get('mediaplayers', {})

        adaptive_switch:str = self.args.get('adaptive_switch', None)
        adaptive_sleep_mode:str = self.args.get('adaptive_sleep_mode', None)

            # Presence detection (tracking)
        self.presence:dict = self.args.get('presence', {})
        self.trackerhandle = None
        for tracker in self.presence:
            self.listen_state(self.presence_change, tracker['tracker'],
                namespace = HASS_namespace,
                tracker = tracker
            )

        for tracker in self.presence:
            if self.get_state(tracker['tracker']) == 'home':
                break
            else:
                self.LIGHT_MODE = translations.away

            # Motion detection
        self.handle = None
        self.all_motion_sensors:dict = {} # To check if all motion sensors is off before turning off motion lights

        motion_sensors:dict = self.args.get('motion_sensors', {}) # TODO Change to MotionSensor class instead of dict
        for motion_sensor in motion_sensors:
            self.listen_state(self.motion_state, motion_sensor['motion_sensor'],
                namespace = HASS_namespace,
                motion_sensor = motion_sensor
            )
            self.all_motion_sensors.update(
                {motion_sensor['motion_sensor'] : self.get_state(motion_sensor['motion_sensor']) in MOTION}
            )

        if 'MQTT_motion_sensors' in self.args:
            MQTT_motion_sensors:list = self.args['MQTT_motion_sensors']
            for motion_sensor in MQTT_motion_sensors:
                self.mqtt.mqtt_subscribe(motion_sensor['motion_sensor'])
                self.mqtt.listen_event(self.MQTT_motion_event, "MQTT_MESSAGE",
                    topic = motion_sensor['motion_sensor'],
                    namespace = MQTT_namespace,
                    motion_sensor = motion_sensor
                )
                self.all_motion_sensors.update(
                    {motion_sensor['motion_sensor'] : False}
                )

        self.bed_sensors:list = self.args.get('bed_sensors', [])
        self.out_of_bed_delay:int = self.args.get('out_of_bed_delay', 0)

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

        self.usePersistentStorage:bool = False

        self.selector_input = self.args.get("selector_input", None)
        if self.selector_input is not None:
            self.listen_state(self.mode_update_from_selector, self.selector_input,
                namespace = HASS_namespace
            )
            self.LIGHT_MODE = self.get_state(self.selector_input, namespace = HASS_namespace)

            input_select_state = self.get_state(self.selector_input, attribute="all")
            current_options = input_select_state["attributes"].get("options", [])
            selector_input_options = list(current_options)
            for mode in self.all_modes:
                if mode not in selector_input_options and mode not in ('fire', 'false-alarm'):
                    selector_input_options.append(mode)

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

            # Makes a list of all valid modes for room
        for light in self.roomlight:
            for mode in light.light_modes:
                if not mode.mode in self.all_modes:
                    self.all_modes.add(mode.mode)
                    modename, roomname = split_around_underscore(mode.mode)
                    if (
                        modename is not None
                        and roomname != str(self.name)
                    ):
                        self.log(
                            f"Your mode name: {mode.mode} might get you into trouble. Please do not use names with underscore. "
                            "You can read more about this change in version 1.4.4 in the documentation. ",
                            level = 'WARNING'
                        )
                if self.selector_input is not None and mode.mode not in selector_input_options:
                    selector_input_options.append(mode.mode)

        if self.selector_input is not None:
            selector_input_options[:] = [
                mode for mode in selector_input_options
                if mode in self.all_modes and mode not in ('fire', 'false-alarm')
]
            if selector_input_options != current_options:
                self.call_service("input_select/set_options",
                    entity_id = self.selector_input,
                    options = selector_input_options,
                    namespace = HASS_namespace
                )

            # Listen sensors for when to update lights based on 'conditions'
        self.listen_sensors = self.args.get('listen_sensors', [])
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

        # Verifies your mode names
        modename, roomname = split_around_underscore(str(self.name))
        if modename is not None:
            self.log(
                f"Your app name: {self.name} might get you into trouble. Please do not use names with underscore. "
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
                with open(self.json_storage, 'r') as json_read:
                    lightwand_data = json.load(json_read)

                lightwand_data.update(
                    {"mode" : self.LIGHT_MODE}
                )
                with open(self.json_storage, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)
            except FileNotFoundError:
                lightwand_data = {"mode" : translations.normal,}
                with open(self.json_storage, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)

    def mode_event(self, event_name, data, **kwargs) -> None:
        """ New mode events. Updates lights if conditions are met. """

        modename, roomname = split_around_underscore(data['mode'])
        if modename is None:
            modename = data['mode']
        elif (
            roomname is not None
            and roomname != str(self.name)
        ):
            return

        if (
            self.LIGHT_MODE == translations.off
            and modename == translations.normal
            and self.prevent_off_to_normal
        ):
            return

        if self.exclude_from_custom:
            if (
                modename == translations.custom
                or modename == translations.wash
            ):
                return

        # Check if old light mode is night and bed is occupied.
        inBed = False
        if str(self.LIGHT_MODE)[:len(translations.night)] == translations.night:
            if (
                modename in (translations.morning, translations.normal)
                and self.prevent_night_to_morning
            ):
                return
            if modename not in (translations.night, translations.off, translations.reset):
                for bed_sensor in self.bed_sensors:
                    if self.get_state(bed_sensor) == 'on':
                        self.listen_state(self.out_of_bed, bed_sensor,
                            new = 'off',
                            duration = self.out_of_bed_delay,
                            oneshot = True
                        )
                        inBed = True
        if (
            modename in self.all_modes
            or modename == translations.morning
        ):
            if modename == translations.morning:
                if not translations.morning in self.all_modes:
                    modename = translations.normal
            if inBed:
                self.getOutOfBedMode = modename
                return

            self.LIGHT_MODE = modename

            if self.selector_input is not None:
                select_name = modename
                if modename == translations.reset:
                    select_name = translations.normal
                input_select_state = self.get_state(self.selector_input, attribute="all")
                options = input_select_state["attributes"].get("options", [])
                if select_name in options:
                    try:
                        self.call_service("input_select/select_option",
                            entity_id = self.selector_input,
                            option = select_name,
                            namespace = self.namespace
                        )
                    except Exception as e:
                        self.log(f"Could not set mode to {self.selector_input}. Error: {e}", level = 'DEBUG')

            if self.LIGHT_MODE in (translations.away, translations.off, translations.night):
                if self.mode_turn_off_delay > 0:
                    self.mode_delay_handler = self.run_in(self.set_Mode_with_delay, self.mode_turn_off_delay)
                    return
            elif self.LIGHT_MODE in (translations.normal, translations.morning):
                if self.mode_turn_on_delay > 0:
                    self.mode_delay_handler = self.run_in(self.set_Mode_with_delay, self.mode_turn_on_delay)
                    return

            self.reactToChange()

            if modename == translations.reset:
                self.LIGHT_MODE = translations.normal

    def mode_update_from_selector(self, entity, attribute, old, new, kwargs) -> None:
        """ Updates mode based on HA selector update. """

        modename, roomname = split_around_underscore(new)
        if modename is None:
            modename = new
        elif (
            roomname is not None
            and roomname != str(self.name)
        ):
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

        sensor = kwargs['motion_sensor']
        if new in MOTION:
            motion_data:dict = {'occupancy': True}
        else:
            motion_data:dict = {'occupancy': False}

        self._process_sensor(sensor, motion_data)

    def MQTT_motion_event(self, event_name, data, **kwargs) -> None:
        """ Listens to motion MQTT event.  """

        motion_data = json.loads(data['payload'])
        sensor = kwargs['motion_sensor']

        """ Test your MQTT settings. Uncomment line below to get logging when motion detected """
        #self.log(f"Motion detected: {sensor} Motion Data: {motion_data}") # FOR TESTING ONLY

        self._process_sensor(sensor, motion_data)

    def _process_sensor(self, sensor: dict, motion_data):
        sensor_id = sensor["motion_sensor"]

        match motion_data:
            case {"occupancy": True}:
                self._activate(sensor_id, sensor)

            case {"occupancy": False}:
                self._deactivate(sensor_id, sensor)

            case {"value": 8}:
                self._activate(sensor_id, sensor)

            case {"value": 0}:
                self._deactivate(sensor_id, sensor)

            case {"contact": False}:
                self._activate(sensor_id, sensor)

            case {"contact": True}:
                self._deactivate(sensor_id, sensor)

    def _activate(self, sensor_id: str, sensor: dict) -> None:
        """Mark the sensor as active, call newMotion. """

        constraints_ok = True
        if "motion_constraints" in sensor:
            try:
                constraints_ok = safe_eval(sensor["motion_constraints"], {"self": self})
            except Exception as exc:
                self.log(f"Constraint eval error for {sensor_id}: {exc}", level="INFO")
                return

        if not constraints_ok:
            return

        self.all_motion_sensors[sensor_id] = True
        self._newMotion()

    def _deactivate(self, sensor_id: str, sensor: dict) -> None:
        """Mark the sensor as inactive, call oldMotion. """

        if self.all_motion_sensors.get(sensor_id, False):
            self.all_motion_sensors[sensor_id] = False
            self._oldMotion(sensor=sensor)

    def _newMotion(self) -> None:
        if self.check_mediaplayers_off():
            for light in self.roomlight:
                if (
                    (str(self.LIGHT_MODE)[:len(translations.night)] != translations.night
                    or light.night_motion)
                    and self.LIGHT_MODE != translations.off
                ):
                    if light.motionlight:
                        light.setMotion(lightmode = self.LIGHT_MODE)

        if self.handle is not None:
            if self.timer_running(self.handle):
                try:
                    self.cancel_timer(self.handle)
                except Exception as e:
                    self.log(
                        f"Was not able to stop timer when motion detected for {self.handle}: {e}",
                        level = 'DEBUG'
                    )
                self.handle = None

    def _oldMotion(self, sensor) -> None:
        if self._checkMotion():
            return

        if self.trackerhandle is not None:
            if self.timer_running(self.trackerhandle):
                try:
                    self.cancel_timer(self.trackerhandle)
                except Exception as e:
                    self.log(f"Was not able to stop timer for {tracker['tracker']}: {e}", level = 'DEBUG')
                self.trackerhandle = None
        if self.handle is not None:
            if self.timer_running(self.handle):
                try:
                    self.cancel_timer(self.handle)
                except Exception as e:
                    self.log(f"Was not able to stop timer for {sensor['motion_sensor']}: {e}", level = 'DEBUG')
        sensor_delay:int = getattr(sensor, 'delay', 60)
        self.handle = self.run_in(self.MotionEnd, sensor_delay)

    def _checkMotion(self) -> bool:
        for sens in self.all_motion_sensors:
            if self.all_motion_sensors[sens]:
                return True

        return False

    def out_of_bed(self, entity, attribute, old, new, kwargs) -> None:
        """ Check if all bed sensors are empty and if so change to current mode. """

        for bed_sensor in self.bed_sensors:
            if self.get_state(bed_sensor) == 'on':
                return
        self.LIGHT_MODE = self.getOutOfBedMode
        self.reactToChange()

    def presence_change(self, entity, attribute, old, new, kwargs) -> None:
        """ Listens to tracker/person state change. """

        tracker:dict = kwargs['tracker']

        if new == 'home':
            constraints_ok = True
            if "tracker_constraints" in tracker:
                try:
                    constraints_ok = safe_eval(tracker["tracker_constraints"], {"self": self})
                except Exception as exc:
                    self.log(f"Constraint eval error for {tracker['tracker']}: {exc}", level="INFO")
                    return

            if not constraints_ok:
                if self.LIGHT_MODE == translations.away:
                    self.LIGHT_MODE = translations.normal
                    self.reactToChange()
                return

            if self.LIGHT_MODE in (translations.normal, translations.away) and self.check_mediaplayers_off():
                self.LIGHT_MODE = translations.normal

                if self.trackerhandle is not None:
                    if self.timer_running(self.trackerhandle):
                        try:
                            self.cancel_timer(self.trackerhandle)
                        except Exception as e:
                            self.log(f"Was not able to stop timer for {tracker['tracker']}: {e}", level = 'DEBUG')
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
                if self.get_state(tracker['tracker']) == 'home':
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

        if self.check_mediaplayers_off():
            for light in self.roomlight:
                if (
                    (str(self.LIGHT_MODE)[:len(translations.night)] != translations.night
                    or light.night_motion)
                    and self.LIGHT_MODE != translations.off
                ):
                    if self.handle is not None:
                        if self.timer_running(self.handle):
                            if light.motionlight:
                                light.setMotion(lightmode = self.LIGHT_MODE)
                            else:
                                light.setLightMode(lightmode = self.LIGHT_MODE)
                            continue

                    if self._checkMotion():
                        if light.motionlight:
                            light.setMotion(lightmode = self.LIGHT_MODE)
                        else:
                            light.setLightMode(lightmode = self.LIGHT_MODE)
                        continue

                light.setLightMode(lightmode = self.LIGHT_MODE)

        # Media Player / sensors
    def media_on(self, entity, attribute, old, new, kwargs) -> None:
        if self.LIGHT_MODE == translations.morning:
            self.LIGHT_MODE = translations.normal
        if self.LIGHT_MODE != translations.night:
            self.check_mediaplayers_off()

    def media_off(self, entity, attribute, old, new, kwargs) -> None:
        self.reactToChange()

    def check_mediaplayers_off(self) -> bool:
        """ Returns true if media player sensors is off or self.LIGHT_DATA != 'normal'/'night'.
            If not it updates lightmode to the first detected media player. """

        if (
            self.LIGHT_MODE in (translations.normal, translations.night, translations.reset)
            or str(self.LIGHT_MODE)[:len(translations.night)] == translations.night
        ):
            for mediaplayer in self.mediaplayers:
                if self.get_state(mediaplayer['mediaplayer']) == 'on':
                    for light in self.roomlight:
                        if (
                            light.checkConditions(light.conditions)
                            and light.checkLuxConstraints()
                        ):
                            light.setLightMode(lightmode = mediaplayer['mode'])
                        elif not light.current_keep_on_Condition:
                            light.turn_off_lights()
                            
                    return False
        return True

