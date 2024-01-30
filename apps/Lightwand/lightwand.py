""" Lightwand by Pythm

    @Pythm / https://github.com/Pythm
"""

__version__ = "1.1.3"

import hassapi as hass
import datetime
import json
import csv
import math

class Room(hass.Hass):

    def initialize(self):

        self.mqtt = None

        self.roomlight:list = []
        
        self.LIGHT_MODE:str = 'normal'
        self.all_modes:list = ['normal', 'away', 'off', 'night', 'custom', 'fire', 'wash']
        self.ROOM_LUX:float = 0.0
        self.OUT_LUX:float = 0.0
        self.RAIN:float = 0.0
        self.JSON_PATH:str = ''

        # Disable custom for room to enable automation even when mode is custom
        self.exclude_from_custom = self.args.get('exclude_from_custom', False)

        self.mediaplayers = self.args.get('mediaplayers', {})

        # Namespaces for HASS and MQTT
        HASS_namespace = self.args.get('HASS_namespace', 'default')
        MQTT_namespace = self.args.get('MQTT_namespace', 'default')
    
        """ This listens to events fired as MODE_CHANGE with data beeing mode = 'yourmode'
            self.fire_event('MODE_CHANGE', mode = 'normal')
            If you already have implemented someting similar in your Home Assistant setup you can easily change
            MODE_CHANGE and > data['mode'] in mode_event to receive whatever data you are sending            
        """
        self.listen_event(self.mode_event, "MODE_CHANGE",
            namespace = HASS_namespace
        )

            # Presence detection
        self.presence = self.args.get('presence', {})
        for tracker in self.presence:
            self.listen_state(self.presence_change, tracker['tracker'],
                namespace = HASS_namespace,
                tracker = tracker
            )

        for tracker in self.presence:
            if self.get_state(tracker['tracker']) == 'home':
                self.LIGHT_MODE = 'normal'
                continue
            else:
                self.LIGHT_MODE = 'away'

            # Motion detection
        self.handle = None
        self.all_motion_sensors:dict = {} # To check if all motion sensors is off before turning off motion lights

        motion_sensors = self.args.get('motion_sensors', {})
        for motion_sensor in motion_sensors:
            self.listen_state(self.motion_state, motion_sensor['motion_sensor'],
                namespace = HASS_namespace,
                motion_sensor = motion_sensor
            )
            self.all_motion_sensors.update(
                {motion_sensor['motion_sensor'] : False}
            )

        MQTT_motion_sensors = self.args.get('MQTT_motion_sensors', {})
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
                constrain_state=lambda x: float(x) > 0,
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
        self.usePersistentStorage = False
        if 'json_path' in self.args:
            self.JSON_PATH = self.args['json_path']
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
            light = MQTTLights(self,
                lights = l['lights'],
                light_modes = l.get('light_modes', []),
                automations = l.get('automations', None),
                motionlight = l.get('motionlights', None),
                lux_turn_on = l.get('lux_turn_on', None),
                lux_turn_off = l.get('lux_turn_off', None),
                lux_constraint = l.get('lux_constraint', None),
                room_lux_turn_on = l.get('room_lux_turn_on', None),
                room_lux_turn_off = l.get('room_lux_turn_off', None),
                room_lux_constraint = l.get('room_lux_constraint', None),
                conditions = l.get('conditions', {'True'}),
                json_path = self.JSON_PATH,
                usePersistentStorage = self.usePersistentStorage,
                MQTT_namespace = MQTT_namespace,
                HASS_namespace = HASS_namespace
            )
            self.roomlight.append(light)

            # Configuration of HASS Lights
        lights = self.args.get('Lights', [])
        for l in lights:
            light = Light(self,
                lights = l['lights'],
                light_modes = l.get('light_modes', []),
                automations = l.get('automations', None),
                motionlight = l.get('motionlights', None),
                lux_turn_on = l.get('lux_turn_on', None),
                lux_turn_off = l.get('lux_turn_off', None),
                lux_constraint = l.get('lux_constraint', None),
                room_lux_turn_on = l.get('room_lux_turn_on', None),
                room_lux_turn_off = l.get('room_lux_turn_off', None),
                room_lux_constraint = l.get('room_lux_constraint', None),
                conditions = l.get('conditions', {'True'}),
                json_path = self.JSON_PATH,
                usePersistentStorage = self.usePersistentStorage,
                HASS_namespace = HASS_namespace
            )
            self.roomlight.append(light)

            # Configuration of HASS Toggle Lights
        toggle = self.args.get('ToggleLights', [])
        for l in toggle:
            light = Toggle(self,
                lights = l['lights'],
                light_modes = l.get('light_modes', []),
                automations = l.get('automations', None),
                motionlight = l.get('motionlights', None),
                lux_turn_on = l.get('lux_turn_on', None),
                lux_turn_off = l.get('lux_turn_off', None),
                lux_constraint = l.get('lux_constraint', None),
                room_lux_turn_on = l.get('room_lux_turn_on', None),
                room_lux_turn_off = l.get('room_lux_turn_off', None),
                room_lux_constraint = l.get('room_lux_constraint', None),
                conditions = l.get('conditions', {'True'}),
                toggle = l.get('toggle',3),
                num_dim_steps = l.get('num_dim_steps',3),
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

            # Listen sensors for when to update lights based on 'conditions'
        self.listen_sensors = self.args.get('listen_sensors', [])
        for sensor in self.listen_sensors:
            self.listen_state(self.state_changed, sensor,
                namespace = HASS_namespace
            )

            # Media players for setting mediaplayer mode
        for mediaplayer in self.mediaplayers:
            self.listen_state(self.media_on, mediaplayer['mediaplayer'],
                new = 'on',
                old = 'off',
                namespace = HASS_namespace,
                mode = mediaplayer['mode']
            )
            self.listen_state(self.media_off, mediaplayer['mediaplayer'],
                new = 'off',
                old = 'on',
                duration = 33,
                namespace = HASS_namespace,
                mode = mediaplayer['mode']
            )

            # Sets light to mediaplayer if on
        if (
            self.LIGHT_MODE == 'normal'
            or self.LIGHT_MODE == 'night'
        ):
            for mediaplayer in self.mediaplayers:
                if self.get_state(mediaplayer['mediaplayer']) == 'on':
                    for light in self.roomlight:
                        light.setLightMode(lightmode = mediaplayer['mode'])
                    continue

        """ End initial setup for Room
        """


    def mode_event(self, event_name, data, kwargs):
        """ New mode events. Updates lights if conditions are met
        """
        if self.exclude_from_custom:
            if (
                data['mode'] == 'custom'
                or data['mode'] == 'wash'
            ):
                return

        if (
            data['mode'] in self.all_modes
            or data['mode'] == 'morning'
        ):
            self.LIGHT_MODE = data['mode']
            if data['mode'] == 'morning':
                if not 'morning' in self.all_modes:
                    self.LIGHT_MODE = 'normal'

                # Persistent storage
            if self.usePersistentStorage:
                with open(self.JSON_PATH, 'r') as json_read:
                    lightwand_data = json.load(json_read)
                lightwand_data.update(
                    { "mode" : self.LIGHT_MODE}
                )
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)

            if self.check_mediaplayers_off():
                string:str = self.LIGHT_MODE
                if (
                    string[:5] != 'night'
                    and self.LIGHT_MODE != 'off'
                ):
                    """ Checks if motion and motion timer has ended to set new lightmode.
                        If mode is 'night*' or 'off' it will set via normal setLigthMode directly
                        to set night and off light settings regardless off motion.
                        Else it will set new lightmode via setMotion if motion is active
                    """
                    if self.handle != None:
                        if self.timer_running(self.handle):
                            for light in self.roomlight:
                                light.setMotion(lightmode = self.LIGHT_MODE)
                            return
                    for sens in self.all_motion_sensors:
                        if self.all_motion_sensors[sens]:
                            for light in self.roomlight:
                                light.setMotion(lightmode = self.LIGHT_MODE)
                            return

                for light in self.roomlight:
                    light.setLightMode(lightmode = self.LIGHT_MODE)
   

        # Motion and presence
    def motion_state(self, entity, attribute, old, new, kwargs):
        sensor = kwargs['motion_sensor']

        if new == 'on':
            self.all_motion_sensors.update(
                {sensor['motion_sensor'] : True}
            )
            self.newMotion(sensor = sensor)
        elif new == 'off':
            self.all_motion_sensors.update(
                {sensor['motion_sensor'] : False}
            )
            self.oldMotion(sensor = sensor)


    def MQTT_motion_event(self, event_name, data, kwargs):
        motion_data = json.loads(data['payload'])
        sensor = kwargs['motion_sensor']

        """ Test your MQTT settings. Uncomment line below to get logging when motion detected """
        #self.log(f"Motion detected: {sensor} Motion Data: {motion_data}") # FOR TESTING ONLY

        if 'occupancy' in motion_data:
            if motion_data['occupancy']:
                self.all_motion_sensors.update(
                    {sensor['motion_sensor'] : True}
                )
                self.newMotion(sensor = sensor)
            else:
                self.all_motion_sensors.update(
                    {sensor['motion_sensor'] : False}
                )
                self.oldMotion(sensor = sensor)
        elif 'value' in motion_data:
            if motion_data['value'] == 8:
                self.all_motion_sensors.update(
                    {sensor['motion_sensor'] : True}
                )
                self.newMotion(sensor = sensor)
            elif motion_data['value'] == 0:
                self.all_motion_sensors.update(
                    {sensor['motion_sensor'] : False}
                )
                self.oldMotion(sensor = sensor)


    def newMotion(self, sensor):
        """ Motion detected. Checks constraints given in motion and setMotion
        """
        if 'motion_constraints' in sensor:
            condition_statement = eval(sensor['motion_constraints'])
            if not condition_statement:
                return

        if self.check_mediaplayers_off():
            for light in self.roomlight:
                light.setMotion(lightmode = self.LIGHT_MODE)

        if self.handle != None:
            if self.timer_running(self.handle):
                try:
                    self.cancel_timer(self.handle)
                except Exception as e:
                    self.log(f"Was not able to stop timer for {sensor['motion_sensor']}: {e}", level = 'DEBUG')
                self.handle = None


    def oldMotion(self, sensor):
        """ Motion no longer detected in sensor. Checks other sensors in room and starts countdown to turn off light
        """
        for sens in self.all_motion_sensors:
            if self.all_motion_sensors[sens]:
                return

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


    def presence_change(self, entity, attribute, old, new, kwargs):
        tracker = kwargs['tracker']

        if new == 'home':
            if 'tracker_constraints' in tracker:
                condition_statement = eval(tracker['tracker_constraints'])
                if not condition_statement:
                    if self.LIGHT_MODE == 'away':
                        self.LIGHT_MODE = 'normal'
                        if self.check_mediaplayers_off():
                            for light in self.roomlight:
                                light.setLightMode(lightmode = self.LIGHT_MODE)
                    return

            if self.handle != None:
                if self.timer_running(self.handle):
                    try:
                        self.cancel_timer(self.handle)
                    except Exception as e:
                        self.log(f"Was not able to stop timer for {tracker['tracker']}: {e}", level = 'DEBUG')
                    finally:
                        self.handle = None

            if (
                self.LIGHT_MODE == 'normal'
                or self.LIGHT_MODE == 'away'
            ):
                self.LIGHT_MODE = 'normal'
                if (
                    'presence' in self.all_modes
                    and self.check_mediaplayers_off()
                ):
                    for light in self.roomlight:
                        light.setLightMode(lightmode = 'presence')
                    if 'delay' in tracker:
                        self.handle = self.run_in(self.MotionEnd, int(tracker['delay']))
                    else:
                        self.handle = self.run_in(self.MotionEnd, 300)
                    return

        elif old == 'home':
            for tracker in self.presence:
                if self.get_state(tracker['tracker']) == 'home':
                    if self.check_mediaplayers_off():
                        for light in self.roomlight:
                            light.setLightMode(lightmode = self.LIGHT_MODE)
                    return
            self.LIGHT_MODE = 'away'

        for light in self.roomlight:
            light.setLightMode(lightmode = self.LIGHT_MODE)


    def MotionEnd(self, kwargs):
        """ Motion / Presence countdown ended. Turns lights back to current mode
        """
        if self.check_mediaplayers_off():
            for light in self.roomlight:
                light.motion = False
                light.setLightMode(lightmode = self.LIGHT_MODE)


    def state_changed(self, entity, attribute, old, new, kwargs):
        """ Update light settings when state of a HA entity is updated
        """
        for sens in self.all_motion_sensors:
            if self.all_motion_sensors[sens]:
                for light in self.roomlight:
                    light.setMotion(lightmode = self.LIGHT_MODE)
                return

        if self.check_mediaplayers_off():
            for light in self.roomlight:
                light.setLightMode(lightmode = self.LIGHT_MODE)


        # Lux / weather
    def out_lux_state(self, entity, attribute, old, new, kwargs):
        if self.outLux1 != float(new):
            self.outLux1 = float(new)

            self.newOutLux()


    def out_lux_event_MQTT(self, event_name, data, kwargs):
        lux_data = json.loads(data['payload'])
        if 'illuminance_lux' in lux_data:
            if self.outLux1 != float(lux_data['illuminance_lux']):
                self.outLux1 = float(lux_data['illuminance_lux']) # Zigbee sensor
                self.newOutLux()
        elif 'value' in lux_data:
            if self.outLux1 != float(lux_data['value']):
                self.outLux1 = float(lux_data['value']) # Zwave sensor
                self.newOutLux()


    def newOutLux(self):
        if (
            self.datetime(aware=True) - self.lux_last_update2 > datetime.timedelta(minutes = 15)
            or self.outLux1 >= self.outLux2
        ):
            self.OUT_LUX = self.outLux1
        
            for light in self.roomlight:
                light.outLux = self.OUT_LUX
                if light.lux_turn_off:
                    if self.OUT_LUX > light.lux_turn_off:
                        light.setLightMode()

                if light.lux_turn_on:
                    if self.OUT_LUX < light.lux_turn_on:
                        light.setLightMode()

                # Persistent storage
            if self.usePersistentStorage:
                with open(self.JSON_PATH, 'r') as json_read:
                    lightwand_data = json.load(json_read)
                lightwand_data.update(
                    { "out_lux" : self.OUT_LUX}
                )
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)

        self.lux_last_update1 = self.datetime(aware=True)


    def out_lux_state2(self, entity, attribute, old, new, kwargs):
        if self.outLux2 != float(new):
            self.outLux2 = float(new)

            self.newOutLux2()


    def out_lux_event_MQTT2(self, event_name, data, kwargs):
        lux_data = json.loads(data['payload'])
        if 'illuminance_lux' in lux_data:
            if self.outLux2 != float(lux_data['illuminance_lux']):
                self.outLux2 = float(lux_data['illuminance_lux']) # Zigbee sensor
                self.newOutLux2()
        elif 'value' in lux_data:
            if self.outLux2 != float(lux_data['value']):
                self.outLux2 = float(lux_data['value']) # Zwave sensor
                self.newOutLux2()


    def newOutLux2(self):
        if (
            self.datetime(aware=True) - self.lux_last_update1 > datetime.timedelta(minutes = 15)
            or self.outLux2 >= self.outLux1
        ):
            self.OUT_LUX = self.outLux2
        
            for light in self.roomlight:
                light.outLux = self.OUT_LUX
                if light.lux_turn_off:
                    if self.OUT_LUX > light.lux_turn_off:
                        light.setLightMode()

                if light.lux_turn_on:
                    if self.OUT_LUX < light.lux_turn_on:
                        light.setLightMode()

                # Persistent storage
            if self.usePersistentStorage:
                with open(self.JSON_PATH, 'r') as json_read:
                    lightwand_data = json.load(json_read)
                lightwand_data.update(
                    { "out_lux" : self.OUT_LUX}
                )
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)

        self.lux_last_update2 = self.datetime(aware=True)


    def room_lux_state(self, entity, attribute, old, new, kwargs):
        if self.ROOM_LUX != float(new):
            self.ROOM_LUX = float(new)

            self.newRoomLux()


    def room_lux_event_MQTT(self, event_name, data, kwargs):
        lux_data = json.loads(data['payload'])
        if 'illuminance_lux' in lux_data:
            if self.ROOM_LUX != float(lux_data['illuminance_lux']):
                self.ROOM_LUX = float(lux_data['illuminance_lux']) # Zigbee sensor
                self.newRoomLux()
        elif 'value' in lux_data:
            if self.ROOM_LUX != float(lux_data['value']):
                self.ROOM_LUX = float(lux_data['value']) # Zwave sensor
                self.newRoomLux()


    def newRoomLux(self):
        for light in self.roomlight:
            light.roomLux = self.ROOM_LUX
            if light.room_lux_turn_off:
                if self.ROOM_LUX > light.room_lux_turn_off:
                    light.setLightMode()

            if light.room_lux_turn_on:
                if self.ROOM_LUX < light.room_lux_turn_on:
                    light.setLightMode()

            # Persistent storage
        if self.usePersistentStorage:
            with open(self.JSON_PATH, 'r') as json_read:
                lightwand_data = json.load(json_read)
            lightwand_data.update(
                { "room_lux" : self.ROOM_LUX}
            )
            with open(self.JSON_PATH, 'w') as json_write:
                json.dump(lightwand_data, json_write, indent = 4)


    def update_rain_amount(self, entity, attribute, old, new, kwargs):
        try:
            if self.RAIN != float(new):
                self.RAIN = float(new)
        except Exception as e:
            self.log(f"Rain amount unavailable. Exception: {e}", level = 'DEBUG')
            self.RAIN = 0.0
        for light in self.roomlight:
            light.rain_amount = self.RAIN


        # Media Player / sensors
    def media_on(self, entity, attribute, old, new, kwargs):
        if self.LIGHT_MODE == 'morning':
            self.LIGHT_MODE = 'normal'
        self.check_mediaplayers_off()


    def media_off(self, entity, attribute, old, new, kwargs):
        if self.check_mediaplayers_off():
            for sens in self.all_motion_sensors:
                if self.all_motion_sensors[sens]:
                    self.newMotion(sensor = sens)
                    return
            for light in self.roomlight:
                light.setLightMode(lightmode = self.LIGHT_MODE)


    def check_mediaplayers_off(self):
        """ Returns true if media player sensors is off
            or self.LIGHT_DATA != 'normal'/'night'
        """
        if self.LIGHT_MODE == 'normal' or self.LIGHT_MODE == 'night':
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
        lux_turn_on,
        lux_turn_off,
        lux_constraint,
        room_lux_turn_on,
        room_lux_turn_off,
        room_lux_constraint,
        conditions,
        json_path,
        usePersistentStorage,
        HASS_namespace
    ):

        self.ADapi = api

        self.lights = lights
        self.light_modes = light_modes
        self.automations = automations
        self.motionlight = motionlight
        self.lux_turn_on = lux_turn_on
        self.lux_turn_off = lux_turn_off
        self.lux_constraint = lux_constraint
        self.room_lux_turn_on = room_lux_turn_on
        self.room_lux_turn_off = room_lux_turn_off
        self.room_lux_constraint = room_lux_constraint
        self.conditions = conditions
        self.JSON_PATH = json_path
        self.usePersistentStorage = usePersistentStorage

        self.outLux:float = 0.0
        self.roomLux:float = 0.0
        self.rain_amount:float = 0.0
        self.lightmode = 'normal'
        self.times_to_adjust_light:list = []
        self.dimHandler = None
        self.motion = False
        self.isON = None
        self.manualHandler = None
        self.brightness:int = 0
        self.current_light_data = {}

        string:str = self.lights[0]
        if string[:6] == 'light.':
            self.ADapi.listen_state(self.BrightnessUpdated, self.lights[0],
                attribute = 'brightness',
                namespace = HASS_namespace
            )
            try:
                self.brightness = int(self.ADapi.get_state(self.lights[0], attribute = 'brightness'))
            except TypeError:
                self.brightness = 0
                string:str = self.lights[0]
            self.isON = self.ADapi.get_state(self.lights[0]) == 'on' 
        if string[:7] == 'switch.':
            self.isON = self.ADapi.get_state(self.lights[0]) == 'on' 


        if self.automations:
            """ Set up automations with times defined and check data
            """
            test_time = self.ADapi.parse_time('00:00:00')
            if test_time != self.ADapi.parse_time(self.automations[0]['time']):
                self.automations.insert(0,
                    {'time': '00:00:00', 'state': 'turn_off'}
                )

            automationsToDelete = []
            timeToAdd: timedelta = datetime.timedelta(minutes = 0)
            for num, automation in enumerate(self.automations):
                    # Checks if multiple times is configured for one entry and finds time to add to following entries
                if 'orLater' in automation:
                    if self.ADapi.parse_time(automation['time']) < self.ADapi.parse_time(automation['orLater']):
                        orLaterDate = self.ADapi.parse_datetime(automation['orLater'])
                        timeDate = self.ADapi.parse_datetime(automation['time'])
                        timeToAdd = orLaterDate -timeDate
                        if timeToAdd < datetime.timedelta(minutes = 0):
                            timeToAdd += datetime.timedelta(days = 1)
                        automation['time'] = automation['orLater']

                elif timeToAdd > datetime.timedelta(minutes = 0):
                    if 'fixed' in automation:
                        timeToAdd = datetime.timedelta(minutes = 0)
                    newtime = self.ADapi.parse_datetime(automation['time']) + timeToAdd
                    automation['time'] = str(newtime.time())

                    # Deletes automations that are earlier than previous time. Useful when both time with sunset and fixed time is given in automations
                if test_time <= self.ADapi.parse_time(automation['time']):
                    test_time = self.ADapi.parse_time(automation['time'])
                elif test_time > self.ADapi.parse_time(automation['time']):
                    if not 'fixed' in automation:
                        """ Check if your times are acting as planned. Uncomment line below to get logging when motion detected """
                        #self.ADapi.log(f"Deletes automation: {self.automations[num]}")
                        automationsToDelete.append(num)

            for num in reversed(automationsToDelete):
                del self.automations[num]

            for automation in self.automations:
                if not 'state' in automation:
                    automation.update(
                        {'state': 'none'}
                    )
                elif (
                    'adjust' in automation['state']
                    and not self.manualHandler
                ):
                    string:str = self.lights[0]
                    if (
                        string[:6] == 'light.'
                        or string[:7] == 'switch.'
                    ):
                        self.manualHandler = self.ADapi.listen_state(self.update_isOn_lights, self.lights[0],
                            namespace = HASS_namespace
                        )
                
                if not automation['time'] in self.times_to_adjust_light:
                    # Adjust lights with new light_data on given time
                    self.times_to_adjust_light.append(automation['time'])


        if self.motionlight:
            """ Set up motion automations with times defined and check data
            """
            if type(self.motionlight) == list:
                test_time = self.ADapi.parse_time('00:00:00')
                if test_time != self.ADapi.parse_time(self.motionlight[0]['time']):
                    self.motionlight.insert(0,
                        {'time': '00:00:00', 'state': 'turn_off'}
                    )

                automationsToDelete = []
                timeToAdd: timedelta = datetime.timedelta(minutes = 0)
                for num, automation in enumerate(self.motionlight):
                        # Checks if multiple times is configured and parse all times 
                    if 'orLater' in automation:
                        if self.ADapi.parse_time(automation['time']) < self.ADapi.parse_time(automation['orLater']):
                            orLaterDate = self.ADapi.parse_datetime(automation['orLater'])
                            timeDate = self.ADapi.parse_datetime(automation['time'])
                            timeToAdd = orLaterDate -timeDate
                            if timeToAdd < datetime.timedelta(minutes = 0):
                                timeToAdd += datetime.timedelta(days = 1)
                            automation['time'] = automation['orLater']

                    elif timeToAdd > datetime.timedelta(minutes = 0):
                        if 'fixed' in automation:
                            timeToAdd = datetime.timedelta(minutes = 0)
                        newtime = self.ADapi.parse_datetime(automation['time']) + timeToAdd
                        automation['time'] = str(newtime.time())

                        # Deletes automations that are earlier than previous time. Useful when both time with sunset and fixed time is given in automations
                    if test_time <= self.ADapi.parse_time(automation['time']):
                        test_time = self.ADapi.parse_time(automation['time'])
                    elif test_time > self.ADapi.parse_time(automation['time']):
                        if not 'fixed' in automation:
                            """ Check if your times are acting as planned. Uncomment line below to get logging when motion detected """
                            #self.ADapi.log(f"Deletes automation: {self.automations[num]}")
                            automationsToDelete.append(num)
                for num in reversed(automationsToDelete):
                    del self.motionlight[num]

                for automation in self.motionlight:
                    if not 'state' in automation:
                        automation.update(
                            {'state': 'none'}
                        )
                    if not automation['time'] in self.times_to_adjust_light:
                        # Adjust lights with new light_data on given time
                        self.times_to_adjust_light.append(automation['time'])

        for mode in self.light_modes:
            """ Set up mode automations with times defined and check data
            """
            if 'automations' in mode:
                test_time = self.ADapi.parse_time('00:00:00')
                if test_time != self.ADapi.parse_time(mode['automations'][0]['time']):
                    mode['automations'].insert(0,
                        {'time': '00:00:00', 'state': 'turn_off'}
                    )

                automationsToDelete = []
                timeToAdd: timedelta = datetime.timedelta(minutes = 0)
                for num, automation in enumerate(mode['automations']):
                        # Checks if multiple times is configured and parse all times 
                    if 'orLater' in automation:
                        if self.ADapi.parse_time(automation['time']) < self.ADapi.parse_time(automation['orLater']):
                            orLaterDate = self.ADapi.parse_datetime(automation['orLater'])
                            timeDate = self.ADapi.parse_datetime(automation['time'])
                            timeToAdd = orLaterDate -timeDate
                            if timeToAdd < datetime.timedelta(minutes = 0):
                                timeToAdd += datetime.timedelta(days = 1)
                            automation['time'] = automation['orLater']

                    elif timeToAdd > datetime.timedelta(minutes = 0):
                        if 'fixed' in automation:
                            timeToAdd = datetime.timedelta(minutes = 0)
                        newtime = self.ADapi.parse_datetime(automation['time']) + timeToAdd
                        automation['time'] = str(newtime.time())

                        # Deletes automations that are earlier than previous time. Useful when both time with sunset and fixed time is given in automations
                    if test_time <= self.ADapi.parse_time(automation['time']):
                        test_time = self.ADapi.parse_time(automation['time'])
                    elif test_time > self.ADapi.parse_time(automation['time']):
                        if not 'fixed' in automation:
                            """ Check if your times are acting as planned. Uncomment line below to get logging when motion detected """
                            #self.ADapi.log(f"Deletes mode automation: {self.automations[num]}")
                            automationsToDelete.append(num)
                for num in reversed(automationsToDelete):
                    del mode['automations'][num]

                for automation in mode['automations']:
                    if not 'state' in automation:
                        automation.update(
                            {'state': 'none'}
                        )
                    if (
                        'adjust' in automation['state']
                        and not self.manualHandler
                    ):
                        string:str = self.lights[0]
                        if (
                            string[:6] == 'light.'
                            or string[:7] == 'switch.'
                        ):
                            self.manualHandler = self.ADapi.listen_state(self.update_isOn_lights, self.lights[0],
                                namespace = HASS_namespace
                            )
                    if not automation['time'] in self.times_to_adjust_light:
                        # Adjust lights with new light_data on given time
                        self.times_to_adjust_light.append(automation['time'])
            elif (
                'state' in mode
                and not self.manualHandler
            ):
                if 'manual' in mode['state']:
                    string:str = self.lights[0]
                    if (
                        string[:6] == 'light.'
                        or string[:7] == 'switch.'
                    ):
                        self.manualHandler = self.ADapi.listen_state(self.update_isOn_lights, self.lights[0],
                            namespace = HASS_namespace
                        )


        if self.motionlight and not self.automations:
            # Sets a valid state turn off in automation when motionlight turns on light for when motion ends
            self.automations = [{'time': '00:00:00', 'state': 'turn_off'}]

        for time in self.times_to_adjust_light:
            self.ADapi.run_daily(self.run_daily_lights, time)


            # Persistent storage
        if self.usePersistentStorage and self.manualHandler:
            with open(self.JSON_PATH, 'r') as json_read:
                lightwand_data = json.load(json_read)

            if not self.lights[0] in lightwand_data:
                lightwand_data.update(
                    { self.lights[0] : {"isON" : self.isLightOn()}}
                )
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)
            self.isON = lightwand_data[self.lights[0]]['isON'] == 'on'


        """ End initial setup for lights
        """


    def run_daily_lights(self, kwargs):
        """ Updates light with new data based on times given in configuration
        """
        if not self.motion:
            self.setLightMode()
        elif type(self.motionlight) == list:
            target_num = self.find_time(automation = self.motionlight)
            if self.motionlight[target_num]['state'] == 'turn_off':
                if self.isON:
                    self.turn_off_lights()


    def find_time(self, automation):
        """ Helper to find correct list item with light data based on time
        """
        prev_time = '00:00:00'
        target_num = 0
        for target_num, automations in enumerate(automation):
            if self.ADapi.now_is_between(prev_time, automations['time']):
                testtid = self.ADapi.parse_time(automations['time'])
                if (
                    datetime.datetime.today().hour == testtid.hour
                    and datetime.datetime.today().minute == testtid.minute
                ):
                    pass
                elif target_num != 0:
                    target_num -= 1
                return target_num
        return target_num


        # Check conditions and constraints
    def checkOnConditions(self):
        for conditions in self.conditions:
            if not eval(conditions):
                return False
        return True


    def checkLuxConstraints(self):
        if self.lux_constraint:
            if self.rain_amount > 1:
                if self.outLux >= self.lux_constraint * 1.5:
                    return False
            elif self.outLux >= self.lux_constraint:
                return False
        if self.room_lux_constraint:
            if self.roomLux >= self.room_lux_constraint:
                return False
        return True


    def setLightMode(self, lightmode = 'None'):
        """ The main function/logic to handle turning on / off lights based on mode selected.
        """
        if lightmode != self.lightmode:
            if self.dimHandler:
                if self.ADapi.timer_running(self.dimHandler):
                    try:
                        self.ADapi.cancel_timer(self.dimHandler)
                    except Exception:
                        self.ADapi.log(f"Could not stop dim timer for {entity}.", level = 'DEBUG')
                self.dimHandler = None

        if lightmode == 'None':
            lightmode = self.lightmode
        
        if lightmode == 'morning':
            # Only do morning mode if Lux and conditions are valid
            if (
                not self.checkOnConditions()
                or not self.checkLuxConstraints()
            ):
                lightmode = 'normal'
                return

        if lightmode == 'custom':
            # Custom mode will break any automation and keep light as is
            self.lightmode = lightmode
            return

        for mode in self.light_modes:
            """ Finds out if new lightmode is configured for light and executes
            """
            if lightmode == mode['mode']:
                self.lightmode = lightmode
                if 'automations' in mode:
                    # Automation sets light according to time of day with Lux and Conditions constraints
                    if (
                        self.checkLuxConstraints()
                        and self.checkOnConditions()
                    ):
                        self.setLightAutomation(automations = mode['automations'])
                    elif self.isON:
                        self.turn_off_lights()
                    return

                elif 'light_data' in mode:
                    # Turns on light with given data. Lux constrained but Conditions do not need to be met
                    if self.checkLuxConstraints():
                        self.turn_on_lights(light_data = mode['light_data'])
                    elif self.isON:
                        self.turn_off_lights()
                    return

                elif 'state' in mode:
                    # Turns on light regardless of Lux and Conditions. Offset can be provided to increase or decrease lighting in mode
                    if (
                        'turn_on' in mode['state']
                        or 'lux_controlled' in mode['state']
                    ):
                        if 'lux_controlled' in mode['state']:
                            if not self.checkLuxConstraints():
                                if self.isON:
                                    self.turn_off_lights()
                                return

                        if 'offset' in mode and self.automations:
                            """ Sets light with offset from brightness defined in automations
                            """
                            self.setLightAutomation(automations = mode, offset = mode['offset'])

                        elif self.automations:
                            """ Sets light with brightness defined in automations
                            """
                            self.setLightAutomation(automations = mode)

                        elif not self.isON:
                            self.turn_on_lights()
                        return
                        
                    elif 'turn_off' in mode['state']:
                        # Turns off light
                        if self.isON:
                            self.turn_off_lights()
                        return
                        
                    elif 'manual' in mode['state']:
                        # Manual on/off. Keeps light as is or turn on/off with other methods
                        return
                
            # Default turn off if away/off/night is not defined as a mode in light
        if (
            lightmode == 'away'
            or lightmode == 'off'
            or lightmode == 'night'
        ):
            self.lightmode = lightmode
            if self.isON:
                self.turn_off_lights()
            return

            # Default turn on maximum light if not fire/wash is defined as a mode in light
        elif (
            lightmode == 'fire'
            or lightmode == 'wash'
        ):
            self.lightmode = lightmode
            self.turn_on_lights_at_max()
            return

            # Mode is normal or not valid for light. Checks Lux and Conditions constraints and does defined automations for light
        self.lightmode = 'normal'
        if (
            self.checkOnConditions()
            and self.checkLuxConstraints()
        ):
            if self.automations:
                self.setLightAutomation(automations = self.automations)
            elif not self.isON:
                self.turn_on_lights()
        elif self.isON:
            self.turn_off_lights()


    def setMotion(self, lightmode = 'None'):
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
            if type(self.motionlight) == list:
                self.setLightAutomation(automations = self.motionlight)

            elif 'light_data' in self.motionlight:
                if 'brightness' in self.motionlight['light_data']:
                    if self.brightness < self.motionlight['light_data']['brightness']:
                        self.turn_on_lights(light_data = self.motionlight['light_data'])

                elif 'value' in self.motionlight['light_data']:
                    if self.brightness < self.motionlight['light_data']['value']:
                        self.turn_on_lights(light_data = self.motionlight['light_data'])

                # Defines more simple on/off with possibility to have offset off normal automation
            elif 'state' in self.motionlight:
                if 'turn_on' in self.motionlight['state']:
                    if (
                        'offset' in self.motionlight
                        and self.automations
                    ):
                        """ Sets light with offset from brightness defined in automations
                        """
                        self.setLightAutomation(automations = self.motionlight, offset = self.motionlight['offset'])

                    elif self.automations:
                        """ Sets light with brightness defined in automations
                        """
                        self.setLightAutomation(automations = self.motionlight)

                    elif not self.isON:
                        self.turn_on_lights()


    def setLightAutomation(self, automations, offset = 0 ):
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
            """ Only 'adjust' lights if already on, or if not turn off.
            """
            if (
                not 'light_data' in automations[target_num]
                and 'light_data' in self.automations[target_num2]
            ):
                """ If provided automation is configured without light_data it will fetch light_data from main automations
                """
                target_num = target_num2
                target_light = self.automations.copy()

            else:
                target_light = automations.copy()

            if 'light_data' in target_light[target_num]:
                target_light_data = target_light[target_num]['light_data'].copy()

                # Brightness 0-255 for HA and Zigbee2mqtt control
                if 'brightness' in target_light[target_num]['light_data']:

                    if 'dimrate' in target_light[target_num]:
                        newbrightness = self.findBrightnessWhenDimRate(automation = target_light) + offset
                        target_light_data.update(
                            {'brightness' : newbrightness}
                        )

                    elif offset != 0:
                        brightness_offset = math.ceil(int(target_light[target_num]['light_data']['brightness']) + offset)
                        if brightness_offset > 0:
                            if brightness_offset < 255:
                                target_light_data.update(
                                    {'brightness' : brightness_offset}
                                )
                            else:
                                target_light_data.update(
                                    {'brightness' : 254}
                                )
                        else:
                            target_light_data.update(
                                {'brightness' : 1}
                            )

                    elif (
                        self.motion
                        and self.brightness > target_light_data['brightness']
                    ):
                        return
                    
                    self.turn_on_lights(light_data = target_light_data)

                # Value in percent for Zwave JS over MQTT
                elif 'value' in target_light[target_num]['light_data']:
                    
                    if 'dimrate' in target_light[target_num]:
                        newbrightness = self.findBrightnessWhenDimRate(automation = target_light) + offset
                        target_light_data.update(
                            {'value' : newbrightness}
                        )
                    elif offset != 0:
                        brightness_offset = math.ceil(int(target_light[target_num]['light_data']['value']) + offset)
                        if brightness_offset > 0:
                            if brightness_offset <= 99:
                                target_light_data.update(
                                    {'value' : brightness_offset}
                                )
                            else:
                                target_light_data.update(
                                    {'value' : 99}
                                )
                        else:
                            target_light_data.update(
                                {'value' : 1}
                            )

                    if (
                        self.motion
                        and self.brightness > target_light_data['value']
                    ):
                        return

                    self.turn_on_lights(light_data =  target_light_data)

            elif not self.isON:
                self.turn_on_lights()

        elif (
            automations[target_num]['state'] != 'adjust'
            and self.isON
        ):
            self.turn_off_lights()


    def findBrightnessWhenDimRate(self, automation):
        """ Dim by one dimming to have the light dim down by one brightness every given minute.
        """
        target_num = self.find_time(automation = automation)
        if 'brightness' in automation[target_num -1]['light_data']:
            try: 
                originalBrightness:int = automation[target_num -1]['light_data']['brightness']
            except (ValueError, TypeError):
                originalBrightness:int = 0
                self.ADapi.log(
                    f"{self.lights[0]} Could not find previous brightness in {automation[target_num -1]['light_data']}",
                    level = 'INFO'
                )

        elif 'value' in automation[target_num -1]['light_data']:
            try: 
                originalBrightness:int = automation[target_num -1]['light_data']['value']
            except (ValueError, TypeError):
                originalBrightness:int = 0
                self.ADapi.log(
                    f"{self.lights[0]} Could not find previous value in {automation[target_num -1]['light_data']}",
                    level = 'INFO'
                )
        else:
            originalBrightness:int = 0

        timeDate = self.ADapi.parse_datetime(automation[target_num]['time'])
        timedifference = math.floor(((datetime.datetime.now() - timeDate).total_seconds())/60)
        newbrightness:int = math.ceil(originalBrightness - (timedifference * automation[target_num]['dimrate']))

        if 'brightness' in automation[target_num]['light_data']:
            if (
                newbrightness < automation[target_num]['light_data']['brightness']
                or newbrightness > automation[target_num-1]['light_data']['brightness']
            ):
                return automation[target_num]['light_data']['brightness']

            if not self.dimHandler:
                runtime = datetime.datetime.now() + datetime.timedelta(minutes = 1)
                self.dimHandler = self.ADapi.run_every(self.dimBrightnessByOne, runtime, automation[target_num]['dimrate'] *60)
                stopDimIn = math.ceil((newbrightness - automation[target_num]['light_data']['brightness']) * automation[target_num]['dimrate'])
                self.ADapi.run_in(self.StopDimByOne, stopDimIn * 60)

        elif 'value' in automation[target_num]['light_data']:
            if (
                newbrightness < automation[target_num]['light_data']['value']
                or newbrightness > automation[target_num-1]['light_data']['value']
            ):
                return automation[target_num]['light_data']['value']

            if not self.dimHandler:
                runtime = datetime.datetime.now() + datetime.timedelta(minutes = 1)
                self.dimHandler = self.ADapi.run_every(self.dimValueByOne, runtime, automation[target_num]['dimrate'] *60)
                stopDimIn = math.ceil((newbrightness - automation[target_num]['light_data']['value']) * automation[target_num]['dimrate'])
                self.ADapi.run_in(self.StopDimByOne, stopDimIn * 60)

        return newbrightness


    def dimBrightnessByOne(self, kwargs):
        if self.brightness > 2:
            ld = {'brightness': self.brightness-1}
            self.turn_on_lights(light_data = ld)
        else:
            self.ADapi.run_in(self.StopDimByOne, 1)


    def dimValueByOne(self, kwargs):
        if self.brightness > 2:
            ld = {'value': self.brightness-1}
            self.turn_on_lights(light_data = ld)
        else:
            self.ADapi.run_in(self.StopDimByOne, 1)


    def StopDimByOne(self, kwargs):
        if self.dimHandler:
            if self.ADapi.timer_running(self.dimHandler):
                try:
                    self.ADapi.cancel_timer(self.dimHandler)
                except Exception:
                    self.ADapi.log(f"Could not stop dim timer for {entity}.", level = 'DEBUG')
            self.dimHandler = None
            
    
        # Updates brightness in light to check when motion if motionlight is brighter/dimmer than light is now.
    def BrightnessUpdated(self, entity, attribute, old, new, kwargs):
        try:
            self.brightness = int(new)
        except TypeError:
            self.brightness = 0


        #Updates persistent storage for lights with adjust/manual modes
    def update_isOn_lights(self, entity, attribute, old, new, kwargs):
        if new == 'on':
            self.isON = True
                # Persistent on/off
            if (
                self.usePersistentStorage
                and self.manualHandler
            ):
                with open(self.JSON_PATH, 'r') as json_read:
                    lightwand_data = json.load(json_read)

                lightwand_data.update(
                    { self.lights[0] : {"isON" : self.isON}}
                )
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)

        elif new == 'off':
            self.isON = False

                # Persistent on/off
            if (
                self.usePersistentStorage
                and self.manualHandler
            ):
                with open(self.JSON_PATH, 'r') as json_read:
                    lightwand_data = json.load(json_read)

                lightwand_data.update(
                    { self.lights[0] : {"isON" : self.isON}}
                )
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)


    def toggle_light(self, kwargs):
        for light in self.lights:
            self.ADapi.toggle(light)


    def turn_on_lights(self, light_data = {}):
        if (
            self.current_light_data != light_data
            or not self.isON
        ):
            self.isON = True
            self.current_light_data = light_data

            for light in self.lights:
                self.ADapi.turn_on(light, **light_data)


    def turn_on_lights_at_max(self):
        self.isON = True
        for light in self.lights:
            string:str = self.lights[0]
            if string[:6] == 'light.':
                self.ADapi.turn_on(light, brightness = 254)
            if string[:7] == 'switch.':
                self.ADapi.turn_on(light)


    def turn_off_lights(self):
        self.current_light_data = {}
        self.isON = False
        for light in self.lights:
            self.ADapi.turn_off(light)


    def isLightOn(self):
        return self.ADapi.get_state(self.lights[0]) == 'on' 


