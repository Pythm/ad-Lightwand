""" Lightwand by Pythm

    FIXME:
    - if 'motion_constraints' becomes true when motion sensor is detecting motion, light will not be updated until motion is redetected

    History:
    v1.0.2
    - Updated with the possibility to dim lights 1 brightness at every x minutes with dimrate.

    @Pythm / https://github.com/Pythm
"""

__version__ = "1.0.1"

import hassapi as hass
import datetime
import json
import csv
import math

class Room(hass.Hass):

    def initialize(self):

        self.roomlight:list = []
        
        self.LIGHT_MODE:str = 'normal'
        self.all_modes:list = ['normal', 'away', 'off', 'night', 'custom', 'fire', 'wash' ]
        self.ROOM_LUX:float = 0.0
        self.OUT_LUX:float = 0.0
        self.RAIN:float = 0.0
        self.JSON_PATH:str = ''

        self.haLightModeText = self.args.get('HALightModeText', None)
        self.exclude_from_custom = self.args.get('exclude_from_custom', False)
        namespace = self.args.get('namespace', 'mqtt')
    
        self.listen_event(self.mode_event, "MODE_CHANGE")

            # Presence detection
        self.presence = self.args.get('presence', {})
        for tracker in self.presence :
            self.listen_state(self.presence_change, tracker['tracker'], tracker = tracker )

        for tracker in self.presence :
            if self.get_state(tracker['tracker']) == 'home' :
                self.LIGHT_MODE = 'normal'
                continue
            else :
                self.LIGHT_MODE = 'away'

            # Motion detection
        self.handle = None
        self.all_motion_sensors:dict = {} # To check if all motion sensors is off before turning off motion lights

        motion_sensors = self.args.get('motion_sensors', {})
        for motion_sensor in motion_sensors :
            self.listen_state(self.motion_state, motion_sensor['motion_sensor'], motion_sensor = motion_sensor )
            self.all_motion_sensors.update({motion_sensor['motion_sensor'] : False})

        zigbee_motion_sensors = self.args.get('zigbee_motion_sensors', {})
        for motion_sensor in zigbee_motion_sensors :
            your_topic:str = "zigbee2mqtt/" + str(motion_sensor['motion_sensor'])
            self.listen_event(self.zigbee_motion_event, "MQTT_MESSAGE", topic = your_topic, namespace=namespace, motion_sensor = motion_sensor )
            self.all_motion_sensors.update({motion_sensor['motion_sensor'] : False})

        zwave_motion_sensors = self.args.get('zwave_motion_sensors', {})
        for motion_sensor in zwave_motion_sensors :
            your_topic:str = "zwave/" + str(motion_sensor['motion_sensor']) + "/notification/endpoint_0/Home_Security/Motion_sensor_status"
            self.listen_event(self.zwave_motion_event, "MQTT_MESSAGE", topic = your_topic, namespace=namespace, motion_sensor = motion_sensor )
            self.all_motion_sensors.update({motion_sensor['motion_sensor'] : False})

            # LUX sensors
        if 'OutLux_sensor' in self.args :
            lux_sensor = self.args['OutLux_sensor']
            self.listen_state(self.out_lux_state, lux_sensor)

        if 'OutLuxZigbee' in self.args :
            out_lux_sensor = self.args['OutLuxZigbee']
            out_lux_topic:str = "zigbee2mqtt/" + str(out_lux_sensor)
            self.listen_event(self.out_lux_event, "MQTT_MESSAGE", topic = out_lux_topic, namespace=namespace)
        if 'OutLuxZwave' in self.args :
            out_lux_sensor = self.args['OutLuxZwave']
            out_lux_topic:str = "zwave/" + str(out_lux_sensor) + "/sensor_multilevel/endpoint_0/Illuminance"
            self.listen_event(self.out_lux_eventZwave, "MQTT_MESSAGE", topic = out_lux_topic, namespace=namespace)

        if 'RoomLux_sensor' in self.args :
            lux_sensor = self.args['RoomLux_sensor']
            self.listen_state(self.room_lux_state, lux_sensor)

        if 'RoomLuxZigbee' in self.args :
            room_lux_sensor_zigbee = self.args['RoomLuxZigbee']
            room_lux_topic:str = "zigbee2mqtt/" + str(room_lux_sensor_zigbee)
            self.listen_event(self.room_lux_event_zigbee, "MQTT_MESSAGE", topic = room_lux_topic, namespace=namespace)

        if 'RoomLuxZwave' in self.args :
            room_lux_sensor_zwave = self.args['RoomLuxZwave']
            room_lux_topic:str = "zwave/" + str(room_lux_sensor_zwave) + "/sensor_multilevel/endpoint_0/Illuminance"
            self.listen_event(self.room_lux_event_zwave, "MQTT_MESSAGE", topic = room_lux_topic, namespace=namespace)

        if 'rain_sensor' in self.args :
            rain_sensor = self.args['rain_sensor']
            self.listen_state(self.update_rain_amount, rain_sensor, constrain_state=lambda x: float(x) > 0 )
            new_rain_amount = self.get_state(rain_sensor)
            try :
                self.RAIN = float(new_rain_amount)
            except Exception as e :
                self.log(f"Rain amount unavailable: {e}", level = 'DEBUG')

        self.usePersistentStorage = False
        if 'json_path' in self.args :
            self.JSON_PATH = self.args['json_path']
            self.JSON_PATH += str(self.name) + '.json'
            self.usePersistentStorage = True

            lightwand_data:dict = {}
            try :
                with open(self.JSON_PATH, 'r') as json_read :
                    lightwand_data = json.load(json_read)
            except FileNotFoundError :
                lightwand_data = {"mode" : "normal",
                                "out_lux" : 0,
                                "room_lux" : 0}
                with open(self.JSON_PATH, 'w') as json_write :
                    json.dump(lightwand_data, json_write, indent = 4)
            self.LIGHT_MODE = lightwand_data['mode']
            self.OUT_LUX = float(lightwand_data['out_lux'])
            self.ROOM_LUX = float(lightwand_data['room_lux'])

            # Lights with configuration
        lights = self.args.get('Lights', [])

        for l in lights :
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
                conditions = l.get('conditions', {'True'}))
            self.roomlight.append(light)

        toggle = self.args.get('ToggleLights', [])
        for l in toggle :
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
                usePersistentStorage = self.usePersistentStorage)
            self.roomlight.append(light)

            # Makes a list of all valid modes for room
        for light in self.roomlight :
            for mode in light.light_modes :
                if not mode['mode'] in self.all_modes :
                    self.all_modes.append(mode['mode'])

            # Media players for light presets
        self.mediaplayers = self.args.get('mediaplayers', {})
        for mediaplayer in self.mediaplayers :
            self.listen_state(self.media_on, mediaplayer['mediaplayer'], new = 'on', old = 'off', mode = mediaplayer['mode'])
            self.listen_state(self.media_off, mediaplayer['mediaplayer'], new = 'off', old = 'on', duration = 33, mode = mediaplayer['mode'])

        for mediaplayer in self.mediaplayers :
            if self.get_state(mediaplayer['mediaplayer']) == 'on' :
                for light in self.roomlight :
                    light.setLightMode(lightmode = mediaplayer['mode'])
                continue


        # Checks new mode events and updates lights if mode is valid for room
    def mode_event(self, event_name, data, kwargs):
        previousMode = self.LIGHT_MODE
            # Update Home Assistant input_text.xx to display current LightMode in Lovelace
        if self.haLightModeText :
            self.set_state(self.haLightModeText, state = data['mode'])

        if self.exclude_from_custom :
            if data['mode'] == 'custom' or data['mode'] == 'wash':
                return

        if data['mode'] in self.all_modes or data['mode'] == 'morning' :
            self.LIGHT_MODE = data['mode']
            if data['mode'] == 'morning' :
                if not 'morning' in self.all_modes :
                    self.LIGHT_MODE = 'normal'

                # Persistent storage
            if self.usePersistentStorage :
                with open(self.JSON_PATH, 'r') as json_read :
                    lightwand_data = json.load(json_read)
                lightwand_data.update({ "mode" : self.LIGHT_MODE})
                with open(self.JSON_PATH, 'w') as json_write :
                    json.dump(lightwand_data, json_write, indent = 4)

            if self.check_mediaplayers_off() :
                string:str = self.LIGHT_MODE
                if string[:5] != 'night' :
                    if self.handle != None :
                        if self.timer_running(self.handle) :
                            for light in self.roomlight :
                                light.setLightMode(lightmode = self.LIGHT_MODE, motion = True)
                            return
                    for sens in self.all_motion_sensors :
                        if self.all_motion_sensors[sens] :
                            for light in self.roomlight :
                                light.setLightMode(lightmode = self.LIGHT_MODE, motion = True)
                            return
                for light in self.roomlight :
                    light.setLightMode(lightmode = self.LIGHT_MODE)
   

        # Motion and presence
    def motion_state(self, entity, attribute, old, new, kwargs):
        sensor = kwargs['motion_sensor']

        if new == 'on' :
            self.all_motion_sensors.update({sensor['motion_sensor'] : True})
            self.newMotion(sensor = sensor)
        elif new == 'off' :
            self.all_motion_sensors.update({sensor['motion_sensor'] : False})
            self.oldMotion(sensor = sensor)

    def zigbee_motion_event(self, event_name, data, kwargs):
        motion_data = json.loads(data['payload'])
        sensor = kwargs['motion_sensor']
        if motion_data['occupancy'] :
            self.all_motion_sensors.update({sensor['motion_sensor'] : True})
            self.newMotion(sensor = sensor)
        else :
            self.all_motion_sensors.update({sensor['motion_sensor'] : False})
            self.oldMotion(sensor = sensor)

    def zwave_motion_event(self, event_name, data, kwargs):
        motion_data = json.loads(data['payload'])
        sensor = kwargs['motion_sensor']

        if motion_data['value'] == 8 :
            self.all_motion_sensors.update({sensor['motion_sensor'] : True})
            self.newMotion(sensor = sensor)
        elif motion_data['value'] == 0 :
            self.all_motion_sensors.update({sensor['motion_sensor'] : False})
            self.oldMotion(sensor = sensor)

    def newMotion(self, sensor):
        if 'motion_constraints' in sensor :
            condition_statement = eval(sensor['motion_constraints'])
            if not condition_statement :
                return

        if self.check_mediaplayers_off() :
            for light in self.roomlight :
                light.setMotion()
        if self.handle != None :
            if self.timer_running(self.handle) :
                try :
                    self.cancel_timer(self.handle)
                except Exception as e :
                    self.log(f"Was not able to stop timer for {sensor['motion_sensor']}: {e}", level = 'DEBUG')
                self.handle = None

    def oldMotion(self, sensor):
        for sens in self.all_motion_sensors :
            if self.all_motion_sensors[sens] :
                return

        if self.handle != None :
            if self.timer_running(self.handle) :
                try :
                    self.cancel_timer(self.handle)
                except Exception as e :
                    self.log(f"Was not able to stop timer for {sensor['motion_sensor']}: {e}", level = 'DEBUG')
        if 'delay' in sensor :
            self.handle = self.run_in(self.MotionEnd, int(sensor['delay']))
        else :
            self.handle = self.run_in(self.MotionEnd, 60)

    def presence_change(self, entity, attribute, old, new, kwargs):
        tracker = kwargs['tracker']

        if new == 'home' :
            if 'tracker_constraints' in tracker :
                condition_statement = eval(tracker['tracker_constraints'])
                if not condition_statement :
                    if self.LIGHT_MODE == 'away' :
                        self.LIGHT_MODE = 'normal'
                        if self.check_mediaplayers_off() :
                            for light in self.roomlight :
                                light.setLightMode(lightmode = self.LIGHT_MODE)
                    return
            if self.handle != None :
                if self.timer_running(self.handle) :
                    try :
                        self.cancel_timer(self.handle)
                    except Exception as e:
                        self.log(f"Was not able to stop timer for {tracker['tracker']}: {e}", level = 'DEBUG')
                    finally :
                        self.handle = None
            if self.LIGHT_MODE == 'normal' or self.LIGHT_MODE == 'away' :
                self.LIGHT_MODE = 'normal'
                if 'presence' in self.all_modes and self.check_mediaplayers_off() :
                    for light in self.roomlight :
                        light.setLightMode(lightmode = 'presence')
                    if 'delay' in tracker :
                        self.handle = self.run_in(self.MotionEnd, int(tracker['delay']))
                    else :
                        self.handle = self.run_in(self.MotionEnd, 300)
        elif old == 'home' :
            for tracker in self.presence :
                if self.get_state(tracker['tracker']) == 'home' :
                    if self.check_mediaplayers_off() :
                        for light in self.roomlight :
                            light.setLightMode(lightmode = self.LIGHT_MODE)
                    return
            self.LIGHT_MODE = 'away'
            for light in self.roomlight :
                light.setLightMode(lightmode = self.LIGHT_MODE)

    def MotionEnd(self, kwargs):
        if self.check_mediaplayers_off() :
            for light in self.roomlight :
                light.setLightMode(lightmode = self.LIGHT_MODE)

        # Lux / weather
    def out_lux_state(self, entity, attribute, old, new, kwargs):
        if self.OUT_LUX != float(new) :
            self.OUT_LUX = float(new)

            self.newOutLux()

    def out_lux_event(self, event_name, data, kwargs):
        lux_data = json.loads(data['payload'])
        if self.OUT_LUX != float(lux_data['illuminance_lux']) :
            self.OUT_LUX = float(lux_data['illuminance_lux']) # Zigbee sensor

            self.newOutLux()

    def out_lux_eventZwave(self, event_name, data, kwargs):
        lux_data = json.loads(data['payload'])
        if self.OUT_LUX != float(lux_data['value']) :
            self.OUT_LUX = float(lux_data['value']) # Zwave sensor

            self.newOutLux()

    def newOutLux(self):
        for light in self.roomlight :
            light.outLux = self.OUT_LUX
            if light.lux_turn_off :
                if self.OUT_LUX > light.lux_turn_off :
                    light.setLightMode()

            if light.lux_turn_on :
                if self.OUT_LUX < light.lux_turn_on :
                    light.setLightMode()

            # Persistent storage
        if self.usePersistentStorage :
            with open(self.JSON_PATH, 'r') as json_read :
                lightwand_data = json.load(json_read)
            lightwand_data.update({ "out_lux" : self.OUT_LUX})
            with open(self.JSON_PATH, 'w') as json_write :
                json.dump(lightwand_data, json_write, indent = 4)

    def room_lux_state(self, entity, attribute, old, new, kwargs):
        if self.ROOM_LUX != float(new) :
            self.ROOM_LUX = float(new)

            self.newRoomLux()

    def room_lux_event_zigbee(self, event_name, data, kwargs):
        lux_data = json.loads(data['payload'])
        if self.ROOM_LUX != float(lux_data['illuminance_lux']) :
            self.ROOM_LUX = float(lux_data['illuminance_lux']) # Zigbee sensor

            self.newRoomLux()

    def room_lux_event_zwave(self, event_name, data, kwargs):
        lux_data = json.loads(data['payload'])
        if self.ROOM_LUX != float(lux_data['value']) :
            self.ROOM_LUX = float(lux_data['value']) # Zwave sensor

            self.newRoomLux()

    def newRoomLux(self) :
        for light in self.roomlight :
            light.roomLux = self.ROOM_LUX
            if light.room_lux_turn_off :
                if self.ROOM_LUX > light.room_lux_turn_off :
                    light.setLightMode()

            if light.room_lux_turn_on :
                if self.ROOM_LUX < light.room_lux_turn_on :
                    light.setLightMode()

            # Persistent storage
        if self.usePersistentStorage :
            with open(self.JSON_PATH, 'r') as json_read :
                lightwand_data = json.load(json_read)
            lightwand_data.update({ "room_lux" : self.ROOM_LUX})
            with open(self.JSON_PATH, 'w') as json_write :
                json.dump(lightwand_data, json_write, indent = 4)

    def update_rain_amount(self, entity, attribute, old, new, kwargs):
        try :
            if self.RAIN != float(new) :
                self.RAIN = float(new)
                for light in self.roomlight :
                    light.rain_amount = self.RAIN
        except Exception as e :
            self.log(f"Rain amount unavailable. Exception : {e}", level = 'DEBUG')
            self.RAIN = 0.0
            for light in self.roomlight :
                light.rain_amount = self.RAIN

        # Media Player / sensors
    def media_on(self, entity, attribute, old, new, kwargs):
        if self.LIGHT_MODE == 'morning' :
            self.LIGHT_MODE = 'normal'
        self.check_mediaplayers_off()

    def media_off(self, entity, attribute, old, new, kwargs):
        if self.check_mediaplayers_off() :
            for sens in self.all_motion_sensors :
                if self.all_motion_sensors[sens] :
                    self.newMotion(sensor = sens)
                    return
            for light in self.roomlight :
                light.setLightMode(lightmode = self.LIGHT_MODE)

    def check_mediaplayers_off(self):
        if self.LIGHT_MODE == 'normal' or self.LIGHT_MODE == 'night' :
            for mediaplayer in self.mediaplayers :
                if self.get_state(mediaplayer['mediaplayer']) == 'on' :
                    for light in self.roomlight :
                        light.setLightMode(lightmode = mediaplayer['mode'])
                    return False
        return True


