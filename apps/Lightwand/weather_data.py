from datetime import timedelta

LUX_STALE_MINUTES   = 15

class LightwandWeather:

    def __init__(self,
        api,
        HASS_namespace,
        MQTT_namespace,
        lux_sensor,
        lux_sensor_mqtt,
        lux_sensor_2,
        lux_sensor_2_mqtt,
        room_lux_sensor,
        room_lux_sensor_mqtt,
    ):
        self.ADapi = api
        self.mqtt = None

        now = self.ADapi.datetime(aware=True)

        self.out_lux:float = 0.0
        self.out_lux_1:float = 0.0
        self.out_lux_2:float = 0.0
        self.out_lux_1_last_update = now - timedelta(minutes = LUX_STALE_MINUTES)
        self.out_lux_2_last_update = now - timedelta(minutes = LUX_STALE_MINUTES)

        self.room_lux:float = 0.0
        self.rain:float = 0.0

            # Setup Outdoor Lux sensor
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

        self.rain = float(data['rain'])
        if (
            now - self.out_lux_1_last_update > timedelta(minutes = LUX_STALE_MINUTES) and
            now - self.out_lux_2_last_update > timedelta(minutes = LUX_STALE_MINUTES)
        ):
            self.out_lux = float(data['lux'])

    def _out_lux_updated(self, entity, attribute, old, new, kwargs) -> None:
        try:
            value = float(new)
        except (ValueError, TypeError):
            return
        if value != self.out_lux_1:
            self._choose_lux(
                new=value,
                other=self.out_lux_2,
                other_last=self.out_lux_2_last_update,
            )
            self.out_lux_1 = value
            self.out_lux_1_last_update = self.ADapi.datetime(aware=True)

    def _out_lux_mqtt_event(self, event_name, data, **kwargs) -> None:
        self._handle_mqtt_lux(data, attr='out_lux_1')

    def _out_lux_2_updated(self, entity, attribute, old, new, kwargs) -> None:
        try:
            value = float(new)
        except (ValueError, TypeError):
            return
        if value != self.out_lux_2:
            self._choose_lux(
                new=value,
                other=self.out_lux_1,
                other_last=self.out_lux_1_last_update,
            )
            self.out_lux_2 = value
            self.out_lux_2_last_update = self.ADapi.datetime(aware=True)

    def _out_lux_2_mqtt_event(self, event_name, data, **kwargs) -> None:
        self._handle_mqtt_lux(data, attr='out_lux_2')

    def _room_lux_updated(self, entity, attribute, old, new, kwargs) -> None:
        try:
            value = float(new)
        except (ValueError, TypeError):
            return
        if value != self.room_lux:
            self.room_lux = value

    def _room_lux_mqtt_event(self, event_name, data, **kwargs) -> None:
        self._handle_mqtt_lux(data, attr='room_lux')

    def _handle_mqtt_lux(self, data, attr):
        payload = data.get('payload')
        if isinstance(payload, bytes):
            try:
                payload_json = payload.decode()
            except Exception:
                return

        try:
            payload_json = json.loads(payload)
        except Exception:
            payload_json = payload

        try:
            if isinstance(payload_json, dict):
                old_attr = getattr(self, attr)
                match payload_json:
                    case {'illuminance': illuminance} if old_attr != float(illuminance):
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
                self._choose_lux(
                    new=value,
                    other=self.out_lux_2,
                    other_last=self.out_lux_2_last_update,
                )
                self.out_lux_1_last_update = now
            elif attr == 'out_lux_2':
                self._choose_lux(
                    new=value,
                    other=self.out_lux_1,
                    other_last=self.out_lux_1_last_update,
                )
                self.out_lux_2_last_update = now
            elif attr == 'room_lux':
                self.room_lux = value

    def _choose_lux(self, new, other, other_last):
        now = self.ADapi.datetime(aware=True)
        if now - other_last > timedelta(minutes=LUX_STALE_MINUTES) or new >= other:
            self.out_lux = new
