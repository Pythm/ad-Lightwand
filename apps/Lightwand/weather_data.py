""" Outdoor lux (and rain) for apps that use the Weather app.
    https://github.com/Pythm/ad-Weather

    This file is identical in Lightwand and ClimateCommander (both are installed from HACS,
    which cannot share files between repos). Change it in both repos.

    Lux comes from the app's own outdoor lux sensors if any are configured, otherwise from the
    WEATHER_CHANGE event. With two own sensors the highest fresh value is used, by design.
    If all own sensors have been silent for EVENT_FALLBACK_MINUTES, the event lux is used.
"""

from datetime import timedelta
import json

LUX_STALE_MINUTES = 15
EVENT_FALLBACK_MINUTES = 20
MIN_REACT_MINUTES = 2

class OutdoorWeather:

    def __init__(self,
        api,
        HASS_namespace,
        MQTT_namespace,
        lux_sensor,
        lux_sensor_mqtt,
        lux_sensor_2,
        lux_sensor_2_mqtt,
        on_change,
        room_lux_sensor = None,
        room_lux_sensor_mqtt = None,
        react_blocked = None,
        min_react_minutes = MIN_REACT_MINUTES,
    ):
        """ on_change: called without arguments when lux (or room lux) changed.
            react_blocked: optional callable, True means do not call on_change now.
            min_react_minutes: minimum time between two calls of on_change. """
        self.ADapi = api
        self.mqtt = None
        self.on_change = on_change
        self.react_blocked = react_blocked
        self.min_react_minutes = min_react_minutes

        now = self.ADapi.datetime(aware=True)

        self.out_lux:float = 0.0
        self.out_lux_1:float = 0.0
        self.out_lux_2:float = 0.0
        self.out_lux_1_last_update = now - timedelta(days = 1)
        self.out_lux_2_last_update = now - timedelta(days = 1)
        self.last_react_update = now - timedelta(minutes = min_react_minutes)
        self.room_lux:float = 0.0
        self.rain:float = 0.0

        if lux_sensor is not None:
            self.ADapi.listen_state(self._out_lux_updated, lux_sensor,
                namespace = HASS_namespace
            )
            try:
                self.out_lux = float(self.ADapi.get_state(lux_sensor,
                    namespace = HASS_namespace
                ))
            except (ValueError, TypeError):
                pass
            else:
                self.out_lux_1 = self.out_lux
                self.out_lux_1_last_update = now

        if lux_sensor_mqtt is not None:
            if not self.mqtt:
                self.mqtt = self.ADapi.get_plugin_api("MQTT")

            self.mqtt.mqtt_subscribe(lux_sensor_mqtt)
            self.mqtt.listen_event(self._out_lux_mqtt_event, "MQTT_MESSAGE",
                topic = lux_sensor_mqtt,
                namespace = MQTT_namespace
            )

        if lux_sensor_2 is not None:
            self.ADapi.listen_state(self._out_lux_2_updated, lux_sensor_2,
                namespace = HASS_namespace
            )
            try:
                self.out_lux_2 = float(self.ADapi.get_state(lux_sensor_2,
                    namespace = HASS_namespace
                ))
            except (ValueError, TypeError):
                pass
            else:
                self.out_lux_2_last_update = now

        if lux_sensor_2_mqtt is not None:
            if not self.mqtt:
                self.mqtt = self.ADapi.get_plugin_api("MQTT")

            self.mqtt.mqtt_subscribe(lux_sensor_2_mqtt)
            self.mqtt.listen_event(self._out_lux_2_mqtt_event, "MQTT_MESSAGE",
                topic = lux_sensor_2_mqtt,
                namespace = MQTT_namespace
            )

        if room_lux_sensor is not None:
            self.ADapi.listen_state(self._room_lux_updated, room_lux_sensor,
                namespace = HASS_namespace
            )
            try:
                self.room_lux = float(self.ADapi.get_state(room_lux_sensor,
                    namespace = HASS_namespace
                ))
            except (ValueError, TypeError):
                pass

        if room_lux_sensor_mqtt is not None:
            if not self.mqtt:
                self.mqtt = self.ADapi.get_plugin_api("MQTT")

            self.mqtt.mqtt_subscribe(room_lux_sensor_mqtt)
            self.mqtt.listen_event(self._room_lux_mqtt_event, "MQTT_MESSAGE",
                topic = room_lux_sensor_mqtt,
                namespace = MQTT_namespace
            )

        self.ADapi.listen_event(self.weather_event, 'WEATHER_CHANGE',
            namespace = HASS_namespace
        )

    def weather_event(self, event_name, data, **kwargs) -> None:
        """ Listens for weather change from the weather app.
            https://github.com/Pythm/ad-Weather """

        now = self.ADapi.datetime(aware=True)

        # The Weather app sends None for data it does not have
        rain = data.get('rain')
        self.rain = float(rain) if rain is not None else 0.0
        lux = data.get('lux')
        if lux is not None and not self._own_lux_reporting():
            self.out_lux = float(lux)
        self._reactToChange()

    def _own_lux_reporting(self) -> bool:
        """ True if an own outdoor lux sensor has reported lately. Without own sensors this is
            always False, so the lux from the Weather app is used. """
        limit = timedelta(minutes = EVENT_FALLBACK_MINUTES)
        now = self.ADapi.datetime(aware=True)
        return (
            now - self.out_lux_1_last_update <= limit
            or now - self.out_lux_2_last_update <= limit
        )

    def _out_lux_updated(self, entity, attribute, old, new, kwargs) -> None:
        try:
            value = float(new)
        except (ValueError, TypeError):
            return
        if value != self.out_lux_1:
            self.out_lux_1 = value
            self.out_lux_1_last_update = self.ADapi.datetime(aware=True)
            self._choose_lux()

    def _out_lux_mqtt_event(self, event_name, data, **kwargs) -> None:
        self._handle_mqtt_lux(data, attr='out_lux_1')

    def _out_lux_2_updated(self, entity, attribute, old, new, kwargs) -> None:
        try:
            value = float(new)
        except (ValueError, TypeError):
            return
        if value != self.out_lux_2:
            self.out_lux_2 = value
            self.out_lux_2_last_update = self.ADapi.datetime(aware=True)
            self._choose_lux()

    def _out_lux_2_mqtt_event(self, event_name, data, **kwargs) -> None:
        self._handle_mqtt_lux(data, attr='out_lux_2')

    def _room_lux_updated(self, entity, attribute, old, new, kwargs) -> None:
        try:
            value = float(new)
        except (ValueError, TypeError):
            return
        if value != self.room_lux:
            self.room_lux = value
            self._reactToChange()

    def _room_lux_mqtt_event(self, event_name, data, **kwargs) -> None:
        self._handle_mqtt_lux(data, attr='room_lux')

    def _handle_mqtt_lux(self, data, attr):

        payload = data.get("payload")
        if isinstance(payload, bytes):
            try:
                payload = payload.decode("utf-8")
            except Exception as e:
                self.ADapi.log(f"Failed to decode payload bytes from {attr}: {e}")
                return

        if isinstance(payload, str):
            try:
                payload_json = json.loads(payload)
            except json.JSONDecodeError:
                payload_json = payload
        else:
            payload_json = payload

        try:
            if isinstance(payload_json, dict):
                old_attr = getattr(self, attr)
                match payload_json:
                    case {'illuminance': illuminance} if illuminance is not None and old_attr != float(illuminance):
                        value = float(illuminance) # Zigbee sensor
                    case {'value': value} if old_attr != float(value):
                        value = float(value) # Zwave sensor
                    case _:
                        return
            else:
                value = float(payload_json)
        except Exception as e:
            return

        if value != getattr(self, attr):
            setattr(self, attr, value)
            now = self.ADapi.datetime(aware=True)
            if attr == 'out_lux_1':
                self.out_lux_1_last_update = now
                self._choose_lux()
            elif attr == 'out_lux_2':
                self.out_lux_2_last_update = now
                self._choose_lux()
            elif attr == 'room_lux':
                self.room_lux = value
                self._reactToChange()

    def _choose_lux(self):
        """ Uses the HIGHEST fresh value of the two outdoor lux sensors, by design.
            Calculated from both stored values, so the result follows the sensor
            in both directions. """
        now = self.ADapi.datetime(aware=True)
        fresh = [
            value
            for value, last in (
                (self.out_lux_1, self.out_lux_1_last_update),
                (self.out_lux_2, self.out_lux_2_last_update),
            )
            if now - last <= timedelta(minutes=LUX_STALE_MINUTES)
        ]
        if fresh:
            self.out_lux = max(fresh)
            self._reactToChange()

    def _reactToChange(self) -> None:
        if self.react_blocked is not None and self.react_blocked():
            return

        now = self.ADapi.datetime(aware=True)
        if now - self.last_react_update >= timedelta(minutes = self.min_react_minutes):
            self.on_change()
            self.last_react_update = now