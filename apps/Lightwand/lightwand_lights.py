from __future__ import annotations

from datetime import timedelta
import json
import bisect
import math
import copy

from typing import List, Tuple, Optional, Set, Union

from translations_lightmodes import translations
from lightwand_config import LightMode, Automation, LightProperties
from lightwand_utils import cancel_timer_handler

from ast_evaluator import safe_eval

class Light:
    """ Parent class for lights. """

    def __init__(self,
                 api,
                 lights: List[str],
                 light_modes: Optional[List[LightMode]],
                 automations: Optional[List[Automation]],
                 motionlight: Optional[Union[List[Automation], LightProperties]],
                 lux_constraint: Optional[float],
                 room_lux_constraint: Optional[float],
                 conditions: List[str],
                 keep_on_conditions: List[str],
                 HASS_namespace: str,
                 night_motion: str,
                 dim_while_motion: str,
                 random_turn_on_delay: int,
                 adaptive_switch: Optional[str],
                 adaptive_sleep_mode: Optional[str],
                 weather):

        self.ADapi = api
        self.HASS_namespace = HASS_namespace

        self.lights = lights
        self.light_modes = light_modes or []
        self.light_modes_by_name: dict[str, LightMode] = {
            lm.mode: lm for lm in self.light_modes
        }

        self.automations = automations or None
        self.motionlight = motionlight or None
        self.lux_constraint = lux_constraint
        self.room_lux_constraint = room_lux_constraint
        self.conditions = conditions
        self.keep_on_conditions = keep_on_conditions
        self.night_motion = night_motion
        self.dim_while_motion = dim_while_motion
        self.random_turn_on_delay = random_turn_on_delay
        self.adaptive_switch = adaptive_switch
        self.adaptive_sleep_mode = adaptive_sleep_mode
        self.weather = weather

        self.has_adaptive_state:bool = False
        self.lightmode:str = translations.normal
        self.dimHandler = None
        self.motion:bool = False
        self.is_on:bool = None
        self.is_turned_on:bool = None
        self.brightness:int = 0
        self.current_light_data:dict = {}

        string:str = self.lights[0]
        if string.startswith('light.'):
            self.ADapi.listen_state(self.BrightnessUpdated, self.lights[0],
                attribute = 'brightness',
                namespace = HASS_namespace
            )
            try:
                self.brightness = int(self.ADapi.get_state(self.lights[0],
                    attribute = 'brightness',
                    namespace = HASS_namespace)
                )
            except TypeError:
                self.brightness = 0

            self.ADapi.listen_state(self.update_isOn_lights, self.lights[0],
                namespace = HASS_namespace
            )
            self.is_on = self.ADapi.get_state(self.lights[0]) == 'on'
        elif string.startswith('switch.'):
            self.ADapi.listen_state(self.update_isOn_lights, self.lights[0],
                namespace = HASS_namespace
            )
            self.is_on = self.ADapi.get_state(self.lights[0]) == 'on'

        # ----- Helpers to check if conditions to turn on/off light has changed
        self.wereMotion:bool = False
        self.current_OnCondition:bool = None
        self.current_keep_on_Condition:bool = None
        self.current_LuxCondition:bool = None

        # ----- Main automations ------------------------------------------------
        if self.automations:
            self.automations_original: List[Automation] = []
            self.automations_original = copy.deepcopy(self.automations)
            self.checkTimesinAutomations(self.automations)

            for automation in self.automations:
                if automation.state == 'adaptive':
                    self.has_adaptive_state = True

        # ----- Motion triggered automations ------------------------------------
        if self.motionlight:
            if isinstance(self.motionlight, List):
                self.motions_original: List[Automation] = []
                self.motions_original = copy.deepcopy(self.motionlight)
                self.checkTimesinAutomations(self.motionlight)

                for automation in self.motionlight:
                    if automation.state == 'adaptive':
                        self.has_adaptive_state = True

            elif isinstance(self.motionlight, LightProperties):
                if self.motionlight.state == 'adaptive':
                    self.has_adaptive_state = True

        # ----- Light mode automations ------------------------------------------
        for mode in self.light_modes:
            if mode.automations:
                for a in mode.automations:
                    if a.state == 'adaptive':
                        self.has_adaptive_state = True
                self.checkTimesinAutomations(mode.automations)

            elif mode.light_properties:
                if mode.light_properties.state == 'adaptive':
                    self.has_adaptive_state = True

        # ----- Create default fallback automations------------------------------
        if self.motionlight and not self.automations:
            self.automations = [Automation(time='00:00:00', state='turn_off')]
            self.automations_original = copy.deepcopy(self.automations)
        elif not self.automations:
            self.automations = [Automation(time='00:00:00', state='none')]
            self.automations_original = copy.deepcopy(self.automations)

        self.ADapi.run_daily(self.rundaily_Automation_Adjustments, '00:01:00')

        if not self.has_adaptive_state:
            self.adaptive_switch = None

        """ End initial setup for lights """

    def rundaily_Automation_Adjustments(self, kwargs) -> None:
        """ Adjusts solar based times in automations daily. """
        if self.automations:
            self.automations = copy.deepcopy(self.automations_original)
            self.checkTimesinAutomations(self.automations)

        if self.motionlight:
            if isinstance(self.motionlight, List):
                self.motionlight = copy.deepcopy(self.motions_original)
                self.checkTimesinAutomations(self.motionlight)

        for mode in self.light_modes:
            if mode.automations:
                mode.automations = copy.deepcopy(mode.original_automations)
                self.checkTimesinAutomations(mode.automations)

    def checkTimesinAutomations(self, automations: List[Automation]) -> None:
        """ Find and adjust times in automations based on clock and sunrise/sunset times.
            Set up some default behaviour. """

        automations_to_delete: list[int] = []
        time_to_add: timedelta = timedelta(minutes=0)
        calculate_from_sunrise: bool = False
        calculate_from_sunset: bool = False
        now_time_notAware = self.ADapi.time()

        if not automations:
            return

        # ----- Check if a starttime at midnight is defined
        test_time = self.ADapi.parse_time('00:00:00')
        if test_time != self.ADapi.parse_time(automations[0].time):
            # Insert a dummy turn off automation at midnight
            automations.insert(
                0,
                Automation(time='00:00:00', state='turn_off')
            )

        # ----- Corrects times in automation
        for num, automation in enumerate(automations):
            # ---- Handle `orLater` -------------------------------------------------
            if automation.orLater:
                or_later_dt = self.ADapi.parse_datetime(automation.orLater, today=True)
                time_dt = self.ADapi.parse_datetime(automation.time, today=True)

                if automation.orLater.startswith('sunrise') or automation.time.startswith('sunrise'):
                    calculate_from_sunrise = True
                    calculate_from_sunset = False
                elif automation.orLater.startswith('sunset') or automation.time.startswith('sunset'):
                    calculate_from_sunrise = False
                    calculate_from_sunset = True

                if self.ADapi.parse_time(automation.time) < self.ADapi.parse_time(automation.orLater):
                    time_to_add = or_later_dt - time_dt
                    """ Check if your times are acting as planned. Uncomment line below to get logging on time change """
                    #self.ADapi.log(f"Time defined with 'orLater': {self.ADapi.parse_time(automation['orLater'])} is later than time: {self.ADapi.parse_time(automation['time'])}")
                    automation.time = automation.orLater
                else:
                    time_to_add = time_dt - or_later_dt

                automation.orLater = None

            # ---- Handle time offsets ------------------------------------------------
            elif time_to_add > timedelta(minutes=0):
                change_time = False
                if automation.fixed:
                    time_to_add = timedelta(minutes=0)
                elif automation.time.startswith('sunrise'):
                    change_time = calculate_from_sunrise
                elif automation.time.startswith('sunset'):
                    if calculate_from_sunrise:
                        calculate_from_sunrise = False
                        time_to_add = timedelta(minutes=0)
                    elif calculate_from_sunset:
                        change_time = True
                else:
                    change_time = True

                if change_time:
                    new_dt = self.ADapi.parse_datetime(automation.time) + time_to_add
                    """ Check if your times are acting as planned. Uncomment line below to get logging on time change """
                    #self.ADapi.log(f"Added {timeToAdd} to {automation['time']}. Light will change at {str(newtime.time())}")
                    automation.time = str(new_dt.time())

            # ---- Remove out of order automations -------------------------------------
            if test_time <= self.ADapi.parse_time(automation.time):
                test_time = self.ADapi.parse_time(automation.time)
            elif test_time > self.ADapi.parse_time(automation.time):
                if not automation.fixed:
                    """ Check if your times are acting as planned. Uncomment line below to get logging on time change """
                    #self.ADapi.log(f"Deletes automation: {automations[num]} based on {test_time} > {self.ADapi.parse_time(automation['time'])}")
                    automations_to_delete.append(num)

            # ---- Prepare data for later scheduling ----------------------------------
            if self.ADapi.parse_time(automation.time) > now_time_notAware:
                self.ADapi.run_once(self._run_daily_lights, automation.time, light_properties = automation.light_properties)
                self.ADapi.log(f"{self.lights[0]} run daily at : {automation.time}", level = "DEBUG") ###

        # ----- Remove automations that are no longer valid
        for idx in reversed(automations_to_delete):
            del automations[idx]

    def _run_daily_lights(self, **kwargs) -> None:
        self.ADapi.log(f"{self.lights[0]} run daily excecuted with properties: {kwargs['light_properties']}", level = "DEBUG") ###
        self.current_light_data = {}
        if self.motion:
            if (
                self.dim_while_motion and self.is_on and
                (not self.lightmode.startswith(translations.night) or self.night_motion) and
                self.lightmode not in (translations.off, translations.custom)
            ):
                self.setMotion(lightmode=self.lightmode)
            return

        light_properties: LightProperties = kwargs['light_properties']
        if light_properties.state == 'turn_off':
            self.turn_off_lights()
            return
        self.current_OnCondition = None
        self.current_keep_on_Condition = None
        self.current_LuxCondition = None
        self.setLightMode()

    def find_time(self, automations: List[Automation]) -> int:
        """ Return the index of the *last* automation whose ``time`` is 
        **less-than or equal to** the current time. """

        now_time_notAware = self.ADapi.time()

        times: List[datetime] = [
            self.ADapi.parse_time(automation.time) for automation in automations
        ]

        idx = bisect.bisect_right(times, now_time_notAware) - 1

        return max(0, idx)

    def checkConditions(self, conditions = None) -> bool:
        """ Checks conditions before turning on automated light. """

        if self.conditions is None:
            return True

        for cond in self.conditions:
            try:
                ok = safe_eval(cond, {"self": self})
            except Exception as exc:
                self.ADapi.log(
                    f"Constraint eval error for {self.lights[0]}: {exc}",
                    level="INFO"
                )
                return False

            if not ok:
                return False
        return True

    def checkLuxConstraints(self) -> bool:
        """Return True if automated lighting is allowed."""

        w   = self.weather
        lc  = self.lux_constraint
        rlc = self.room_lux_constraint

        if lc is not None:
            thresh = lc * 1.5 if w.rain > 1 else lc
            if w.out_lux >= thresh:
                return False

        if rlc is not None and w.room_lux >= rlc:
            return False

        return True

    def setLightMode(self, lightmode: str = 'none') -> None:
        """ Main routine that decides what to do with the light(s) depending on the
        currently selected *mode* and on the conditions that are enabled """

        new_OnCondition = self.checkConditions(conditions = self.conditions) if self.conditions is not None else True
        new_keep_on_Condition = self.checkConditions(conditions = self.keep_on_conditions) if self.keep_on_conditions is not None else False
        new_LuxCondition = self.checkLuxConstraints()

        if lightmode == translations.reset:
            self.current_light_data = {}
            self.is_turned_on = None
        elif (
            (lightmode == self.lightmode or lightmode == 'none')
            and self.current_OnCondition == new_OnCondition
            and self.current_keep_on_Condition == new_keep_on_Condition
            and self.current_LuxCondition == new_LuxCondition
        ):
            if self.motionlight:
                if not self.wereMotion:
                    return
                elif not self.motion:
                    self.wereMotion = False
            else:
                return
        elif self.motionlight and not self.motion:
            self.wereMotion = False
        self.current_OnCondition = new_OnCondition
        self.current_keep_on_Condition = new_keep_on_Condition
        self.current_LuxCondition = new_LuxCondition

        if lightmode == 'none':
            lightmode = self.lightmode

        if lightmode != self.lightmode:
            self.current_light_data = {}
            self.is_turned_on = None
            cancel_timer_handler(ADapi = self.ADapi, handler = self.dimHandler)
            self.dimHandler = None

            if (
                self.adaptive_sleep_mode is not None and
                not lightmode.startswith(translations.night)
            ):
                self.ADapi.turn_off(self.adaptive_sleep_mode)

        if lightmode == translations.morning:
            # Morning mode is only valid when both the on condition and the
            # lux condition are true.
            if not self.current_OnCondition or not self.current_LuxCondition:
                lightmode = translations.normal

        elif lightmode == translations.custom:
            # Custom mode turns off all automation and keeps the light as it
            # currently is.
            if self.has_adaptive_state:
                self.setAdaptiveLightingOff()
            self.lightmode = lightmode
            return

        if lightmode not in (translations.normal, translations.reset):
            mode = self.light_modes_by_name.get(lightmode)
            if mode is not None:
                self.lightmode = lightmode
                if mode.automations:
                    light_properties, mode_brightness_compare = self.getLightAutomationData(
                        automations=mode.automations
                    )
                elif mode.light_properties:
                    light_properties: LightProperties = mode.light_properties

                if 'lux_controlled' in light_properties.state and not self.current_LuxCondition:
                    self.turn_off_lights()
                    return
                
                if light_properties.offset != 0:
                    self.setLightAutomation(automations=self.automations, light_properties=light_properties)
                else:
                    self.setLightAutomation(automations=mode.automations, light_properties=light_properties)
                return

        if lightmode in (translations.away, translations.off):
            self.lightmode = lightmode
            self.turn_off_lights()
            return

        if lightmode.startswith(translations.night):
            self.lightmode = lightmode
            if self.adaptive_sleep_mode is not None:
                self.ADapi.turn_on(self.adaptive_sleep_mode)
            else:
                self.turn_off_lights()
            return

        if lightmode in (translations.fire, translations.wash):
            self.lightmode = lightmode
            self.turn_on_lights_at_max()
            return

        self.lightmode = translations.normal
        if (
            (self.current_OnCondition and self.current_LuxCondition)
            or self.current_keep_on_Condition
        ):
            self.setLightAutomation(automations=self.automations)
        else:
            self.turn_off_lights()

    def setMotion(self, lightmode: str = 'none') -> None:
        """ Sets motion lights when motion is detected. """

        if lightmode == 'none':
            lightmode = self.lightmode
        elif lightmode == translations.reset:
            self.current_light_data = {}
            lightmode = translations.normal
            self.wereMotion = False

        light_properties: Optional[LightProperties] = None

        self.motion = True
        self.current_OnCondition = self.checkConditions(conditions = self.conditions) if self.conditions is not None else True
        new_LuxCondition = self.checkLuxConstraints()

        if self.current_LuxCondition is not True and new_LuxCondition is True:
            self.wereMotion = False

        if self.current_OnCondition is not True or new_LuxCondition is not True:
            if self.dim_while_motion:
                if self.lightmode != lightmode:
                    self.ADapi.log(f"New light mode {lightmode} when conditions not met during motion & dim while motion") ###
                    self.current_light_data = {}
                    self.is_turned_on = None
                    self.lightmode = lightmode
                self.turn_off_lights()
            return

        if (
            not self.wereMotion
            or self.dim_while_motion
            or self.lightmode != lightmode
        ):
            motion_brightness_compare:int = 0
            if isinstance(self.motionlight, List):
                light_properties, motion_brightness_compare = self.getLightAutomationData(
                    automations=self.motionlight
                )

            elif isinstance(self.motionlight, LightProperties):
                light_properties = self.motionlight
                motion_brightness_compare = light_properties.resolve_brightness_to_255()

            if motion_brightness_compare == 0:
                motion_brightness_compare = self.current_light_data.get('brightness', self.brightness) 
                if not self.wereMotion:
                    motion_brightness_compare += light_properties.offset

        else: # No change since last motion
            return

        if lightmode not in (translations.normal, translations.reset):
            mode = self.light_modes_by_name.get(lightmode)
            if mode is not None:
                if mode.automations:
                    light_properties_for_mode, mode_brightness_compare = self.getLightAutomationData(
                        automations=mode.automations
                    )
                else:
                    light_properties_for_mode = mode.light_properties
                    mode_brightness_compare = light_properties_for_mode.resolve_brightness_to_255()
                
                if mode_brightness_compare == 0 and light_properties_for_mode.offset > 0:
                    automation_light_properties, automation_brightness_compare = self.getLightAutomationData(
                        automations=self.automations
                    )
                    mode_brightness_compare = automation_brightness_compare + light_properties_for_mode.offset

                if mode.noMotion:
                    self.motion = False
                    if self.lightmode != lightmode:
                        self.setLightMode(lightmode=lightmode)
                    return

                if light_properties_for_mode.state == 'adaptive' and self.brightness != 0 and self.lightmode == lightmode:
                    mode_brightness_compare = self.brightness

                else:
                    light_properties = light_properties_for_mode

                if light_properties.state in ('manual', 'pass'):
                    if self.lightmode != lightmode:
                        self.setLightMode(lightmode=lightmode)
                    return

                if motion_brightness_compare < mode_brightness_compare:
                    if self.lightmode != lightmode:
                        self.setLightMode(lightmode=lightmode)
                    return

            if lightmode in (translations.fire, translations.wash):
                self.lightmode = lightmode
                self.turn_on_lights_at_max()
                return

        self.lightmode = lightmode
        self.wereMotion = True

        if light_properties is None:
            return

        if light_properties.state in ('turn_on', 'adjust', 'none', 'adaptive'):
            if isinstance(self.motionlight, List):
                self.setLightAutomation(automations=self.motionlight, light_properties=light_properties)
            elif isinstance(self.motionlight, LightProperties):
                self.setLightAutomation(light_properties=light_properties)

        elif light_properties.state == 'turn_off':
            self.turn_off_lights()

    def setLightAutomation(self, automations: List[Automation] = None, light_properties: LightProperties = None) -> None:
        """ Finds the appropriate light_properties and adjusts lights """

        current_state = 'none'
        target_num = None
        target_light_data = None

        found_light_data = False
        if automations is not None:
            try:
                target_num = self.find_time(automations = automations)
            except TypeError:
                pass
            else:
                if light_properties is None and hasattr(automations[target_num], 'light_properties'):
                    light_properties = automations[target_num].light_properties
                    current_state = automations[target_num].state
                if light_properties.light_data is not None:
                    target_light_data = light_properties.light_data
                    found_light_data = True

        if not found_light_data:
            try:
                target_num = self.find_time(automations = self.automations)
            except TypeError:
                pass
            else:
                if hasattr(self.automations[target_num].light_properties, 'light_data'):
                    automations = self.automations
                    if light_properties is None:
                        light_properties = automations[target_num].light_properties
                    if light_properties.light_data is None:
                        if automations[target_num].light_properties.light_data is not None:
                            target_light_data = automations[target_num].light_properties.light_data

        if light_properties is not None:
            if current_state == 'none' and light_properties.state is not None:
                if light_properties.state != 'none':
                    current_state = light_properties.state
            if target_light_data is None and light_properties.light_data is not None:
                target_light_data = light_properties.light_data

        if (current_state == 'pass' and self.is_on) or current_state == 'manual':
            if self.has_adaptive_state:
                self.setAdaptiveLightingOff()
            return
        if current_state == 'turn_off':
            if self.has_adaptive_state:
                self.setAdaptiveLightingOff()
            self.turn_off_lights()
            return

        if (
            (current_state == 'adjust' and self.is_on)
            or current_state != 'adjust'
        ):

            if 'adaptive' in current_state:
                self.turn_on_lights()
                self.setAdaptiveLightingOn()

                base_kwargs = {
                    'entity_id': self.adaptive_switch,
                    'namespace': self.HASS_namespace,
                }
                if not (light_properties.max_brightness_pct or light_properties.min_brightness_pct):
                    base_kwargs['use_defaults'] = 'configuration'
                else:
                    base_kwargs.update(light_properties.brightness_kwargs())

                self.ADapi.call_service(
                    'adaptive_lighting/change_switch_settings',
                    **base_kwargs
                )
                return

            elif self.has_adaptive_state:
                self.setAdaptiveLightingOff()

            if target_light_data is not None:
                target_brightness = light_properties.brightness
                if target_brightness is None:
                    target_brightness = target_light_data.get('brightness', 'value')

                if automations[target_num].dimrate is not None:
                    stoptime = automations[target_num + 1].time if target_num + 1 < len(automations) else '23:59:59'
                    if self.ADapi.now_is_between(
                        automations[target_num].time, stoptime
                    ):
                        target_brightness = (
                            self.findBrightnessWhenDimRate(automation=automations, target_num=target_num) + light_properties.offset
                        )

                light_properties_copy = copy.deepcopy(light_properties)

                if target_brightness is not None:
                    light_properties_copy.brightness = max(
                        1,
                        min(254, math.ceil(target_brightness + light_properties.offset))
                    )
                    self.turn_on_lights(light_data=light_properties_copy.light_data)
                    return

            else:
                self.turn_on_lights()
                return

        elif (
            current_state != "adjust"
            and not self.current_keep_on_Condition
        ):
            self.turn_off_lights()

    def getLightAutomationData(self, automations: List[Automation]) -> Tuple[LightProperties, int]:
        """ Resolve the Automation that is active at the current moment and
        return a copy of that Automation together with the brightness
        that should be applied. """

        try:
            target_num = self.find_time(automations = automations)
        except TypeError:
            return None, 0

        target: LightProperties = automations[target_num].light_properties

        if target.light_data is None:
            return target, 0

        dim_brightness: int = 0

        if automations[target_num].dimrate is not None:
            stoptime = automations[target_num + 1].time if target_num + 1 < len(automations) else '23:59:59'
            if self.ADapi.now_is_between(automations[target_num].time, stoptime):
                dim_brightness = self.findBrightnessWhenDimRate(automation=automations, target_num=target_num)

        if target.brightness is not None:
            if dim_brightness > 0:
                target_copy: LightProperties = copy.deepcopy(target)
                target_copy.brightness = dim_brightness
                return target_copy, dim_brightness

            return target, int(target.brightness)

        return target_copy, 0

    def findBrightnessWhenDimRate(self, automation: List[Automation], target_num: int) -> int:
        """ Interpolate a single-step dimming value. """

        now_notAware = self.ADapi.datetime()
        time_date = self.ADapi.parse_datetime(
            automation[target_num].time, today=True
        )
        minutes_elapsed = math.floor(
            ((now_notAware - time_date).total_seconds()) / 60
        )

        # Brightness/value of the previous step and of the current step.
        prev = automation[target_num - 1] if target_num > 0 else None
        current = automation[target_num]

        if prev is None or prev.light_properties.light_data is None or current.light_properties.light_data is None:
            return 0

        if 'brightness' in prev.light_properties.light_data:
            original = int(prev.light_properties.light_data['brightness'])
            target = int(current.light_properties.light_data['brightness'])
        elif 'value' in prev.light_properties.light_data:
            original = int(prev.light_properties.light_data['value'])
            target = int(current.light_properties.light_data['value'])

        new_brightness: int = 0

        if original > target:
            step = math.floor(minutes_elapsed / current.dimrate)
            new_brightness = math.ceil(original - step)

            if new_brightness < target or new_brightness > original:
                return target

            if self.dimHandler is None:
                runtime = now_notAware + timedelta(minutes=int(current.dimrate))
                self.dimHandler = self.ADapi.run_every(
                    self._decrease_brightness_by_one,
                    runtime,
                    current.dimrate * 60,
                    targetBrightness=target,
                )

        elif original < target:
            step = math.floor(minutes_elapsed / current.dimrate)
            new_brightness = math.ceil(original + step)

            if new_brightness > target or new_brightness < original:
                return target

            if self.dimHandler is None:
                runtime = now_notAware + timedelta(minutes=int(current.dimrate))
                self.dimHandler = self.ADapi.run_every(
                    self._increase_brightness_by_one,
                    runtime,
                    current.dimrate * 60,
                    targetBrightness=target,
                )

        if new_brightness == 0:
            new_brightness = target

        return new_brightness

    def _decrease_brightness_by_one(self, **kwargs) -> None:

        targetBrightness = kwargs['targetBrightness']
        if 'brightness' in self.current_light_data:
            if self.current_light_data['brightness'] > targetBrightness:
                self.current_light_data['brightness'] -= 1
                self.turn_on_lights(light_data = self.current_light_data)
                return
        self._stop_dim_by_one()

    def _increase_brightness_by_one(self, **kwargs) -> None:

        targetBrightness = kwargs['targetBrightness']
        if 'brightness' in self.current_light_data:
            if self.current_light_data['brightness'] < targetBrightness:
                self.current_light_data['brightness'] += 1
                self.turn_on_lights(light_data = self.current_light_data)
                return
        self._stop_dim_by_one()

    def _stop_dim_by_one(self) -> None:

        cancel_timer_handler(ADapi = self.ADapi, handler = self.dimHandler)
        self.dimHandler = None

    def BrightnessUpdated(self, entity, attribute, old, new, kwargs) -> None:
        """ Updates brightness in light to check when motion if motionlight is brighter/dimmer than light is now. """

        try:
            self.brightness = int(new)
        except TypeError:
            self.brightness = 0
            return
        self._check_brightness_value()

    def _check_brightness_value(self):
        """Correct brightness if the desired value is ±1. """

        current_brigtness = self.current_light_data.get('brightness')
        if current_brigtness is not None:
            if abs(self.brightness - current_brigtness) == 1:
                self._correct_brightness_value(
                    oldBrightness=current_brigtness,
                    newBrightness=self.brightness,
                )

    def _correct_brightness_value(self, oldBrightness: int, newBrightness: int) -> None:
        """ Correct brightness in the internal automation structures."""
        if self.automations:
            for automation in self.automations_original:
                if automation.light_properties.brightness == oldBrightness:
                    if automation.dimrate is not None:
                        return
                    automation.light_properties.brightness = newBrightness

        if self.motionlight:
            if isinstance(self.motionlight, List):
                motions = self.motions_original
                for automation in motions:
                    if automation.light_properties.brightness == oldBrightness:
                        if automation.dimrate is not None:
                            return
                        automation.light_properties.brightness = newBrightness
            elif isinstance(self.motionlight, LightProperties):
                if self.motionlight.brightness == oldBrightness:
                    self.motionlight.brightness = newBrightness

        for mode in self.light_modes:
            if mode.automations:
                for automation in mode.original_automations:
                    if automation.light_properties.brightness == oldBrightness:
                        if automation.dimrate is not None:
                            return
                        automation.light_properties.brightness = newBrightness

    def setAdaptiveLightingOn(self) -> None:
        """ Set Adaptive lighting to take control over brightness to on. """

        if self.adaptive_switch is not None:
            self.ADapi.call_service('adaptive_lighting/set_manual_control',
                entity_id = self.adaptive_switch,
                manual_control = False,
                namespace = self.HASS_namespace
            )
        else:
            self.ADapi.log(
                f"Adaptive lighting switch not defined in configuration. Define switch with: 'adaptive_switch'",
                level = 'WARNING'
            )

    def setAdaptiveLightingOff(self) -> None:
        """ Set Adaptive lighting to take control over brightness to on. """

        if self.adaptive_switch is not None:
            self.ADapi.call_service('adaptive_lighting/set_manual_control',
                entity_id = self.adaptive_switch,
                manual_control = True,
                namespace = self.HASS_namespace
            )
        else:
            self.ADapi.log(
                f"Adaptive lighting switch not defined in configuration. Define switch with: 'adaptive_switch'",
                level = 'WARNING'
            )

    def update_isOn_lights(self, entity, attribute, old, new, kwargs) -> None:
        """ Updates isON state for light for checks and persistent storage when restarting Home Assistant. """
        if new == 'on':
            self.is_on = True
        elif new == 'off':
            self.is_on = False

    def turn_on_lights(self, light_data: dict = {}) -> None:
        """ Turns all lights in ``self.lights`` on with the supplied
        *light_data*. """
        if self._check_update_light_with_new_data(light_data=light_data):
            self.current_light_data = copy.deepcopy(light_data)
            self.is_turned_on = True

            if self.random_turn_on_delay == 0:
                for light in self.lights:
                    self.ADapi.turn_on(light, **self.current_light_data)
            else:
                for light in self.lights:
                    self.ADapi.run_in(
                        self.turn_on_lights_with_delay,
                        delay=0,
                        random_start=0,
                        random_end=self.random_turn_on_delay,
                        light=light,
                        light_data=self.current_light_data,
                    )

    def turn_on_lights_with_delay(self, **kwargs) -> None:
        """ Turns on lights with random delay. """

        self.ADapi.turn_on(kwargs['light'], **kwargs['light_data'])

    def turn_on_lights_at_max(self) -> None:
        """ Turns on lights with brightness 254. """

        self.is_turned_on = True
        if self.has_adaptive_state:
            self.setAdaptiveLightingOff()

        self.current_light_data = {'brightness' : 254}
        for light in self.lights:
            string:str = self.lights[0]
            if string.startswith('light.'):
                if self.random_turn_on_delay == 0:
                    self.ADapi.turn_on(light, brightness = 254)
                else:
                    self.ADapi.run_in(self.turn_on_lights_with_delay, delay = 0,  random_start = 0, random_end = self.random_turn_on_delay, light = light, light_data = {'brightness': 254})
            if string.startswith('switch.'):
                self.ADapi.turn_on(light)

    def turn_off_lights(self) -> None:
        """ Turns off lights. """

        self.current_light_data = {}
        if self.is_on is not False and self.is_turned_on is not False:
            self.is_turned_on = False
            if self.has_adaptive_state:
                self.setAdaptiveLightingOff()
            self.current_light_data = {}
            if self.random_turn_on_delay == 0:
                for light in self.lights:
                    self.ADapi.turn_off(light)
            else:
                for light in self.lights:
                    self.ADapi.run_in(self.turn_off_lights_with_delay, delay = 0,  random_start = 0, random_end = self.random_turn_on_delay, light = light)
        self.brightness = 0

    def turn_off_lights_with_delay(self, **kwargs)  -> None:
        """ Turns off light with random delay """

        self.ADapi.turn_off(kwargs['light'])

    def _check_update_light_with_new_data(self, light_data: dict = {}) -> bool:
        light_data = self._validate_light_data(light_data or {})
        return (
            self.current_light_data != light_data or
            self.is_on is not True
        )

    def _validate_light_data(self, data: dict) -> dict:
        if not isinstance(data, dict):
            self.ADapi.log(f"light_data must be a dict, got {type(data)!r} for {self.lights[0]} with data {data}", level = 'WARNING')
            raise TypeError
        return data


