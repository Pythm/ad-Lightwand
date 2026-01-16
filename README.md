# Lightwand by Pythm  
**An [AppDaemon](https://github.com/AppDaemon/appdaemon) app for advanced lighting control via Home Assistant or MQTT**  
Set light data based on time of day, use Mode Change events or environmental conditions like lux levels, rain, and sensors like motion, presence and media players.  

![AI-Generated Illustration](/_d4d6a73c-b264-4fa6-b431-6d403c01c1f5.jpg)  

---

## 📌 Key Features
- **Mode-based automation** with `MODE_CHANGE` events
- **Lux-based lighting** with rain and time configurations
- **Multiple sensor inputs** for maximum flexibility

---

## 📱 Supported Platforms

This app is designed to work with:

- [AppDaemon](https://github.com/AppDaemon/appdaemon)
- [Home Assistant](https://www.home-assistant.io/)

Home Assistant is a popular open-source home automation platform that offers a wide range of features and integrations with various smart home devices. If you're not already using Home Assistant, I recommend checking it out.

AppDaemon is a loosely coupled, multi-threaded, sandboxed Python execution environment for writing automation apps for various types of home automation software, including Home Assistant and MQTT.

---

## 📦 Installation and Configuration

1. Have Home Assistant and Appdaemon up and running

2. `git clone` into your [AppDaemon](https://appdaemon.readthedocs.io/en/latest/) `apps` directory.
2. Add configuration to a `.yaml` or `.toml` file to enable the `ElectricalManagement` module.
3. Add the configuration to your `.yaml` file:

**Minimum Configuration** 
```yaml
your_room_name:
  module: lightwand
  class: Room
  Lights:
    - lights:
      - light.yourLight
```

---

## 🎯 Configuration Overview  

### 📌 Lights Configuration  
Define lights using `Lights`, `MQTTLights`, or `ToggleLights`.

> [!TIP]
> You can configure multiple lights under each `-lights:` but look into creating groups in your controller, for a better network health.

#### ✅ `Lights` (Home Assistant Entities)  
Use Home Assistant switches/lights. Example:  
```yaml
Lights:
  - lights:
    - light.kitchen
```

#### ✅ `MQTTLights` (Direct MQTT Control)  
Use MQTT for devices like Zigbee2MQTT.
```yaml
MQTTLights:
  - lights:
    - zigbee2mqtt/YourLight
```

#### ✅ `ToggleLights` (Dimming via Toggles)  
For bulbs that dim with toggle actions:  
```yaml
ToggleLights:
  - lights:
    - switch.toggle_bulb
    toggle: 2  # Number of toggles to reach desired brightness
    num_dim_steps: 3  # Steps in bulb dimming
    toggle_speed: 0.8 # Set time in seconds between each toggle

      light_modes:
        - mode: night
          toggle: 3
```
Toggle lights does not support motion or time based automations, only a mode with a toggle. If you need motion use Light with only on/off.

---

## 🧭 Mode Change Events  

### 🔁 Triggering Modes  
Use `MODE_CHANGE` events to activate predefined or custom modes.  

#### ✅ From AppDaemon:  
```python
self.fire_event("MODE_CHANGE", mode='your-mode-name')
```

#### ✅ From Home Assistant:  
```yaml
day:
  alias: "your_mode_name"
  sequence:
    - event: MODE_CHANGE
      event_data:
        mode: 'your-mode-name'
```

> [!TIP]  
> Check out [ModeManagement](https://github.com/Pythm/ad-ModeManagement) example code if you want to automate `away`, `morning`, or `night` modes.  

> [!TIP]  
> Already using events in your automations? Check out the [translation section](https://github.com/Pythm/ad-Lightwand?tab=readme-ov-file#translating-or-changing-modes) on how to listen for a different event than `"MODE_CHANGE"` and using translated mode names.

---

### 📌 Predefined Mode Names  

| Mode Name | Behavior |  
|----------|----------|  
| `normal` | Default automation mode for day-to-day usage with lux constraints and conditions. |  
| `morning` | Acts like `normal` mode but can be used with specific light settings for mornings. |  
| `reset` | Resets all lights to their `normal` mode settings. |  
| `away` | Defaults to **off** with motion detection enabled. |
| `night` / `off` | Defaults to **off** with motion detection disabled. |  
| `fire` / `wash` | Turns lights on with **maximum brightness**. |  
| `custom` | Manual control — **disables all automation**. |  

**Custom Mode Names**  
- With the exception of `custom` and `reset`, you can use **any** mode name in `light_modes`.  
- You can **overwrite** default behavior by configuring the mode.  
- In addition to `night` (or its translation, such as `nacht`) mode you can configure modes beginning with night, for instance `night-kid-bedroom`. All modes starting with night or off will by default disable motion detection.

---

### 🔄 Setting `normal` vs `reset` Mode from Automations  
- **Normal**: Safe for automations; does **not override** manual changes.  
- **Reset**: Forces lights back to their **original `normal` settings**.  

---

### 🏠 Change Mode in One Room  
To change the mode for a single room, use the mode name + `_appName`.  
- `appName` is the name you defined for your app in the configuration.  

> [!NOTE]  
> Avoid using underscore `_` in your names.

As an alternative to firing an event, you can use a **Home Assistant selector** with `selector_input`.  
- The app will update the selector options dynamically based on `MODE_CHANGE` events.
- Version 2.0.0 and later auto populates the selector_input with valid modes for the room.
- Use `selector_input_exclude_modes` to exclude mode names from the selector. Note that if the active mode is not in the selector it will show the old name.

```yaml
your_room_name:
  ...
  selector_input: input_select.livingroom_mode_light
  selector_input_exclude_modes:
    - away
    - wash
```

> [!NOTE]  
> The selector **does not enforce** validation (e.g., preventing invalid mode names).  
> Use `mode_name + _appName` for precise control over individual rooms.  

---


### 🔄 Translating or Changing Modes

#### Steps to Customize Mode Names
1. **Save the File Persistently**  
   Store the supplied example `translation.json` in a location that persists across sessions and updates (e.g., `/config/lightwand/translation.json`).  

2. **Edit the Translation File**  
   Modify `translation.json` to update the mode names and event settings.  
   > **Tip**  
   > In `translation.json`, you can specify a custom event name (e.g., `"LIGHT_MODE"`) instead of the default `"MODE_CHANGE"` to match your existing automations.  

   **Only translate the words that already exist in the default file.** The json file only contains mode names with a predefined action.

3. **Specify the Path and Language in Configuration**  
   Use the `language_file` parameter and `lightwand_language` to set your preferred language in **one** of your room‑app configurations:  

   ```yaml
   your_room_name:
     ...
     language_file: /config/lightwand/translation.json
     lightwand_language: "en"
   ```  

   Lightwand creates a singleton that can be imported by other apps to listen to the same modes.  

4. **Consistency Across the System**  
   If you translate a word (for instance, `"off"` → `"aus"` and `"night"` → `"nacht"`), **every** app that uses the translation will recognize the new word.
   These mode names are pre defined and have some logic behind it and you can then do modes like "nachtKinderzimmer" (nightChildRoom) to treat the room as in night mode. To turn off only in the livingroom you would use "aus_Wohnzimmer". If you have translated `"off"` → `"aus"` a call like `off_LivingRoom` would be interpreted as a *custom* mode named `"off"` rather than the built‑in off‑logic, leading to unexpected behaviour.

   The translated names will need to be changed throughout your entire setup in everything from scripts to other automations.

> **Note**  
> **Custom Modes Are Your Choice** Any mode that you create *outside* the predefined set is a light mode where you must specify either state or light_data.
> * These do **not** need to be added to `translation.json`.  


---

#### Quick Reference Table

| Default Mode | Example German Translation | Example Usage |
|--------------|---------------------------|---------------|
| `normal`     | `automatik`               | `automatik_LivingRoom` |
| `off`        | `aus`                     | `aus_Kitchen` |
| `night`      | `nacht`                   | `nacht_Bedroom` |
| `reset`      | `zurücksetzen`            | `reset_Garage` |
| `custom`     | `manuell`                 | `manuell_Security` |

---

> **Note**  
> Translating night and off also results in the app checking if a mode name starts with the translated mode name equivalent, to turn off and prevent motion.

With this approach you can keep your translations clean, maintain logical consistency across your automations, and extend Lightwand with your own custom modes when needed.
---


## 📈 Configuring Light Behavior

### 🔁 Setting `light_data`
- **`light_data`** contains attributes like brightness, color, and transition. It defines the **specific light settings** for each scenario (e.g., automations, modes, or motion events).

**Example**:
```yaml
      automations:
        light_data:
          brightness: 80
          transition: 3
          color:
            x: 0.5075
            y: 0.4102
```
Lightwand can be used together with the [Adaptive Lighting custom component for Home Assistant](https://github.com/basnijholt/adaptive-lighting) to automatically adjust the minimum and maximum brightness in modes, in addition to turning lights on and off. However, Lightwand does not know what brightness level Adaptive Lighting will set, so when combined with motion the light may dim instead of brighten when motion is detected.

- To use **Adaptive Lighting** in automations, motionlights, or modes, define `state: adaptive`. [Check out the wiki for Adaptive Lighting setup](https://github.com/Pythm/ad-Lightwand/wiki/Combining-Lightwand-with-Adaptive-Lighting-Custom-Component).

---

### 🔁 Setting `state`
- **`state`**: Controls on/off behavior for lights.
  - **Default behavior** depends on the **mode** being used:
    - In **`normal` and user defined modes**, the default is **`turn_on`**.
    - In **`away`**, **`night`**, or **`off`** modes, the default is **`turn_off`** (as described in the "Mode Change Events" section).
  - If no `state` is explicitly defined, the mode's default behavior applies.

- **`turn_off`**: Turns the light off at the given time or in the specified mode.
- **`adjust`**: Does not turn the light on or off, but adjusts it to the `light_data` defined for the current state.
- **`pass`**: Lightwand will apply the `light_data` as a "turn on" command, but **will not send a new command** if the light is already on. Lights running a program (e.g., "sunrise" effect in Philips Hue) will **restart the program** every time a new command is sent.
- **`manual`**: Lightwand will **not interact** with the light in this mode.
- **`lux_controlled`**: The light will be on if **lux levels are below the defined `lux_constraint`**.

**Example**:
```yaml
      light_modes:
        - mode: decor
          state: lux_controlled
      lux_constraint: 5000
```

> [!TIP]
> To enable lux control in a mode, include `state: lux_controlled`.

---

### 📈 Automations
Automations are configured by defining an array of time-based rules. These can be **clock-based**, **solar-based** (using sunrise/sunset times), or a combination of both.  

**Key Rules for Automations**:
- When `lightmode` is set to `normal`, Lightwand checks for defined `light_data` and `state` in `automations`.
- Automations can also be configured under `motionlights` and `light_modes`.  
- **For a light to turn on** when the selected lightmode is an automation, **both `lux_constraint` and `conditions` must pass**.  

#### Defining Times  
- Automations use `time` to define when changes occur.  
- Use `orLater` to combine solar and clock-based times for seasonal accuracy.  
- If `orLater` is used, all subsequent times are shifted by the same `timedelta` unless `fixed: True` is defined.  
- `fixed: True` locks the time from being moved or deleted.  

**Example**:  
```yaml
      automations:
        - time: '08:00:00'
          orLater: 'sunrise + 00:15:00'
        - time: '20:00:00'
          fixed: True
          state: turn_off
```

> [!TIP]  
> Use the commented-out logging in the Python file to debug time changes. Search for:  
> `Check if your times are acting as planned. Uncomment line below to get logging on time change`.  

> [!NOTE]  
> If `time: '00:00:00'` is not defined, a default `turn_off` state will be applied at midnight if other times are configured in automations or motionlights.  

> [!NOTE]  
> If only `time` is provided in automations, the light will turn on if conditions are met. However, if no `light_data` is defined, nothing will be adjusted.  

---

### 🌫️ Motion Behavior  
Configure `motionlights` to define how lights react to motion detection.  

**Minimum Configuration**:  
```yaml
  motion_sensors:
    - sensor: binary_sensor.yourMotionSensor
  Lights:
    - lights:
      - light.kitchen
      motionlights:
```

**Key Rules for Motion Behavior**:  
- For the light to turn on, **both `lux_constraint` and `conditions` must pass** if the lightmode is `normal`.  
- If another mode is active, behavior depends on how that mode is configured.  

**Example with `motionlights` and `light_data`**:  
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
> When motion is active, the light will **not dim down**. Motion detection will also **not reduce brightness** if another mode sets brightness higher.  

> [!NOTE]  
> If **media players are on** or **night/off mode** is active, motion detection is **deactivated**.  

---

### 🔄 Configuring Light Modes  
Light modes are defined under `light_modes` as an array. They can include:  
- `automations` for time-based settings  
- `light_data` for specific attributes  
- `state` (e.g., `lux_controlled`, `turn_off`, or `manual`)  

**Example with Multiple Configurations**:  
```yaml
      light_modes:
        - mode: morning
          light_data:
            brightness: 220
            transition: 3
            color_temp: 427
        - mode: decor
          offset: -20 # Optional offset from brightness defined in normal mode
        - mode: tv
          state: turn_off
        - mode: away
          state: lux_controlled
        - mode: nightKid
          state: manual
        - mode: night
          automations:
            - time: '00:00:00'
            - time: '03:00:00'
              state: turn_off
            - time: '23:00:00'
        - mode: low_with_Automation
          automations:
            - light_data:
                brightness: 20
```

> [!TIP]  
> Use `noMotion: True` in a mode to **prevent motion detection** from altering the light.  

---

### 🛠️ Additional Options and Configurations  

There are several options to fine-tune how lights behave:  

#### **Dimming with `dimrate`**  
Use `dimrate` in automations to control how quickly brightness changes (e.g., `dimrate: 2` = 1 brightness unit per 2 minutes). The light will **dim from the last timed brightness** until the target brightness is met.  

#### **Adjust Brightness with `offset`**  
Use `offset` to dynamically increase or decrease brightness for dimmable lights when `motionlights` or `light_modes` are active. The offset is applied to the brightness defined in `light_data`.  

**Example**:  
```yaml
  motionlights:
    offset: 35
```

> [!NOTE]  
> If the current mode is **not configured with automations**, `motionlights` with `offset` will **not activate**.  


#### **Room-Level Options**  
- `exclude_from_custom`: Excludes the room from `custom` and `wash` modes (useful for outdoor or kid’s rooms).  
- `prevent_off_to_normal`: Keeps lights `off` if a new mode is `normal`.  
- `prevent_night_to_morning`: Keeps lights in `night` mode if a new mode is `morning` or `normal`.  
- `dim_while_motion`: Enables dimming of lights when motion is detected.

> [!TIP]  
> If preventing normal mode use `reset` mode or set lightmode for spesific room to get back to normal.

#### **Light-Level Options**  
- `night_motion`: Enables motion detection during `night` mode.  

#### **Holiday Lights Control**
Set an `input_boolean` (or similar) as `enable_light_control` for switches/lights you only use for special occations like christmas or during winter time.  
The app will control the light/switch only if this switch is ON.  
If the switch is OFF, the app will leave the light untouched, allowing other tasks to use it.

> **NOTE**  
> The setting is read only at startup, so you must restart AppDaemon (or the app) to enable/disable control.

**Example**:  
```yaml
  # Configure in room
  options:
    - exclude_from_custom
    - dim_while_motion
    - prevent_off_to_normal
    - prevent_night_to_morning
  MQTTLights:
    - lights:
      - zigbee2mqtt/ENTRE_Switch
      # Configure in light
      options:
        - night_motion
      enable_light_control: input_boolean.xmas_light_control
```

> [!TIP]  
> Use one `input_boolean` switch to disable holiday lights and hide related modes in the Home Assistant frontend.  

---

## 🌦️ Sensors & Constraints  

### 🌤️ Weather Sensors  

#### 📌 Notes  
- **Weather Data**: Use the [ad-Weather](https://github.com/Pythm/ad-Weather) app for **optimal integration**. It consolidates all your weather sensors into a single app and publishes events for other apps to consume.  
  > ⚠️ **Important**: If you configure weather sensors **directly in Lightwand**, they will **take precedence** over the `ad-Weather` app.  

You can define **two outdoor lux sensors**. The second sensor can be defined with a suffix of `_2`. The app will use the **higher lux value** or the **last updated value** if the other sensor hasn't updated in the last 15 minutes. Use `OutLux_sensor` for Home Assistant sensors and `OutLuxMQTT` for MQTT sensors.

- Only **one room lux sensor** can be defined, and it can be either an MQTT or Home Assistant entity.  
- **Rain sensors** currently only support Home Assistant entities.  

**Example**:  
```yaml
  OutLux_sensor: sensor.lux_sensor
  OutLuxMQTT_2: zigbee2mqtt/OutdoorHueLux
  RoomLux_sensor: sensor.lux_sensor
  RoomLuxMQTT: zwave/KITCHEN_sensor/sensor_multilevel/endpoint_0/Illuminance
  rain_sensor: sensor.netatmo_rain
```

---

### 📡 Motion Sensors and Presence Trackers  

You can define the **time delay** (in seconds) after motion detection before the lights return to normal. You can also define **constraints** for each sensor using an python `if` statement checked againts the ast_evaluator.py. These constraints must be `true` for motion to activate. 

**Example**:  
```yaml
  motion_sensors:
    - sensor: binary_sensor.yourMotionSensor
  MQTT_motion_sensors:
    - sensor: zigbee2mqtt/KITCHEN_sensor
      delay: 60
      constraints: "self.now_is_between('06:50:00', '23:00:00') and self.get_tracker_state('person.wife') == 'home' or self.get_state('switch.kitch_espresso') == 'on' "
```

> [!TIP]  
> Tracker will set mode as `away` when not home, but there are **no restrictions** on calling new modes or switching to `normal` when in `away` mode.  

For **presence tracking**, define the trackers in the `presence` section. When a tracker is `home`, the app will switch to `presence` mode.  If `presence` is not defined in `light_modes` or constraints are not met then the room will switch to `normal` mode. If all defined trackers are **not home**, the room will switch to `away` mode.  

**Example**:  
```yaml
  presence:
    - sensor: person.wife
      constraints: "self.now_is_between('06:30:00', '23:00:00') "
```

> [!NOTE]  
> Trackers will **not change modes** when returning home unless the current mode is `normal` or `away`.  

---

### 🛏️ Bed Sensors   
- The `bed_sensors` feature keeps the light in **night** mode until the bed is exited.  
  You can now define a constraint for the bed sensor that, when it is not true, will prevent the bed from being considered *occupied*.

**Example**:  
```yaml
  bed_sensors: 
    - sensor: binary_sensor.bed_occupied
      delay: 5
```

---

### 📺 Media Players  

Sorted by **priority** if more than one media player is defined in a room. You can use any entity with an `on/off` state (e.g., sensors, switches).  

- Define the **mode name** for each media player.  
- Define `light_data` in `light_modes` for the corresponding mode.  

**Behavior**:  
- The "media mode" will **override** normal lighting behavior when motion is detected, during `morning`, `normal`, or `night*` modes.

> [!TIP]  
> Define a `delay` for media players that report `on` states shortly after being turned off. This prevents lights from dimming up and down repeatedly.  

**Example**:  
```yaml
  mediaplayers:
    - mediaplayer: binary_sensor.yourXboxGamerTag
      mode: pc
    - mediaplayer: media_player.tv
      mode: tv
      delay: 30
```

---

## 🛠️ Advanced Configurations  

### 📌 Conditions and Constraints  

You can use **lux sensors** to control or constrain lights. Optionally, you can define `IF` statements that must be met for the light to turn on during `normal`, `morning`, or `motion` modes, or when automations are triggered. The app inherits the **AppDaemon API** as `self.ADapi`.  

> **Example Use Case**:  
> I use this on some lights in my living room and kitchen to detect if my wife is **not home**, without setting the room to `away` mode.  

To define custom conditions, create a `listen_sensors` list for the sensors you use in your statements. The app will update the light when any condition changes.  

**Example**:  
```yaml
  listen_sensors:
    - person.wife
  # Some light data...
  conditions:
    - "self.ADapi.get_tracker_state('person.wife') == 'home'"
  keep_on_conditions:
    - "self.ADapi.get_tracker_state('person.wife') == 'home'"
  lux_constraint: 12000
  room_lux_constraint: 100
```

> [!NOTE]  
> - The `conditions` block keeps the light **off** if all conditions are `true`.  
> - The `keep_on_conditions` block keeps the light **on** if **any** condition is `true`.  

---

### 🔄 Manual Changes to Lights  

If you've configured all your lights to your liking, the normal automation should suffice for day-to-day use. However, there are times when you may need to make **manual adjustments**, such as for special events or when the automation doesn't match your needs.  

> [!NOTE]  
> Manual changes will **persist** until:  
> - The **motion delay** ends.  
> - **Lux levels** rise above the `lux_constraint`.  
> - A **new mode** is activated.  
> - A **time-based automation** runs.  

> [!WARNING]  
> If you define **multiple lights** in a list, the app will **only listen to the first light** in the list. For example:  
> ```yaml
>   - lights:
>     - light.spot1
>     - light.spot2
> ```  
> The app will **only detect changes to `light.spot1`**. If you turn on `light.spot2` only, the `reset` mode will **not work**.  

> [!TIP]  
> To **reset** to the default automation, call the `reset` mode or `reset + _appName`.  

---

### 🔄 Persistent Storage  
Each lightwand app will write the current light mode on termination to a json file and read it on initialization. Default location for json files is ```pyton {self.AD.config_dir}/persistent/lightwand/ ```. You can overrule this by defining `json_path`.

### 🧱 Namespaces  
Define MQTT/HASS namespaces if not using defaults:  
```yaml
MQTT_namespace: mqtt
HASS_namespace: default
```

### 🔄 Delays & Network Health  
Add delays to avoid network congestion:  
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
---

## 📌 Notes & Tips  
- Use **MQTT Explorer** to find device topics.  
- **Group Zigbee devices** in your controller to reduce network load.  
- **Adaptive Lighting** can be used with `adaptive_switch` and `adaptive_sleep_mode`.  

---

## 📚 Get started
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
  OutLux_sensor_2: sensor.lux_sensor2
  OutLuxMQTT: zigbee2mqtt/OutdoorLux
  OutLuxMQTT_2: zigbee2mqtt/OutdoorLux2
  RoomLux_sensor: sensor.room_lux_sensor
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
---

## 📦 Contributing  
- **Report issues** on [GitHub](https://github.com/Pythm/ad-Lightwand)  
- **Suggest features** via pull requests on the dev branch

---

## 📝 License  
MIT License. See [LICENSE](LICENSE) file for details.  

---  
**Lightwand by [Pythm](https://github.com/Pythm)**  
*Automate your lights with precision and flexibility.*