class MQTTLights(Light):
    """ Child class for lights to control lights directly over MQTT
    """

    def __init__(self, api,
        lights,
        light_modes,
        automations,
        motionlight,
        lux_turn_on,
        lux_turn_off,
        lux_constraint,
        room_lux_turn_on,
        room_lux_turn_off,
        room_lux_constraint,
        conditions,
        json_path,
        usePersistentStorage,
        MQTT_namespace,
        HASS_namespace
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
            lux_turn_on = lux_turn_on,
            lux_turn_off = lux_turn_off,
            lux_constraint = lux_constraint,
            room_lux_turn_on = room_lux_turn_on,
            room_lux_turn_off = room_lux_turn_off,
            room_lux_constraint = room_lux_constraint,
            conditions = conditions,
            json_path = json_path,
            usePersistentStorage = usePersistentStorage,
            HASS_namespace = HASS_namespace
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


    def light_event_MQTT(self, event_name, data, kwargs):
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
            try:
                self.brightness = int(lux_data['brightness'])
            except (ValueError, TypeError):
                self.brightness = 0

            self.isON = self.brightness != 0
            if 'brightness' in self.current_light_data:
                if self.current_light_data['brightness'] != self.brightness:
                    self.current_light_data = {}

        elif 'value' in lux_data:
            if type(lux_data['value']) == bool:
                self.isON = lux_data['value']

            elif type(lux_data['value']) == int:
                if (
                    lux_data['value'] > 0
                    and lux_data['value'] <= 255
                ):
                    self.brightness = int(lux_data['value'])
                    self.isON = True

                elif lux_data['value'] == 0:
                    self.isON = False
                
                if 'value' in self.current_light_data:
                    if self.current_light_data['value'] != self.brightness:
                        self.current_light_data = {}

        elif 'state' in lux_data:
            self.isON = lux_data['state'] == 'ON'


            # Persistent on/off
        if self.usePersistentStorage:
            with open(self.JSON_PATH, 'r') as json_read:
                lightwand_data = json.load(json_read)

            lightwand_data.update(
                { self.lights[0] : {"isON" : self.isON}}
            )
            with open(self.JSON_PATH, 'w') as json_write:
                json.dump(lightwand_data, json_write, indent = 4)


    def turn_on_lights(self, light_data = {}):

        if (
            self.current_light_data != light_data
            or not self.isON
        ):
            self.current_light_data = light_data

            for light in self.lights:
                if 'zigbee2mqtt' in light:
                    if (
                        not self.isON
                        and not light_data
                    ):
                        light_data.update(
                            {"state" : "ON"}
                        )

                if 'switch_multilevel' in light:
                    if not self.isON:
                        light_data.update(
                            {"ON" : True}
                        )

                elif 'switch_binary' in light:
                    if not self.isON:
                        light_data.update(
                            {"ON" : True}
                        )
                    if (
                        'value' in light_data
                        and self.isON
                    ):
                        continue
                payload = json.dumps(light_data)

                self.mqtt.mqtt_publish(
                    topic = str(light) + "/set",
                    payload = payload,
                    namespace = self.MQTT_namespace
                )
                self.isON = True


    def turn_on_lights_at_max(self):
        light_data:dict = {}

        if not self.isON:
            light_data.update({"ON" : True})

        for light in self.lights:
            if 'zigbee2mqtt' in light:
                light_data.update({"brightness" : 254})
            elif 'switch_multilevel' in light:
                light_data.update({"value" : 99})

            payload = json.dumps(light_data)
            self.mqtt.mqtt_publish(topic = str(light) + "/set", payload = payload, namespace = self.MQTT_namespace)
            self.isON = True


    def turn_off_lights(self):
        self.current_light_data = {}
        if self.isON:
            for light in self.lights:
                self.mqtt.mqtt_publish(topic = str(light) + "/set", payload = "OFF", namespace = self.MQTT_namespace)
            self.isON = False


    def isLightOn(self):
        return self.isON


class Toggle(Light):
    """ Child class for lights to control lights that dim by toggle
    """

    def __init__(self, api,
        lights,
        light_modes,
        automations,
        motionlight,
        lux_turn_on,
        lux_turn_off,
        lux_constraint,
        room_lux_turn_on,
        room_lux_turn_off,
        room_lux_constraint,
        conditions,
        toggle,
        num_dim_steps,
        json_path,
        usePersistentStorage,
        HASS_namespace
    ):

        self.ADapi = api
        self.current_toggle = 0
        self.toggle_lightbulb = toggle * 2 - 1
        self.fullround_toggle = num_dim_steps * 2

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
            lux_turn_on = lux_turn_on,
            lux_turn_off = lux_turn_off,
            lux_constraint = lux_constraint,
            room_lux_turn_on = room_lux_turn_on,
            room_lux_turn_off = room_lux_turn_off,
            room_lux_constraint = room_lux_constraint,
            conditions = conditions,
            json_path = json_path,
            usePersistentStorage = usePersistentStorage,
            HASS_namespace = HASS_namespace
        )


    def setLightMode(self, lightmode = 'None'):
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

                    if self.current_toggle == toggle_bulb:
                        return

                    elif self.current_toggle > toggle_bulb:
                        self.current_toggle -= self.fullround_toggle
                    sec = 1

                    while self.current_toggle < toggle_bulb:
                        self.ADapi.run_in(self.toggle_light, sec)
                        self.current_toggle += 1
                        sec += 1
                    
                elif 'state' in mode:
                    if 'turn_off' in mode['state']:
                        # Turns off light
                        self.turn_off_lights()
                        self.current_toggle = 0

                    # Persistent toggle
                if self.usePersistentStorage:
                    with open(self.JSON_PATH, 'r') as json_read:
                        lightwand_data = json.load(json_read)

                    lightwand_data[self.lights[0]].update(
                        {"toggle" : self.current_toggle}
                    )
                    with open(self.JSON_PATH, 'w') as json_write:
                        json.dump(lightwand_data, json_write, indent = 4)
                return

        if (
            lightmode == 'away'
            or lightmode == 'off'
            or lightmode == 'night'
        ):
            self.lightmode = lightmode
            self.turn_off_lights()
            self.current_toggle = 0
                # Persistent toggle
            if self.usePersistentStorage:
                with open(self.JSON_PATH, 'r') as json_read:
                    lightwand_data = json.load(json_read)

                lightwand_data[self.lights[0]].update(
                    {"toggle" : self.current_toggle}
                )
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)
            return

        elif (
            lightmode == 'fire'
            or lightmode == 'wash'
        ):
            self.lightmode = lightmode

            if self.current_toggle == 1:
                return

            elif self.current_toggle > self.toggle_lightbulb:
                self.current_toggle -= self.fullround_toggle
            sec = 1

            while self.current_toggle < 1:
                self.ADapi.run_in(self.toggle_light, sec)
                self.current_toggle += 1
                sec += 1

                # Persistent toggle
            if self.usePersistentStorage:
                with open(self.JSON_PATH, 'r') as json_read:
                    lightwand_data = json.load(json_read)

                lightwand_data[self.lights[0]].update(
                    {"toggle" : self.current_toggle}
                )
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)
            return

        self.lightmode = 'normal'
        if (
            self.checkOnConditions()
            and self.checkLuxConstraints()
        ):
            if self.current_toggle == self.toggle_lightbulb:
                return

            elif self.current_toggle > self.toggle_lightbulb:
                self.current_toggle -= self.fullround_toggle
            sec = 1

            while self.current_toggle < self.toggle_lightbulb:
                self.ADapi.run_in(self.toggle_light, sec)
                self.current_toggle += 1
                sec += 1

        else:
            self.turn_off_lights()
            self.current_toggle = 0

            # Persistent toggle
        if self.usePersistentStorage:
            with open(self.JSON_PATH, 'r') as json_read:
                lightwand_data = json.load(json_read)

            lightwand_data[self.lights[0]].update(
                {"toggle" : self.current_toggle}
            )
            with open(self.JSON_PATH, 'w') as json_write:
                json.dump(lightwand_data, json_write, indent = 4)


    def setMotion(self, lightmode = 'None'):
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

            if self.current_toggle == self.toggle_lightbulb:
                return

            elif self.current_toggle > self.toggle_lightbulb:
                self.current_toggle -= self.fullround_toggle
            sec = 1

            while self.current_toggle < self.toggle_lightbulb:
                self.ADapi.run_in(self.toggle_light, sec)
                self.current_toggle += 1
                sec += 1

                # Persistent toggle
            if self.usePersistentStorage:
                with open(self.JSON_PATH, 'r') as json_read:
                    lightwand_data = json.load(json_read)

                lightwand_data[self.lights[0]].update(
                    {"toggle" : self.current_toggle}
                )
                with open(self.JSON_PATH, 'w') as json_write:
                    json.dump(lightwand_data, json_write, indent = 4)
