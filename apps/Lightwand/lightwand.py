""" Lightwand by Pythm

    @Pythm / https://github.com/Pythm
"""

__version__ = "1.4.0"

import appdaemon.plugins.hass.hassapi as hass
import datetime
import json
import csv
import math
import copy

class Room(hass.Hass):

    def initialize(self):

        self.mqtt = None

        self.roomlight:list = []
        
        self.LIGHT_MODE:str = 'normal'
        self.all_modes:list = ['normal', 'away', 'off', 'night', 'custom', 'fire', 'wash', 'reset']
        self.getOutOfBedMode:str = 'normal'
        self.ROOM_LUX:float = 0.0
        self.OUT_LUX:float = 0.0
        self.RAIN:float = 0.0
        self.JSON_PATH:str = ''


        self.exclude_from_custom:bool = self.args.get('exclude_from_custom', False) # Old configuration of exclude from custom...
        night_motion:bool = False
        dim_while_motion:bool = False

        # Options defined in configurations
        if 'options' in self.args:
            self.exclude_from_custom = 'exclude_from_custom' in self.args['options']
            night_motion = 'night_motion' in self.args['options']
            dim_while_motion = 'dim_while_motion' in self.args['options']
        room_night_motion:bool = night_motion
        room_dim_while_motion:bool = dim_while_motion


        self.mode_turn_off_delay:int = self.args.get('mode_turn_off_delay', 0)
        self.mode_turn_on_delay:int = self.args.get('mode_turn_on_delay',0)
        self.mode_delay_handler = None
        random_turn_on_delay:int = self.args.get('random_turn_on_delay',0)

        self.mediaplayers:dict = self.args.get('mediaplayers', {})

        adaptive_switch:str = self.args.get('adaptive_switch', None)
        adaptive_sleep_mode:str = self.args.get('adaptive_sleep_mode', None)

        # Namespaces for HASS and MQTT
        HASS_namespace:str = self.args.get('HASS_namespace', 'default')
        MQTT_namespace:str = self.args.get('MQTT_namespace', 'default')

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
                self.LIGHT_MODE = 'normal'
                break
            else:
                self.LIGHT_MODE = 'away'

            # Motion detection
        self.handle = None
        self.all_motion_sensors:dict = {} # To check if all motion sensors is off before turning off motion lights

        motion_sensors:dict = self.args.get('motion_sensors', {})
        for motion_sensor in motion_sensors:
            self.listen_state(self.motion_state, motion_sensor['motion_sensor'],
                namespace = HASS_namespace,
                motion_sensor = motion_sensor
            )
            self.all_motion_sensors.update(
                {motion_sensor['motion_sensor'] : self.get_state(motion_sensor['motion_sensor']) == 'on'}
            )


        if 'MQTT_motion_sensors' in self.args:
            MQTT_motion_sensors:list = self.args['MQTT_motion_sensors']
            if not self.mqtt:
                self.mqtt = self.get_plugin_api("MQTT")
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


            # Weather sensors
        self.outLux1:float = 0.0
        self.outLux2:float = 0.0
        self.lux_last_update1 = self.datetime(aware=True) - datetime.timedelta(minutes = 20) # Helpers for last updated when two outdoor lux sensors in use
        self.lux_last_update2 = self.datetime(aware=True) - datetime.timedelta(minutes = 20)

        if 'OutLux_sensor' in self.args:
            lux_sensor = self.args['OutLux_sensor']
            self.listen_state(self.out_lux_state, lux_sensor,
                namespace = HASS_namespace
            )
            new_lux = self.get_state(lux_sensor,
                namespace = HASS_namespace)
            try:
                self.OUT_LUX = float(new_lux)
            except ValueError as ve:
                self.OUT_LUX:float = 0.0
                self.log(f"Not able to set Rain amount. Exception: {ve}", level = 'DEBUG')
            except Exception as e:
                self.OUT_LUX:float = 0.0
                self.log(f"Not able to set Rain amount. Exception: {e}", level = 'INFO')

        if 'OutLuxMQTT' in self.args:
            if not self.mqtt:
                self.mqtt = self.get_plugin_api("MQTT")
            out_lux_sensor = self.args['OutLuxMQTT']
            self.mqtt.mqtt_subscribe(out_lux_sensor)
            self.mqtt.listen_event(self.out_lux_event_MQTT, "MQTT_MESSAGE",
                topic = out_lux_sensor,
                namespace = MQTT_namespace
            )

        if 'OutLux_sensor_2' in self.args:
            lux_sensor = self.args['OutLux_sensor_2']
            self.listen_state(self.out_lux_state2, lux_sensor,
                namespace = HASS_namespace
            )
        if 'OutLuxMQTT_2' in self.args:
            if not self.mqtt:
                self.mqtt = self.get_plugin_api("MQTT")
            out_lux_sensor = self.args['OutLuxMQTT_2']
            self.mqtt.mqtt_subscribe(out_lux_sensor)
            self.mqtt.listen_event(self.out_lux_event_MQTT2, "MQTT_MESSAGE",
                topic = out_lux_sensor,
                namespace = MQTT_namespace
            )

        if 'RoomLux_sensor' in self.args:
            lux_sensor = self.args['RoomLux_sensor']
            self.listen_state(self.room_lux_state, lux_sensor,
                namespace = HASS_namespace
            )
            new_lux = self.get_state(lux_sensor,
                namespace = HASS_namespace)
            try:
                self.ROOM_LUX = float(new_lux)
            except ValueError as ve:
                self.ROOM_LUX:float = 0.0
                self.log(f"Not able to set Rain amount. Exception: {ve}", level = 'DEBUG')
            except Exception as e:
                self.ROOM_LUX:float = 0.0
                self.log(f"Not able to set Rain amount. Exception: {e}", level = 'INFO')

        if 'RoomLuxMQTT' in self.args:
            if not self.mqtt:
                self.mqtt = self.get_plugin_api("MQTT")
            room_lux_sensor_zigbee = self.args['RoomLuxMQTT']
            self.mqtt.mqtt_subscribe(room_lux_sensor_zigbee)
            self.mqtt.listen_event(self.room_lux_event_MQTT, "MQTT_MESSAGE",
                topic = room_lux_sensor_zigbee,
                namespace = MQTT_namespace
            )


        if 'rain_sensor' in self.args:
            rain_sensor = self.args['rain_sensor']
            self.listen_state(self.update_rain_amount, rain_sensor,
                namespace = HASS_namespace
            )
            new_rain_amount = self.get_state(rain_sensor)
            try:
                self.RAIN = float(new_rain_amount)
            except ValueError as ve:
                self.RAIN:float = 0.0
                self.log(f"Not able to set Rain amount. Exception: {ve}", level = 'DEBUG')
            except Exception as e:
                self.RAIN:float = 0.0
                self.log(f"Not able to set Rain amount. Exception: {e}", level = 'INFO')

            # Persistent storage for storing mode and lux data
        self.usePersistentStorage:bool = False
        if 'json_path' in self.args:
            self.JSON_PATH:str = self.args['json_path']
            self.JSON_PATH += str(self.name) + '.json'
            self.usePersistentStorage = True

            lightwand_data:dict = {}
            try:
                with open(self.JSON_PATH, 'r') as json_read:
                    lightwand_data = json.load(json_read)
            except FileNotFoundError:
                lightwand_data = {"mode" : "normal",
                                "out_lux" : 0,
                                "room_lux" : 0}
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)

            self.LIGHT_MODE = lightwand_data['mode']
            self.OUT_LUX = float(lightwand_data['out_lux'])
            self.ROOM_LUX = float(lightwand_data['room_lux'])

            # Configuration of MQTT Lights
        lights = self.args.get('MQTTLights', [])
        for l in lights:
            if 'enable_light_control' in l:
                if self.get_state(l['enable_light_control']) == 'off':
                    continue
            if 'options' in l:
                if 'exclude_from_custom' in l['options']:
                    self.exclude_from_custom = True
                if 'night_motion' in l['options']:
                    night_motion = True
                if 'dim_while_motion' in l['options']:
                    dim_while_motion = True
            if 'motionlights' in l:
                if l['motionlights'] == None:
                    l['motionlights'] = {'state': 'none'}
            light = MQTTLights(self,
                lights = l['lights'],
                light_modes = l.get('light_modes', []),
                automations = l.get('automations', None),
                motionlight = l.get('motionlights', None),
                lux_constraint = l.get('lux_constraint', None),
                room_lux_constraint = l.get('room_lux_constraint', None),
                conditions = l.get('conditions', ['True']),
                json_path = self.JSON_PATH,
                usePersistentStorage = self.usePersistentStorage,
                MQTT_namespace = MQTT_namespace,
                HASS_namespace = HASS_namespace,
                night_motion = night_motion,
                adaptive_switch = l.get('adaptive_switch', adaptive_switch),
                adaptive_sleep_mode = l.get('adaptive_sleep_mode', adaptive_sleep_mode),
                dim_while_motion = dim_while_motion
            )
            self.roomlight.append(light)
            # Reset option to room option
            night_motion = room_night_motion
            dim_while_motion = room_dim_while_motion


            # Configuration of HASS Lights
        lights = self.args.get('Lights', [])
        for l in lights:
            if 'enable_light_control' in l:
                if self.get_state(l['enable_light_control']) == 'off':
                    continue
            if 'options' in l:
                if 'exclude_from_custom' in l['options']:
                    self.exclude_from_custom = True
                if 'night_motion' in l['options']:
                    night_motion = True
                if 'dim_while_motion' in l['options']:
                    dim_while_motion = True
            if 'motionlights' in l:
                if l['motionlights'] == None:
                    l['motionlights'] = {'state': 'none'}
            light = Light(self,
                lights = l['lights'],
                light_modes = l.get('light_modes', []),
                automations = l.get('automations', None),
                motionlight = l.get('motionlights', None),
                lux_constraint = l.get('lux_constraint', None),
                room_lux_constraint = l.get('room_lux_constraint', None),
                conditions = l.get('conditions', ['True']),
                json_path = self.JSON_PATH,
                usePersistentStorage = self.usePersistentStorage,
                HASS_namespace = HASS_namespace,
                night_motion = night_motion,
                adaptive_switch = l.get('adaptive_switch', adaptive_switch),
                adaptive_sleep_mode = l.get('adaptive_sleep_mode', adaptive_sleep_mode),
                dim_while_motion = dim_while_motion
            )
            self.roomlight.append(light)
            # Reset option to room option
            night_motion = room_night_motion
            dim_while_motion = room_dim_while_motion

            # Configuration of HASS Toggle Lights
        toggle = self.args.get('ToggleLights', [])
        for l in toggle:
            if 'enable_light_control' in l:
                if self.get_state(l['enable_light_control']) == 'off':
                    continue
            if 'motionlights' in l:
                if l['motionlights'] == None:
                    l['motionlights'] = {'state': 'none'}
            light = Toggle(self,
                lights = l['lights'],
                light_modes = l.get('light_modes', []),
                automations = l.get('automations', None),
                motionlight = l.get('motionlights', None),
                lux_constraint = l.get('lux_constraint', None),
                room_lux_constraint = l.get('room_lux_constraint', None),
                conditions = l.get('conditions', ['True']),
                toggle = l.get('toggle',3),
                num_dim_steps = l.get('num_dim_steps',3),
                toggle_speed = l.get('toggle_speed',1),
                prewait_toggle = l.get('prewait_toggle', 0),
                json_path = self.JSON_PATH,
                usePersistentStorage = self.usePersistentStorage,
                HASS_namespace = HASS_namespace
            )
            self.roomlight.append(light)


            # Makes a list of all valid modes for room
        for light in self.roomlight:
            for mode in light.light_modes:
                if not mode['mode'] in self.all_modes:
                    self.all_modes.append(mode['mode'])
            light.random_turn_on_delay = random_turn_on_delay

            # Listen sensors for when to update lights based on 'conditions'
        self.listen_sensors = self.args.get('listen_sensors', [])
        for sensor in self.listen_sensors:
            self.listen_state(self.state_changed, sensor,
                namespace = HASS_namespace
            )

            # Update lux
        for light in self.roomlight:
            light.roomLux = self.ROOM_LUX
            light.outLux = self.OUT_LUX

            # Media players for setting mediaplayer mode
        mediaIsOn:bool = False
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
            if self.get_state(mediaplayer['mediaplayer']) == 'on':
                mediaIsOn = True

            # Sets lights at startup
        
        if (
            self.LIGHT_MODE == 'normal'
            or self.LIGHT_MODE == 'night'
            and mediaIsOn
        ):
            for mediaplayer in self.mediaplayers:
                if self.get_state(mediaplayer['mediaplayer']) == 'on':
                    for light in self.roomlight:
                        light.setLightMode(lightmode = mediaplayer['mode'])
                    break
        
        if not mediaIsOn:
            self.reactToChange()
    
        """ This listens to events fired as MODE_CHANGE with data beeing mode = 'yourmode'
            self.fire_event('MODE_CHANGE', mode = 'normal')
            If you already have implemented someting similar in your Home Assistant setup you can easily change
            MODE_CHANGE and > data['mode'] in mode_event to receive whatever data you are sending            
        """
        self.listen_event(self.mode_event, "MODE_CHANGE",
            namespace = HASS_namespace
        )


        """ End initial setup for Room
        """


    def terminate(self) -> None:
        """ Writes out data to persistent storage before terminating.
        """
        if self.usePersistentStorage:

            with open(self.JSON_PATH, 'r') as json_read:
                lightwand_data = json.load(json_read)
            
            for light in self.roomlight:
                if (
                    light.adjustLight_enabled
                    or type(light).__name__ == 'MQTTLights'
                ):
                    if light.lights[0] in lightwand_data:
                        lightwand_data[light.lights[0]].update(
                            {"isON" : light.isON}
                        )
                elif type(light).__name__ == 'Toggle':
                    if light.lights[0] in lightwand_data:
                        lightwand_data[light.lights[0]].update(
                            {"toggle" : light.current_toggle}
                        )
            lightwand_data.update(
                {"mode" : self.LIGHT_MODE,
                "out_lux" : self.OUT_LUX,
                "room_lux" : self.ROOM_LUX}
            )
            with open(self.JSON_PATH, 'w') as json_write:
                json.dump(lightwand_data, json_write, indent = 4)


    def mode_event(self, event_name, data, kwargs) -> None:
        """ New mode events. Updates lights if conditions are met
        """
        if self.exclude_from_custom:
            if (
                data['mode'] == 'custom'
                or data['mode'] == 'wash'
            ):
                return


        """ Check if old light mode is night and bed is occupied."""
        string:str = self.LIGHT_MODE
        inBed = False
        if string[:5] == 'night':
            newmode_string:str = data['mode']
            if (
                newmode_string[:5] != 'night'
                and newmode_string[:3] != 'off'
            ):
                for bed_sensor in self.bed_sensors:
                    if self.get_state(bed_sensor) == 'on':
                        self.listen_state(self.out_of_bed, bed_sensor, new = 'off', oneshot = True)
                        inBed = True

        if (
            data['mode'] in self.all_modes
            or data['mode'] == 'morning'
            or data['mode'] == 'off_' + str(self.name)
            or data['mode'] == 'normal_' + str(self.name)
            or data['mode'] == 'reset_' + str(self.name)
        ):
            if inBed:
                self.getOutOfBedMode = data['mode']
                return

            self.LIGHT_MODE = data['mode']
            if data['mode'] == 'morning':
                if not 'morning' in self.all_modes:
                    self.LIGHT_MODE = 'normal'

            if (
                self.LIGHT_MODE == 'away'
                or self.LIGHT_MODE == 'off'
                or self.LIGHT_MODE == 'night'
            ):
                if self.mode_turn_off_delay > 0:
                    self.mode_delay_handler = self.run_in(self.set_Mode_with_delay, self.mode_turn_off_delay)
                    return
            elif (
                self.LIGHT_MODE == 'normal'
                or self.LIGHT_MODE == 'morning'
            ):
                if self.mode_turn_on_delay > 0:
                    self.mode_delay_handler = self.run_in(self.set_Mode_with_delay, self.mode_turn_on_delay)
                    return


            self.reactToChange()

            if (
                data['mode'] == 'normal_' + str(self.name)
                or data['mode'] == 'reset_' + str(self.name)
                or data['mode'] == 'reset'
            ):
                self.LIGHT_MODE = 'normal'


    def set_Mode_with_delay(self, kwargs):

        if self.mode_delay_handler != None:
            if self.timer_running(self.mode_delay_handler):
                try:
                    self.cancel_timer(self.mode_delay_handler)
                except Exception:
                    self.log(f"Could not stop dim timer for {entity}.", level = 'DEBUG')
            self.mode_delay_handler = None

        self.reactToChange()

        if (
            self.LIGHT_MODE == 'normal_' + str(self.name)
            or self.LIGHT_MODE == 'reset_' + str(self.name)
            or self.LIGHT_MODE == 'reset'
        ):
            self.LIGHT_MODE = 'normal'

        # Motion and presence

    def motion_state(self, entity, attribute, old, new, kwargs) -> None:
        # Listens to motion state
        sensor = kwargs['motion_sensor']

        if new == 'on':
            if 'motion_constraints' in sensor:
                if not eval(sensor['motion_constraints']):
                    return
            self.all_motion_sensors.update(
                {sensor['motion_sensor'] : True}
            )
            self.newMotion()
        elif (
            new == 'off'
            and self.all_motion_sensors[sensor['motion_sensor']]
            ):
            self.all_motion_sensors.update(
                {sensor['motion_sensor'] : False}
            )
            self.oldMotion(sensor = sensor)


    def MQTT_motion_event(self, event_name, data, kwargs) -> None:
        # Listens to motion MQTT event
        motion_data = json.loads(data['payload'])
        sensor = kwargs['motion_sensor']

        """ Test your MQTT settings. Uncomment line below to get logging when motion detected """
        #self.log(f"Motion detected: {sensor} Motion Data: {motion_data}") # FOR TESTING ONLY

        if 'occupancy' in motion_data:
            if motion_data['occupancy']:
                if 'motion_constraints' in sensor:
                    if not eval(sensor['motion_constraints']):
                        return
                self.all_motion_sensors.update(
                    {sensor['motion_sensor'] : True}
                )
                self.newMotion()
            elif self.all_motion_sensors[sensor['motion_sensor']]:
                self.all_motion_sensors.update(
                    {sensor['motion_sensor'] : False}
                )
                self.oldMotion(sensor = sensor)
        elif 'value' in motion_data:
            if motion_data['value'] == 8:
                if 'motion_constraints' in sensor:
                    if not eval(sensor['motion_constraints']):
                        return
                self.all_motion_sensors.update(
                    {sensor['motion_sensor'] : True}
                )
                self.newMotion()
            elif (
                motion_data['value'] == 0
                and self.all_motion_sensors[sensor['motion_sensor']]
            ):
                self.all_motion_sensors.update(
                    {sensor['motion_sensor'] : False}
                )
                self.oldMotion(sensor = sensor)


    def newMotion(self) -> None:
        """ Motion detected. Checks constraints given in motion and setMotion
        """
        if self.check_mediaplayers_off():
            string:str = self.LIGHT_MODE
            for light in self.roomlight:
                if (
                    (string[:5] != 'night'
                    or light.night_motion)
                    and string[:3] != 'off'
                ):
                    if light.motionlight:
                        light.setMotion(lightmode = self.LIGHT_MODE)

        if self.handle != None:
            if self.timer_running(self.handle):
                try:
                    self.cancel_timer(self.handle)
                except Exception as e:
                    self.log(
                        f"Was not able to stop timer when motion detected for {self.handle}: {e}",
                        level = 'DEBUG'
                    )
                self.handle = None

        if self.trackerhandle != None:
            if self.timer_running(self.trackerhandle):
                try:
                    self.cancel_timer(self.trackerhandle)
                except Exception as e:
                    self.log(f"Was not able to stop timer for {tracker['tracker']}: {e}", level = 'DEBUG')
                finally:
                    self.trackerhandle = None


    def oldMotion(self, sensor) -> None:
        """ Motion no longer detected in sensor. Checks other sensors in room and starts countdown to turn off light
        """
        if self.checkMotion():
            return

        if self.trackerhandle != None:
            if self.timer_running(self.trackerhandle):
                try:
                    self.cancel_timer(self.trackerhandle)
                except Exception as e:
                    self.log(f"Was not able to stop timer for {tracker['tracker']}: {e}", level = 'DEBUG')
                finally:
                    self.trackerhandle = None
        if self.handle != None:
            if self.timer_running(self.handle):
                try:
                    self.cancel_timer(self.handle)
                except Exception as e:
                    self.log(f"Was not able to stop timer for {sensor['motion_sensor']}: {e}", level = 'DEBUG')
        if 'delay' in sensor:
            self.handle = self.run_in(self.MotionEnd, int(sensor['delay']))
        else:
            self.handle = self.run_in(self.MotionEnd, 60)


    def checkMotion(self) -> bool:
        for sens in self.all_motion_sensors:
            if self.all_motion_sensors[sens]:
                return True

        return False
        

    def out_of_bed(self, entity, attribute, old, new, kwargs) -> None:
        for bed_sensor in self.bed_sensors:
            if self.get_state(bed_sensor) == 'on':
                return
        self.LIGHT_MODE = self.getOutOfBedMode
        self.reactToChange()


    def presence_change(self, entity, attribute, old, new, kwargs) -> None:
        # Listens to tracker/person state change
        tracker:dict = kwargs['tracker']

        if new == 'home':
            if 'tracker_constraints' in tracker:
                if not eval(tracker['tracker_constraints']):
                    if self.LIGHT_MODE == 'away':
                        self.LIGHT_MODE = 'normal'
                        self.reactToChange()
                    return

            if (
                self.LIGHT_MODE == 'normal'
                or self.LIGHT_MODE == 'away'
            ):
                self.LIGHT_MODE = 'normal'
                if (
                    'presence' in self.all_modes
                    and self.check_mediaplayers_off()
                ):
                    if self.trackerhandle != None:
                        if self.timer_running(self.trackerhandle):
                            try:
                                self.cancel_timer(self.trackerhandle)
                            except Exception as e:
                                self.log(f"Was not able to stop timer for {tracker['tracker']}: {e}", level = 'DEBUG')
                            finally:
                                self.trackerhandle = None
                    for light in self.roomlight:
                        light.setLightMode(lightmode = 'presence')
                    if 'delay' in tracker:
                        self.trackerhandle = self.run_in(self.MotionEnd, int(tracker['delay']))
                    else:
                        self.trackerhandle = self.run_in(self.MotionEnd, 300)
                    return

        elif old == 'home':
            for tracker in self.presence:
                if self.get_state(tracker['tracker']) == 'home':
                    self.reactToChange()
                    return
            self.LIGHT_MODE = 'away'

        for light in self.roomlight:
            light.setLightMode(lightmode = self.LIGHT_MODE)


    def MotionEnd(self, kwargs) -> None:
        """ Motion / Presence countdown ended. Turns lights back to current mode
        """
        if self.check_mediaplayers_off():
            for light in self.roomlight:
                light.motion = False
                light.last_motion_brightness = 0
                light.setLightMode(lightmode = self.LIGHT_MODE)


    def state_changed(self, entity, attribute, old, new, kwargs) -> None:
        """ Update light settings when state of a HA entity is updated
        """
        self.reactToChange()


    def reactToChange(self):

        if self.check_mediaplayers_off():
            string:str = self.LIGHT_MODE
            for light in self.roomlight:
                if (
                    (string[:5] != 'night'
                    or light.night_motion)
                    and string[:3] != 'off'
                ):
                    if self.handle != None:
                        if self.timer_running(self.handle):
                            if light.motionlight:
                                light.setMotion(lightmode = self.LIGHT_MODE)
                            else:
                                light.setLightMode(lightmode = self.LIGHT_MODE)
                            continue

                    if self.checkMotion():
                        if light.motionlight:
                            light.setMotion(lightmode = self.LIGHT_MODE)
                        else:
                            light.setLightMode(lightmode = self.LIGHT_MODE)
                        continue

                light.setLightMode(lightmode = self.LIGHT_MODE)


        # Lux / weather
    def out_lux_state(self, entity, attribute, old, new, kwargs) -> None:
        try:
            if self.outLux1 != float(new):
                self.outLux1 = float(new)
        except ValueError as ve:
            self.log(f"Not able to get new outlux. ValueError: {ve}", level = 'DEBUG')
        except TypeError as te:
            self.log(f"Not able to get new outlux. TypeError: {te}", level = 'DEBUG')
        except Exception as e:
            self.log(f"Not able to get new outlux. Exception: {e}", level = 'WARNING')
        else:
            self.newOutLux()


    def out_lux_event_MQTT(self, event_name, data, kwargs) -> None:
        lux_data = json.loads(data['payload'])
        if 'illuminance_lux' in lux_data:
            if self.outLux1 != float(lux_data['illuminance_lux']):
                self.outLux1 = float(lux_data['illuminance_lux']) # Zigbee sensor
                self.newOutLux()
        elif 'illuminance' in lux_data:
            if self.outLux1 != float(lux_data['illuminance']):
                self.outLux1 = float(lux_data['illuminance']) # Zigbee sensor
                self.newOutLux()
        elif 'value' in lux_data:
            if self.outLux1 != float(lux_data['value']):
                self.outLux1 = float(lux_data['value']) # Zwave sensor
                self.newOutLux()


    def newOutLux(self) -> None:
        if (
            self.datetime(aware=True) - self.lux_last_update2 > datetime.timedelta(minutes = 15)
            or self.outLux1 >= self.outLux2
        ):
            self.OUT_LUX = self.outLux1

            for light in self.roomlight:
                light.outLux = self.OUT_LUX

            if self.mode_delay_handler != None:
                if self.timer_running(self.mode_delay_handler):
                    return

            self.reactToChange()

        self.lux_last_update1 = self.datetime(aware=True)


    def out_lux_state2(self, entity, attribute, old, new, kwargs) -> None:
        if self.outLux2 != float(new):
            self.outLux2 = float(new)

            self.newOutLux2()


    def out_lux_event_MQTT2(self, event_name, data, kwargs) -> None:
        lux_data = json.loads(data['payload'])
        if 'illuminance_lux' in lux_data:
            if self.outLux2 != float(lux_data['illuminance_lux']):
                self.outLux2 = float(lux_data['illuminance_lux']) # Zigbee sensor
                self.newOutLux2()
        elif 'illuminance' in lux_data:
            if self.outLux2 != float(lux_data['illuminance']):
                self.outLux2 = float(lux_data['illuminance']) # Zigbee sensor
                self.newOutLux2()
        elif 'value' in lux_data:
            if self.outLux2 != float(lux_data['value']):
                self.outLux2 = float(lux_data['value']) # Zwave sensor
                self.newOutLux2()


    def newOutLux2(self) -> None:
        if (
            self.datetime(aware=True) - self.lux_last_update1 > datetime.timedelta(minutes = 15)
            or self.outLux2 >= self.outLux1
        ):
            self.OUT_LUX = self.outLux2

            for light in self.roomlight:
                light.outLux = self.OUT_LUX

            if self.mode_delay_handler != None:
                if self.timer_running(self.mode_delay_handler):
                    return

            self.reactToChange()

        self.lux_last_update2 = self.datetime(aware=True)


    def room_lux_state(self, entity, attribute, old, new, kwargs) -> None:
        if self.ROOM_LUX != float(new):
            self.ROOM_LUX = float(new)

            self.newRoomLux()


    def room_lux_event_MQTT(self, event_name, data, kwargs) -> None:
        lux_data = json.loads(data['payload'])
        if 'illuminance_lux' in lux_data:
            if self.ROOM_LUX != float(lux_data['illuminance_lux']):
                self.ROOM_LUX = float(lux_data['illuminance_lux']) # Zigbee sensor
                self.newRoomLux()
        elif 'illuminance' in lux_data:
            if self.ROOM_LUX != float(lux_data['illuminance']):
                self.ROOM_LUX = float(lux_data['illuminance']) # Zigbee sensor
                self.newRoomLux()
        elif 'value' in lux_data:
            if self.ROOM_LUX != float(lux_data['value']):
                self.ROOM_LUX = float(lux_data['value']) # Zwave sensor
                self.newRoomLux()


    def newRoomLux(self) -> None:
        for light in self.roomlight:
            light.roomLux = self.ROOM_LUX

        if self.mode_delay_handler != None:
                if self.timer_running(self.mode_delay_handler):
                    return

        self.reactToChange()


    def update_rain_amount(self, entity, attribute, old, new, kwargs) -> None:
        if new != old:
            try:
                self.RAIN = float(new)
            except ValueError as ve:
                self.log(f"Rain amount unavailable. ValueError: {ve}", level = 'DEBUG')
                self.RAIN = 0.0
            except TypeError as te:
                self.log(f"Rain amount unavailable. TypeError: {te}", level = 'DEBUG')
                self.RAIN = 0.0
            except Exception as e:
                self.log(f"Not able to get new rain amount. Exception: {e}", level = 'WARNING')
                self.RAIN = 0.0
            
            for light in self.roomlight:
                light.rain_amount = self.RAIN


        # Media Player / sensors
    def media_on(self, entity, attribute, old, new, kwargs) -> None:
        if self.LIGHT_MODE == 'morning':
            self.LIGHT_MODE = 'normal'
        if self.LIGHT_MODE != 'night':
            self.check_mediaplayers_off()


    def media_off(self, entity, attribute, old, new, kwargs) -> None:
        
        self.reactToChange()


    def check_mediaplayers_off(self) -> bool:
        """ Returns true if media player sensors is off
            or self.LIGHT_DATA != 'normal'/'night'
        """
        if (
            str(self.LIGHT_MODE)[:6] == 'normal'
            or str(self.LIGHT_MODE)[:5] == 'night'
            or str(self.LIGHT_MODE)[:5] == 'reset'
        ):
            for mediaplayer in self.mediaplayers:
                if self.get_state(mediaplayer['mediaplayer']) == 'on':
                    for light in self.roomlight:
                        light.setLightMode(lightmode = mediaplayer['mode'])
                    return False
        return True


