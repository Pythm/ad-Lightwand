# Lightwand
an Appdaemon app for complete control of your lights in every situation

## Updates to come
Improved time of day setting of the light (with brightness). Reason : The need for light varies massively from summer to winter (I'm living in Norway). At 21.00 it can be bright as day in summer, need for some light during autum/spring and pitch black in winter. It can be done now but the configuration becomes quite messy. 

## Installation

Download the `Lightwand` directory from inside the `apps` directory here to your local `apps` directory, then add the configuration to enable the `Lightwand` module.

## App usage and tips to configure
All sections and configurations are optional, so you use only what is applicable
    
To get full control over light this app uses mode_event "MODE_CHANGE" in Home Assistant to set different light modes with 'normal' mode as default setting. See my ModeManagement example code if you want to automate some default away/morning/night modes or you can define scripts and activate in lovelace to trigger a mode_event like this:

    day:
      alias: "Day"
      sequence:
        - event: MODE_CHANGE
          event_data:
            mode: 'normal'
I have chosen this approach because I also base some other automations on mode change. E.g. 'dinner' mode will also send a notification to kids phones and tablets..

When a mode_event with "MODE_CHANGE" is triggered, it will check thru all defined modes for all lights in room.
<br>- If mode is defined in room and in light it will update light with attributes defined in mode
<br>- If mode is not defined in light but is present in room, light will revert to normal mode
<br>- If mode is not defined in room, room will keep existing mode

There are predefined mode names that behaves differently and does different things:

<b>Motion sensors</b> will trigger 'motion' mode for room. Configure 'motion' in 'light_modes' to change light during motion detection. 
<br>- 'motion' mode will do extra check to not turn down brightness in case other modes sets brightness brighter e.g. 'wash'.
<br>- 'motion' will not fire if media players are on.

<b>Presence trackers</b> will trigger 'presence' when new == 'home' and sets 'away' if all trackers defined in room is != 'home'. When presence detected it will go to 'normal' if old state is 'away' and 'presence' is not defined in 'light_mode'

custom mode will disable all automation and keep light as is for all lights in program. Useful for special days you want to do something different with the lights. Be aware that it does not do any motion or lux detection either
<br>- Use 'exclude_from_custom: True' in configuration to exclude the room from custom mode. Can be useful for rooms you forget to adjust light like outdoor lights and kids bedroom.

Some mode names have a default off : 'away', 'off', 'night'
<br>And some modes have a default full brightness: 'fire', 'wash'
<br>All mode names except 'custom' can be defined in 'light_modes' with your own configuration to override default behaviour. Useful for rgb lighting to set a colourtemp instead of colour for wash or keep some lights lux constrained during night
    
Other modes with additional behaviour: 'morning', 'night*'
<br>morning behaves as 'normal' mode with conditions and Lux constraints. I use 'morning' for some extra light during workdays.
<br>When 'morning' mode is triggered, mode will be set to 'normal' if not defined in room
<br>In addition to 'night' mode you can configure modes beginning with 'night', for instance 'night_Kids_Bedroom'. All modes starting with 'night' will not fire motion light when detected

<br>
<b>All lights for the room is configured under 'Lights'. There you can configure multiple '-lights' with settings but with same Lux/presence/media players.</b>

Configure default light behaviour for 'normal' mode with automations. Not needed if you only want lux control on/off. Both Lux constraint and Conditions need to be meet before lights turns on.

Automations is based on 'time' that can be both time with sunrise/sunset +- or fixed time. App deletes automations that are later than next in cases where both time with sunrise/sunset and fixed time is given. Yes I live quite far North so sunrise/sunset varies a lot. Some considerations when writing your automations:
<br>If '00:00:00' is not defined a 'turn_off' state will be default at midnight if other times is configured or 'motion' in defined 'light_mode'. 
<br>Each time can have a 'state' and/or a 'light_data'

'state' defines behavior. No need to define 'state' in 'time' for the times you want light to turn on automatically or based on lux constraints and conditions.
<br>- adjust: Does not turn on or off light but adjusts light_data at given time. Turn on/off with other modes or manual switch
<br>- turn_off: Turns off light at given time

'light_data' contains a set of attributes to be set to light: brightness, transition, color_temp, rgb_color, effect, etc. All attributes are optional.

<br>
You can create as many modes in 'light_mode' as you are able to have the time to configure and they can be defined with automations for different light settings during the day, light_data for one fits all setting or with a simple state: turn_on, lux_controlled, turn_off or manual.
<br>'automations' is configured and functions the same as automations for normal with lux and conditions constraints. Most common use for automation in mode is 'normal' mode turn_off and 'motion' containing automation.
<br>'light_data' can be used if you only want one setting to turn on light with given data. This is Lux constrained but Conditions do not need to be met.
<br>'state' defines behaviour as in normal automation and can be turn_on, lux_controlled, turn_off or manual
<br>- 'turn_on' turns on light regardless of Lux and Conditions
<br>- 'lux_controlled' only turns/keeps light on if lux is below lux_constraint
<br>- 'turn_off' Turns off light
<br>- 'manual' Completly manual on/off/brightness etc.

'offset' can be provided to state 'lux_controlled' or 'turn_on' to increase or decrease brightness based on 'light_data' in normal automation

<br>
Zigbee and Zwave motion and lux sensors listens to MQTT events
If you have not set up mqtt you can use HA sensors to listen for HA state change

<br><br>
Easisest to start off with is to copy this example. There is a lot of list/dictionaries that needs to be correctly indented. And remember: All sections and configurations are optional, so you use only what is applicable

## App configuration

```yaml
your_room_name:
  module: lightwand
  class: Room
  # Uses Json to store mode and lux data for persistency when restarted. Adds 'your_room_name' + '.json' to the json_path
  json_path: /config/appdaemon/apps/Lightwand/wand_
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

  # You can define an Home Assistant input_text in one of the rooms to display current LightMode in Lovelace. It will allways update with latest mode even if mode is not present in room
  haLightModeText: input_text.lightmode

  # Exclude the room from custom mode
  exclude_from_custom: True

  # Motion sensors. Needs 'mode: motion' defined in 'light_modes' to change light when motion detected
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
          effect: sunrice
      - time: '09:15:00'
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
      - time: '23:00:00'
        state: turn_off

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
      " Lux turn off will send a new update to light if new lux detected is above set target
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
`json_path` | True | string | `/config/appdaemon/apps/Lightwand/wand_`| Uses Json to store mode and lux data for persistency when restarted. Adds 'your_room_name' + '.json' to the json_path
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
`motion_sensors`-`motion_sensor` | True | string || HA Motion sensor
`motion_sensors`-`delay` | True | int | 60 | Input delay in seconds before light turns back from motion to current mode
`motion_sensors`-`motion_constraints` | True | string || if statement that must be true for motion to activate. Inherits Appdaemon API to self
`zigbee_motion_sensors` | True | dictionary || Zigbee motion sensors. MQTT name. Needs mode 'motion' defined in 'light_modes' to change light when motion detected
`zigbee_motion_sensors`-`motion_sensor` | True | string || HA Motion sensor
`zigbee_motion_sensors`-`delay` | True | int | 60 | Input delay in seconds before light turns back from motion to current mode
`zigbee_motion_sensors`-`motion_constraints` | True | string || if statement that must be true for motion to activate. Inherits Appdaemon API to self
`zwave_motion_sensors` | True | dictionary || Zwave over mqtt motion sensors. MQTT name. Needs mode 'motion' defined in 'light_modes' to change light when motion detected
`zwave_motion_sensors`-`motion_sensor` | True | string || HA Motion sensor
`zwave_motion_sensors`-`delay` | True | int | 60 | Input delay in seconds before light turns back from motion to current mode
`zwave_motion_sensors`-`motion_constraints` | True | string || if statement that must be true for motion to activate. Inherits Appdaemon API to self
`presence` | True | dictionary || HA Presence detection. Will fire 'normal' mode if not 'presence' is defined in 'light_modes' if current mode is away and tracker returns 'home'. Sets mode as away for room if all trackers are not equal to 'home'.
`presence`-`tracker` | True | string || HA tracker sensor
`presence`-`delay` | True | int | 60 | Input delay in seconds before light turns back from presence to normal mode
`presence`-`tracker_constraints` | True | string || if statement that must be true for presence to activate. Inherits Appdaemon API to self
`mediaplayers` | True | dictionary || Media players sorted by priority if more than one mediaplayer is defined
`mediaplayers`-`mediaplayer` | True | string || Media player entity. Can be any HA sensor or switch with on/off state
`mediaplayers`-`mode` | True | string || Define mode name here and define light attributes in 'light_modes' with same mode name
`Lights` | True | list || All different configurations for Lights in room
`Lights`-`lights` | False | list || Lights/switches to be controlled with given configuration
`Lights`-`lights`-`automations` | False | list || Configure default light behaviour for 'normal' mode with automations. Not needed if you only want lux control on/off
`Lights`-`lights`-`automations`-`time` | False | dictionary || Can be sunrise/sunset +- or fixed time
`Lights`-`lights`-`automations`-`time`-`state` | True | string || adjust/ turn_off
`Lights`-`lights`-`automations`-`time`-`light_data` | True | attributes || attributes to be set to light: brightness, transition, color_temp, rgb_color, effect, etc
`Lights`-`lights`-`light_modes`-`mode` | False | list || Name of mode. Define light modes to change light accordingly
`Lights`-`lights`-`light_modes`-`mode`-`automations` | False | list || Configure light behaviour for mode with automations. E.g. for different light during day with motion
`Lights`-`lights`-`light_modes`-`mode`-`automations`-`time` | False | dictionary || Can be sunrise/sunset +- or fixed time
`Lights`-`lights`-`light_modes`-`mode`-`automations`-`time`-`state` | True | string || adjust/ turn_off
`Lights`-`lights`-`light_modes`-`mode`-`automations`-`time`-`light_data` | True | attributes || attributes to be set to light: brightness, transition, color_temp, rgb_color, effect, etc
`Lights`-`lights`-`light_modes`-`mode`-`state` | True | string || turn_on/ lux_controlled/ manual/ turn_off
`ToggleLights` | True | list || Use ToggleLights instead of Lights for bulbs/lights that dim with toggle
`ToggleLights`-`lights`-`toggle` | True | int | 3 | On toggles to get desired dim
`ToggleLights`-`lights`-`num_dim_steps` | True | int | 3 | Number of dim steps in bulb
`ToggleLights`-`lights`-`light_modes`-`mode`-`toggle` | False | dictionary || On toggles to get desired dim for mode
`lux_constraint` | True | int | | Outdoor lux constraint
`lux_turn_on` | True | int | | Outdoor lux to turn on light if below
`lux_turn_off` | True | int | | Outdoor lux to turn off light if above
`room_lux_constraint` | True | int | | Room lux constraint
`room_lux_turn_on` | True | int | | Room lux to turn on light if below
`room_lux_turn_off` | True | int | | Room lux to turn off light if above
`conditions` | True | list ||  Conditions as if statement to be meet for light to turn on at normal/morning/motion mode or with automations defined. Inherits Appdaemon Api as ADapi