class Light:

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
    conditions):

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

        self.outLux:float = 0.0
        self.roomLux:float = 0.0
        self.rain_amount:float = 0.0
        self.lightmode = 'normal'
        self.times_to_adjust_light:list = []

            # Set up automations and times defined
        if self.automations :
            test_time = self.ADapi.parse_time('00:00:00')
            if test_time != self.ADapi.parse_time(self.automations[0]['time']) :
                self.automations.insert(0, {'time': '00:00:00', 'state': 'turn_off'})

            automationsToDelete = []
            timeToAdd: timedelta = datetime.timedelta(minutes = 0)
            for num, automation in enumerate(self.automations) :
                    # Checks if multiple times is configured and parse all times 
                if 'orLater' in automation :
                    if self.ADapi.parse_time(automation['time']) < self.ADapi.parse_time(automation['orLater']) :
                        orLaterDate = self.ADapi.parse_datetime(automation['orLater'])
                        timeDate = self.ADapi.parse_datetime(automation['time'])
                        timeToAdd = orLaterDate -timeDate
                        if timeToAdd < datetime.timedelta(minutes = 0) :
                            timeToAdd += datetime.timedelta(days = 1)
                        automation['time'] = automation['orLater']
                elif timeToAdd > datetime.timedelta(minutes = 0) :
                    if 'fixed' in automation :
                        timeToAdd = datetime.timedelta(minutes = 0)
                    newtime = self.ADapi.parse_datetime(automation['time']) + timeToAdd
                    automation['time'] = str(newtime.time())

                    # Deletes automations that are earlier than previous time. Useful when both time with sunset and fixed time is given in automations
                if test_time <= self.ADapi.parse_time(automation['time']) :
                    test_time = self.ADapi.parse_time(automation['time'])
                elif test_time > self.ADapi.parse_time(automation['time']) :
                    if not 'fixed' in automation :
                        #self.ADapi.log(f"Deletes automation: {self.automations[num]}") # For logging purposes to check if your times are as planned
                        automationsToDelete.append(num)

            for num in reversed(automationsToDelete) :
                del self.automations[num]

                brightness = 0
                for automation in self.automations :
                    if 'dimrate' in automation :
                        if 'light_data' in automation :
                            if 'brightness' in automation['light_data'] :
                                timeDate = self.ADapi.parse_datetime(automation['time'])
                                while brightness > automation['light_data']['brightness'] :
                                    brightness -= 1
                                    timeDate += datetime.timedelta(minutes = automation['dimrate'])
                                    self.automations.append({'time':  str(timeDate), 'light_data': {'brightness': brightness}})
                    if 'light_data' in automation :
                        if 'brightness' in automation['light_data'] :
                            brightness = automation['light_data']['brightness']

            for automation in self.automations :
                if not 'state' in automation :
                    automation.update({'state': 'none'})
                # Adjust lights with new light_data on given time
                if not automation['time'] in self.times_to_adjust_light :
                        self.times_to_adjust_light.append(automation['time'])

            # Set up motion automation and times defined
        if self.motionlight :
            if type(self.motionlight) == list :
                test_time = self.ADapi.parse_time('00:00:00')
                if test_time != self.ADapi.parse_time(self.motionlight[0]['time']) :
                    self.motionlight.insert(0, {'time': '00:00:00', 'state': 'turn_off'})

                automationsToDelete = []
                timeToAdd: timedelta = datetime.timedelta(minutes = 0)
                for num, automation in enumerate(self.motionlight) :
                        # Checks if multiple times is configured and parse all times 
                    if 'orLater' in automation :
                        if self.ADapi.parse_time(automation['time']) < self.ADapi.parse_time(automation['orLater']) :
                            orLaterDate = self.ADapi.parse_datetime(automation['orLater'])
                            timeDate = self.ADapi.parse_datetime(automation['time'])
                            timeToAdd = orLaterDate -timeDate
                            if timeToAdd < datetime.timedelta(minutes = 0) :
                                timeToAdd += datetime.timedelta(days = 1)
                            automation['time'] = automation['orLater']
                    elif timeToAdd > datetime.timedelta(minutes = 0) :
                        if 'fixed' in automation :
                            timeToAdd = datetime.timedelta(minutes = 0)
                        newtime = self.ADapi.parse_datetime(automation['time']) + timeToAdd
                        automation['time'] = str(newtime.time())

                        # Deletes automations that are earlier than previous time. Useful when both time with sunset and fixed time is given in automations
                    if test_time <= self.ADapi.parse_time(automation['time']) :
                        test_time = self.ADapi.parse_time(automation['time'])
                    elif test_time > self.ADapi.parse_time(automation['time']) :
                        if not 'fixed' in automation :
                            #self.ADapi.log(f"Deletes automation: {self.automations[num]}") # For logging purposes to check if your times are as planned
                            automationsToDelete.append(num)
                for num in reversed(automationsToDelete) :
                    del self.motionlight[num]

                brightness = 0
                for automation in self.motionlight :
                    if 'dimrate' in automation :
                        if 'light_data' in automation :
                            if 'brightness' in automation['light_data'] :
                                timeDate = self.ADapi.parse_datetime(automation['time'])
                                while brightness > automation['light_data']['brightness'] :
                                    brightness -= 1
                                    timeDate += datetime.timedelta(minutes = automation['dimrate'])
                                    self.motionlight.append({'time':  str(timeDate), 'light_data': {'brightness': brightness}})
                    if 'light_data' in automation :
                        if 'brightness' in automation['light_data'] :
                            brightness = automation['light_data']['brightness']

                for automation in self.motionlight :
                    if not 'state' in automation :
                        automation.update({'state': 'none'})
                    # Adjust lights with new light_data on given time
                    if not automation['time'] in self.times_to_adjust_light :
                        self.times_to_adjust_light.append(automation['time'])

            # Set up automations in modes and times if defined
        for mode in self.light_modes :
            if 'automations' in mode :
                test_time = self.ADapi.parse_time('00:00:00')
                if test_time != self.ADapi.parse_time(mode['automations'][0]['time']) :
                    mode['automations'].insert(0, {'time': '00:00:00', 'state': 'turn_off'})

                automationsToDelete = []
                timeToAdd: timedelta = datetime.timedelta(minutes = 0)
                for num, automation in enumerate(mode['automations']) :
                        # Checks if multiple times is configured and parse all times 
                    if 'orLater' in automation :
                        if self.ADapi.parse_time(automation['time']) < self.ADapi.parse_time(automation['orLater']) :
                            orLaterDate = self.ADapi.parse_datetime(automation['orLater'])
                            timeDate = self.ADapi.parse_datetime(automation['time'])
                            timeToAdd = orLaterDate -timeDate
                            if timeToAdd < datetime.timedelta(minutes = 0) :
                                timeToAdd += datetime.timedelta(days = 1)
                            automation['time'] = automation['orLater']
                    elif timeToAdd > datetime.timedelta(minutes = 0) :
                        if 'fixed' in automation :
                            timeToAdd = datetime.timedelta(minutes = 0)
                        newtime = self.ADapi.parse_datetime(automation['time']) + timeToAdd
                        automation['time'] = str(newtime.time())

                        # Deletes automations that are earlier than previous time. Useful when both time with sunset and fixed time is given in automations
                    if test_time <= self.ADapi.parse_time(automation['time']) :
                        test_time = self.ADapi.parse_time(automation['time'])
                    elif test_time > self.ADapi.parse_time(automation['time']) :
                        if not 'fixed' in automation :
                            #self.ADapi.log(f"Deletes mode automation: {self.automations[num]}") # For logging purposes to check if your times are as planned
                            automationsToDelete.append(num)
                for num in reversed(automationsToDelete) :
                    del mode['automations'][num]

                brightness = 0
                for automation in mode['automations'] :
                    if 'dimrate' in automation :
                        if 'light_data' in automation :
                            if 'brightness' in automation['light_data'] :
                                timeDate = self.ADapi.parse_datetime(automation['time'])
                                while brightness > automation['light_data']['brightness'] :
                                    brightness -= 1
                                    timeDate += datetime.timedelta(minutes = automation['dimrate'])
                                    mode['automations'].append({'time':  str(timeDate), 'light_data': {'brightness': brightness}})
                    if 'light_data' in automation :
                        if 'brightness' in automation['light_data'] :
                            brightness = automation['light_data']['brightness']

                for automation in mode['automations'] :
                    if not 'state' in automation :
                        automation.update({'state': 'none'})
                    # Adjust lights with new light_data on given time
                    if not automation['time'] in self.times_to_adjust_light :
                        self.times_to_adjust_light.append(automation['time'])

            # Sets a valid state turn off in automation when motionlight turns on light for when motion ends
        if self.motionlight and not self.automations :
            self.automations = [{'time': '00:00:00', 'state': 'turn_off'}]

        for time in self.times_to_adjust_light :
            self.ADapi.run_daily(self.run_daily_lights, time)

    def run_daily_lights(self, kwargs):
        if self.lightmode != 'motion' :
            self.setLightMode()
        else :
            self.setMotion()

    def find_time(self, automation):
        prev_time = '00:00:00'
        target_num = 0
        for target_num, automations in enumerate(automation) :
            if self.ADapi.now_is_between(prev_time, automations['time']) :
                testtid = self.ADapi.parse_time(automations['time'])
                if datetime.datetime.today().hour == testtid.hour and datetime.datetime.today().minute == testtid.minute :
                    pass
                elif target_num != 0 :
                    target_num -= 1
                return target_num
        return target_num

    def checkOnConditions(self):
        for conditions in self.conditions :
            if not eval(conditions) :
                return False
        return True

    def checkLuxConstraints(self):
        if self.lux_constraint :
            if self.rain_amount > 1 :
                if self.outLux >= self.lux_constraint * 1.5:
                    return False
            elif self.outLux >= self.lux_constraint :
                return False
        if self.room_lux_constraint :
            if self.roomLux >= self.room_lux_constraint :
                return False
        return True

    def setLightMode(self, lightmode = 'None', motion = False):
        if lightmode == 'None' :
            lightmode = self.lightmode
        
            # Only do morning mode if Lux and conditions are valid
        if lightmode == 'morning' :
            if not self.checkOnConditions() or not self.checkLuxConstraints() :
                lightmode = 'normal'
                return
            # Custom mode will break any automation and keep light as is
        if lightmode == 'custom' :
            self.lightmode = lightmode
            return

            # Finds out if new lightmode is configured for light and executes
        for mode in self.light_modes :
            if lightmode == mode['mode'] :
                self.lightmode = lightmode
                    # Automation sets light according to time of day with Lux and Conditions constraints
                if 'automations' in mode :
                    if self.checkLuxConstraints() and self.checkOnConditions() :
                        self.setLightAutomation(automations = mode['automations'], motion = motion)
                    else :
                        for light in self.lights :
                            if self.ADapi.get_state(light) == 'on' :
                                string:str = light
                                if string[:5] == 'light' :
                                    self.ADapi.turn_off(light, transition = 3)
                                elif string[:5] == 'switc' :
                                    self.ADapi.turn_off(light)
                    return
                    # Turns on light with given data. Lux constrained but Conditions do not need to be met
                elif 'light_data' in mode :
                    for light in self.lights :
                        if self.checkLuxConstraints() :
                            if motion :
                                try :
                                    brightness = int(self.ADapi.get_state(light, attribute = 'brightness'))
                                except TypeError :
                                    brightness = 0
                                if brightness < mode['light_data']['brightness'] :
                                    self.ADapi.turn_on(light, **mode['light_data'])
                            else :
                                self.ADapi.turn_on(light, **mode['light_data'])
                        else :
                            if self.ADapi.get_state(light) == 'on' :
                                string:str = light
                                if string[:5] == 'light' :
                                    self.ADapi.turn_off(light, transition = 3)
                                elif string[:5] == 'switc' :
                                    self.ADapi.turn_off(light)
                    return
                elif 'state' in mode :
                        # Turns on light regardless of Lux and Conditions. Offset can be provided to increase or decrease lighting in mode
                    if 'turn_on' in mode['state'] :
                        for light in self.lights :
                            string:str = light
                            if string[:5] == 'light' :
                                    # If offset is provided in mode
                                if 'offset' in mode and self.automations :
                                    target_num = self.find_time(automation = self.automations)
                                    if 'light_data' in self.automations[target_num] :
                                        target = self.automations[target_num]['light_data'].copy()
                                        offset = int(mode['offset'])
                                        brightness_offset = math.ceil(int(target['brightness']) + offset )
                                        target.update({'brightness' : brightness_offset})
                                        if motion :
                                            try :
                                                brightness = int(self.ADapi.get_state(light, attribute = 'brightness'))
                                            except TypeError :
                                                brightness = 0
                                            if brightness < brightness_offset :
                                                self.ADapi.turn_on(light, **target)
                                        else :
                                            self.ADapi.turn_on(light, **target)
                                    else :
                                        self.ADapi.log(f"No light_data in automation to base offset off for {self.lights} in {self.automations[target_num]}", level = 'WARNING')
                                        self.ADapi.turn_on(light, transition = 3)
                                    # If not offset is provided set standard
                                elif self.automations and self.ADapi.get_state(light) == 'off' :
                                    target_num = self.find_time(automation = self.automations)
                                    if 'light_data' in self.automations[target_num] :
                                        self.setLightAutomation(automations = self.automations, motion = motion)
                                    else :
                                        self.ADapi.log(f"No light_data in automation for {self.lights} in {self.automations[target_num]}", level = 'WARNING')
                                        self.ADapi.turn_on(light, transition = 3)
                                elif self.ADapi.get_state(light) == 'off':
                                    self.ADapi.log(f"No automation provided for {self.lights}", level = 'WARNING')
                                    self.ADapi.turn_on(light, transition = 3)

                            elif string[:5] == 'switc' and self.ADapi.get_state(light) == 'off' :
                                self.ADapi.turn_on(light)
                        return
                        # Same as turn_on but with Lux constraints
                    elif 'lux_controlled' in mode['state'] :
                        if self.checkLuxConstraints() :
                            if 'offset' in mode and self.automations :
                                target_num = self.find_time(automation = self.automations)
                                if 'light_data' in self.automations[target_num] :
                                    target = self.automations[target_num]['light_data'].copy()
                                    offset = int(mode['offset'])
                                    brightness_offset = math.ceil(int(target['brightness']) + offset )
                                    target.update({'brightness' : brightness_offset})
                                    if motion :
                                        try :
                                            brightness = int(self.ADapi.get_state(light, attribute = 'brightness'))
                                        except TypeError :
                                            brightness = 0
                                        if brightness < brightness_offset :
                                            self.ADapi.turn_on(light, **target)
                                    else :
                                        self.ADapi.turn_on(light, **target)
                                else :
                                    self.ADapi.log(f"No light_data in automation to base offset off for {self.lights} in {self.automations[target_num]}", level = 'WARNING')
                                    self.ADapi.turn_on(light, transition = 3)
                            elif self.automations :
                                self.setLightAutomation(automations = self.automations, motion = motion)
                            else :
                                for light in self.lights :
                                    if self.ADapi.get_state(light) == 'off' :
                                        string:str = light
                                        if string[:5] == 'light' :
                                            self.ADapi.turn_on(light, transition = 3)
                                        elif string[:5] == 'switc' :
                                            self.ADapi.turn_on(light)
                        else :
                            for light in self.lights :
                                if self.ADapi.get_state(light) == 'on' :
                                    string:str = light
                                    if string[:5] == 'light' :
                                        self.ADapi.turn_off(light, transition = 3)
                                    elif string[:5] == 'switc' :
                                        self.ADapi.turn_off(light)
                        return
                        # Turns off light
                    elif 'turn_off' in mode['state'] :
                        for light in self.lights :
                            if self.ADapi.get_state(light) == 'on' :
                                string:str = light
                                if string[:5] == 'light' :
                                    self.ADapi.turn_off(light, transition = 3)
                                elif string[:5] == 'switc' :
                                    self.ADapi.turn_off(light)
                        return
                        # Manual on/off
                    elif 'manual' in mode['state'] :
                        return
                
            # Default turn off if away/off/night is not defined as a mode in light
        if lightmode == 'away' or lightmode == 'off' or lightmode == 'night' :
            self.lightmode = lightmode
            for light in self.lights :
                if self.ADapi.get_state(light) == 'on' :
                    string:str = light
                    if string[:5] == 'light' :
                        self.ADapi.turn_off(light, transition = 3)
                    elif string[:5] == 'switc' :
                        self.ADapi.turn_off(light)
            return
            # Default turn on maximum light if not fire/wash is defined as a mode in light
        elif lightmode == 'fire' or lightmode == 'wash' :
            self.lightmode = lightmode
            for light in self.lights :
                string:str = light
                if string[:5] == 'light' :
                    self.ADapi.turn_on(light, brightness = 255)
                elif string[:5] == 'switc' :
                    self.ADapi.turn_on(light)
            return

            # Mode is normal or not valid for light. Checks Lux and Conditions constraints and does defined automations for light
        self.lightmode = 'normal'
        if self.checkOnConditions() and self.checkLuxConstraints() :
            if self.automations :
                self.setLightAutomation(automations = self.automations, motion = motion)
            else:
                for light in self.lights :
                    if self.ADapi.get_state(light) == 'off' :
                        string:str = light
                        if string[:5] == 'light' :
                            self.ADapi.turn_on(light, transition = 3)
                        elif string[:5] == 'switc' :
                            self.ADapi.turn_on(light)
        else :
            for light in self.lights :
                if self.ADapi.get_state(light) == 'on' :
                    string:str = light
                    if string[:5] == 'light' :
                        self.ADapi.turn_off(light, transition = 3)
                    elif string[:5] == 'switc' :
                        self.ADapi.turn_off(light)

        # Sets motion light
    def setMotion(self):
        if self.motionlight :
            if not self.checkOnConditions() or not self.checkLuxConstraints() :
                return
                # Custom mode will break any automation and keep light as is
            if self.lightmode == 'custom' :
                return

                # Do not do motion mode if current mode is starting with night
            string:str = self.lightmode
            if string[:5] == 'night' :
                return

                # Do not adjust if current mode's state is manual.
            for mode in self.light_modes :
                if self.lightmode == mode['mode'] :
                    if 'state' in mode :
                        if 'manual' in mode['state'] :
                            return

            self.lightmode = 'motion'
            if type(self.motionlight) == list :
                target_num = self.find_time(automation = self.motionlight)
                if 'light_data' in self.motionlight[target_num] :
                    for light in self.lights :
                        try :
                            brightness = int(self.ADapi.get_state(light, attribute = 'brightness'))
                        except TypeError :
                            brightness = 0
                        if brightness < self.motionlight[target_num]['light_data']['brightness'] :
                            if self.motionlight[target_num]['state'] == 'adjust' and self.ADapi.get_state(light) == 'off' :
                                continue
                            self.ADapi.turn_on(light, **self.motionlight[target_num]['light_data'])
                elif 'turn_off' in self.motionlight[target_num] :
                    for light in self.lights :
                        if self.ADapi.get_state(light) == 'on' :
                            string:str = light
                            if string[:5] == 'light' :
                                self.ADapi.turn_off(light, transition = 3)
                            elif string[:5] == 'switc' :
                                self.ADapi.turn_off(light)
                elif self.ADapi.get_state(light) == 'off' :
                    for light in self.lights :
                        string:str = light
                        if string[:5] == 'light' :
                            self.ADapi.turn_on(light, transition = 3)
                        elif string[:5] == 'switc' :
                            self.ADapi.turn_on(light)

            elif 'light_data' in self.motionlight :
                for light in self.lights :
                    try :
                        brightness = int(self.ADapi.get_state(light, attribute = 'brightness'))
                    except TypeError :
                        brightness = 0
                    if brightness < self.motionlight['light_data']['brightness'] :
                        self.ADapi.turn_on(light, **self.motionlight['light_data'])

                # Defines more simple on/off with possibility to have offset off normal automation
            elif 'state' in self.motionlight :
                if 'turn_on' in self.motionlight['state'] :
                    for light in self.lights :
                        string:str = light
                        if string[:5] == 'light' :
                            if 'offset' in self.motionlight and self.automations :
                                target_num = self.find_time(automation = self.automations)
                                if 'light_data' in self.automations[target_num] :
                                    target = self.automations[target_num]['light_data'].copy()
                                    offset = int(self.motionlight['offset'])
                                    brightness_offset = math.ceil(int(target['brightness']) + offset )
                                    target.update({'brightness' : brightness_offset})
                                    self.ADapi.turn_on(light, **target)
                                else :
                                    self.ADapi.log(f"No light_data in automation to base offset off for {self.lights} in {self.automations[target_num]}", level = 'WARNING')
                                    self.ADapi.turn_on(light, transition = 3)
                            elif self.automations and self.ADapi.get_state(light) == 'off' :
                                target_num = self.find_time(automation = self.automations)
                                if 'light_data' in self.automations[target_num] :
                                    self.setLightAutomation(automations = self.automations, motion = True)
                                else :
                                    self.ADapi.log(f"No light_data in automation for {self.lights} in {self.automations[target_num]}", level = 'WARNING')
                                    self.ADapi.turn_on(light, transition = 3)
                            elif self.ADapi.get_state(light) == 'off':
                                self.ADapi.log(f"No automation provided for {self.lights}", level = 'WARNING')
                                self.ADapi.turn_on(light, transition = 3)
                        elif string[:5] == 'switc' and self.ADapi.get_state(light) == 'off' :
                            self.ADapi.turn_on(light)

    def setLightAutomation(self, automations, motion = False ):
        target_num = self.find_time(automation = automations)
        target_num2 = self.find_time(automation = self.automations)
        if automations[target_num]['state'] == 'adjust' :
            if 'light_data' in automations[target_num] :
                for light in self.lights :
                    if self.ADapi.get_state(light) == 'on' :
                        if motion :
                            try :
                                brightness = int(self.ADapi.get_state(light, attribute = 'brightness'))
                            except TypeError :
                                brightness = 0
                            if brightness < automations[target_num]['light_data']['brightness'] :
                                self.ADapi.turn_on(light, **automations[target_num]['light_data'])
                        else :
                            self.ADapi.turn_on(light, **automations[target_num]['light_data'])
            elif 'light_data' in self.automations[target_num2] :
                for light in self.lights :
                    if self.ADapi.get_state(light) == 'on' :
                        if motion :
                            try :
                                brightness = int(self.ADapi.get_state(light, attribute = 'brightness'))
                            except TypeError :
                                brightness = 0
                            if brightness < automations[target_num2]['light_data']['brightness'] :
                                self.ADapi.turn_on(light, **automations[target_num2]['light_data'])
                        else :
                            self.ADapi.turn_on(light, **self.automations[target_num2]['light_data'])
        elif automations[target_num]['state'] != 'turn_off' :
            if 'light_data' in automations[target_num] :
                for light in self.lights :
                    if motion :
                        try :
                            brightness = int(self.ADapi.get_state(light, attribute = 'brightness'))
                        except TypeError :
                            brightness = 0
                        if brightness < automations[target_num]['light_data']['brightness'] :
                            self.ADapi.turn_on(light, **automations[target_num]['light_data'])
                    elif not motion :
                        self.ADapi.turn_on(light, **automations[target_num]['light_data'])
            elif 'light_data' in self.automations[target_num2] :
                for light in self.lights :
                    if motion :
                        try :
                            brightness = int(self.ADapi.get_state(light, attribute = 'brightness'))
                        except TypeError :
                            brightness = 0
                        if brightness < automations[target_num2]['light_data']['brightness'] :
                            self.ADapi.turn_on(light, **automations[target_num2]['light_data'])
                    else :
                        self.ADapi.turn_on(light, **self.automations[target_num2]['light_data'])
            else :
                for light in self.lights :
                    if self.ADapi.get_state(light) == 'off' :
                        string:str = light
                        if string[:5] == 'light' :
                            self.ADapi.turn_on(light, transition = 3)
                        elif string[:5] == 'switc' :
                            self.ADapi.turn_on(light)
        else :
            for light in self.lights :
                if self.ADapi.get_state(light) == 'on' :
                    string:str = light
                    if string[:5] == 'light' :
                        self.ADapi.turn_off(light, transition = 3)
                    elif string[:5] == 'switc' :
                        self.ADapi.turn_off(light)

    def toggle_light(self, kwargs):
        for light in self.lights :
            self.ADapi.toggle(light)