class Light:
    """ Parent class for lights
    """

    def __init__(self, api,
        lights,
        light_modes,
        automations,
        motionlight,
        lux_constraint,
        room_lux_constraint,
        conditions,
        json_path,
        usePersistentStorage,
        HASS_namespace,
        night_motion,
        adaptive_switch,
        adaptive_sleep_mode,
        dim_while_motion
    ):

        self.ADapi = api
        self.HASS_namespace = HASS_namespace

        self.lights:list = lights
        self.light_modes:list = light_modes
        self.automations = automations
        self.motionlight = motionlight
        self.lux_constraint = lux_constraint
        self.room_lux_constraint = room_lux_constraint
        self.conditions:list = conditions
        self.JSON_PATH:str = json_path
        self.usePersistentStorage:bool = usePersistentStorage
        self.night_motion:bool = night_motion
        self.dim_while_motion:bool = dim_while_motion
        self.random_turn_on_delay:int = 0

        self.adaptive_switch = adaptive_switch
        self.adaptive_sleep_mode = adaptive_sleep_mode
        self.has_adaptive_state:bool = False

        self.outLux:float = 0.0
        self.roomLux:float = 0.0
        self.rain_amount:float = 0.0
        self.lightmode:str = 'normal'
        self.times_to_adjust_light:list = []
        self.dimHandler = None
        self.motion:bool = False
        self.isON:bool = None
        self.adjustLight_enabled:bool = False
        self.brightness:int = 0
        self.last_motion_brightness:int = 0
        self.current_light_data:dict = {}


        string:str = self.lights[0]
        if string[:6] == 'light.':
            self.ADapi.listen_state(self.BrightnessUpdated, self.lights[0],
                attribute = 'brightness',
                namespace = HASS_namespace
            )
            try:
                self.brightness = int(self.ADapi.get_state(self.lights[0],
                    attribute = 'brightness',
                    namespace = HASS_namespace)
                )
            except TypeError:
                self.brightness = 0

            self.ADapi.listen_state(self.update_isOn_lights, self.lights[0],
                namespace = HASS_namespace
            )
            self.isOn = self.ADapi.get_state(self.lights[0]) == 'on'
        if string[:7] == 'switch.':
            self.ADapi.listen_state(self.update_isOn_lights, self.lights[0],
                namespace = HASS_namespace
            )
            self.isOn = self.ADapi.get_state(self.lights[0]) == 'on'
        

        # Helpers to check if conditions to turn on/off light has changed
        self.wereMotion:bool = False
        self.current_OnCondition:bool = None
        self.current_LuxCondition:bool = None


        """ Set up automations with times defined and check data
        """
        self.automations_original:list = []
        if self.automations:
            self.automations_original = copy.deepcopy(self.automations)
            self.checkTimesinAutomations(self.automations)

            string:str = self.lights[0]
            for automation in self.automations:
                if (
                    'adjust' in automation['state']
                    and self.adjustLight_enabled
                ):
                    if (
                        string[:6] == 'light.'
                        or string[:7] == 'switch.'
                    ):
                        self.adjustLight_enabled = True
                if 'adaptive' in automation['state']:
                    self.has_adaptive_state = True

        self.motions_original:list = []
        if self.motionlight:
            if type(self.motionlight) == list:
                self.motions_original = copy.deepcopy(self.motionlight)
                self.checkTimesinAutomations(self.motionlight)

                for automation in self.motionlight:
                    if 'adaptive' in automation['state']:
                        self.has_adaptive_state = True
            elif 'state' in self.motionlight:
                if 'adaptive' in self.motionlight['state']:
                    self.has_adaptive_state = True
            elif not 'state' in self.motionlight:
                self.motionlight.update(
                    {'state': 'none'}
                )
                

        for mode in self.light_modes:
            if 'automations' in mode:
                mode['original'] = copy.deepcopy(mode['automations'])
                self.checkTimesinAutomations(mode['automations'])

                for automation in mode['automations']:
                    if (
                        'adjust' in automation['state']
                        and self.adjustLight_enabled
                    ):
                        string:str = self.lights[0]
                        if (
                            string[:6] == 'light.'
                            or string[:7] == 'switch.'
                        ):
                            self.adjustLight_enabled = True

                    if 'adaptive' in automation['state']:
                        self.has_adaptive_state = True
            elif 'state' in mode:
                if 'adaptive' in mode['state']:
                    self.has_adaptive_state = True
            elif not 'state' in mode:
                mode.update(
                    {'state': 'none'}
                )


        if self.motionlight and not self.automations:
            # Sets a valid state turn off in automation when motionlight turns on light for when motion ends
            self.automations = [{'time': '00:00:00', 'state': 'turn_off'}]
            self.automations_original = copy.deepcopy(self.automations)


        self.ADapi.run_daily(self.rundaily_Automation_Adjustments, '00:01:00')

        for time in self.times_to_adjust_light:
            if not self.ADapi.now_is_between(time, '00:01:00'):
                self.ADapi.run_once(self.run_daily_lights, time)

        if not self.has_adaptive_state:
            self.adaptive_switch = None

            # Persistent storage
        if self.usePersistentStorage and self.adjustLight_enabled:
            with open(self.JSON_PATH, 'r') as json_read:
                lightwand_data = json.load(json_read)

            if not self.lights[0] in lightwand_data:
                lightwand_data.update(
                    { self.lights[0] : {"isON" : self.isOn}}
                )
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)
            elif self.isON == None:
                self.isON = lightwand_data[self.lights[0]]['isON'] == 'on'


        """ End initial setup for lights
        """


    def rundaily_Automation_Adjustments(self, kwargs) -> None:
        """ Adjusts solar based times in automations daily
        """
        if self.automations:
            self.automations = copy.deepcopy(self.automations_original)
            self.checkTimesinAutomations(self.automations)

        if self.motionlight:
            if type(self.motionlight) == list:
                self.motionlight = copy.deepcopy(self.motions_original)
                self.checkTimesinAutomations(self.motionlight)

        for mode in self.light_modes:
            if 'automations' in mode:
                mode['automations'] = copy.deepcopy(mode['original'])
                self.checkTimesinAutomations(mode['automations'])

        for time in self.times_to_adjust_light:
            self.ADapi.run_once(self.run_daily_lights, time)


    def checkTimesinAutomations(self, automations:list) -> None:
        """ Find and adjust times in automations based on clock and sunrise/sunset times.
            Set up some default behaviour.
        """

        automationsToDelete:list = []
        timeToAdd: timedelta = datetime.timedelta(minutes = 0)
        calculateFromSunrise:bool = False
        calculateFromSunset:bool = False

            # Check if a starttime at midnight is defined
        test_time = self.ADapi.parse_time('00:00:00')
        if not 'time' in automations[0]:
            automations[0].update(
                {'time': '00:00:00'}
            )
        elif test_time != self.ADapi.parse_time(automations[0]['time']):
            automations.insert(0,
                {'time': '00:00:00', 'state': 'turn_off'}
            )

            # Corrects times in automation
        for num, automation in enumerate(automations):
                # Checks if multiple times is configured and parse all times 
            if 'orLater' in automation:
                orLaterDate = self.ADapi.parse_datetime(automation['orLater'], today = True)
                timeDate = self.ADapi.parse_datetime(automation['time'], today = True)
                if (
                    automation['orLater'][:7] == 'sunrise'
                    or automation['time'][:7] == 'sunrise'
                ):
                    calculateFromSunrise = True
                    calculateFromSunset = False
                elif (
                    automation['orLater'][:6] == 'sunset'
                    or automation['time'][:6] == 'sunset'
                ):
                    calculateFromSunrise = False
                    calculateFromSunset = True

                if self.ADapi.parse_time(automation['time']) < self.ADapi.parse_time(automation['orLater']):
                    timeToAdd = orLaterDate - timeDate
                    """ Check if your times are acting as planned. Uncomment line below to get logging on time change """
                    #self.ADapi.log(f"Time defined with 'orLater': {self.ADapi.parse_time(automation['orLater'])} is later than time: {self.ADapi.parse_time(automation['time'])}")
                    automation['time'] = automation['orLater']
                else:
                    timeToAdd = timeDate - orLaterDate

                automation.pop('orLater')

            elif timeToAdd > datetime.timedelta(minutes = 0):
                changeTime = False
                if 'fixed' in automation:
                    timeToAdd = datetime.timedelta(minutes = 0)
                elif str(automation['time'])[:7] == 'sunrise':
                    if calculateFromSunrise:
                        changeTime = True

                elif str(automation['time'])[:6] == 'sunset':
                    if calculateFromSunrise:
                        calculateFromSunrise = False
                        timeToAdd = datetime.timedelta(minutes = 0)
                    elif calculateFromSunset:
                        changeTime = True

                else:
                    changeTime = True

                if changeTime:
                    newtime = self.ADapi.parse_datetime(automation['time']) + timeToAdd
                    """ Check if your times are acting as planned. Uncomment line below to get logging on time change """
                    #self.ADapi.log(f"Added {timeToAdd} to {automation['time']}. Light will change at {str(newtime.time())}")
                    automation['time'] = str(newtime.time())

                # Deletes automations that are earlier than previous time. Useful when both time with sunset and fixed time is given in automations
            if test_time <= self.ADapi.parse_time(automation['time']):
                test_time = self.ADapi.parse_time(automation['time'])
            elif test_time > self.ADapi.parse_time(automation['time']):
                if not 'fixed' in automation:
                    """ Check if your times are acting as planned. Uncomment line below to get logging on time change """
                    #self.ADapi.log(f"Deletes automation: {automations[num]} based on {test_time} > {self.ADapi.parse_time(automation['time'])}")
                    automationsToDelete.append(num)

            # Delete automations with unvalid times
        for num in reversed(automationsToDelete):
            del automations[num]


            # Adds valid state and sets up times to adjust lights
        for automation in automations:
            if not 'state' in automation:
                automation.update(
                    {'state': 'none'}
                )
            if not automation['time'] in self.times_to_adjust_light:
                # Adjust lights with new light_data on given time
                self.times_to_adjust_light.append(automation['time'])
            if 'dimrate' in automation:
                if 'brightness' in automation['light_data']:
                    brightness = int(automation['light_data']['brightness'])
                elif 'value' in automation['light_data']:
                    brightness = int(automation['light_data']['value'])

                if prv_brightness > brightness:
                    stopDimMin:int = math.ceil((prv_brightness - brightness) * automation['dimrate'])
                    stopDimTime = self.ADapi.parse_datetime(automation['time']) + datetime.timedelta(minutes = stopDimMin)
                    automation['stop'] = str(stopDimTime.time())
                elif prv_brightness < brightness:
                    stopDimMin:int = math.ceil((brightness - prv_brightness) * automation['dimrate'])
                    stopDimTime = self.ADapi.parse_datetime(automation['time']) + datetime.timedelta(minutes = stopDimMin)
                    automation['stop'] = str(stopDimTime.time())

            if 'light_data' in automation:
                if 'brightness' in automation['light_data']:
                    prv_brightness = int(automation['light_data']['brightness'])
                elif 'value' in automation['light_data']:
                    prv_brightness = int(automation['light_data']['value'])


    def correctBrightness(self, oldBrightness:int, newBrightness:int) -> None:
        """ Correct brightness in lists if the difference between values is +/- 1 when setting new brightness
            to avoid repeatedly attempting to set an invalid brightness value in the dimmer
        """
        if self.automations:
            for automation in self.automations_original:
                if 'light_data' in automation:
                    if 'brightness' in automation['light_data']:
                        if oldBrightness == int(automation['light_data']['brightness']):
                            automation['light_data'].update({'brightness': newBrightness})
                    elif 'value' in automation['light_data']:
                        if oldBrightness == int(automation['light_data']['value']):
                            automation['light_data'].update({'value': newBrightness})

        if self.motionlight:
            if type(self.motionlight) == list:
                for automation in self.motions_original:
                    if 'light_data' in automation:
                        if 'brightness' in automation['light_data']:
                            if oldBrightness == int(automation['light_data']['brightness']):
                                automation['light_data'].update({'brightness': newBrightness})
                        elif 'value' in automation['light_data']:
                            if oldBrightness == int(automation['light_data']['value']):
                                automation['light_data'].update({'value': newBrightness})

        for mode in self.light_modes:
            if 'automations' in mode:
                for automation in mode['original']:
                    if 'light_data' in automation:
                        if 'brightness' in automation['light_data']:
                            if oldBrightness == int(automation['light_data']['brightness']):
                                automation['light_data'].update({'brightness': newBrightness})
                        elif 'value' in automation['light_data']:
                            if oldBrightness == int(automation['light_data']['value']):
                                automation['light_data'].update({'value': newBrightness})


    def run_daily_lights(self, kwargs) -> None:
        """ Updates light with new data based on times given in configuration
        """
        if not self.motion:
            self.current_OnCondition = None
            self.current_LuxCondition = None
            self.setLightMode()
        elif type(self.motionlight) == list:
            target_num = self.find_time(automation = self.motionlight)
            if self.motionlight[target_num]['state'] == 'turn_off':
                if self.isON or self.isON == None:
                    self.turn_off_lights()
            elif (
                self.dim_while_motion
                and self.motion
            ):
                self.setMotion()


    def find_time(self, automation:list) -> int:
        """ Helper to find correct list item with light data based on time
        """
        prev_time = '00:00:00'
        target_num:int = 0
        for target_num, automations in enumerate(automation):
            if self.ADapi.now_is_between(prev_time, automations['time']):
                testtid = self.ADapi.parse_time(automations['time'])
                if (
                    datetime.datetime.today().hour == testtid.hour
                    and datetime.datetime.today().minute == testtid.minute
                    and datetime.datetime.today().second == testtid.second
                ):
                    pass
                elif target_num != 0:
                    target_num -= 1
                return target_num
            prev_time = automations['time']
        return target_num


        # Check conditions and constraints
    def checkOnConditions(self) -> bool:
        for conditions in self.conditions:
            if not eval(conditions):
                return False
        return True


    def checkLuxConstraints(self) -> bool:
        if self.lux_constraint != None:
            if self.rain_amount > 1:
                if self.outLux >= self.lux_constraint * 1.5:
                    return False
            elif self.outLux >= self.lux_constraint:
                return False
        if self.room_lux_constraint != None:
            if self.roomLux >= self.room_lux_constraint:
                return False
        return True


    def setLightMode(self, lightmode:str = 'None') -> None:
        """ The main function/logic to handle turning on / off lights based on mode selected.
        """
        # Checking if anything has changed.
        if (
            (lightmode == self.lightmode
            or lightmode == 'None')
            and self.current_OnCondition == self.checkOnConditions()
            and self.current_LuxCondition == self.checkLuxConstraints()
            and str(lightmode)[:5] != 'reset'
        ):
            if self.motionlight:
                if not self.wereMotion:
                    return
                elif not self.motion:
                    self.wereMotion = False
            else :
                # Nothing has changed.
                return
        
        self.current_OnCondition = self.checkOnConditions()
        self.current_LuxCondition = self.checkLuxConstraints()

        if lightmode != self.lightmode:
            if self.dimHandler != None:
                if self.ADapi.timer_running(self.dimHandler):
                    try:
                        self.ADapi.cancel_timer(self.dimHandler)
                    except Exception:
                        self.ADapi.log(f"Could not stop dim timer for {entity}.", level = 'DEBUG')
                self.dimHandler = None
            
            if (
                str(lightmode)[:5] != 'night'
                and str(self.lightmode)[:5] == 'night'
                and self.adaptive_sleep_mode != None
            ):
                self.ADapi.turn_off(self.adaptive_sleep_mode)

        if lightmode == 'None':
            lightmode = self.lightmode
        
        if lightmode == 'morning':
            # Only do morning mode if Lux and conditions are valid
            if (
                not self.current_OnCondition
                or not self.current_LuxCondition
            ):
                lightmode = 'normal'

        if lightmode == 'custom':
            # Custom mode will break any automation and keep light as is
            if self.has_adaptive_state:
                self.setAdaptiveLightingOff()
            self.lightmode = lightmode
            return


        for mode in self.light_modes:
            # Finds out if new lightmode is configured for light and executes
            if lightmode == mode['mode']:
                self.lightmode = lightmode
                if 'automations' in mode:
                    # Automation sets light according to time of day with Lux and Conditions constraints
                    if (
                        self.current_LuxCondition
                        and self.current_OnCondition
                    ):
                        self.setLightAutomation(automations = mode['automations'])
                    elif self.isON or self.isON == None:
                        self.turn_off_lights()
                    return

                if (
                    'turn_on' in mode['state']
                    or 'none' in mode['state']
                    or 'lux_controlled' in mode['state']
                ):
                    if 'lux_controlled' in mode['state']:
                        if not self.current_LuxCondition:
                            if self.isON or self.isON == None:
                                self.turn_off_lights()
                            return

                    if self.has_adaptive_state:
                        self.setAdaptiveLightingOff()

                    if 'light_data' in mode:
                        # Turns on light with given data. Lux constrained but Conditions do not need to be met
                        self.turn_on_lights(light_data = mode['light_data'])

                    elif (
                        'offset' in mode
                        and self.automations
                    ):
                        # Sets light with offset from brightness defined in automations
                        self.setLightAutomation(automations = mode, offset = mode['offset'])


                    elif self.automations:
                        # Sets light with brightness defined in automations
                        self.setLightAutomation(automations = mode)

                    elif not self.isON or self.isON == None:
                        self.turn_on_lights()
                    return
                    
                elif 'turn_off' in mode['state']:
                    # Turns off light
                    if self.isON or self.isON == None:
                        self.turn_off_lights()
                    return
                    
                elif 'manual' in mode['state']:
                    # Manual on/off. Keeps light as is or turn on/off with other methods
                    if self.has_adaptive_state:
                        self.setAdaptiveLightingOff()
                    return

                elif 'adaptive' in mode['state']:
                    if not self.isON or self.isON == None:
                        self.turn_on_lights()
                    self.setAdaptiveLightingOn()
                    if 'max_brightness_pct' in mode:
                        if 'min_brightness_pct' in mode:
                            self.ADapi.call_service('adaptive_lighting/change_switch_settings',
                                entity_id = self.adaptive_switch,
                                max_brightness = mode['max_brightness_pct'],
                                min_brightness = mode['min_brightness_pct'],
                                namespace = self.HASS_namespace
                            )
                        else:
                            self.ADapi.call_service('adaptive_lighting/change_switch_settings',
                                entity_id = self.adaptive_switch,
                                max_brightness = mode['max_brightness_pct'],
                                namespace = self.HASS_namespace
                            )
                    else:
                        self.ADapi.call_service('adaptive_lighting/change_switch_settings',
                            entity_id = self.adaptive_switch,
                            use_defaults = 'configuration',
                            namespace = self.HASS_namespace
                        )

                    return


            # Default turn off if away/off/night is not defined as a mode in light
        if (
            lightmode == 'away'
            or lightmode == 'off'
            or lightmode == 'off_' + str(self.ADapi.name)
        ):
            self.lightmode = lightmode
            if self.isON or self.isON == None:
                self.turn_off_lights()
            return

        elif (
            lightmode == 'night'
            or lightmode == 'night_' + str(self.ADapi.name)
        ):
            self.lightmode = lightmode
            if self.adaptive_sleep_mode != None:
                self.ADapi.turn_on(self.adaptive_sleep_mode)
            elif self.isON or self.isON == None:
                self.turn_off_lights()
            return

            # Default turn on maximum light if not fire/wash is defined as a mode in light
        elif (
            lightmode == 'fire'
            or lightmode == 'wash'
        ):
            self.lightmode = lightmode
            if self.has_adaptive_state:
                self.setAdaptiveLightingOff()
            self.turn_on_lights_at_max()
            return

            # Mode is normal or not valid for light. Checks Lux and Conditions constraints and does defined automations for light
        self.lightmode = 'normal'
        if (
            self.current_OnCondition
            and self.current_LuxCondition
        ):
            if self.automations:
                self.setLightAutomation(automations = self.automations)
            elif not self.isON or self.isON == None:
                if self.has_adaptive_state:
                    self.setAdaptiveLightingOff()
                self.turn_on_lights()
        elif self.isON or self.isON == None:
            self.turn_off_lights()


    def setMotion(self, lightmode:str = 'None') -> None:
        """ Sets motion lights when motion is detected insted of using setModeLight
        """
        if (
            lightmode == 'off'
            or lightmode == 'custom'
        ):
            self.lightmode = lightmode
            return

        if lightmode == 'None':
            lightmode = self.lightmode
        elif str(lightmode)[:5] == 'reset':
            lightmode = 'normal'
        elif str(lightmode)[:6] == 'normal':
            lightmode = 'normal'

        mode_brightness:int = 0
        offset:int = 0
        adaptive_min_mode:int = 0
        adaptive_max_mode:int = -1
        target_light_data:dict = {}
        motion_light_data:dict = {}
        self.motion = True
        self.wereMotion = True
        


            # Get light data for motion setting
        if (
            self.last_motion_brightness == 0
            or self.dim_while_motion
            or self.lightmode != lightmode
        ):
            if type(self.motionlight) == list:
                motion_light_data, self.last_motion_brightness = self.getLightAutomationData(automations = self.motionlight)

            elif 'light_data' in self.motionlight:
                if 'brightness' in self.motionlight['light_data']:
                    self.last_motion_brightness = self.motionlight['light_data']['brightness']
                elif 'value' in self.motionlight['light_data']:
                    self.last_motion_brightness = self.motionlight['light_data']['value']

                motion_light_data = self.motionlight

            elif 'offset' in self.motionlight:
                offset = self.motionlight['offset']

            elif 'state' in self.motionlight:
                if 'adaptive' in self.motionlight['state']:
                    if 'max_brightness_pct' in self.motionlight:
                        self.last_motion_brightness = (255*self.motionlight['max_brightness_pct'])/100
                        motion_light_data = {'state': 'adaptive'}


        self.lightmode = lightmode

            # Get light data if lightmode is not normal automations
        if lightmode != 'normal':
            for mode in self.light_modes:
                """ Finds out if new lightmode is configured for light and executes
                """
                if lightmode == mode['mode']:

                        # Do not adjust if current mode's state is manual.
                    if 'state' in mode:
                        if 'manual' in mode['state']:
                            if self.has_adaptive_state:
                                self.setAdaptiveLightingOff()
                            return
                        elif 'adaptive' in mode['state']:
                            if 'noMotion' in mode:
                                self.motion = False
                                self.setLightMode(lightmode = lightmode)
                                return
                            if 'max_brightness_pct' in mode:
                                adaptive_max_mode = mode['max_brightness_pct']
                                if 'min_brightness_pct' in mode:
                                    adaptive_min_mode = mode['min_brightness_pct']

                    if self.wereMotion:   
                        if 'automations' in mode:
                            target_light_data, mode_brightness = self.getLightAutomationData(automations = mode['automations'])
                            if (
                                offset > 0
                                and not 'noMotion' in mode
                            ):
                                if self.has_adaptive_state:
                                    self.setAdaptiveLightingOff()
                                if (
                                    self.checkOnConditions()
                                    and self.checkLuxConstraints()
                                ):
                                    self.setLightAutomation(automations = mode['automations'], offset = offset)
                                return

                            elif (
                                self.last_motion_brightness <= mode_brightness
                                or 'noMotion' in mode
                            ):
                                if self.has_adaptive_state:
                                    self.setAdaptiveLightingOff()
                                if (
                                    self.checkOnConditions()
                                    and self.checkLuxConstraints()
                                ):
                                    if 'light_data' in target_light_data:
                                        self.turn_on_lights(light_data = target_light_data['light_data'])
                                return

                        elif 'light_data' in mode:
                            if 'lux_controlled' in mode['state']:
                                if not self.checkLuxConstraints():
                                    return

                            if 'brightness' in mode['light_data']:
                                mode_brightness = mode['light_data']['brightness']
                            elif 'value' in mode['light_data']:
                                mode_brightness = mode['light_data']['value']
                            if (
                                self.last_motion_brightness <= mode_brightness
                                or 'noMotion' in mode
                            ):
                                if self.has_adaptive_state:
                                    self.setAdaptiveLightingOff()
                                self.turn_on_lights(light_data = mode['light_data'])
                                return

                        elif 'offset' in mode:
                            if 'lux_controlled' in mode['state']:
                                if not self.checkLuxConstraints():
                                    return

                            automation_light_data, automation_brightness = self.getLightAutomationData(automations = self.automations)
                            if (
                                offset == 0
                                and type(self.motionlight) == list
                                and self.last_motion_brightness <= automation_brightness + mode['offset']
                            ):
                                if self.has_adaptive_state:
                                    self.setAdaptiveLightingOff()
                                self.setLightAutomation(automations = self.motionlight, offset = mode['offset'])
                                return

                            elif (
                                (offset > 0
                                and offset < mode['offset'])
                                or 'noMotion' in mode
                            ):
                                if self.has_adaptive_state:
                                    self.setAdaptiveLightingOff()
                                self.setLightAutomation(automations = self.automations, offset = mode['offset'])
                                return

            if (
                lightmode == 'fire'
                or lightmode == 'wash'
            ):
                if self.has_adaptive_state:
                    self.setAdaptiveLightingOff()
                self.turn_on_lights_at_max()
                return


        if (
            not self.checkOnConditions()
            or not self.checkLuxConstraints()
        ):
            return


        if (
            self.last_motion_brightness > 0
            and not motion_light_data
        ):
            return

            # Set light to motion

        if motion_light_data:
            if (
                'turn_on' in motion_light_data['state']
                or 'none' in motion_light_data['state']
            ):
                if self.has_adaptive_state:
                    self.setAdaptiveLightingOff()

                if 'light_data' in motion_light_data:
                    self.turn_on_lights(light_data = motion_light_data['light_data'])
                
                elif self.automations:
                    # Sets light with brightness defined in automations
                    self.setLightAutomation(automations = self.motionlight)
                else:
                    self.turn_on_lights()

            if 'turn_off' in motion_light_data['state']:
                self.turn_off_lights()
        
        elif (
            offset != 0
            and self.automations
        ):
            if self.has_adaptive_state:
                self.setAdaptiveLightingOff()
            self.setLightAutomation(automations = self.motionlight, offset = offset)


        elif 'state' in self.motionlight:
            if 'adaptive' in self.motionlight['state']:
                if not self.isON or self.isON == None:
                    self.turn_on_lights()

                self.setAdaptiveLightingOn()
                if 'max_brightness_pct' in self.motionlight:
                    if 'min_brightness_pct' in self.motionlight:
                        if (
                            adaptive_max_mode > self.motionlight['max_brightness_pct']
                            and adaptive_min_mode >= self.motionlight['min_brightness_pct']
                        ):
                            self.ADapi.call_service('adaptive_lighting/change_switch_settings',
                                entity_id = self.adaptive_switch,
                                max_brightness = adaptive_max_mode,
                                min_brightness = adaptive_min_mode,
                                namespace = self.HASS_namespace
                            )
                        elif (
                            self.motionlight['max_brightness_pct'] > adaptive_max_mode
                            and self.motionlight['min_brightness_pct'] >= adaptive_min_mode
                        ):
                            self.ADapi.call_service('adaptive_lighting/change_switch_settings',
                                entity_id = self.adaptive_switch,
                                max_brightness = self.motionlight['max_brightness_pct'],
                                min_brightness = self.motionlight['min_brightness_pct'],
                                namespace = self.HASS_namespace
                            )

                        # min_brightness_pct is not set
                    elif adaptive_max_mode  > self.motionlight['max_brightness_pct']:
                        self.ADapi.call_service('adaptive_lighting/change_switch_settings',
                            entity_id = self.adaptive_switch,
                            max_brightness = adaptive_max_mode,
                            namespace = self.HASS_namespace
                        )

                    elif self.motionlight['max_brightness_pct'] > adaptive_max_mode:
                        self.ADapi.call_service('adaptive_lighting/change_switch_settings',
                            entity_id = self.adaptive_switch,
                            max_brightness = self.motionlight['max_brightness_pct'],
                            namespace = self.HASS_namespace
                        )
                else:
                    self.ADapi.call_service('adaptive_lighting/change_switch_settings',
                        entity_id = self.adaptive_switch,
                        use_defaults = 'configuration',
                        namespace = self.HASS_namespace
                    )
            else:
                self.turn_on_lights()


    def setLightAutomation(self, automations:list, offset:int = 0 ) -> None:
        """ Set light data
        """
        target_light = dict()
        try:
            target_num = self.find_time(automation = automations)
        except TypeError:
            target_num = 0
            automations = [automations]

        target_num2 = self.find_time(automation = self.automations)

        if (
            (automations[target_num]['state'] == 'adjust' and self.isON)
            or (automations[target_num]['state'] != 'adjust' and automations[target_num]['state'] != 'turn_off')
        ):
            # Only 'adjust' lights if already on, or if not turn off.
            if (
                not 'light_data' in automations[target_num]
                and 'light_data' in self.automations[target_num2]
            ):
                # If provided automation is configured without light_data it will fetch light_data from main automations
                target_num = target_num2
                target_light = self.automations

            else:
                target_light = automations

            if 'light_data' in target_light[target_num]:

                # Brightness 0-255 for HA and Zigbee2mqtt control
                if 'brightness' in target_light[target_num]['light_data']:
                    light_dataBrightness = int(target_light[target_num]['light_data']['brightness'])
                elif 'value' in target_light[target_num]['light_data']:
                    light_dataBrightness = int(target_light[target_num]['light_data']['value'])


                    """ Correct brightness in lists if the difference between values is +/- 1 
                        to avoid repeatedly attempting to set an invalid brightness value in the dimmer
                    """
                if (
                    not 'dimrate' in target_light[target_num]
                    and offset == 0
                ):
                    if (
                        self.brightness +1 == light_dataBrightness
                        or self.brightness -1 == light_dataBrightness
                    ):
                        self.correctBrightness(
                            oldBrightness = light_dataBrightness,
                            newBrightness = self.brightness    
                        )
                        if 'brightness' in target_light[target_num]['light_data']:
                            target_light[target_num]['light_data']['brightness'] = self.brightness
                        elif 'value' in target_light[target_num]['light_data']:
                            target_light[target_num]['light_data']['value'] = self.brightness

                        
                target_light_data = copy.deepcopy(target_light[target_num]['light_data'])

                if 'dimrate' in target_light[target_num]:
                    if self.ADapi.now_is_between(target_light[target_num]['time'], target_light[target_num]['stop']):
                        dimbrightness = self.findBrightnessWhenDimRate(automation = target_light) + offset
                        if 'brightness' in target_light_data:
                            target_light_data.update(
                                {'brightness' : dimbrightness}
                            )
                        elif 'value' in target_light_data:
                            target_light_data.update(
                                {'value' : dimbrightness}
                            )

                elif offset != 0:
                    brightness_offset = math.ceil(int(target_light_data['brightness']) + offset)
                    if brightness_offset > 0:
                        if brightness_offset >= 255:
                            brightness_offset = 254
                    else:
                        brightness_offset = 1
                    if 'brightness' in target_light_data:
                        target_light_data.update(
                            {'brightness' : brightness_offset}
                        )
                    elif 'value' in target_light_data:
                        target_light_data.update(
                            {'value' : brightness_offset}
                        )

                if self.has_adaptive_state:
                    self.setAdaptiveLightingOff()
                self.turn_on_lights(light_data = target_light_data)


            elif 'adaptive' in automations[target_num]['state']:
                if not self.isON or self.isON == None:
                    self.turn_on_lights()
                self.setAdaptiveLightingOn()
                if 'max_brightness_pct' in automations[target_num]:
                    if 'min_brightness_pct' in automations[target_num]:
                        self.ADapi.call_service('adaptive_lighting/change_switch_settings',
                            entity_id = self.adaptive_switch,
                            max_brightness = automations[target_num]['max_brightness_pct'],
                            min_brightness = automations[target_num]['min_brightness_pct'],
                            namespace = self.HASS_namespace
                        )
                    else:
                        self.ADapi.call_service('adaptive_lighting/change_switch_settings',
                            entity_id = self.adaptive_switch,
                            max_brightness = automations[target_num]['max_brightness_pct'],
                            namespace = self.HASS_namespace
                        )
                else:
                    self.ADapi.call_service('adaptive_lighting/change_switch_settings',
                        entity_id = self.adaptive_switch,
                        use_defaults = 'configuration',
                        namespace = self.HASS_namespace
                    )

            elif not self.isON or self.isON == None:
                if self.has_adaptive_state:
                    self.setAdaptiveLightingOff()
                self.turn_on_lights()

        elif (
            automations[target_num]['state'] != 'adjust'
            and (self.isON or self.isON == None)
        ):
            self.turn_off_lights()


    def getLightAutomationData(self, automations:list) -> (dict,int):
        """ Returns brightness for mode if mode has automations
        """
        target_light = dict()
        try:
            target_num = self.find_time(automation = automations)
        except TypeError:
            return target_light, 0

        if not 'light_data' in automations[target_num]:
            # Provided automation is configured without light_data
            return automations[target_num], 0

        target_light = automations[target_num]

        if 'light_data' in target_light:
            target_light_data = copy.deepcopy(target_light)
            dimbrightness:int = 0
            if 'dimrate' in target_light_data:
                if self.ADapi.now_is_between(target_light_data['time'], target_light_data['stop']):
                    dimbrightness = self.findBrightnessWhenDimRate(automation = automations)

            # Brightness 0-255 for HA and Zigbee2mqtt control
            if 'brightness' in target_light_data['light_data']:
                if dimbrightness > 0:
                    target_light_data['light_data'].update(
                        {'brightness' : dimbrightness}
                    )
                    return target_light_data, dimbrightness

                return target_light_data, int(target_light_data['light_data']['brightness'])

            # Value in percent for Zwave JS over MQTT
            elif 'value' in target_light_data['light_data']:
                if dimbrightness > 0:
                    target_light_data['light_data'].update(
                        {'value' : dimbrightness}
                    )
                    return target_light_data, dimbrightness

                return target_light_data, int(target_light_data['light_data']['value'])

        return target_light, 0


    def findBrightnessWhenDimRate(self, automation:list) -> int:
        """ Dim by one dimming to have the light dim down by one brightness every given minute.
        """
        originalBrightness:int = 0
        newbrightness:int = 0
        targetBrightness:int = 0
        brightnessvalue:str = 'brightness'

        target_num = self.find_time(automation = automation)
        timeDate = self.ADapi.parse_datetime(automation[target_num]['time'],
            today = True
        )

        timedifference = math.floor(((datetime.datetime.now() - timeDate).total_seconds())/60)

        if 'brightness' in automation[target_num -1]['light_data']:
            originalBrightness = automation[target_num -1]['light_data']['brightness']
            targetBrightness = automation[target_num]['light_data']['brightness']

        elif 'value' in automation[target_num -1]['light_data']:
            originalBrightness = automation[target_num -1]['light_data']['value']
            targetBrightness = automation[target_num]['light_data']['value']

            brightnessvalue = 'value'


        if originalBrightness > targetBrightness:
            newbrightness = math.ceil(originalBrightness - math.floor(timedifference/automation[target_num]['dimrate']))
            if (
                newbrightness < targetBrightness
                or newbrightness > originalBrightness
            ):
                # Outside dim target for dimming down
                return targetBrightness

            if self.dimHandler == None:
                runtime = datetime.datetime.now() + datetime.timedelta(minutes = int(automation[target_num]['dimrate']))
                self.dimHandler = self.ADapi.run_every(self.dimBrightnessByOne, runtime, automation[target_num]['dimrate'] *60,
                    targetBrightness = targetBrightness,
                    brightnessvalue = brightnessvalue
                )
                self.ADapi.run_at(self.StopDimByOne, automation[target_num]['stop'])

        elif originalBrightness < targetBrightness:
            newbrightness = math.ceil(originalBrightness + math.floor(timedifference/automation[target_num]['dimrate']))
            if (
                newbrightness > targetBrightness
                or newbrightness < originalBrightness
            ):
                # Outside dim target for dimming up
                return targetBrightness
            
            if self.dimHandler == None:
                runtime = datetime.datetime.now() + datetime.timedelta(minutes = int(automation[target_num]['dimrate']))
                self.dimHandler = self.ADapi.run_every(self.increaseBrightnessByOne, runtime, automation[target_num]['dimrate'] *60,
                    targetBrightness = targetBrightness,
                    brightnessvalue = brightnessvalue
                )
                self.ADapi.run_at(self.StopDimByOne, automation[target_num]['stop'])

        return newbrightness


    def dimBrightnessByOne(self, kwargs) -> None:
        """ Dim by one dimming to have the light dim down by one brightness every given minute.
        """
        targetBrightness = kwargs['targetBrightness']
        brightnessvalue = kwargs['brightnessvalue']
        if self.brightness > targetBrightness:
            self.brightness -= 1
            ld = {brightnessvalue: self.brightness}
            self.turn_on_lights(light_data = ld)
        else:
            self.ADapi.run_in(self.StopDimByOne, 1)


    def increaseBrightnessByOne(self, kwargs) -> None:
        """ Increase brightness by one every given minute.
        """
        targetBrightness = kwargs['targetBrightness']
        brightnessvalue = kwargs['brightnessvalue']
        if self.brightness < targetBrightness:
            self.brightness += 1
            ld = {brightnessvalue: self.brightness}
            self.turn_on_lights(light_data = ld)
        else:
            self.ADapi.run_in(self.StopDimByOne, 1)


    def StopDimByOne(self, kwargs) -> None:
        """ Stops dimming by one
        """
        if self.dimHandler != None:
            if self.ADapi.timer_running(self.dimHandler):
                try:
                    self.ADapi.cancel_timer(self.dimHandler)
                except Exception:
                    self.ADapi.log(f"Could not stop dim timer for {entity}.", level = 'DEBUG')
            self.dimHandler = None
            

    def BrightnessUpdated(self, entity, attribute, old, new, kwargs) -> None:
        """ Updates brightness in light to check when motion if motionlight is brighter/dimmer than light is now.
        """
        try:
            self.brightness = int(new)
        except TypeError:
            self.brightness = 0
        except Exception as e:
            self.ADapi.log(f"Error getting new brightness: {new}. Exception: {e}", level = 'WARNING')


    def setAdaptiveLightingOn(self) -> None:
        """ Set Adaptive lighting to take control over brightness to on
        """
        if self.adaptive_switch != None:
            self.ADapi.call_service('adaptive_lighting/set_manual_control',
                entity_id = self.adaptive_switch,
                manual_control = False,
                namespace = self.HASS_namespace
            )
        else:
            self.ADapi.log(
                f"Adaptive lighting switch not defined in configuration. Define switch with: 'adaptive_switch'",
                level = 'WARNING'
            )


    def setAdaptiveLightingOff(self) -> None:
        """ Set Adaptive lighting to take control over brightness to on
        """
        if self.adaptive_switch != None:
            self.ADapi.call_service('adaptive_lighting/set_manual_control',
                entity_id = self.adaptive_switch,
                manual_control = True,
                namespace = self.HASS_namespace
            )
        else:
            self.ADapi.log(
                f"Adaptive lighting switch not defined in configuration. Define switch with: 'adaptive_switch'",
                level = 'WARNING'
            )


    def update_isOn_lights(self, entity, attribute, old, new, kwargs) -> None:
        """ Updates isON state for light for checks and persistent storage when restarting Home Assistant
        """
        if new == 'on':
            self.isON = True

        elif new == 'off':
            self.isON = False


    def toggle_light(self, kwargs) -> None:
        """ Toggles light on/off
        """
        for light in self.lights:
            self.ADapi.toggle(light)


    def turn_on_lights(self, light_data:dict = {}) -> None:
        """ Turns on lights with given data
        """
        if (
            self.current_light_data != light_data
            or not self.isON
            or self.isON == None
        ):
            self.current_light_data = light_data

            if self.random_turn_on_delay == 0:
                for light in self.lights:
                    self.ADapi.turn_on(light, **light_data)
            else:
                for light in self.lights:
                    self.ADapi.run_in(self.turn_on_lights_with_delay, delay = 0,  random_start = 0, random_end = self.random_turn_on_delay, light = light, light_data = light_data)


    def turn_on_lights_with_delay(self, kwargs) -> None:
        """ Turns on lights with random delay
        """
        self.ADapi.turn_on(kwargs['light'], **kwargs['light_data'])

    def turn_on_lights_at_max(self) -> None:
        for light in self.lights:
            string:str = self.lights[0]
            if string[:6] == 'light.':
                if self.random_turn_on_delay == 0:
                    self.ADapi.turn_on(light, brightness = 254)
                else:
                    self.ADapi.run_in(self.turn_on_lights_with_delay, delay = 0,  random_start = 0, random_end = self.random_turn_on_delay, light = light, light_data = light_data)
            if string[:7] == 'switch.':
                self.ADapi.turn_on(light)


    def turn_off_lights(self) -> None:
        """ Turns off lights
        """
        if self.has_adaptive_state:
            self.setAdaptiveLightingOff()
        self.current_light_data = {}
        if self.random_turn_on_delay == 0:
            for light in self.lights:
                self.ADapi.turn_off(light)
        else:
            for light in self.lights:
                self.ADapi.run_in(self.turn_off_lights_with_delay, delay = 0,  random_start = 0, random_end = self.random_turn_on_delay, light = light)
        self.brightness = 0


    def turn_off_lights_with_delay(self, kwargs) -> None:
        """ Turns off light with random delay
        """
        self.ADapi.turn_off(kwargs['light'])