class MQTTLight(Light):
    """ Child class for lights to control lights directly over MQTT """

    def __init__(self,
                 api,
                 lights: List[str],
                 light_modes: Optional[List],
                 automations: Optional[List],
                 motionlight: Optional[List],
                 lux_constraint: Optional[float],
                 room_lux_constraint: Optional[float],
                 conditions: List[str],
                 keep_on_conditions: List[str],
                 HASS_namespace: str,
                 night_motion: str,
                 dim_while_motion: str,
                 random_turn_on_delay: int,
                 adaptive_switch: Optional[str],
                 adaptive_sleep_mode: Optional[str],
                 weather,
                 MQTT_namespace: str,
                 mqtt_plugin):

        self.mqtt = mqtt_plugin
        self.MQTT_namespace = MQTT_namespace

        for light in lights:
            light_topic:str = light
            self.mqtt.mqtt_subscribe(light_topic)
            self.mqtt.listen_event(self.light_event_MQTT, 'MQTT_MESSAGE',
                topic = light_topic,
                namespace = self.MQTT_namespace
            )

        super().__init__(api,
                         lights,
                         light_modes,
                         automations,
                         motionlight,
                         lux_constraint,
                         room_lux_constraint,
                         conditions,
                         keep_on_conditions,
                         HASS_namespace,
                         night_motion,
                         dim_while_motion,
                         random_turn_on_delay,
                         adaptive_switch,
                         adaptive_sleep_mode,
                         weather)

    def light_event_MQTT(self, event_name, data, **kwargs) -> None:
        """ Listens to updates to MQTT lights. """

        try:
            lux_data = json.loads(data['payload'])
        except Exception as e:
            return

        """ Get your X / Y color from setting RGB light.
            Uncomment the if and log lines below """
        #if 'color' in lux_data:
        #    self.ADapi.log(f"{data['topic']} Color in lux: {lux_data['color']}")

        if 'brightness' in lux_data:
            self.is_on = lux_data['state'] == 'ON'
            self.brightness = lux_data['brightness']
            self._check_brightness_value()

        elif 'value' in lux_data:
            if type(lux_data['value']) == bool:
                self.is_on = lux_data['value']

            elif type(lux_data['value']) == int:
                self.brightness = int(lux_data['value'])
                if (
                    lux_data['value'] > 0
                    and lux_data['value'] <= 100
                ):
                    self._check_brightness_value()
                    self.is_on = True
                elif lux_data['value'] == 0:
                    self.is_on = False

        elif 'state' in lux_data:
            self.is_on = lux_data['state'] == 'ON'

        else:
            """ No valid state based on program. Let user know """
            self.ADapi.log(
                f"Unknown data for {self.lights[0]}. This has not been programmed yet. "
                "Please issue a request at https://github.com/Pythm/ad-Lightwand "
                f"and provide what MQTT brigde and light type you are trying to control, in addition to the data sent from broker: {lux_data}"
            )

    def turn_on_lights(self, light_data:dict = {}) -> None:
        """ Turns on lights with given data. """

        if self._check_update_light_with_new_data(light_data=light_data):
            self.current_light_data = copy.deepcopy(light_data)
            self.is_turned_on = True

            for light in self.lights:
                if 'zigbee2mqtt' in light:
                    if not light_data:
                        light_data.update(
                            {'state' : 'ON'}
                        )

                if light in ('switch_multilevel', 'switch_binary'):
                    if self.is_on is not True:
                        light_data.update(
                            {'ON' : True}
                        )

                if self.random_turn_on_delay == 0:
                    self._publish_update_to_light(light = light, light_data = light_data)
                else:
                    self.ADapi.run_in(self.turn_on_lights_with_delay,
                                      delay = 0,
                                      random_start = 0,
                                      random_end = self.random_turn_on_delay,
                                      light = light,
                                      light_data = light_data)

    def turn_on_lights_with_delay(self, **kwargs) -> None:
        """ Turns on light with random delay. """

        self._publish_update_to_light(light = kwargs['light'], light_data = kwargs['light_data'])

    def turn_on_lights_at_max(self) -> None:
        """ Turns on lights with brightness 254. """

        self.is_turned_on = True
        if self.has_adaptive_state:
            self.setAdaptiveLightingOff()

        light_data:dict = {}
        self.current_light_data = {'brightness' : 254}

        if self.is_on is not True:
            light_data.update({'ON' : True})

        for light in self.lights:
            if 'zigbee2mqtt' in light:
                light_data.update({'brightness' : 254})
                
            elif 'switch_multilevel' in light:
                light_data.update({'value' : 99})

            if self.random_turn_on_delay == 0:
                self._publish_update_to_light(light = light, light_data = light_data)
            else:
                self.ADapi.run_in(self.turn_on_lights_with_delay,
                                  delay = 0,
                                  random_start = 0,
                                  random_end = self.random_turn_on_delay,
                                  light = light,
                                  light_data = light_data)

    def turn_off_lights(self) -> None:
        """ Turns off lights. """

        if self.has_adaptive_state:
            self.setAdaptiveLightingOff()
        self.current_light_data = {}
        if self.is_on is not False and self.is_turned_on is not False:
            self.is_turned_on = False
            if self.random_turn_on_delay == 0:
                for light in self.lights:
                    self.mqtt.mqtt_publish(topic = str(light) + '/set', payload = 'OFF', namespace = self.MQTT_namespace)
            else:
                for light in self.lights:
                    self.ADapi.run_in(self.turn_off_lights_with_delay,
                                      delay = 0,
                                      random_start = 0,
                                      random_end = self.random_turn_on_delay,
                                      light = light)

    def turn_off_lights_with_delay(self, **kwargs) -> None:
        """ Turns off light with random delay. """

        self.mqtt.mqtt_publish(topic = str(kwargs['light']) + '/set', payload = 'OFF', namespace = self.MQTT_namespace)

    def _publish_update_to_light(self, light: str, light_data: dict) -> None:
        payload = json.dumps(light_data)
        self.mqtt.mqtt_publish(
            topic = str(light) + '/set',
            payload = payload,
            namespace = self.MQTT_namespace
        )

