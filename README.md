# Lightwand by Pythm
an Appdaemon app for extensive control of lights via [Home Assistant](https://www.home-assistant.io/) or MQTT. Set light data based on time of day or use Mode Change event in Home Assistant to set your light, in addition to lux, rain and multiple motion, presence, and media player sensors.

![Picture is generated with AI](/_d4d6a73c-b264-4fa6-b431-6d403c01c1f5.jpg)

## Installation
1. Download the `Lightwand` directory from inside the `apps` directory here to your [Appdaemon](https://appdaemon.readthedocs.io/en/latest/) `apps` directory.
2. Add the configuration to a .yaml or .toml file to enable the `Lightwand` module. Minimum required in your configuration is:

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

Each app contains one `Room` defined with Appname, that in the above example equals *nameyourRoom*. You input all of the sensors you want to use for that room, and define all the lights you want to automate.


## Lights
All lights for the room is configured as either `MQTTLights` to control lights directly via MQTT, or `Lights` as Home Assistant lights/switches. Optionally as Home Assistant switches you can configure `ToggleLights` if you have lights/bulbs that dim with toggle.
Each of the different light types can have multiple <b>-lights</b> as lists with the lights / switches. Each set containing the same settings including automations, motions, modes, lux on/off/constraints and conditions.

#### MQTTLights
To control lights via MQTT make sure to set up the[ MQTT plugin](https://appdaemon.readthedocs.io/en/latest/CONFIGURE.html#mqtt) in Appdaemon. The app will automatically set up subscription and listen for needed MQTT topics.
Developed for [zigbee2mqtt](https://www.zigbee2mqtt.io/). There you can control everything from switches to dimmers and RGB lights to Philips Hue. Just define light_data with the brightness, color, effect you want to control. Check your zigbee2mqtt for what your light supports. Brightness is set in range 1-255.

MQTT can also be used with [zwaveJsUi](https://github.com/zwave-js/zwave-js-ui?tab=readme-ov-file#readme). Only tested with switches and dimmable light. Brigtness is set with 'value' in range 1 to 99.

<br>Mqtt light names are full topics for targets excluding /set, case sensitive.
<br>Zigbee2mqtt should be something like: zigbee2mqtt/YourLightName
<br>Zwave could be something like: zwave/YourLightName/switch_multilevel/endpoint_1/targetValue

> [!TIP]
> I recommend [MQTT Explorer](https://mqtt-explorer.com/) or similar to find MQTT topic.


#### Home Assistant Lights
Is configured with Lights and can control switches and lights. Use entity-id including type as name. Check your entity in Home Assistant for what your light supports as data like brightness, transition, rgb, color temp, etc.

#### ToggleLights
ToggleLights is Home Assistant switch entities. Toggles are configured with a `toggle` number on how many times to turn on light to get wanted dim instead of light_data for dimmable lights. Input `num_dim_steps` as number of dim steps in bulb.


## Mode change events
> [!IMPORTANT]
> This app listens to event "MODE_CHANGE" in Home Assistant to set different light modes with `normal` mode as default setting.
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

> [!TIP]
> Check out [ModeManagement](https://github.com/Pythm/ad-ModeManagement) example code if you want to automate some default away/morning/night modes.

### Mode names
> [!IMPORTANT]
> When an event with "MODE_CHANGE" is triggered, it will check thru all defined modes for all lights in the app/Room.
> <br>- If mode is defined in room and for light it will update light with state/data defined in mode.
> <br>- If mode is not defined in light but is present in room, light will be set to normal mode.
> <br>- If mode is not defined in room, the lights will keep existing mode.


##### Predefined mode names 
All mode names except <b>'custom'</b> can be defined in 'light_modes' with your own configuration.

> [!NOTE]
> Setting mode to 'custom' stops all automation like mediaplayer, motion and lux control.

The predefined mode names with default turn on/off:

Mode names that defaults to off:
- `away`
- `off`
- `night`
Mode names with default full brightness:
- `fire`
- `wash`


Other modes with additional behaviour:
- `morning` behaves as `normal` mode with conditions and Lux constraints. Useful for some extra light in morning during workdays. When `morning` mode is triggered, mode will be set to `normal` after media players is turned off.

- In addition to `night` mode you can configure modes beginning with night, for instance `night_kids_bedroom`. All modes starting with night or off will by default disable motion detection.

'custom' mode will disable all automation and keep light as is for all lights. Useful for special days you want to do something different with the lights.

- `reset` sets all lights back to normal automation.

Only change one room:
To change only one room you can call either normal, off, or reset + _appName. Appname is what you call your app in configuration. See AppName example on nameyourRoom in [Installation](https://github.com/Pythm/ad-Lightwand?tab=readme-ov-file#installation). Given this name the mode to call to reset only that rom will be `reset_nameyourRoom`.

> [!TIP]
> You are free to define whatever you like even for the names with default value. Useful for rgb lighting to set a colourtemp for wash or keep some lights on during night mode.

##### Normal vs Reset Modes
While the distinction between normal and reset modes is subtle, it's essential to note that calling normal mode when the current mode is already set to normal will have no effect. To simplify automation and user interactions, I use the following approach:

In automations that adjust lighting modes automatically, I call normal mode.
For all other cases, such as user interface interactions or switch activations, I call reset mode.
This separation helps maintain a clean and intuitive control flow for both automated and manual lighting adjustments.


### Maintaining a Healthy Network and Infrastructure
When controlling multiple lights simultaneously, especially those that don't natively support transition commands, you may experience network congestion. This is because the controller needs to send multiple commands to each dimmer, generating significant traffic.

To mitigate this issue, consider grouping zigbee devices together in your zigbee2mqtt controller and referencing them by a group name under `MQTTlights`. This approach can help reduce network strain compared to listing all individual devices.

#### Add delays
If you experience problems that not all lights responds every time to mode changes you can add delays to see if it helps to distribute the network traffic over time. You have then two options.

##### Add delay to activate modes
An option for room configuration is to add delay in seconds on mode change. The modes that will wait with the option `mode_turn_off_delay` is away, off and night. The modes that will change after delay with option `mode_turn_on_delay` is modes: normal and morning.

> [!TIP]
> Setting different delays to rooms will help not to flood the zigbee/zwave network if you have a lot of lights.

You can also use this delay if you want to keep the light on/off for longer in some rooms when you exit or come home.

> [!NOTE]
> Motion, Precence (trackers) and when listening to state changes with 'listen_sensors', will override any delay if app reacts to state change.

```yaml
  mode_turn_off_delay: 2
  mode_turn_on_delay: 2
```

##### Add delay to every change
You can also add a random delay `random_turn_on_delay` defined with an number, and the lights in the room, will be turned on/off randomly between zero and the given number in seconds. This applies to every change, including motion.

> [!IMPORTANT]
> Try to avoid setting this in rooms that sets the light turn on by motion. This delay is also added to turn on/off lights when motion is detected.

```yaml
  random_turn_on_delay: 2
```

## Automating lights
Setting up automation is configured by time with a state and/or light data or use [Adaptive Lighting ](https://github.com/basnijholt/adaptive-lighting/tree/main) custom component to control the brightness and color control.

### Defining times
Automations contains a set of times for each set of light and is activated with mode 'normal'. If you only want lux control on/off, you do not need to set up any time automations.
> [!NOTE]
> Both Lux constraint and your conditions need to be meet before lights turns on in normal automation.

Automations are based on time, which can be either solar-based (using sunrise/sunset times) or clock-based. Optionally, in addition to `time`, you can also specify `orLater` to combine solar and clock-based times for more accurate control over when lights change depending on the season. If `orLater` is defined, it will shift all subsequent times by the same timedelta as long as not fixed or changed from sunrise to sunset time. In the example under with clock-based time at 08:00:00 and a solar-based time at sunrise + 00:15:00 defined with `orLater`, the clock-based time at 20:00 will shift by the same amount as the time difference between 08:00 and sunrise + 15 minutes. However, if you use a sunset time instead, the timeshift will stop at the first sunset time. A new timeshift is introduced every time `orLater` is used.

App deletes automations that have a time that are earlier than previous automation time if a time with solar-based and clock-based time is mixed in automations and the `orLater` is not used.

You can in prevent shifts and deletions with a `fixed`: True, which locks the time from being moved or deleted. I use this to make sure the lights in children's rooms turn off at bedtime, even when the sun sets after.

```yaml
      automations:
      - time: '08:00:00'
        orLater: 'sunrise + 00:15:00'
      - time: '20:00:00'
        fixed: True
        state: turn_off
```

> [!TIP]
> There are ready logs inn the python file commented out with # to easily log changes to times done by the app. Search code for: `Check if your times are acting as planned. Uncomment line below to get logging on time change`. Just uncomment the log line to see what changes the app does to your timing.

### Chosing between state and light_data
Each defined time can have a **state** and/or a **light_data**.

<b>State</b> defines behavior.
- turn_off: Turns off light at the given time. Can also be defined in motion lights to turn off and keep the light off after the given time until the next time. E.g., turn off at kids' bedroom at 21:00.
- adjust: Does not turn on or off the light but adjusts `light_data` at the given time. Turn on/off with other modes or manual switch. Not applicable for motion.

<b>Light data</b> contains a set of attributes to be set to the light, such as brightness, transition, color temperature, RGB color, effect, etc. Light data must have either brightness (HA or Zigbee2Mqtt) or value (zwaveJsUi). Other attributes are optional.

Use `dimrate` to set brightness transition -/+ 1 brightness per x minutes. Dimming from previous timed brightness until brightness is met.

> [!NOTE]
> If '00:00:00' is not defined a turn_off state will be default at midnight if other times is configured in automations or motionlights for lights.

If you only provide time in automation, the state will be set to `none` and the light will turn on if conditions are met. However, if you do not provide any light data it will not adjust anything.
If you do not provide time you must specify state.

### Use Adaptive Lighting instead of setting light data
Use [Adaptive Lighting ](https://github.com/basnijholt/adaptive-lighting/tree/main) custom component to control your brightness and color control for automation, motion or mode with setting state to 'adaptive'.

There is no need to configure Adaptive Lighting with 'detect_non_ha_changes' or 'take_over_control' when you set it up, if you only use Lightwand and Adaptive Lighting as automations for light. Lightwand is programmed to not change light if changed outside app until there is a change in sensors for room. If you change light manually then check Adaptive Lightings documetation for information if you need 'detect_non_ha_changes' or 'take_over_control'. Lightwand will set manual control with the provided "Adaptive Lighting" switch that you'll need to define. If a state or mode does not use Adaptive lighting Lightwand will update manual control to true, and then give back control when state is again `adaptive`.

Automatic setting of Adaptive Lighting's "Sleep Mode" is also implemented if you prefer to have a dimmed light instead of turning it completely off during night. All you need to do is define the `adaptive_sleep_mode` switch, and have one of the states in automation, motionlight or modes beeing `adaptive`. The switch will then be activated when night mode is called and keep light at a minimum as configured in Adaptive light, instead of turning it off. This applies to both `night` and `night_` + appName modes.

```yaml
  # The swiches can be configured in the room
  adaptive_switch: switch.adaptive_lighting_yourName
  adaptive_sleep_mode: switch.adaptive_lighting_sleep_mode_yourName
  # Or in lights
    - lights:
      - light.yourLight
      adaptive_switch: switch.adaptive_lighting_yourName
      adaptive_sleep_mode: switch.adaptive_lighting_sleep_mode_yourName
```

Minimum configuration to use Adaptive Lighting brightness and color temp setting is with:

```yaml
      automations:
      - state: adaptive
```
To include max and min brightness it looks like this:
```yaml
      automations:
      - state: adaptive
        max_brightness_pct: 60
        min_brightness_pct: 10
```

To configure with motionlights:
```yaml
      motionlights:
        state: adaptive
        max_brightness_pct: 80
        min_brightness_pct: 30
```


To use in mode configure with:
```yaml
      light_modes:
        - mode: your_mode
          state: adaptive
          max_brightness_pct: 100
          min_brightness_pct: 1
```

Automations, motionlights and automations in modes all supports list with times and states so you can configure Adaptive Lighting to only be active during specific times.


**Important Consideration for Adaptive Lighting**

When setting up `min` and `max` brightness values in the configuration, keep in mind that Lightwand does not know what brightness Adaptive Lighting will set. This can impact motionlights when changing between modes.

For more information on this issue, see [issue #16](https://github.com/Pythm/ad-Lightwand/issues/16).


### Motion behaviour
Configure `motionlights` to change light based on motion sensors in room. A minimum configuration to have the light turn on if lux constraints and conditions are met is:

```yaml
  motion_sensors:
    - motion_sensor: binary_sensor.yourMotionSensor
  Lights:
    - lights:
      - light.kitchen
      motionlights:
        state: turn_on
```

You can provide `offset` to dimmable lights to increase compared to `light_data` in automation for normal light. Insted of `state` you can define `light_data`, or even input your `automations` here with times if you want different brightness during the day for motion lights.

Automations example:
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
> When motion is active the light will not dim down. Motion detected will also not turn down brightness to set motion, in case other modes sets brightness higher e.g. <b>wash</b> active and set to 255 and motion only set to 125, light will stay at 255 brightness.
> <br>If media players is on or night* / off mode is active motion lighting is deactivated.


State with offset example:
```yaml
      motionlights:
        state: turn_on
        offset: 35
```


### Configure mode light
You can create as many modes in <b>light_mode</b> as you are able to have the time to configure, and they can be defined with automations for different light settings during the day, light_data for one fits all setting or with a simple state: turn_on, lux_controlled, turn_off or manual.

`automations` is configured and functions the same as automations for normal with lux and conditions constraints.
`light_data` can be used if you only want one setting to turn on light with given data. This is Lux constrained but Conditions do not need to be met.
`state` defines behaviour as in normal automation and can be turn_on, lux_controlled, turn_off or manual.
  - `turn_on` turns on light regardless of Lux and Conditions
  - `lux_controlled` only turns/keeps light on if lux is below lux_constraint
  - `turn_off` Turns off light
  - `manual` Completly manual on/off/brightness etc.

`offset` can be provided to state lux_controlled or turn_on to increase or (-) decrease brightness based on light_data in normal automation.

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
          state: lux_controlled # Follows Lux to turn on/off
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
You can define time after sensor no longer detects motion before it turns light back with `delay` in seconds. This defauts to 60 seconds. You can also define constraints to each sensor as an if statement that must be true for motion to activate. Inherits Appdaemon API to self.

Trackers will trigger 'presence' mode when new == home and sets 'away' mode if all trackers defined in room is not home. When presence is detected it will go to 'normal' mode if old state is 'away' and 'presence' is not defined in light_mode. Trackers will not change mode unless it is normal or away.

```yaml
  motion_sensors:
    - motion_sensor: binary_sensor.yourMotionSensor
  MQTT_motion_sensors:
    - motion_sensor: zigbee2mqtt/KITCHEN_sensor
      delay: 60
      motion_constraints: "self.now_is_between('06:50:00', '23:00:00') and self.get_tracker_state('person.wife') == 'home' or self.get_state('switch.kitch_espresso') == 'on' "
  presence:
    - tracker: person.wife
      tracker_constraints: "self.now_is_between('06:30:00', '23:00:00') "
```

> [!TIP]
> Tracker will set mode as away when not home but there is no restrictions on calling new modes or normal when away.

With `bed_sensor` light mode will stay at nigth mode until bed is exited, to then turn on normal operations when bed is exited.

### Media Players
Sorted by priority if more than one media player is defined in a room. Can be any sensor or switch with an on/off state. Define the name of the mode for each sensor and define light attributes in `light_modes`. The "media mode" will set the light and keep it as the media mode when motion is detected, as well as during morning, normal, and night* modes. Calling any other modes will set the light to the new mode. If any of the morning, normal, or night* modes are called when the media is on, the media mode will be active again.

> [!TIP]
> Input `delay` option when a TV reports a 'on' state shortly after being turned off and then reported a 'off' state again to avoid lights dimming up and down and up again.

```yaml
  mediaplayers:
    - mediaplayer: binary_sensor.yourXboxGamerTag
      mode: pc
    - mediaplayer: media_player.tv
      mode: tv
      delay: 0
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

### Custom options
`options` is a list with choices. It can be configured for the room or for each light.
- Enable motion detection during night mode with `night_motion`
- By default the light does not dim down when motion is detected. With `dim_while_motion` you allow the light to dim down even when motion, but only if the lightmode is `normal`.
- `exclude_from_custom` will exclude the room from 'custom' mode and 'wash' mode. Can be useful for rooms you forget to adjust light, like outdoor lights and kid's bedroom. Exclude from custom applies to the whole room, even if configured for one light.

When you configure holliday lights you can add `enable_light_control` to those lights. This is a HA input_boolean or other with on/off state. By design this only reads state on reboot/startup and if state is off, the lights will not be added to room. You can then keep the configuration for next year, but disable all those switches ticking on and off during the whole year, or free them up to other things, with one HA switch.

> [!TIP]
> I use one switch to disable xmas lights and also to hide any buttons with modes created for xmas in Home Assistant Frontend

```yaml
  #Configure in room
  options:
    - exclude_from_custom
    - dim_while_motion

  MQTTLights:
    - lights:
      - zigbee2mqtt/ENTRE_Spot
      # Configure in light
      options:
        - night_motion

      enable_light_control: input_boolean.xmas_light_control
```

### Conditions and constraints
You can use Lux sensors to control or constrain lights. Optionally you can provide IF statements to be meet for light to turn on at normal/morning/motion mode or with automations defined. Inherits Appdaemon Api as ADapi.
<br>I use this on some of the lights in my livingroom and kitchen for when my wife is not home but without using the presence tracker because I do not want to set my rooms as away.
You can define any statement you want so I have not figured out a better way than to create a 'listen_sensors' list for the sensors you use in statement so light can be updated when the condition changes.

```yaml
  listen_sensors:
    - person.wife
  #Some light data...
      conditions:
        - "self.ADapi.get_tracker_state('person.wife') == 'home'"
      lux_constraint: 12000
      room_lux_constraint: 100
```

## Manual changes to lights
If you manage to configure every light to your liking, normal automation should be sufficient for day-to-day use without intervention. However, there are days when you'll need something else. To avoid creating a mode for every possible scenario, I've tried to keep the automations so that if you set or adjust lights manually, they will stay until:
-Motion inclusive given delay has ended
-Lux levels go from below to above lux constraint. They will remain on if turned on when lux is above.
-Mode is changed
-Time automation is executed when conditions are met (e.g., if lux is above the constraint, automation will not execute)

> [!NOTE]
> If you define more than one light in the list the app only listens for changes in the first light in the list. In the example below the app will only detect changes to spot1. If you then only turn on spot2, the reset mode will not work.

```yaml
    - lights:
      - light.spot1
      - light.spot2
```

> [!TIP]
> To reset back to normal automation you can call mode `reset` or  `reset` + _appName

### Persistent storage
Define a path to store json files with `json_path` for persistent storage to recall last MQTT data and current lightmode for room on reboot. It writes data on terminate/reboot to store current mode for room and outdoor lux, room lux, and if lights is on or off for lights where needed.

Toggle lights automation will break if persistent storage is not configured. It is used to store current toggles.

This will increase writing to disk so it is not recomended for devices running on a SD card.

If it is not configured the lightmode will be set to normal/away/media depending on presence tracking and if media player is on.

## Namespace
If you have defined a namespace for MQTT other than default you need to define your namespace with `MQTT_namespace`. Same for HASS you need to define your namespace with `HASS_namespace`.

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

  # Exclude the room from custom mode or allow motion detection during night
  options:
    - exclude_from_custom
    - night_motion
    - dim_while_motion

  # Motion sensors.
  # Input delay in seconds before light turns back from motion to 'mode' light
  # motion_constraints takes an if statement that must be true for motion to activate. Inherits Appdaemon API to self
    # Example from my kitchen:
    # "self.now_is_between('06:50:00', '23:00:00') and self.get_tracker_state('person.yourwife') == 'home' or self.get_state('switch.espresso') == 'on' "
  motion_sensors:
    - motion_sensor: binary_sensor.motion_sensor_home_security_motion_detection
      delay: 60
      motion_constraints: "self.now_is_between('06:30:00', '21:00:00')"
  MQTT_motion_sensors:
    - motion_sensor: zigbee2mqtt/
      delay: 60
      motion_constraints: "self.now_is_between('06:30:00', '21:00:00')"

  # Presence tracker detection. Configuration is same as motion sensors
  # Sets mode as away for room if all trackers are not equal to 'home'.
  # Sets mode to presence if defined in light_modes or normal if not defined when returning home
  presence:
    - tracker: person.yourwife
      delay: 60
      tracker_constraints: "self.now_is_between('06:30:00', '22:00:00') "
    - tracker: person.yourself
      delay: 60
      tracker_constraints: "self.now_is_between('06:30:00', '22:00:00') "

  # Media players. Sorted by priority if more than one mediaplayer is defined in room. Can be any sensor or switch with on/off state
  # Define name of mode here and define light attributes in 'light_modes'
  mediaplayers:
    - mediaplayer: binary_sensor.yourXboxGamerTag
      mode: pc
    - mediaplayer: media_player.tv
      mode: tv

  # Add delay to turn on/off lights.
  mode_turn_off_delay: 2
  mode_turn_on_delay: 2

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
      toggle_speed: 0.8 # Set time in seconds between each toggle
      light_modes:
        - mode: night
          toggle: 3
        - mode: gaming
          state: turn_off

      # Lux constraints will only check when a new update to light is sent, like motion/presence, media player on/off or normal mode
      # Lux turn on will send a new update to light if new lux detected is below set target
      # Lux turn off will send a new update to light if new lux detected is above set target
      lux_constraint: 12000
      room_lux_constraint: 100

      # Conditions as if statement to be meet for light to turn on at normal/morning/motion mode or with automations defined
      # Inherits Appdaemon Api as ADapi.
      conditions:
        - "self.ADapi.get_tracker_state('person.kid') == 'home'"
        - "self.ADapi.now_is_between('06:50:00', '23:30:00')"
```

### Key definitions for defining app
key | optional | type | default | introduced in | description
-- | -- | -- | -- | -- | --
`module` | False | string | | v1.0.0 | The module name of the app.
`class` | False | string | | v1.0.0 | The name of the Class.
`HASS_namespace` | True | string | default | v1.1.0 | HASS namespace
`MQTT_namespace` | True | string | default | v1.1.0 | MQTT namespace
`options` | True | list | False | v1.1.5 | Can contain exclude_from_custom to exclude the room from custom mode, and night_motion to allow motion detection during night
`json_path` | True | string | | v1.0.0 | Use Json for persistency when restarted. Adds 'your_room_name' + '.json' to the json_path
`rain_sensor` | True | sensor | | v1.0.0 | HA sensor for detection of rain. If rain is detected, it will raise lux constraint by * 1.5
`OutLux_sensor` | True | sensor | | v1.0.0 | Sensor for Lux detection
`OutLuxMQTT` | True | MQTT sensor | | v1.0.0 | Lux detection via MQTT
`OutLux_sensor_2` | True | sensor | | v1.0.3 | Secondary Sensor for Lux detection
`OutLuxMQTT_2` | True | MQTT sensor | | v1.0.3 | Secondary Lux detection via MQTT
`RoomLuxMQTT` | True | string | | v1.0.0 | MQTT lux sensor for lux control and constraint
`RoomLux_sensor` | True | string | | v1.0.0 | HA Lux sensor for lux control and constraint
`mediaplayers` | True | dict | | v1.0.0 | Media players sorted by priority if more than one mediaplayer is defined
`motion_sensors` | True | dict | | v1.0.0 | HA Motion sensors
`MQTT_motion_sensors` | True | dict | | v1.0.0 | MQTT motion sensors
`presence` | True | dict | | v1.0.0 | HA Presence detection
`Lights` | True | list | | v1.0.0 | HA lights
`MQTTLights` | True | list | | v1.1.0 | MQTT lights
`ToggleLights` | True | list | | v1.0.0 | Use ToggleLights instead of Lights for bulbs/lights that dim with toggle
`listen_sensors` | True | list | | v1.1.0 | List of sensors to listen to state change for updating light
`mode_turn_off_delay` | True | int | | v1.3.1 | Add delay to turn on and off
`mode_turn_on_delay` | True | int | | v1.3.1 | Add delay to turn on and off
`random_turn_on_delay` | True | int | | v1.3.2 | Add delay to turn on and off
`adaptive_switch` | True | string | | v1.3.3 | HA switch to turn on/off Adaptive Lighting
`adaptive_sleep_mode` | True | string | | v1.3.4 | HA switch to turn on/off Adaptive Lightings sleep mode

### Key definitions to add to motion and presence sensors
key | optional | type | default | introduced in | description
-- | -- | -- | -- | -- | --
`motion_sensor` | True | sensor | | v1.0.0 | Motion sensor
`delay` | True | int | 60 | v1.0.0 | Input delay in seconds before light turns back from motion to current mode
`motion_constraints` | True | string | | v1.0.0 | if statement that must be true for motion to activate. Inherits Appdaemon API to self
`bed_sensor` | True | sensor | | v1.1.6 | This will wait until bed is exited to turn on light in room when night ended

### Key definitions to add to Lights
key | optional | type | default | introduced in | description
-- | -- | -- | -- | -- | --
`lights` | True | list | | v1.0.0 | list of lights
`automations` | True | dict | | v1.0.0 | Configure default light behaviour for 'normal' mode with automations
`motionlights` | True | dict | | v1.0.0 | Configure default light behaviour for motion detected
`light_modes` | True | dict | | v1.0.0 | Name of mode. Define light modes to change light accordingly
`lux_constraint` | True | int | | v1.0.0 | Outdoor lux constraint
`room_lux_constraint` | True | int | | v1.0.0 | Room lux constraint
`conditions` | True | list | | v1.0.0 | Conditions as if statement. Inherits Appdaemon Api as ADapi
`toggle_speed` | True | float | 1 | v1.1.4 | Set time in seconds between each toggle. Supports sub second with 0.x