class MQTTLights(Light):
    """ Child class for lights to control lights directly over MQTT
    """

    def __init__(self, api,
        lights,
        light_modes,
        automations,
        motionlight,
        lux_constraint,
        room_lux_constraint,
        conditions,
        json_path,
        usePersistentStorage,
        MQTT_namespace,
        HASS_namespace,
        night_motion,
        adaptive_switch,
        adaptive_sleep_mode,
        dim_while_motion
    ):

        self.ADapi = api
        self.mqtt = self.ADapi.get_plugin_api("MQTT")
        self.MQTT_namespace = MQTT_namespace

        for light in lights:
            light_topic:str = light
            self.mqtt.mqtt_subscribe(light_topic)
            self.mqtt.listen_event(self.light_event_MQTT, "MQTT_MESSAGE",
                topic = light_topic,
                namespace = self.MQTT_namespace
            )

        super().__init__(self.ADapi,
            lights = lights,
            light_modes = light_modes,
            automations = automations,
            motionlight = motionlight,
            lux_constraint = lux_constraint,
            room_lux_constraint = room_lux_constraint,
            conditions = conditions,
            json_path = json_path,
            usePersistentStorage = usePersistentStorage,
            HASS_namespace = HASS_namespace,
            night_motion = night_motion,
            adaptive_switch = adaptive_switch,
            adaptive_sleep_mode = adaptive_sleep_mode,
            dim_while_motion = dim_while_motion
        )

            # Persistent storage
        if usePersistentStorage:
            with open(json_path, 'r') as json_read:
                lightwand_data = json.load(json_read)

            if not lights[0] in lightwand_data:
                self.turn_on_lights()
                self.isON = True
                lightwand_data.update(
                    { self.lights[0] : {"isON" : self.isON}}
                )
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)
            else:
                self.isON = lightwand_data[lights[0]]['isON']


    def light_event_MQTT(self, event_name, data, kwargs) -> None:
        try:
            lux_data = json.loads(data['payload'])
        except Exception as e:
            self.ADapi.log(f"Could not get payload from topic for {data['topic']}. Exception: {e}", level = 'DEBUG')
            return

        """ Get your X / Y color from setting RGB light.
            Uncomment the if and log lines below """
        #if 'color' in lux_data:
        #    self.ADapi.log(f"{data['topic']} Color in lux: {lux_data['color']}")

        if 'brightness' in lux_data:
            self.isON = lux_data['state'] == 'ON'
            if not self.isON or self.isON == None:
                self.brightness = 0
                self.current_light_data = {}
            else:
                try:
                    self.brightness = int(lux_data['brightness'])
                except (ValueError, TypeError):
                    self.brightness = 0

                if 'brightness' in self.current_light_data:
                    if self.current_light_data['brightness'] != self.brightness:
                        self.current_light_data = {}

        elif 'value' in lux_data:
            if type(lux_data['value']) == bool:
                self.isON = lux_data['value']

            elif type(lux_data['value']) == int:
                self.brightness = int(lux_data['value'])
                if (
                    lux_data['value'] > 0
                    and lux_data['value'] <= 100
                ):
                    self.isON = True
                elif lux_data['value'] == 0:
                    self.isON = False
                
                if 'value' in self.current_light_data:
                    if self.current_light_data['value'] != self.brightness:
                        self.current_light_data = {}
            else:
                """ No valid state based on program. Let user know
                """
                self.ADapi.log(
                    f"New value lux data for {self.lights[0]} is not bool or int and has not been programmed yet. "
                    "Please issue a request at https://github.com/Pythm/ad-Lightwand "
                    f"and provide what MQTT brigde and light type you are trying to control, in addition to the data sent from broker: {lux_data}"
                )

        elif 'state' in lux_data:
            self.isON = lux_data['state'] == 'ON'

        else:
            """ No valid state based on program. Let user know
            """
            self.ADapi.log(
                f"Unknown data for {self.lights[0]}. This has not been programmed yet. "
                "Please issue a request at https://github.com/Pythm/ad-Lightwand "
                f"and provide what MQTT brigde and light type you are trying to control, in addition to the data sent from broker: {lux_data}"
            )


    def turn_on_lights(self, light_data:dict = {}) -> None:

        if (
            self.current_light_data != light_data
            or not self.isON
            or self.isON == None
        ):
            self.current_light_data = light_data

            for light in self.lights:
                if 'zigbee2mqtt' in light:
                    if (
                        (not self.isON or self.isON == None)
                        and not light_data
                    ):
                        light_data.update(
                            {"state" : "ON"}
                        )

                if 'switch_multilevel' in light:
                    if not self.isON or self.isON == None:
                        light_data.update(
                            {"ON" : True}
                        )

                elif 'switch_binary' in light:
                    if not self.isON or self.isON == None:
                        light_data.update(
                            {"ON" : True}
                        )
                    if (
                        'value' in light_data
                        and (self.isON or self.isON == None)
                    ):
                        continue

                if self.random_turn_on_delay == 0:
                    payload = json.dumps(light_data)
                    self.mqtt.mqtt_publish(
                        topic = str(light) + "/set",
                        payload = payload,
                        namespace = self.MQTT_namespace
                    )
                else:
                    self.ADapi.run_in(self.turn_on_lights_with_delay, delay = 0,  random_start = 0, random_end = self.random_turn_on_delay, light = light, light_data = light_data)

            self.isON = True


    def turn_on_lights_with_delay(self, kwargs) -> None:
        """ Turns on light with random delay
        """
        payload = json.dumps(kwargs['light_data'])
        light = kwargs['light']
        self.mqtt.mqtt_publish(
            topic = str(light) + "/set",
            payload = payload,
            namespace = self.MQTT_namespace
        )


    def turn_on_lights_at_max(self) -> None:
        light_data:dict = {}

        if not self.isON or self.isON == None:
            light_data.update({"ON" : True})

        for light in self.lights:
            if 'zigbee2mqtt' in light:
                light_data.update({"brightness" : 254})
            elif 'switch_multilevel' in light:
                light_data.update({"value" : 99})

            if self.random_turn_on_delay == 0:
                payload = json.dumps(light_data)
                self.mqtt.mqtt_publish(
                    topic = str(light) + "/set",
                    payload = payload,
                    namespace = self.MQTT_namespace
                )
            else:
                self.ADapi.run_in(self.turn_on_lights_with_delay, delay = 0,  random_start = 0, random_end = self.random_turn_on_delay, light = light, light_data = light_data)

        self.isON = True


    def turn_off_lights(self) -> None:
        if self.has_adaptive_state:
            self.setAdaptiveLightingOff()
        self.current_light_data = {}
        if self.isON or self.isON == None:

            if self.random_turn_on_delay == 0:
                for light in self.lights:
                    self.mqtt.mqtt_publish(topic = str(light) + "/set", payload = "OFF", namespace = self.MQTT_namespace)
            else:
                for light in self.lights:
                    self.ADapi.run_in(self.turn_off_lights_with_delay, delay = 0,  random_start = 0, random_end = self.random_turn_on_delay, light = light)

            self.isON = False


    def turn_off_lights_with_delay(self, kwargs) -> None:
        """ Turns off light with random delay
        """
        light = kwargs['light']
        self.mqtt.mqtt_publish(topic = str(light) + "/set", payload = "OFF", namespace = self.MQTT_namespace)