class ToggleLight(Light):
    """ Child class for lights to control lights that dim by toggle """

    def __init__(self,
                 api,
                 lights: List[str],
                 light_modes: Optional[List],
                 automations: Optional[List],
                 motionlight: Optional[List],
                 lux_constraint: Optional[float],
                 room_lux_constraint: Optional[float],
                 conditions: List[str],
                 keep_on_conditions: List[str],
                 HASS_namespace: str,
                 night_motion: str,
                 dim_while_motion: str,
                 random_turn_on_delay: int,
                 adaptive_switch: Optional[str],
                 adaptive_sleep_mode: Optional[str],
                 weather,
                 toggle: int,
                 num_dim_steps: int,
                 toggle_speed: int,
                 prewait_toggle: int):

        self.current_toggle:int = 0
        self.toggle_lightbulb:int = toggle * 2 - 1
        self.fullround_toggle:int = num_dim_steps * 2
        try:
            self.toggle_speed = float(toggle_speed)
        except(ValueError, TypeError):
            self.toggle_speed:float = 1
        self.prewait_toggle:float = prewait_toggle  

        super().__init__(api,
                         lights,
                         light_modes,
                         automations,
                         motionlight,
                         lux_constraint,
                         room_lux_constraint,
                         conditions,
                         keep_on_conditions,
                         HASS_namespace,
                         night_motion,
                         dim_while_motion,
                         random_turn_on_delay,
                         adaptive_switch,
                         adaptive_sleep_mode,
                         weather)

        if self.is_on:
            self.current_toggle = self.toggle_lightbulb 

    def setLightMode(self, lightmode:str = 'none') -> None:
        """ The main function/logic to handle turning on / off lights based on mode selected. """

        self.current_OnCondition = self.checkConditions(conditions = self.conditions) if self.conditions is not None else True
        self.current_keep_on_Condition = self.checkConditions(conditions = self.keep_on_conditions) if self.keep_on_conditions is not None else False
        self.current_LuxCondition = self.checkLuxConstraints()

        if lightmode == 'none':
            lightmode = self.lightmode

        if lightmode == translations.morning:
            if not self.current_OnCondition or not self.current_LuxCondition:
                lightmode = translations.normal

        if lightmode == translations.custom:
            self.lightmode = lightmode
            return

        if lightmode not in (translations.normal, translations.reset):
            mode = self.light_modes_by_name.get(lightmode)
            if mode is not None:
                self.lightmode = lightmode
                
                if mode.light_properties and mode.light_properties.toggle:
                    # Turns on light regardless of Lux and Conditions
                    toggle_bulb = mode.light_properties.toggle * 2 - 1
                    self.calculateToggles(toggle_bulb = toggle_bulb)

                elif 'turn_off' in mode.light_properties.state:
                    # Turns off light
                    self.turn_off_lights()
                return

        if lightmode in (translations.away, translations.off, translations.night):
            self.lightmode = lightmode
            self.turn_off_lights()
            return

        if lightmode in (translations.fire, translations.wash):
            self.lightmode = lightmode
            if self.current_toggle == 1:
                return

            self.calculateToggles(toggle_bulb = 1)
            return

        self.lightmode = translations.normal
        if (
            (self.current_OnCondition and self.current_LuxCondition)
            or self.current_keep_on_Condition
        ):
            if self.current_toggle == self.toggle_lightbulb:
                return

            self.calculateToggles(toggle_bulb = self.toggle_lightbulb)
        else:
            self.turn_off_lights()

    def toggle_light(self, kwargs) -> None:
        """ Toggles light on/off.  """

        for light in self.lights:
            self.ADapi.toggle(light)

    def turn_off_lights(self):
        if self.is_on is not False and self.is_turned_on is not False:
            self.is_turned_on = False
            for light in self.lights:
                self.ADapi.turn_off(light)
            self.current_toggle = 0

    def calculateToggles(self, toggle_bulb:int = 1) -> None:
        """ Calculates how many toggles to perform to get correct dim. """

        if self.current_toggle == toggle_bulb:
            return

        elif self.current_toggle > toggle_bulb:
            self.current_toggle -= self.fullround_toggle
        sec = self.prewait_toggle

        while self.current_toggle < toggle_bulb:
            self.ADapi.run_in(self.toggle_light, sec)
            self.current_toggle += 1
            sec += self.toggle_speed

        sec += 120
        self.ADapi.run_in(self.checkToggleAfterRun, sec)

    def checkToggleAfterRun(self, kwargs) -> None:
        """ Checks if light is on after toggle run. """

        if self.ADapi.get_state(self.lights[0]) == 'off':
            toggle_bulb = self.current_toggle
            self.current_toggle = 0
            self.calculateToggles(toggle_bulb = toggle_bulb)
