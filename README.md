# Lightwand
an Appdaemon app for extensive control of lights based on time of day with mode event in addition to motion, presence, lux, rain, and media player sensors.

## Installation
Download the `Lightwand` directory from inside the `apps` directory here to your Appdaemon `apps` directory, then add configuration to a yaml file to enable the `Lightwand` module. See configuration below or my lightwand.yaml file for examples.

## App usage and tips to configure
All sections and configurations are optional, so you use only what is applicable.
Each app contains one 'Room' with all of the sensors you want to use for that room and define all the lights to automate the way you want.

### Mode change events
This app listens to event "MODE_CHANGE" in Home Assistant to set different light modes with 'normal' mode as default setting. See my ModeManagement example code if you want to automate some default away/morning/night modes. https://github.com/Pythm/ad-ModeManagement

Options is to call new mode from another app with:

    self.fire_event("MODE_CHANGE", mode = 'your_mode_name')

Or define scripts in Home Assistant and activate with automation/in lovelace to trigger an event:

    day:
      alias: "Day"
      sequence:
        - event: MODE_CHANGE
          event_data:
            mode: 'normal'


I have chosen this approach because I also base some other automations on mode change. E.g. calling 'dinner' mode from iPhone with ios_event will also send a notification to childrens phones and tablets.
<br>
<br>
When a event with "MODE_CHANGE" is triggered, it will check thru all defined modes for all lights in the app/Room.
<br>- If mode is defined in room and in light it will update light with attributes defined in mode
<br>- If mode is not defined in light but is present in room, light will revert to normal mode
<br>- If mode is not defined in room, the lights will keep existing mode. The idea here is if you want to have something other than usual for livingroom and still have night setting in kid's bedrooms.

There are some predefined mode names that behaves differently and does different things:
<br>All mode names except <b>custom</b> can be defined in 'light_modes' with your own configuration.
<br>Mode names with a default <b>off</b> : 'away', 'off', 'night'
<br>Mode names with default <b>full brightness</b> : 'fire', 'wash'
You are free to define whatever you like even for the names with default value. Useful for rgb lighting to set a colourtemp for wash or keep some lights lux constrained during night.

<b>Presence trackers</b> will trigger 'presence' when new == 'home' and sets 'away' if all trackers defined in room is not 'home'. When presence is detected it will go to 'normal' if old state is 'away' and 'presence' is not defined in 'light_mode'

Other modes with additional behaviour: <b>morning</b>, <b>night*</b>
<br>morning behaves as 'normal' mode with conditions and Lux constraints. Useful for some extra light in morning during workdays.
<br>When 'morning' mode is triggered, mode will be set to 'normal' if not defined in room and after media player turns off.
<br>In addition to 'night' mode you can configure modes beginning with 'night', for instance 'night_Kids_Bedroom'. All modes starting with 'night' will disable motion detection. 

When <b>custom</b> mode is triggered it will disable all automation and keep light as is for all lights. Useful for special days you want to do something different with the lights. Be aware that it does not do any mediaplayer/motion or lux detection either.
<br>- Use 'exclude_from_custom: True' in configuration to exclude the room from custom mode. Can be useful for rooms you forget to adjust light like outdoor lights and kid's bedroom.
<br><br>
You can define an Home Assistant input_text in one of the apps/rooms to display current LightMode in Lovelace. It will allways update with latest mode even if mode is not present in room.

### Default light behaviour
is configured with automations for each set of light and is activated with mode <b>normal</b>. If you only want lux control on/off you do not need to set up any automations. Both Lux constraint and conditions need to be meet before lights turns on in normal mode.

Automations is based on 'time' that can be both time with sunrise/sunset +- or fixed time. App sorts thru and deletes automations that are earlier than previous time when both time with sunset and fixed time is given in automations in cases where both time with sunrise/sunset and fixed time is given. I live quite far North so sunrise/sunset varies a lot and might be a bigger problem here than other places. In addition to 'time' you can also specify 'orLater' to have more accurate control of when lights changes depending on season. E.g.

    - time: '08:00:00'
      orLater: 'sunrise + 00:15:00'

If 'orLater' is later than 'time' it will shift all times following the same timedelta as here until a new 'orLater' is defined.

You can in prevent shifts and deletions with a 'fixed: True' under time that locks time from beeing moved of deleted. I only use this to make sure the lights for the children turns off at bedtime even when sun sets after.

Use dimrate to set brightness transition over time. -/+ 1 brightness pr x minutes.

### Motion behaviour
Configure <b>motionlights</b> to change light based on motion sensors in room. Easiest configuration is

    motionlights:
      state: turn_on

to have the light turn on if lux constraints and conditions are met.
If light is dimmable you can provide offset to 'state: turn_on' to increase or decrease brightness compared to 'light_data' in automation for normal light. You can also define light_data here or even a new set of automations with times same as automations for normal mode if you want different brightness etc during the day. 
<br>- motionlights will not turn down brightness in case other modes sets brightness higher e.g. <b>wash</b>.
<br>- If media players is on or night* mode is active motion detection is deactivated.