class Toggle(Light):
    """ Child class for lights to control lights that dim by toggle
    """

    def __init__(self, api,
        lights,
        light_modes,
        automations,
        motionlight,
        lux_constraint,
        room_lux_constraint,
        conditions,
        toggle,
        num_dim_steps,
        toggle_speed,
        prewait_toggle,
        json_path,
        usePersistentStorage,
        HASS_namespace
    ):

        self.ADapi = api
        self.current_toggle:int = 0
        self.toggle_lightbulb:int = toggle * 2 - 1
        self.fullround_toggle:int = num_dim_steps * 2
        try:
            self.toggle_speed = float(toggle_speed)
        except(ValueError, TypeError):
            self.toggle_speed:float = 1
        self.prewait_toggle:float = prewait_toggle

            # Persistent storage
        if usePersistentStorage:
            with open(json_path, 'r') as json_read:
                lightwand_data = json.load(json_read)

            if not lights[0] in lightwand_data:
                if self.ADapi.get_state(lights[0]) == 'on':
                    self.current_toggle = self.toggle_lightbulb
                else:
                    self.current_toggle = 0
                lightwand_data.update(
                    { lights[0] : {"toggle" : self.current_toggle}}
                )
                with open(json_path, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)
            self.current_toggle = lightwand_data[lights[0]]['toggle']

        else:
            if self.ADapi.get_state(lights[0]) == 'on':
                self.current_toggle = self.toggle_lightbulb   

    
        super().__init__(self.ADapi,
            lights = lights,
            light_modes = light_modes,
            automations = automations,
            motionlight = motionlight,
            lux_constraint = lux_constraint,
            room_lux_constraint = room_lux_constraint,
            conditions = conditions,
            json_path = json_path,
            usePersistentStorage = usePersistentStorage,
            HASS_namespace = HASS_namespace,
            night_motion = False,
            adaptive_switch = None,
            adaptive_sleep_mode = None,
            dim_while_motion = False
        )


    def setLightMode(self, lightmode:str = 'None') -> None:
        if lightmode == 'None':
            lightmode = self.lightmode

        if lightmode == 'morning':
            if (
                not self.checkOnConditions()
                or not self.checkLuxConstraints()
            ):
                lightmode = 'normal'
                return

        if lightmode == 'custom':
            self.lightmode = lightmode
            return

        for mode in self.light_modes:
            if lightmode == mode['mode']:
                self.lightmode = lightmode
                if 'toggle' in mode:
                    # Turns on light regardless of Lux and Conditions
                    toggle_bulb = mode['toggle'] * 2 - 1
                    self.calculateToggles(toggle_bulb = toggle_bulb)

                elif 'state' in mode:
                    if 'turn_off' in mode['state']:
                        # Turns off light
                        self.turn_off_lights()
                        self.current_toggle = 0

                return

        if (
            lightmode == 'away'
            or lightmode == 'off'
            or lightmode == 'off_' + str(self.ADapi.name)
            or lightmode == 'night'
        ):
            self.lightmode = lightmode
            self.turn_off_lights()
            self.current_toggle = 0

            return

        elif (
            lightmode == 'fire'
            or lightmode == 'wash'
        ):
            self.lightmode = lightmode

            if self.current_toggle == 1:
                return

            self.calculateToggles(toggle_bulb = 1)

            return

        self.lightmode = 'normal'
        if (
            self.checkOnConditions()
            and self.checkLuxConstraints()
        ):
            if self.current_toggle == self.toggle_lightbulb:
                return

            self.calculateToggles(toggle_bulb = self.toggle_lightbulb)

        else:
            self.turn_off_lights()
            self.current_toggle = 0


    def setMotion(self, lightmode:str = 'None') -> None:
        """ Sets motion lights when motion is detected insted of using setModeLight
        """
        if lightmode == 'None':
            lightmode = self.lightmode

        if self.motionlight:
            if (
                not self.checkOnConditions()
                or not self.checkLuxConstraints()
            ):
                return

            """ Custom mode will break any automation and keep light as is
                Do not do motion mode if current mode is starting with night or is off
            """
            if (
                lightmode == 'off'
                or lightmode == 'custom'
            ):
                return

            string:str = lightmode
            if string[:5] == 'night':
                if not 'night' in self.motionlight:
                    self.motion = False
                    return

                # Do not adjust if current mode's state is manual.
            for mode in self.light_modes:
                if lightmode == mode['mode']:
                    if 'state' in mode:
                        if 'manual' in mode['state']:
                            return

            self.motion = True


            if 'toggle' in self.motionlight[0]:
                # Turns on light regardless of Lux and Conditions
                toggle_bulb = self.motionlight[0]['toggle'] * 2 - 1

                if self.current_toggle == toggle_bulb:
                    return

                self.calculateToggles(toggle_bulb = toggle_bulb)


    def calculateToggles(self, toggle_bulb:int = 1) -> None:
        if self.current_toggle == toggle_bulb:
            return

        elif self.current_toggle > toggle_bulb:
            self.current_toggle -= self.fullround_toggle
        sec = self.prewait_toggle

        while self.current_toggle < toggle_bulb:
            self.ADapi.run_in(self.toggle_light, sec)
            self.current_toggle += 1
            sec += self.toggle_speed

        sec += 120
        self.ADapi.run_in(self.checkToggleAfterRun, sec)


    def checkToggleAfterRun(self, kwargs) -> None:
        if self.ADapi.get_state(self.lights[0]) == 'off':
            toggle_bulb = self.current_toggle
            self.current_toggle = 0
            self.calculateToggles(toggle_bulb = toggle_bulb)