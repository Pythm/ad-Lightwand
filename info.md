# Lightwand by Pythm
an Appdaemon app for extensive control of lights via [Home Assistant](https://www.home-assistant.io/) or MQTT. Set light data based on time of day or use Mode Change event in Home Assistant to set your light, in addition to motion, presence, lux, rain, and media player sensors.


## Installation
Download the `Lightwand` directory from inside the `apps` directory to your [Appdaemon](https://appdaemon.readthedocs.io/en/latest/) `apps` directory, then add configuration to a .yaml or .toml file to enable the `Lightwand` module. Minimum required in your configuration is:
```yaml
nameyourRoom:
  module: lightwand
  class: Room
  Lights:
    - lights:
      - light.yourLight
```

## App usage and configuration
> [!TIP]
> All sections and configurations except the minimum above are optional, so you use only what is applicable.
> Each app contains one 'Room' with all of the sensors you want to use for that room and define all the lights to automate.


## Lights
<b>All lights</b> for the room is configured as either <b>MQTTLights</b> to control lights directly via MQTT or <b>Lights</b> as Home Assistant lights/switches. Optionally as Home Assistant switches you can configure <b>ToggleLights</b> if you have lights/bulbs that dim with toggle.
<br>You can configure multiple <b>-lights</b> as lists of the lights / switches you want to configure, with the same settings including automations, motions, modes, lux on/off/constraints and conditions.

### MQTTLights
Tested with [zigbee2mqtt](https://www.zigbee2mqtt.io/). There you can control everything from switches to dimmers and RGB lights to Philips Hue. Just define light_data with the brightness, color, effect you want to control. Check your zigbee2mqtt for what your light supports. Brightness is in step 1-255.
<br>
<br>Is beeing testet with [zwaveJsUi](https://github.com/zwave-js/zwave-js-ui?tab=readme-ov-file#readme). I will only test switches and dimmable light. Brigtness is set with 'value' in range 1 to 99.
<br>
<br>Mqtt light names are full topics for targets excluding /set, case sensitive.
<br>Zigbee2mqtt should be something like: zigbee2mqtt/YourLightName
<br>Zwave could be something like: zwave/YourLightName/switch_multilevel/endpoint_1/targetValue
<br>App will subscribe to MQTT topics.

> [!TIP]
> I recommend [MQTT Explorer](https://mqtt-explorer.com/) or similar to find Zwave topic.

I do not see any advantages yet to control Zwave via Mqtt rather than via Home Assistant but the option is there

### Home Assistant Lights
Is configured with Lights and can control switches and lights. Use entity-id including type as name. Check your entity in Home Assistant for what your light supports as data like brightness, transition, rgb, etc.

### ToggleLights
ToggleLights is Home Assistant switch entities. Toggles are configured with a number 'toggle' on how many times to turn on light to get wanted dim instead of light_data for dimmable lights. Input 'num_dim_steps' as number of dim steps in bulb.


## Mode change events
> [!IMPORTANT]
> This app listens to event "MODE_CHANGE" in Home Assistant to set different light modes with 'normal' mode as default setting.
> The use of events in Appdaemon and Home Assistant is well documented in [Appdaemon docs - Events](https://appdaemon.readthedocs.io/en/latest/APPGUIDE.html#events)

To set mode from another appdaemon app simply use:
```python
self.fire_event("MODE_CHANGE", mode = 'your_mode_name')
```

Or define scripts in Home Assistant and activate with automation or in lovelace:

```yaml
day:
  alias: "your_mode_name"
  sequence:
    - event: MODE_CHANGE
      event_data:
        mode: 'your_mode_name'
```

See my [ModeManagement](https://github.com/Pythm/ad-ModeManagement) example code if you want to automate some default away/morning/night modes.

### Mode names
> [!IMPORTANT]
> When an event with "MODE_CHANGE" is triggered, it will check thru all defined modes for all lights in the app/Room.
> <br>- If mode is defined in room and for light it will update light with state/data defined in mode
> <br>- If mode is not defined in light but is present in room, light will be set to normal mode
> <br>- If mode is not defined in room, the lights will keep existing mode

There are some predefined mode names that behaves and does different things:
<br>All mode names except <b>'custom'</b> can be defined in 'light_modes' with your own configuration.
<br>Mode names that defaults to off:
<br>- 'away'
<br>- 'off'
<br>- 'night'
<br>Mode names with default full brightness:
<br>- 'fire'
<br>- 'wash'
<br> You are free to define whatever you like even for the names with default value. Useful for rgb lighting to set a colourtemp for wash or keep some lights lux constrained during night.

Other modes with additional behaviour:
<br>- 'morning' behaves as 'normal' mode with conditions and Lux constraints. Useful for some extra light in morning during workdays.
<br>When 'morning' mode is triggered, mode will be set to 'normal' if not defined in room and after media players is turned off.
<br>- 'night*' and 'off'. In addition to 'night' mode you can configure modes beginning with 'night', for instance 'night_Kids_Bedroom'.
<br>All modes starting with 'night' in addition to 'off' will disable motion detection. 
<br>
<br>'custom' mode will disable all automation and keep light as is for all lights. Useful for special days you want to do something different with the lights.
> [!NOTE]
> 'custom' does not do any mediaplayer, motion or lux control.

```yaml
  exclude_from_custom: True
```
in configuration will exclude the room from custom and wash mode. Can be useful for rooms you forget to adjust light, like outdoor lights and kid's bedroom.

## Defining times for lights
is configured with automations for each set of light and is activated with mode 'normal'. If you only want lux control on/off you do not need to set up any automations.
> [!NOTE]
> Both Lux constraint and conditions need to be meet before lights turns on in normal automation.

Automations is based on 'time' that can be both time with sunrise/sunset +- or fixed time. App deletes automations that have a time that are earlier than previous automation time. Useful when both time with sunset and fixed time is given in automations.

Optionally in addition to 'time' you can also specify 'orLater' to have more accurate control of when lights changes depending on season.
If 'orLater' is later than 'time' it will shift all times following the same timedelta as here until a new 'orLater' is defined.

You can in prevent shifts and deletions with a 'fixed: True' under time that locks time from beeing moved of deleted. I use this to make sure the lights for the children turns off at bedtime even when sun sets after.

```yaml
      automations:
      - time: '08:00:00'
        orLater: 'sunrise + 00:15:00'
      - time: '20:00:00'
        fixed: True
```

## Motion behaviour
Configure <b>motionlights</b> to change light based on motion sensors in room. A minimum configuration to have the light turn on if lux constraints and conditions are met is:

```yaml
  motion_sensors:
    - motion_sensor: binary_sensor.yourMotionSensor
  Lights:
    - lights:
      - light.kitchen
      motionlights:
        state: turn_on
```

If light is dimmable you can provide offset to 'state: turn_on' to increase or decrease brightness compared to 'light_data' in automation for normal light. Insted of 'state' you can define 'light_data', or even input your automations here with times if you want different brightness etc during the day for motion lights.

```yaml
      motionlights:
      - time: '00:00:00'
        light_data:
          brightness: 3
      - time: '06:50:00'
        light_data:
          brightness: 160
      - time: '08:30:00'
        orLater: 'sunrise + 00:15:00'
        light_data:
          brightness: 180
      - time: 'sunrise + 01:30:00'
        light_data:
          brightness: 120
      - time: '20:00:00'
        orLater: 'sunset + 00:30:00'
        dimrate: 2
        light_data:
          brightness: 3
```
> [!NOTE]
> motionlights will not turn down brightness in case other modes sets brightness higher e.g. <b>wash</b>.
> <br>If media players is on or night* / off mode is active motion lighting is deactivated.

### Configure automations and motionlights
Each defined time can have a <b>state</b> and/or a <b>light_data</b>
<br>
<br><b>state</b> defines behavior. No need to define state in time for lux constraints and conditions.
<br>- turn_off: light at given time. Can also be defined in motionlights to turn off and keep light off after given time until next time. E.g. turn off at kid's bedroom at 21:00.
<br>- adjust: Does not turn on or off light but adjusts light_data at given time. Turn on/off with other modes or manual switch. Not applicable for motion.

<b>light_data</b> contains a set of attributes to be set to light: brightness, transition, color_temp, rgb_color, effect, etc. All attributes are optional.

Use dimrate to set brightness transition over time. -/+ 1 brightness pr x minutes counting down from previous brightness until brightness is met.

> [!NOTE]
> If '00:00:00' is not defined a 'turn_off' state will be default at midnight if other times is configured in automations or motionlights is defined for lights.

### Configure modes
You can create as many modes in <b>light_mode</b> as you are able to have the time to configure and they can be defined with automations for different light settings during the day, light_data for one fits all setting or with a simple state: turn_on, lux_controlled, turn_off or manual.
<br>'automations' is configured and functions the same as automations for normal with lux and conditions constraints.
<br>'light_data' can be used if you only want one setting to turn on light with given data. This is Lux constrained but Conditions do not need to be met.
<br>'state' defines behaviour as in normal automation and can be turn_on, lux_controlled, turn_off or manual.
<br>- 'turn_on' turns on light regardless of Lux and Conditions
<br>- 'lux_controlled' only turns/keeps light on if lux is below lux_constraint
<br>- 'turn_off' Turns off light
<br>- 'manual' Completly manual on/off/brightness etc.
<br>
<br>'offset' can be provided to state 'lux_controlled' or 'turn_on' to increase or decrease brightness based on 'light_data' in normal automation.

An example :

```yaml
      light_modes:
        - mode: morning
          light_data: # Define specific light attributes for given mode
            brightness: 220
            transition: 3
            color_temp: 427
        - mode: decor
          state: turn_on # Turns on regardless of Lux constraints or defined conditions
          offset: -20 # Optional offset from brightness defined in normal mode
        - mode: tv
          state: turn_off
        - mode: away
          state: lux_controlled # Follows Lux Turn on/off
        - mode: nightKid
          state: manual # Disable all automation when this mode is active
        - mode: night
          automations: # Define own automation for mode. Lux constraints and defined conditions must be meet.
          - time: '00:00:00'
          - time: '03:00:00'
            state: turn_off
          - time: '23:00:00'
```

## Sensors
MQTT sensor names are full topics for targets excluding /set, case sensitive. App will subscribe to MQTT topics. Home Assistant sensors uses entity-id as sensor name.

### Motion Sensors and Presence trackers
You can define time after sensor no longer detects motion before it turns light back with <b>'delay'</b> in seconds, and define constraints to each sensor as an if statement that must be true for motion to activate. Inherits Appdaemon API to self.

Trackers will trigger 'presence' mode when new == 'home' and sets 'away' if all trackers defined in room is not 'home'. When presence is detected it will go to 'normal' if old state is 'away' and 'presence' is not defined in 'light_mode'. Trackers will not change mode unless it is normal or away.

```yaml
  motion_sensors:
    - motion_sensor: binary_sensor.yourMotionSensor
  MQTT_motion_sensors:
    - motion_sensor: zigbee2mqtt/KITCHEN_sensor
      delay: 300
      motion_constraints: "self.now_is_between('06:50:00', '23:00:00') and self.get_tracker_state('person.wife') == 'home' or self.get_state('switch.kitch_espresso') == 'on' "
  presence:
    - tracker: person.wife
      tracker_constraints: "self.now_is_between('06:30:00', '23:00:00') "
```

> [!TIP]
> Tracker will set mode as away when not home but there is no restrictions on calling new modes or normal when away.

### Media players
Sorted by priority if more than one mediaplayer is defined in room. Can be any sensor or switch with on/off state. Define name of mode for each sensor and define light attributes in 'light_modes'. Media mode will set light and keep as media mode when motion is detected as well as morning, normal and night* modes are called. Calling any other modes will set light to the new mode. If any of the morning, normal or night* modes is called when media is on, media mode will be active again.

```yaml
  mediaplayers:
    - mediaplayer: binary_sensor.yourXboxGamerTag
      mode: pc
    - mediaplayer: media_player.tv
      mode: tv
```

### Weather sensors
You can configure two outdoor lux sensors with the second ending with '_2' and it will keep the highest lux or last if other is not updated last 15 minutes. There can only be one room lux sensor but it can be either MQTT or Home Assistant sensor. Rain sensor can for now only be Home Assistant sensor.

```yaml
  OutLux_sensor: sensor.lux_sensor
  OutLuxMQTT_2: zigbee2mqtt/OutdoorHueLux
  RoomLux_sensor: sensor.lux_sensor
  RoomLuxMQTT: zwave/KITCHEN_sensor/sensor_multilevel/endpoint_0/Illuminance
  rain_sensor: sensor.netatmo_rain
```

### Conditions and constraints
You can use Lux sensors to control or constrain lights. Optionally you can provide IF statements to be meet for light to turn on at normal/morning/motion mode or with automations defined. Inherits Appdaemon Api as ADapi.
<br>I use this on some of the lights in my livingroom and kitchen for when my wife is not home but without using the presence sensor because I do not want to set my rooms as away.
You can define any statement you want so I have not figured out a better way than to create a 'listen_sensors' list for the sensors you use in statement so light can be updated when the condition changes.

```yaml
  listen_sensors:
    - person.wife
  #Some light data...
      conditions:
        - "self.ADapi.get_tracker_state('person.wife') == 'home'"
      lux_constraint: 12000
      lux_turn_on: 10000
      lux_turn_off: 12000
      room_lux_constraint: 100
      room_lux_turn_on: 80
      room_lux_turn_off: 100
```

### Persistent storage
Define a path to store json files with 'json_path' for persistent storage. This will store current mode for room and outdoor lux, room lux, and if lights is on for lights that has adjust/manual states and MQTT lights. Toggle lights will store current toggles.

## Namespace
If you have defined a namespace for MQTT other than default you need to define your namespace with 'MQTT_namespace'. Same for HASS you need to define your namespace with 'HASS_namespace'.

# Get started
Easisest to start off with is to copy this example and update with your sensors and lights and build from that. There is a lot of list/dictionaries that needs to be correctly indented. And remember: All sections and configurations are optional, so you use only what is applicable.

## App configuration

```yaml
your_room_name:
  module: lightwand
  class: Room
  # Configure path to store Json for mode and lux data. This will give you some persistency when restarted. Adds 'your_room_name' + '.json' to the json_path
  json_path: /path/to/your/storage/

  # Namespaces for MQTT and HASS if other than default.
  MQTT_namespace: mqtt
  HASS_namespace: hass

  # Lux sensors for lux control and constraint
  OutLux_sensor: sensor.lux_sensor
  OutLuxMQTT_2: zigbee2mqtt/OutdoorHueLux
  RoomLux_sensor: sensor.lux_sensor
  RoomLuxMQTT: zwave/KITCHEN_sensor/sensor_multilevel/endpoint_0/Illuminance

  # HA sensor for detection of rain. If rain is detected, it will raise lux constraint by * 1.5
  rain_sensor: sensor.netatmo_rain

  # Listen to sensors to update Lights when there is a change
  listen_sensors:
    - person.wife

  # Exclude the room from custom mode
  exclude_from_custom: True

  # Motion sensors.
  # Input delay in seconds before light turns back from motion to 'mode' light
  # motion_constraints takes an if statement that must be true for motion to activate. Inherits Appdaemon API to self
    # Example from my kitchen:
    # "self.now_is_between('06:50:00', '23:00:00') and self.get_tracker_state('person.yourwife') == 'home' or self.get_state('switch.espresso') == 'on' "
  motion_sensors:
    - motion_sensor: binary_sensor.motion_sensor_home_security_motion_detection
      delay: 600
      motion_constraints: "self.now_is_between('06:30:00', '21:00:00')"
  MQTT_motion_sensors:
    - motion_sensor: zigbee2mqtt/
      delay: 600
      motion_constraints: "self.now_is_between('06:30:00', '21:00:00')"

  # Presence detection. Configuration is same as motion sensors
  # Sets mode as away for room if all trackers are not equal to 'home'.
  # Sets mode to presence if defined in light_modes or normal if not defined when returning home
  presence:
    - tracker: person.yourwife
      delay: 600
      tracker_constraints: "self.now_is_between('06:30:00', '22:00:00') "
    - tracker: person.yourself
      delay: 600
      tracker_constraints: "self.now_is_between('06:30:00', '22:00:00') "

  # Media players. Sorted by priority if more than one mediaplayer is defined in room. Can be any sensor or switch with on/off state
  # Define name of mode here and define light attributes in 'light_modes'
  mediaplayers:
    - mediaplayer: binary_sensor.yourXboxGamerTag
      mode: pc
    - mediaplayer: media_player.tv
      mode: tv

  # Configure lights and switches as Lights. Lights that dim with toggle is configured with 'ToggleLights' insted of 'Lights'
  MQTTLights:
    # Configure as many light with different settings you wish in a room and each lights configuration can have many lights/switches
    - lights:
      - zigbee2mqtt/hue1
      - zigbee2mqtt/hue2

      # Configure default light behaviour for 'normal' mode with automations. Not needed if you only want lux control on/off
      # Both Lux and Conditions need to be meet before lights turns on
      # 'time' can be both time with sunrise/sunset +- and fixed time
      # 'state' defines behavior:
      #     adjust: Does not turn on or off light but adjusts light_data on given time. Turn on/off with other modes or manual switch
      #     turn_off: Turns off light at given time
      #     No need to define 'state' in 'time' for the times you want light to turn on
      # 'light_data' can contain a set of attributes to be set to light: brightness, transition, color_temp, rgb_color, effect, etc
      automations:
      - time: '06:30:00'
        light_data:
          brightness: 255
          effect: sunrise
      - time: '09:15:00'
        orLater: 'sunrise + 00:20:00'
        light_data:
          brightness: 255
          effect: colorloop
      - time: 'sunrise + 01:30:00'
        light_data:
          brightness: 120
          transition: 3
          color:
            x: 0.5075
            y: 0.4102
      - time: '22:00:00'
        light_data:
          brightness: 80
          effect: fireplace
      - time: '22:01:00'
        dimrate: 2 # Will start to dim from previous brightness (80) - 1 per x minutes. In this case every 2 minutes.
        light_data:
          brightness: 10
          effect: fireplace
      - time: '23:00:00'
        state: turn_off

      # Configure motion lights same way as normal automations
      motionlights:
      - time: '06:30:00'
        light_data:
          brightness: 160
      - time: '08:30:00'
        orLater: 'sunrise + 00:30:00'
        light_data:
          brightness: 120
      - time: 'sunset - 00:30:00'
        orLater: '19:00:00'
        light_data:
          brightness: 140
      - time: 'sunset + 00:30:00'
        light_data:
          brightness: 110
      - time: '23:00:00'
        state: turn_off # Turn off at given time even when motion.
        fixed: True

      # Define light modes to change light accordingly.
      # Modes can be configured with automations, light_data or state: turn_on, lux_controlled or turn_off
      # 'automations' is configured and functions the same as automations for normal with lux and conditions constraints
      # Most common use for automation in mode is 'normal' mode turn_off and 'motion' containing automation
      # 'light_data' can be used if you only want one setting to turn on light with given data
      #      Lux constrained but Conditions do not need to be met
      # 'state' defines behaviour:
      #     'turn_on' turns on light regardless of Lux and Conditions
      #     'lux_controlled' only keeps light on if lux is below lux_constraint
      #     'turn_off' Turns off light
      # 'offset' can be provided if state 'lux_controlled' or 'turn_on' is defined to increase or decrease brightness
      #      based on 'light_data' in normal automation
      light_modes:
        - mode: night_kid
          light_data:
            brightness: 10
        - mode: presence
          state: turn_on
        - mode: motion
          automations:
          - time: '00:00:00'
            light_data:
              brightness: 100
          - time: '04:00:00'
            light_data:
              brightness: 110
          - time: sunrise - 00:10:00
            light_data:
              brightness: 160
          - time: sunset + 00:30:00
            light_data:
              brightness: 60
        - mode: pc
          state: turn_off
        - mode: tv
          state: lux_controlled
          offset: -50

  ToggleLights:
    - lights:
      - switch.toggle_bulb
      toggle: 2 # On toggles to get desired dim
      num_dim_steps: 3 # Number of dim steps in bulb
      light_modes:
        - mode: night
          toggle: 3
        - mode: gaming
          state: turn_off

      # Lux constraints will only check when a new update to light is sent, like motion/presence, media player on/off or normal mode
      # Lux turn on will send a new update to light if new lux detected is below set target
      # Lux turn off will send a new update to light if new lux detected is above set target
      lux_constraint: 12000
      lux_turn_on: 10000
      lux_turn_off: 12000
      room_lux_constraint: 100
      room_lux_turn_on: 80
      room_lux_turn_off: 100

      # Conditions as if statement to be meet for light to turn on at normal/morning/motion mode or with automations defined
      # Inherits Appdaemon Api as ADapi.
      conditions:
        - "self.ADapi.get_tracker_state('person.kid') == 'home'"
        - "self.ADapi.now_is_between('06:50:00', '23:30:00')"
```