### Lights
<b>All lights</b> for the room is configured under <b>Lights</b> or optionally <b>ToggleLights</b> if you have lights/bulbs that dim with toggle. There you can configure multiple <b>-lights</b> that contains a list of the lights you want to configure with the same settings and automations, motionlights, light_modes, lux on/off/constraints and conditions

ToggleLights is configured with a number in 'toggle' on how many times to turn on light to get wanted dim instead of light_data for dimmable lights.

### Configure automations and motionlights
Each defined time can have a <b>state</b> and/or a <b>light_data</b>
<br><br>
<b>state</b> defines behavior. No need to define state in time for the times you want light to turn on, or based on lux constraints and conditions if any restrictions is defined.
<br>- turn_off: Turns off light at given time. Can also be defined in motionlights to turn off and keep light off after given time until next time. E.g. turn off at kid's bedroom at 21:00.
<br>- adjust: Does not turn on or off light but adjusts light_data at given time. Turn on/off with other modes or manual switch. Not applicable for motion.

<b>light_data</b> contains a set of attributes to be set to light: brightness, transition, color_temp, rgb_color, effect, etc. All attributes are optional.
<br><br>
Some considerations when writing your automations:
<br>If '00:00:00' is not defined a 'turn_off' state will be default at midnight if other times is configured in automations or motionlights in defined for lights.

### Configure modes
You can create as many modes in <b>light_mode</b> as you are able to have the time to configure and they can be defined with automations for different light settings during the day, light_data for one fits all setting or with a simple state: turn_on, lux_controlled, turn_off or manual.
<br>'automations' is configured and functions the same as automations for normal with lux and conditions constraints.
<br>'light_data' can be used if you only want one setting to turn on light with given data. This is Lux constrained but Conditions do not need to be met.
<br>'state' defines behaviour as in normal automation and can be turn_on, lux_controlled, turn_off or manual.
<br>- 'turn_on' turns on light regardless of Lux and Conditions
<br>- 'lux_controlled' only turns/keeps light on if lux is below lux_constraint
<br>- 'turn_off' Turns off light
<br>- 'manual' Completly manual on/off/brightness etc.
<br><br>
'offset' can be provided to state 'lux_controlled' or 'turn_on' to increase or decrease brightness based on 'light_data' in normal automation.

### Sensors
Zigbee and Zwave motion and lux sensors listens to MQTT events. Default namespace is mqtt
<br>If you have not set up mqtt you can use HA sensors to listen for HA state change.
<br>You can define time after sensor not longer detects motion before it turns light back with <b>delay</b> in seconds, and define constraints to each motion sensor as an if statement that must be true for motion to activate. Inherits Appdaemon API to self. Same applies to trackers and if presence mode is defined it will stay in that mode for seconds defined with delay.

### Media players
Sorted by priority if more than one mediaplayer is defined in room. Can be any sensor or switch with on/off state. Define name of mode for each sensor and define light attributes in 'light_modes'. Media mode will set light and keep as media mode when motion is detected as well as morning, normal and night* modes are called. Calling any other modes will set light to the new mode. If any of the morning, normal or night* modes is called when media is on, media mode will be active again.

### Conditions and constraints
You can use Lux sensors to control or constrain lights. Optionally you can provide if statement to be meet for light to turn on at normal/morning/motion mode or with automations defined. Inherits Appdaemon Api as ADapi.

### Get started
Easisest to start off with is to copy this example and update with your sensors and lights and build from that. There is a lot of list/dictionaries that needs to be correctly indented. And remember: All sections and configurations are optional, so you use only what is applicable.

## App configuration

