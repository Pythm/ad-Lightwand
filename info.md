## App configuration

```yaml
your_room_name:
  module: lightwand
  class: Room
  # Uses Json to store mode and lux data for persistency when restarted. Adds 'your_room_name' + '.json' to the json_path
  json_path: /config/appdaemon/apps/Lightwand/wand_

  # Lux sensors for lux control and constraint
  OutLuxZigbee: OutdoorLux
  OutLuxZwave: Outdoorsensor
  OutLux_sensor: sensor.hue_outdoor_sensor_illuminance_lux
  RoomLuxZigbee: motionsensor
  RoomLuxZwave: Multisensor
  RoomLux_sensor: sensor.motion_sensor_illuminance
  # HA sensor for detection of rain. If rain is detected, it will raise lux constraint by * 1.5
  rain_sensor: sensor.netatmo_rain

  # You can define an Home Assistant input_text in one of the rooms to display current LightMode in Lovelace
  haLightModeText: input_text.lightmode

  # Exclude the room from custom mode
  exclude_from_custom: True

  # Motion sensors. Needs 'mode: motion' defined in 'light_modes' to change light when motion detected. Use MQTT name for zigbee and zwave over mqtt sensors
  # Input delay in seconds before light turns back from motion to 'mode' light. Default delay is 60 second
  # motion_constraints takes an if statement that must be true for motion to activate. Inherits Appdaemon API to self. Example from my kitchen:
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
  presence:
    - tracker: person.yourwife
      delay: 600
      tracker_constraints: "self.now_is_between('06:30:00', '22:00:00') "
    - tracker: person.yourself
      delay: 600
      tracker_constraints: "self.now_is_between('06:30:00', '22:00:00') "

  # Media players. Sorted by priority if more than one mediaplayer is defined in room. Can be any sensor or switch with on/off state.
  # Define name of mode here and define light attributes in 'light_modes'
  mediaplayers:
    - mediaplayer: binary_sensor.yourXboxGamerTag
      mode: pc
    - mediaplayer: media_player.tv
      mode: tv

  # Configure lights and switches as Lights. Lights that dim with toggle is configured with 'ToggleLights'
  Lights:
    # Configure as many light with different settings you wish in a room and each lights configuration can have many lights/switches
    - lights:
      - light.hue
      - light.hue2

      # Configure default light behaviour for 'normal' mode with automations. Not needed if you only want lux control on/off
      # Both Lux and Conditions need to be meet before lights turns on
      # 'time' can be both time with sunrise/sunset +- and fixed time
      #     App deletes automations that are later than next in cases where both time with sunrise/sunset and fixed time is given
      # If not '00:00:00' is defined a 'turn_off' state will be default at midnight if 'motion' in 'light_mode' or other times is configured
      # 'state' defines behavior:
      #     adjust: Does not turn on or off light but adjusts light_data on given time. Turn on/off with other modes or manual switch
      #     manual: Completly manual on/off/brightness etc.
      #     turn_off: Turns off light at given time
      #     No need to define 'state' in 'time' for the times you want light to turn on automatically
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
      # 'light_data' can be used if you only want one setting to turn on light with given data. Lux constrained but Conditions do not need to be met
      # 'state' defines behaviour:
      #     'turn_on' turns on light regardless of Lux and Conditions
      #     'lux_controlled' only keeps light on if lux is below lux_constraint
      #     'turn_off' Turns off light
      # 'offset' can be provided if state 'lux_controlled' or 'turn_on' is defined to increase or decrease brightness based on 'light_data' in normal automation
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
`json_path` | True | string | `/config/appdaemon/apps/Lightwand/wand_s`| Uses Json to store mode and lux data for persistency when restarted. Adds 'your_room_name' + '.json' to the json_path
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
`zigbee_motion_sensors` | True | dictionary || HA Motion sensors. Needs mode 'motion' defined in 'light_modes' to change light when motion detected
`zigbee_motion_sensors`-`motion_sensor` | True | string || HA Motion sensor
`zigbee_motion_sensors`-`delay` | True | int | 60 | Input delay in seconds before light turns back from motion to current mode
`zigbee_motion_sensors`-`motion_constraints` | True | string || if statement that must be true for motion to activate. Inherits Appdaemon API to self
`zwave_motion_sensors` | True | dictionary || HA Motion sensors. Needs mode 'motion' defined in 'light_modes' to change light when motion detected
`zwave_motion_sensors`-`motion_sensor` | True | string || HA Motion sensor
`zwave_motion_sensors`-`delay` | True | int | 60 | Input delay in seconds before light turns back from motion to current mode
`zwave_motion_sensors`-`motion_constraints` | True | string || if statement that must be true for motion to activate. Inherits Appdaemon API to self
`presence` | True | dictionary || HA Presence detection. Will fire 'normal' mode if not 'presence' is defined in 'light_modes' if current mode is away and tracker returns 'home'. Sets mode as away for room if all trackers are not equal to 'home'.
`presence`-`tracker` | True | string || HA tracker sensor
`presence`-`delay` | True | int | 60 | Input delay in seconds before light turns back from presence to normal mode
`presence`-`tracker_constraints` | True | string || if statement that must be true for presence to activate. Inherits Appdaemon API to self

  # Media players. Sorted by priority if more than one mediaplayer is defined in room. Can be any sensor or switch with on/off state.
  # Define name of mode here and define light attributes in 'light_modes'
  mediaplayers:
    - mediaplayer: binary_sensor.yourXboxGamerTag
      mode: pc
    - mediaplayer: media_player.tv
      mode: tv

  # Configure lights and switches as Lights. Lights that dim with toggle is configured with 'ToggleLights'
  Lights:
    # Configure as many light with different settings you wish in a room and each lights configuration can have many lights/switches
    - lights:
      - light.hue
      - light.hue2

      # Configure default light behaviour for 'normal' mode with automations. Not needed if you only want lux control on/off
      # Both Lux and Conditions need to be meet before lights turns on
      # 'time' can be both time with sunrise/sunset +- and fixed time
      #     App deletes automations that are later than next in cases where both time with sunrise/sunset and fixed time is given
      # If not '00:00:00' is defined a 'turn_off' state will be default at midnight if 'motion' in 'light_mode' or other times is configured
      # 'state' defines behavior:
      #     adjust: Does not turn on or off light but adjusts light_data on given time. Turn on/off with other modes or manual switch
      #     manual: Completly manual on/off/brightness etc.
      #     turn_off: Turns off light at given time
      #     No need to define 'state' in 'time' for the times you want light to turn on automatically
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
      # 'light_data' can be used if you only want one setting to turn on light with given data. Lux constrained but Conditions do not need to be met
      # 'state' defines behaviour:
      #     'turn_on' turns on light regardless of Lux and Conditions
      #     'lux_controlled' only keeps light on if lux is below lux_constraint
      #     'turn_off' Turns off light
      # 'offset' can be provided if state 'lux_controlled' or 'turn_on' is defined to increase or decrease brightness based on 'light_data' in normal automation
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