class Toggle(Light):

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
    usePersistentStorage):

        self.ADapi = api
        self.JSON_PATH = json_path

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
        conditions = conditions)

        self.toggle_lightbulb = toggle * 2 - 1
        self.fullround_toggle = num_dim_steps * 2
        self.usePersistentStorage = usePersistentStorage

            # Persistent storage
        if self.usePersistentStorage :
            with open(self.JSON_PATH, 'r') as json_read :
                lightwand_data = json.load(json_read)

            for light in self.lights :
                if not light in lightwand_data :
                    if self.ADapi.get_state(light) == 'on' :
                        self.current_toggle = self.toggle_lightbulb
                    else :
                        self.current_toggle = 0
                    lightwand_data.update({ light : {"toggle" : self.current_toggle }})
                    with open(self.JSON_PATH, 'w') as json_write :
                        json.dump(lightwand_data, json_write, indent = 4)
                self.current_toggle = lightwand_data[light]['toggle']
                break
        else :
            for light in self.lights :
                if self.ADapi.get_state(light) == 'on' :
                    self.current_toggle = self.toggle_lightbulb
                else :
                    self.current_toggle = 0
                break

    def setLightMode(self, lightmode = 'None'):
        if lightmode == 'None' :
            lightmode = self.lightmode

        if lightmode == 'morning' :
            if not self.checkOnConditions() or not self.checkLuxConstraints() :
                lightmode = 'normal'
                return

        if lightmode == 'custom' :
            self.lightmode = lightmode
            return

        for mode in self.light_modes :
            if lightmode == mode['mode'] :
                self.lightmode = lightmode
                    # Turns on light regardless of Lux and Conditions
                if 'toggle' in mode :
                    toggle_bulb = mode['toggle'] * 2 - 1
                    for light in self.lights :
                        if self.current_toggle == toggle_bulb :
                            return
                        elif self.current_toggle > toggle_bulb :
                            self.current_toggle -= self.fullround_toggle
                        sec = 1
                        while self.current_toggle < toggle_bulb :
                            self.ADapi.run_in(self.toggle_light, sec)
                            self.current_toggle += 1
                            sec += 1
                    # Turns off light
                elif 'state' in mode :
                    if 'turn_off' in mode['state'] :
                        for light in self.lights :
                            if self.ADapi.get_state(light) == 'on' :
                                self.ADapi.turn_off(light)
                                self.current_toggle = 0
                    # Persistent toggle
                if self.usePersistentStorage :
                    with open(self.JSON_PATH, 'r') as json_read :
                        lightwand_data = json.load(json_read)

                    for light in self.lights :
                        lightwand_data.update({ light : {"toggle" : self.current_toggle }})
                        with open(self.JSON_PATH, 'w') as json_write :
                            json.dump(lightwand_data, json_write, indent = 4)
                return

        if lightmode == 'away' or lightmode == 'off' or lightmode == 'night' :
            self.lightmode = lightmode
            for light in self.lights :
                if self.ADapi.get_state(light) == 'on' :
                    self.ADapi.turn_off(light)
                    self.current_toggle = 0
                # Persistent toggle
            if self.usePersistentStorage :
                with open(self.JSON_PATH, 'r') as json_read :
                    lightwand_data = json.load(json_read)

                for light in self.lights :
                    lightwand_data.update({ light : {"toggle" : self.current_toggle }})
                    with open(self.JSON_PATH, 'w') as json_write :
                        json.dump(lightwand_data, json_write, indent = 4)
            return

        elif lightmode == 'fire' or lightmode == 'wash'  :
            self.lightmode = lightmode
            for light in self.lights :
                if self.current_toggle == 1 :
                    return
                elif self.current_toggle > self.toggle_lightbulb :
                    self.current_toggle -= self.fullround_toggle

                while self.current_toggle < 1 :
                    self.ADapi.run_in(self.toggle_light, self.current_toggle)
                    self.current_toggle += 1
                # Persistent toggle
            if self.usePersistentStorage :
                with open(self.JSON_PATH, 'r') as json_read :
                    lightwand_data = json.load(json_read)

                for light in self.lights :
                    lightwand_data.update({ light : {"toggle" : self.current_toggle }})
                    with open(self.JSON_PATH, 'w') as json_write :
                        json.dump(lightwand_data, json_write, indent = 4)
            return

        self.lightmode = 'normal'
        if self.checkOnConditions() and self.checkLuxConstraints() :
            for light in self.lights :
                if self.current_toggle == self.toggle_lightbulb :
                    return
                elif self.current_toggle > self.toggle_lightbulb :
                    self.current_toggle -= self.fullround_toggle

                while self.current_toggle < self.toggle_lightbulb :
                    self.ADapi.run_in(self.toggle_light, self.current_toggle)
                    self.current_toggle += 1
        else :
            for light in self.lights :
                if self.ADapi.get_state(light) == 'on' :
                    self.ADapi.turn_off(light)
                    self.current_toggle = 0

            # Persistent toggle
        if self.usePersistentStorage :
            with open(self.JSON_PATH, 'r') as json_read :
                lightwand_data = json.load(json_read)

            for light in self.lights :
                lightwand_data.update({ light : {"toggle" : self.current_toggle }})
                with open(self.JSON_PATH, 'w') as json_write :
                    json.dump(lightwand_data, json_write, indent = 4)


    def setMotion(self):
        if self.motionlight :
            if not self.checkOnConditions() or not self.checkLuxConstraints() :
                return
                # Custom mode will break any automation and keep light as is
            if self.lightmode == 'custom' :
                return

                # Do not do motion mode if current mode is starting with night
            string:str = self.lightmode
            if string[:5] == 'night' :
                return

                # Do not adjust if current mode's state is manual.
            for mode in self.light_modes :
                if self.lightmode == mode['mode'] :
                    if 'state' in mode :
                        if 'manual' in mode['state'] :
                            return

            self.lightmode = 'motion'
            for light in self.lights :
                if self.current_toggle == self.toggle_lightbulb :
                    return
                elif self.current_toggle > self.toggle_lightbulb :
                    self.current_toggle -= self.fullround_toggle

                while self.current_toggle < self.toggle_lightbulb :
                    self.ADapi.run_in(self.toggle_light, self.current_toggle)
                    self.current_toggle += 1

                # Persistent toggle
            if self.usePersistentStorage :
                with open(self.JSON_PATH, 'r') as json_read :
                    lightwand_data = json.load(json_read)

                for light in self.lights :
                    lightwand_data.update({ light : {"toggle" : self.current_toggle }})
                    with open(self.JSON_PATH, 'w') as json_write :
                        json.dump(lightwand_data, json_write, indent = 4)