```yaml
your_room_name:
  module: lightwand
  class: Room
  # Configure path to store Json for mode and lux data. This will give you some persistency when restarted. Adds 'your_room_name' + '.json' to the json_path
  json_path: /path/to/your/storage/
  namespace: mqtt

  # Lux sensors for lux control and constraint
  OutLuxZigbee: OutdoorLux
  OutLuxZwave: Outdoorsensor
  OutLux_sensor: sensor.hue_outdoor_sensor_illuminance_lux
  RoomLuxZigbee: motionsensor
  RoomLuxZwave: Multisensor
  RoomLux_sensor: sensor.motion_sensor_illuminance

  # HA sensor for detection of rain. If rain is detected, it will raise lux constraint by * 1.5
  rain_sensor: sensor.netatmo_rain

  # Home Assistant input_text to display current LightMode in Lovelace
  haLightModeText: input_text.lightmode

  # Exclude the room from custom mode
  exclude_from_custom: True

  # Motion sensors.
  # Use MQTT name for zigbee and zwave over mqtt sensors
  # Input delay in seconds before light turns back from motion to 'mode' light
  # motion_constraints takes an if statement that must be true for motion to activate. Inherits Appdaemon API to self
    # Example from my kitchen:
    # "self.now_is_between('06:50:00', '23:00:00') and self.get_tracker_state('person.yourwife') == 'home' or self.get_state('switch.espresso') == 'on' "
  motion_sensors:
    - motion_sensor: binary_sensor.motion_sensor_home_security_motion_detection
      delay: 600
      motion_constraints: "self.now_is_between('06:30:00', '21:00:00')"
  zigbee_motion_sensors:
    - motion_sensor: motionsensor_room
      delay: 600
      motion_constraints: "self.now_is_between('06:30:00', '21:00:00')"
  zwave_motion_sensors:
    - motion_sensor: Multisensor_room
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
  Lights:
    # Configure as many light with different settings you wish in a room and each lights configuration can have many lights/switches
    - lights:
      - light.hue
      - light.hue2

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
          rgb_color:
            - 255
            - 0
            - 255
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
      - time: '21:00:00'
        state: turn_off
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

key | optional | type | default | description
-- | -- | -- | -- | --
`module` | False | string | lightwand | The module name of the app.
`class` | False | string | Room | The name of the Class.
`json_path` | True | string || Use Json to store mode and lux data for persistency when restarted. Adds 'your_room_name' + '.json' to the json_path
`namespace` | True | string | `mqtt`| MQTT namespace
`OutLuxZigbee` | True | string | | Zigbee lux sensor for lux control and constraint
`OutLuxZwave` | True | string || Zwave over MQTT lux sensor for lux control and constraint
`OutLux_sensor` | True | string || HA Lux sensor for lux control and constraint
`RoomLuxZigbee` | True | string | | Zigbee lux sensor for lux control and constraint
`RoomLuxZwave` | True | string || Zwave over MQTT lux sensor for lux control and constraint
`RoomLux_sensor` | True | string || HA Lux sensor for lux control and constraint
`rain_sensor` | True | string || HA sensor for detection of rain. If rain is detected, it will raise lux constraint by * 1.5
`haLightModeText` | True | string || HA input_text to display current LightMode in Lovelace. Only needed in one of the rooms/apps
`exclude_from_custom` | True | bool | False | Exclude the room from custom mode
`motion_sensors` | True | dictionary || HA Motion sensors. Needs mode 'motion' defined in 'light_modes' to change light when motion detected
`zigbee_motion_sensors` | True | dictionary || Zigbee motion sensors. MQTT name. Needs mode 'motion' defined in 'light_modes' to change light when motion detected
`zwave_motion_sensors` | True | dictionary || Zwave over mqtt motion sensors. MQTT name. Needs mode 'motion' defined in 'light_modes' to change light when motion detected
`motion_sensor` | True | string || HA Motion sensor
`delay` | True | int | 60 | Input delay in seconds before light turns back from motion to current mode
`motion_constraints` | True | string || if statement that must be true for motion to activate. Inherits Appdaemon API to self
`presence` | True | dictionary || HA Presence detection. Will fire 'normal' mode if not 'presence' is defined in 'light_modes' if current mode is away and tracker returns 'home'. Sets mode as away for room if all trackers are not equal to 'home'.
`tracker` | True | string || HA tracker sensor
`delay` | True | int | 60 | Input delay in seconds before light turns back from presence to normal mode
`tracker_constraints` | True | string || if statement that must be true for presence to activate. Inherits Appdaemon API to self
`mediaplayers` | True | dictionary || Media players sorted by priority if more than one mediaplayer is defined
`mediaplayer` | True | string || Media player entity. Can be any HA sensor or switch with on/off state
`mode` | True | string || Define mode name here for media player and define light attributes in 'light_modes' with same mode name
`Lights` | True | list || All different configurations for Lights in room
`lights` | False | list || Lights/switches to be controlled with given configuration
`automations` | False | list || Configure default light behaviour for 'normal' mode with automations. Not needed if you only want lux control on/off
`time` | False | dictionary || Can be sunrise/sunset +- or fixed time
`orLater` | False | string || Can be sunrise/sunset +- or fixed time
`state` | True | string || adjust/ turn_off
`light_data` | True | attributes || attributes to be set to light: brightness, transition, color_temp, rgb_color, effect, etc
`mode` | False | list || Name of mode. Define light modes to change light accordingly
`automations` | False | list || Configure light behaviour for mode with automations. E.g. for different light during day with motion
`time` | False | dictionary || Can be sunrise/sunset +- or fixed time
`state` | True | string || adjust/ turn_off
`light_data` | True | attributes || attributes to be set to light: brightness, transition, color_temp, rgb_color, effect, etc
`state` | True | string || turn_on/ lux_controlled/ manual/ turn_off
`ToggleLights` | True | list || Use ToggleLights instead of Lights for bulbs/lights that dim with toggle
`toggle` | True | int | 3 | On toggles to get desired dim
`num_dim_steps` | True | int | 3 | Number of dim steps in bulb
`toggle` | False | dictionary || On toggles to get desired dim for mode
`lux_constraint` | True | int | | Outdoor lux constraint
`lux_turn_on` | True | int | | Outdoor lux to turn on light if below
`lux_turn_off` | True | int | | Outdoor lux to turn off light if above
`room_lux_constraint` | True | int | | Room lux constraint
`room_lux_turn_on` | True | int | | Room lux to turn on light if below
`room_lux_turn_off` | True | int | | Room lux to turn off light if above
`conditions` | True | list ||  Conditions as if statement to be meet for light to turn on at normal/morning/motion mode or with automations defined. Inherits Appdaemon Api as ADapi
