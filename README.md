# Lightwand by Pythm

An AppDaemon app for extensive control of lights via [Home Assistant](https://www.home-assistant.io/) or MQTT. Set light data based on time of day or use Mode Change events to set your lights, incorporating lux levels, rain conditions, and multiple motion, presence, and media player sensors.

![Picture is generated with AI](/_d4d6a73c-b264-4fa6-b431-6d403c01c1f5.jpg)

## Introduction

Lightwand offers a flexible way to automate your lights based on various environmental conditions. With its support for MQTT and Home Assistant, it easily integrates into existing smart home setups, providing robust lighting control.

## Installation

1. Install via HACS or git clone into your [AppDaemon](https://appdaemon.readthedocs.io/en/latest/) `apps` directory.
2. Add the following configuration to a `.yaml` or `.toml` file to enable the Lightwand module:

```yaml
nameyourRoom:
  module: lightwand
  class: Room
  Lights:
    - lights:
      - light.yourLight
```

## Lights
Configure all lights for a room using either `MQTTLights` to control lights directly via MQTT, or `Lights` as Home Assistant lights/switches. Optionally, if you have bulbs that dim with toggle actions, configure them under `ToggleLights`.
Each of the different light types can have multiple `-lights:` as lists with the lights / switches to control, and under each you configure how the light should react to time/sensors/modes. 

> [!TIP]
> You can configure multiple lights under each `-lights:` but look into creating groups in your controller instead, for a better network health.


#### MQTTLights
To control lights via MQTT set up Appdaemon with the [MQTT plugin](https://appdaemon.readthedocs.io/en/latest/CONFIGURE.html#mqtt) to connect Appdaemon to your MQTT broker. Define the MQTT namespace with `MQTT_namespace` in the app. The app will automatically set up subscription and listen for MQTT topics.
Developed for [zigbee2mqtt](https://www.zigbee2mqtt.io/). There you can control everything from switches to dimmers and RGB lights to Philips Hue. Check your controller or device for what data your light supports. Brightness is set in range 1-255.

MQTT can also be used with [zwaveJsUi](https://github.com/zwave-js/zwave-js-ui?tab=readme-ov-file#readme). Only tested with switches and dimmable light. Brigtness is set as percentage with 'value' in range 0 to 99, where 0 is off.

<br>Mqtt light names are full topics for targets excluding /set, case sensitive.
<br>Zigbee2mqtt should be something like: zigbee2mqtt/YourLightName
<br>Zwave could be something like: zwave/YourLightName/switch_multilevel/endpoint_1/targetValue

> [!TIP]
> I recommend [MQTT Explorer](https://mqtt-explorer.com/) or similar to find MQTT topic.


#### Home Assistant Lights
Entities defined under `Lights` can be Home Assistant switches and lights. Use entity-id including type as name.

Check your entity in [Home Assistant developer-tools -> state](https://my.home-assistant.io/redirect/developer_states/) for what your light supports when setting light_data.
<a href="https://my.home-assistant.io/redirect/developer_states/" target="_blank" rel="noreferrer noopener"><img src="https://my.home-assistant.io/badges/developer_states.svg" alt="Open your Home Assistant instance and show your state developer tools." /></a>

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

####
As an option to fire an event you can set light in rooms with Home assistant selectors configured with: `selector_input`.

### Mode names
> [!IMPORTANT]
> When an event with "MODE_CHANGE" is triggered, it will check thru all defined modes for all lights in the app/Room.
> <br>- If mode is defined in room and for light it will update light with state/data defined in mode.
> <br>- If mode is not defined in light but is present in room, light will be set to normal mode. Any lights set to media modes will be set to normal.
> <br>- If mode is not defined in room, the lights will keep existing mode.

Modes are configured for each `-lights:` entry and can look something like this:

```yaml
      light_modes:
        - mode: morning
          light_data: # Define specific light attributes for given mode
            brightness: 220
            transition: 3
            color_temp: 427
        - mode: decor
          offset: -20 # Optional offset from brightness defined in normal mode
        - mode: tv
          state: turn_off
        - mode: away
          state: lux_controlled # Follows Lux to turn on/off
        - mode: nightKid
          state: manual # Disable all automation when this mode is active
        - mode: night
          automations: # Define own automation for mode.
          - time: '00:00:00'
          - time: '03:00:00'
            state: turn_off
          - time: '23:00:00'
```

##### Predefined mode names 
With the exception of <b>`custom`</b> and <b>`reset`</b> you can create whatever mode name you wish to use when defining `light_modes` and apply your own configuration.

> [!NOTE]
> Setting mode to `custom` stops all automation like mediaplayer, motion and lux control.

Setting lightmode to one of the predefined mode names, you only have to configure that mode in light if you want the light behave different that with the default action.

Mode names that defaults to off:
- `away`
- `off`
- `night`
Mode names with default full brightness:
- `fire`
- `wash`


Other mode names with additional behaviour:
- `morning` behaves as `normal` mode with condition and Lux constraints. Useful for some extra light in morning during workdays. When `morning` mode is triggered, mode will be set to `normal` after media players is turned off.

- In addition to `night` mode you can configure modes beginning with night, for instance `night_kids_bedroom`. All modes starting with night or off will by default disable motion detection.

- `custom` mode will disable all automation and keep light as is for all lights. Useful for special days you want to do something different with the lights.

- `reset` sets all lights back to normal automation.

Only change one room:
To change only one room call the mode name + _appName. Appname is what you call your app in configuration. See AppName example on nameyourRoom in [Installation](https://github.com/Pythm/ad-Lightwand?tab=readme-ov-file#installation). Given this name the mode to call to reset only that rom will be `modename_nameyourRoom`.


> [!TIP]
> You are free to define whatever you like even for the names with default values. Useful for rgb lighting to set a color_temp for wash, or keep some lights on during night mode.


##### Normal vs Reset Modes
While the distinction between normal and reset modes is subtle, it's essential to note that calling normal mode when the current mode is already set to normal will have no effect on the lights you have manually changed. Calling reset mode will force a reset to normal settings. To simplify automation and user interactions, I use the following approach:

In automations that changes lighting modes automatically, I call normal mode.
For all other cases, such as user interface interactions or switch activations, I call reset mode.
In this way if mode is already normal, and I perform changes to the lights, automations will not change the lights.

### Translating or Changing Modes

Starting from version 1.5.0, a `translation.json` file has been included to allow customization of mode names according to user preference. You can modify this file to reflect your preferred terminology.

#### Steps to Customize Mode Names:
1. **Modify the Translation File**: Edit the `translation.json` file to update mode names and event settings as desired.
2. **Save in a Persistent Location**: Store the modified `translation.json` file in a location that persists across sessions.
3. **Define the Path**: Specify the path to your custom translation file using the configuration option: `language_file`.

#### Customizing Event Listeners:
- Within the `translation.json`, you can also specify different events for the app to listen to, rather than relying on the default `MODE_CHANGE` event.

#### Setting Language Preferences:
- Set your preferred language by configuring the `lightwand_language`. Available options include `"en"` for English and `"de"` for German. Ensure that these values match those defined in your example file.

By following these steps, you can tailor the application to better suit your linguistic preferences and operational needs.
```json
{
    "en": {
        "MODE_CHANGE": "MODE_CHANGE",
        "normal": "normal",
        "morning": "morning",
        "away": "away",
        "off": "off",
        "night": "night",
        "custom": "custom",
        "manual": "manual",
        "fire": "fire",
        "wash": "wash",
        "reset": "reset"
    },
    "de": {
        "MODE_CHANGE": "MODE_CHANGE",
        "normal": "automatik",
        "morning": "morgen",
        "away": "abwesend",
        "off": "aus",
        "night": "nacht",
        "custom": "custom",
        "manual": "manuell",
        "fire": "brand",
        "wash": "hell",
        "reset": "zurücksetzen"
    }
}
```

## Setting up how lights will behave
This chapter will try to explain all the different options you have when configuring states and light_data, and set up automation.


### Chosing between state and light_data
##### state
Defines how light will be automated. If not defined in mode under `light_modes`, it will turn on by default. When configuring `automations` and `motionlights`, control is lux constrained and conditions need to pass.

- `turn_off`: Turns off light at the given time/mode.
- `adjust`: Does not turn on or off the light but adjusts to the `light_data` configured with the state at the given time.
- `pass` : Lights that runs a program, like the 'sunrise' effect in Philips Hue restarts the program every time it receives an command. With this state Lightwand will set light_data with the turn on command, but Lightwand will not send a new command if the light is on.

> [!NOTE]
> If a automation or mode has `adjust` as state, using motion detection will turn on the light.

States only applicable for modes defined with `light_modes`:
- `manual`: Lightwand will not do anything to the lights when in the mode with manual state.
- `lux_controlled` Light will be on if lux is below lux_constraint.

To use Adaptive Lighting in automation, motionlight or mode define state as `adaptive`.

Example on how to configure modes with states.
```yaml
      light_modes:
        - mode: night
          state: lux_controlled # Set to lux controlled during night in stead of default off for night.
        - mode: decor
        - mode: tv
          state: turn_off
```

##### light_data
contains a set of attributes to be set to the light, such as brightness, transition, color temperature, RGB color, effect, etc.

> [!NOTE]
> If you have dimmable light and only use state to turn on and off, the light will do just that and not change brightness / light_data.

Example on how to configure light_data:
```yaml
        light_data:
          brightness: 80
          transition: 3
          color:
            x: 0.5075
            y: 0.4102
```

> [!TIP]
> `light_data` can be configured with every `state` except `manual`. To get lux control when using a mode include the `state: lux_controlled`.


#### Use Adaptive Lighting instead of setting light_data
Use [Adaptive Lighting ](https://github.com/basnijholt/adaptive-lighting/tree/main) custom component to control your brightness and color control for automation, motion or mode with setting state to 'adaptive'.

Using Adaptive Lighting with Lightwand is considered experimental but with the right configurations it should work.

It is created a [issue #16](https://github.com/Pythm/ad-Lightwand/issues/16) where you can post any unwanted behaviour when using Adaptive Lighting.

There is no need to configure Adaptive Lighting with 'detect_non_ha_changes' or 'take_over_control' when you set it up, if you only use Lightwand and Adaptive Lighting as automations for light. Lightwand is programmed to not change light if changed outside app until there is a change in sensors for room. If you change light manually then check Adaptive Lightings documetation for information if you need 'detect_non_ha_changes' or 'take_over_control'. Lightwand will set manual control with the provided "Adaptive Lighting" switch that you'll need to define. If a state or mode does not use Adaptive lighting Lightwand will update manual control to true, and then give back control when state is again `adaptive`.

Automatic setting of Adaptive Lighting's "Sleep Mode" is also implemented if you prefer to have a dimmed light instead of turning it completely off during night. All you need to do is define the `adaptive_sleep_mode` switch, and have one of the states in automation, motionlight or modes beeing `adaptive`. The switch will then be activated when night mode is called and keep light at a minimum as configured in Adaptive light, instead of turning it off. This applies to both `night` and `night_` + appName modes.


##### Important Consideration for Adaptive Lighting

When setting up `min` and `max` brightness values in the configuration, keep in mind that Lightwand does not know what brightness Adaptive Lighting will set. This will impact motionlights when changing between modes and motion can turn down light. To prevent this you can define 

[Check out the wiki on how to configure Adaptive Lighting](https://github.com/Pythm/ad-Lightwand/wiki/Combining-Lightwand-with-Adaptive-Lighting-Custom-Component)


### Automating lights

Setting up automation is configured by setting up an array when configuring. This is configured with a time if you input more than one entry, but can be only a `state` and/or `light_data`.

When lightmode is set to `normal` Lightwand will check if you have defined `automations`. If not, the light will only be turned on and off without setting any `light_data`.

Automations can also be configured for `motionlights`, and in `light_modes`.

> [!NOTE]
> For a light to turn on when the selected lightmode is a automation both `lux_constraint` and `conditions` must pass.


#### Defining times
Automations contains a set of times for each set of light. 

Automations are based on time, which can be either solar-based (using sunrise/sunset times) or clock-based. Optionally, in addition to `time`, you can also specify `orLater` to combine solar and clock-based times for more accurate control over when lights change depending on the season. If `orLater` is defined, it will shift all subsequent times by the same timedelta as long as not time is set as `fixed`, or time has changed from using sunrise to sunset time. In the example under with clock-based time at 08:00:00 and a solar-based time at sunrise + 00:15:00 defined with `orLater`, the clock-based time at 20:00 will shift by the same amount as the time difference between 08:00 and sunrise + 15 minutes. However, if you use a sunset time instead, the timeshift will stop at the first sunset time. A new timeshift is introduced or changed every time `orLater` is used.

App deletes automations that have a time that are earlier than previous automation time if a time with solar-based and clock-based time is mixed in automations and the `orLater` is not used.

You can in prevent shifts and deletions with a `fixed`: True, which locks the time from being moved or deleted.

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

> [!NOTE]
> If time '00:00:00' is not defined a turn_off state will be default at midnight if other times is configured in automations or motionlights for lights.

> [!NOTE]
> If you only provide time in automation, the state will be set to `none` and the light will turn on if conditions are met. However, if you do not provide any light_data, it will not adjust anything.


### Motion behaviour
Configure `motionlights` to define how light should react when motion is detected. A minimum configuration to have the light turn on is:

```yaml
  motion_sensors:
    - motion_sensor: binary_sensor.yourMotionSensor
  Lights:
    - lights:
      - light.kitchen
      motionlights:
```
For the light to turn on both `lux_constraint` and `conditions` must pass the test if lightmode is normal. If another mode is active it depends on how that mode is configured if light will react to motion.

Automations example with motionlights where brightness is set with light_data:
```yaml
      motionlights:
      - time: '00:00:00'
        light_data:
          brightness: 3
      - time: '03:00:00'
        state: turn_off
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
> When motion is active the light will not dim down. Motion detected will also not turn down brightness to set motion, in case other modes sets brightness higher.

> [!NOTE]
> If media players is on or night* / off mode is active motion detection is deactivated.


### Configure light modes
The different modes is configured under `light_modes` as an array. They can be defined with `automations` for different light settings during the day, `light_data` or with a simple state: `lux_controlled`, `turn_off` or `manual`.

In addition to configuring `automations` / `light_data` or `state` you can also prevent motion detection from changing the light with `noMotion: True` configured in the mode.


An example with the different ways to configure modes:

```yaml
      light_modes:
        - mode: morning
          light_data: # Define specific light attributes for given mode
            brightness: 220
            transition: 3
            color_temp: 427
        - mode: decor
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
        - mode: low_with_Automation
          automations:
            - light_data:
                brightness: 20
```


### Additional options and configurations
There are several options and configurations to take more control over how light reacts.

An option to dim light slowly up or down is to use `dimrate` in addition to `light_data` in automations, to set brightness transition -/+ 1 brightness per x minutes. Dimming from previous timed brightness until brightness is met.

You can define an `offset` to dimmable lights to increase or decrease brightness when `motionlights` or `light_modes` is active. This offset is applied to the brighness defined in light_data when configuring with automations.


Offset is configured like this:
```yaml
      motionlights:
        offset: 35
```

> [!NOTE]
> If the current mode is not configured with automations, motionlight with offset will not activate.


#### Defining options
`options` is an array with choices that can be configured for the room or in each `-lights` entry.
- Enable motion detection during night mode with `night_motion`
- Enable light to dim down when motion is detected with `dim_while_motion`.
- `exclude_from_custom` will exclude the room from 'custom' mode and 'wash' mode. Can be useful for rooms you forget to adjust light, like outdoor lights and kid's bedroom. Exclude from custom applies to the whole room, even if configured for one light.


When you configure holliday lights you can add `enable_light_control` to those lights. This is a HA input_boolean or other with on/off state. By design this only reads state on reboot/startup and if state is off, the lights will not be added to room. You can then keep the configuration for next year, but disable all those switches ticking on and off during the whole year, or free them up to other things, with one HA switch.

> [!TIP]
> I use one switch to disable xmas lights and also to hide any buttons with modes created for xmas in Home Assistant Frontend.

The option `prevent_off_to_normal` is to keep lights off if mode in room is off and automation is setting normal. This is useful if you have kids home sick or teenagers that like to sleep in when they have the day off, if you are using a automation to change from morning to normal the light will stay off. Reset to normal operation with `reset` mode.


```yaml
  #Configure in room
  options:
    - exclude_from_custom
    - dim_while_motion
    - prevent_off_to_normal

  MQTTLights:
    - lights:
      - zigbee2mqtt/ENTRE_Spot
      # Configure in light
      options:
        - night_motion

      enable_light_control: input_boolean.xmas_light_control
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
There is also an option to set `out_of_bed_delay` if you have unstable bedsensors and need to give them some extra seconds to see if the sensor detects again.

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


## Persistent storage
Define a path to store json files with `json_path` for persistent storage to recall last MQTT data and current lightmode for room on reboot. It writes data on terminate/reboot to store current mode for room and outdoor lux, room lux, and if lights is on or off for lights where needed.

Toggle lights automation will break if persistent storage is not configured. It is used to store current toggles.

This will increase writing to disk so it is not recomended for devices running on a SD card.

If it is not configured the lightmode will be set to normal/away/media depending on presence tracking and if media player is on.


## Namespace
If you have defined a namespace for MQTT other than default you need to define your namespace with `MQTT_namespace`. Same for HASS you need to define your namespace with `HASS_namespace`.


## Maintaining a Healthy Network and Infrastructure
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


# Get started
Easisest to start off with is to copy this example and update with your sensors and lights and build from that. There is a lot of list/dictionaries that needs to be correctly indented. And remember: All sections and configurations are optional, so you use only what is applicable.

## App configuration

```yaml
your_room_name:
  module: lightwand
  class: Room
  # Configure path to store Json for mode and lux data. This will give you some persistency when restarted. Adds 'your_room_name' + '.json' to the json_path
  json_path: /path/to/your/storage/
  language_file: /conf/apps/Lightwand/translations.json
  lightwand_language: no


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
      - zigbee2mqtt/hue

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

      # Configure motion lights
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

      light_modes:
        - mode: night_kid
          light_data:
            brightness: 10
        - mode: presence
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

