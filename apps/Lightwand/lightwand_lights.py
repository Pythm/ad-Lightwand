from __future__ import annotations

from datetime import timedelta
import json
import bisect
import math
import copy

from typing import List, Tuple, Optional, Set, Union

from translations_lightmodes import translations
from lightwand_config import Automation, LightMode

from ast_evaluator import safe_eval

class Light:
    """ Parent class for lights. """

    def __init__(self,
                 api,
                 lights: List[str],
                 light_modes: Optional[List[LightMode]],
                 automations: Optional[List[Automation]],
                 motionlight: Optional[Union[List[Automation], LightMode]],
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
        self.times_to_adjust_light:list = []
        self.dimHandler = None
        self.motion:bool = False
        self.isON:bool = None
        self.brightness:int = 0
        self.current_light_data:dict = {}

        string:str = self.lights[0]
        if string[:6] == 'light.':
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
            self.isOn = self.ADapi.get_state(self.lights[0]) == 'on'
        if string[:7] == 'switch.':
            self.ADapi.listen_state(self.update_isOn_lights, self.lights[0],
                namespace = HASS_namespace
            )
            self.isOn = self.ADapi.get_state(self.lights[0]) == 'on'

        # Helpers to check if conditions to turn on/off light has changed
        self.wereMotion:bool = False
        self.current_OnCondition:bool = None
        self.current_keep_on_Condition:bool = None
        self.current_LuxCondition:bool = None

        self.automations_original: List[Automation] = []

        # ----- Main automations ------------------------------------------------
        if self.automations:
            self.automations_original = copy.deepcopy(self.automations)

            self.checkTimesinAutomations(self.automations)

            entity_prefix: str = self.lights[0][:6]

            for automation in self.automations:
                if automation.light_mode.state == 'adaptive':
                    self.has_adaptive_state = True

        # ----- Motion triggered automations ------------------------------------
        self.motions_original: List[Automation] = []

        if self.motionlight:
            if isinstance(self.motionlight, List):
                self.motions_original = copy.deepcopy(self.motionlight)
                self.checkTimesinAutomations(self.motionlight)

                for automation in self.motionlight:
                    if automation.light_mode.state == 'adaptive':
                        self.has_adaptive_state = True

            elif isinstance(self.motionlight, LightMode):
                if self.motionlight.automations:
                    self.checkTimesinAutomations(self.motionlight.automations)
                if self.motionlight.state == 'adaptive':
                    self.has_adaptive_state = True

        # ----- Light mode automations ------------------------------------------
        for mode in self.light_modes:
            if mode.automations:
                mode.original_automations = copy.deepcopy(mode.automations)
                self.checkTimesinAutomations(mode.automations)

                for automation in mode.automations:
                    if automation.light_mode.state == 'adaptive':
                        self.has_adaptive_state = True
            else:
                if mode.state:
                    if mode.state == 'adaptive':
                        self.has_adaptive_state = True

        if self.motionlight and not self.automations:
            self.automations = [Automation(time='00:00:00', state='turn_off')]
            self.automations_original = copy.deepcopy(self.automations)
        elif not self.automations:
            self.automations = [Automation(time='00:00:00', state='none')]
            self.automations_original = copy.deepcopy(self.automations)

        self.ADapi.run_daily(self.rundaily_Automation_Adjustments, '00:01:00')

        for time in self.times_to_adjust_light:
            if self.ADapi.parse_time(time) > self.ADapi.time():
                self.ADapi.run_once(self.run_daily_lights, time)

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
            elif isinstance(self.motionlight, LightMode) and self.motionlight.automations:
                self.checkTimesinAutomations(self.motionlight.automations)

        for mode in self.light_modes:
            if mode.automations:
                mode.automations = copy.deepcopy(mode.original_automations)
                self.checkTimesinAutomations(mode.automations)

        for time in self.times_to_adjust_light:
            self.ADapi.run_once(self.run_daily_lights, time)


    def checkTimesinAutomations(self, automations: List[Automation]) -> None:
        """ Find and adjust times in automations based on clock and sunrise/sunset times.
            Set up some default behaviour. """

        automations_to_delete: list[int] = []
        time_to_add: timedelta = timedelta(minutes=0)
        calculate_from_sunrise: bool = False
        calculate_from_sunset: bool = False

        if not automations:
            return

            # Check if a starttime at midnight is defined
        test_time = self.ADapi.parse_time('00:00:00')
        if test_time != self.ADapi.parse_time(automations[0].time):
            # Insert a dummy turn off automation at midnight
            automations.insert(
                0,
                Automation(time='00:00:00', state='turn_off')
            )

        prev_brightness: Optional[int] = None
        # Corrects times in automation
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
            if automation.time not in self.times_to_adjust_light:
                self.times_to_adjust_light.append(automation.time)

            # ---- Handle dimming ------------------------------------------------------
            if automation.dimrate and automation.light_mode.brightness is not None:
                brightness = automation.light_mode.brightness

                if prev_brightness is not None:
                    stop_dim_min = math.ceil(
                        abs(prev_brightness - brightness) * automation.dimrate
                    )
                    stop_dt = (
                        self.ADapi.parse_datetime(automation.time)
                        + timedelta(minutes=stop_dim_min)
                    )
                    automation.stoptime = str(stop_dt.time())

                prev_brightness = brightness

        # --------------------------------------------------------------------------
        # Remove automations that are no longer valid
        # --------------------------------------------------------------------------
        for idx in reversed(automations_to_delete):
            del automations[idx]

    def run_daily_lights(self, kwargs) -> None:
        """ Called once a day at the times stored in ``self.times_to_adjust_light``. """

        if (
            not self.motion or
            (self.lightmode.startswith(translations.night) and not self.night_motion) or
            self.lightmode in (translations.off, translations.custom)
        ):
            self.current_OnCondition = None
            self.current_keep_on_Condition = None
            self.current_LuxCondition = None
            self.setLightMode()
            return

        found_match = False
        match self.motionlight:
            case list() as ml:
                target_idx = self.find_time(automations=ml)
                chosen_light = ml[target_idx].light_mode
                found_match = True
            case LightMode() as lm:
                chosen_light = lm
                found_match = True
            case _: ###
                self.ADapi.log(f"Found no match for {self.lights[0]} motionlights: {self.motionlight}") ###

        if found_match and chosen_light.state == 'turn_off':
            if self.isON or self.isON is None:
                self.turn_off_lights()
            return

        if self.dim_while_motion and self.motion:
            self.setMotion()


    def find_time(self, automations: List[Automation]) -> int:
        """ Return the index of the *last* automation whose ``time`` is 
        **less-than or equal to** the current time. """

        now_notAware = self.ADapi.time()

        times: List[datetime] = [
            self.ADapi.parse_time(automation.time) for automation in automations
        ]

        idx = bisect.bisect_right(times, now_notAware) - 1

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
            if self.dimHandler is not None and self.ADapi.timer_running(self.dimHandler):
                try:
                    self.ADapi.cancel_timer(self.dimHandler)
                except Exception:
                    self.ADapi.log(
                        f"Could not stop dim timer for {entity}.", level='DEBUG'
                    )
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
                    mode_LightMode, mode_brightness_compare = self.getLightAutomationData(
                        automations=mode.automations
                    )
                else:
                    mode_LightMode = mode

                if (mode_LightMode.state in ('turn_on', 'none', 'lux_controlled', 'adaptive')
                    or ('adjust' in mode_LightMode.state and self.isON)):

                    if 'lux_controlled' in mode_LightMode.state and not self.current_LuxCondition:
                        if self.isON or self.isON is None:
                            self.turn_off_lights()
                        return

                    self.setLightAutomation(automations=mode.automations, light_mode=mode_LightMode)
                return

        if lightmode in (translations.away, translations.off):
            self.lightmode = lightmode
            if self.isON or self.isON is None:
                self.turn_off_lights()
            return

        if lightmode.startswith(translations.night):
            self.lightmode = lightmode
            if self.adaptive_sleep_mode is not None:
                self.ADapi.turn_on(self.adaptive_sleep_mode)
            elif self.isON or self.isON is None:
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


    def setMotion(self, lightmode: str = 'none') -> None:
        """ Sets motion lights when motion is detected. """

        if lightmode == 'none':
            lightmode = self.lightmode
        elif lightmode == translations.reset:
            lightmode = translations.normal
            self.wereMotion = False

        motion_LightMode: Optional[LightMode] = None
        self.motion = True
        self.current_OnCondition = self.checkConditions(conditions = self.conditions) if self.conditions is not None else True
        self.current_LuxCondition = self.checkLuxConstraints()

        if not self.current_OnCondition or not self.current_LuxCondition:
            return

        if (
            not self.wereMotion
            or self.dim_while_motion
            or self.lightmode != lightmode
        ):
            motion_brightness_compare:int = 0
            if isinstance(self.motionlight, List):
                motion_LightMode, motion_brightness_compare = self.getLightAutomationData(
                    automations=self.motionlight
                )

            elif isinstance(self.motionlight, LightMode):
                motion_LightMode = self.motionlight

                motion_brightness_compare = motion_LightMode.resolve_brightness_to_255()
            else:
                self.ADapi.log(f"Found no isinstance for {self.motionlight}") ###

            if motion_brightness_compare == 0:
                motion_brightness_compare = self.current_light_data.get('brightness', self.brightness) + motion_LightMode.offset

        else: # No change since last motion
            return

        self.lightmode = lightmode
        self.wereMotion = True

        if lightmode not in (translations.normal, translations.reset):
            mode = self.light_modes_by_name.get(lightmode)
            if mode is not None:
                if mode.automations:
                    mode_LightMode, mode_brightness_compare = self.getLightAutomationData(
                        automations=mode.automations
                    )
                else:
                    mode_LightMode = mode
                    mode_brightness_compare = mode.resolve_brightness_to_255()
                
                if mode_brightness_compare == 0:
                    mode_brightness_compare = self.current_light_data.get('brightness', self.brightness) + mode_LightMode.offset
                
                self.ADapi.log(f"Mode in {mode_LightMode.state}") ###
                if mode_LightMode.noMotion:
                    self.motion = False
                    self.ADapi.log(f"noMotion in {mode_LightMode.mode}") ###
                    return

                if mode_LightMode.state == 'adaptive' and self.brightness != 0:
                    self.ADapi.log(
                        f"Mode {mode.mode} state is adaptive. Updating brightness from "
                        f"{mode_brightness_compare} to {self.brightness}") ###
                    mode_brightness_compare = self.brightness

                if mode_LightMode.state in ('manual', 'pass'):
                    return

                if motion_brightness_compare < mode_brightness_compare:
                    self.ADapi.log(
                        f"Motion when mode. Mode has higher brightness. "
                        f"{motion_brightness_compare} < {mode_brightness_compare}") ###
                    return

            if lightmode in (translations.fire, translations.wash):
                self.turn_on_lights_at_max()
                return

        if motion_LightMode is None:
            self.ADapi.log(f" WARNING: No Motion Ligth Data for {self.lights[0]} ? Turns on lights..") ###
            self.turn_on_lights()
            return

        if motion_LightMode.state in ('turn_on', 'adjust', 'none', 'adaptive'):
            
            #if motion_LightMode.light_data:
            #    self.turn_on_lights(light_data=motion_LightMode.light_data)
            if isinstance(self.motionlight, List):
                self.setLightAutomation(automations=self.motionlight, light_mode=motion_LightMode)
            elif isinstance(self.motionlight, LightMode):
                self.setLightAutomation(light_mode=motion_LightMode)

        elif motion_LightMode.state == 'turn_off':
            self.turn_off_lights()
        else:
            self.ADapi.log(f"No Motion logic for {self.lights[0]}") ###


    def setLightAutomation(self, automations: List[Automation] = None, light_mode: LightMode = None) -> None:
        """ Resolve the *target* automation (or, if it does not contain light_data,
        fall back to the normal automations that belong to this
        :class:`LightController` instance) and turn the light on with
        the resolved ``light_data``. """

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
                if light_mode is None and hasattr(automations[target_num], 'light_mode'):
                    light_mode = automations[target_num].light_mode
                    current_state = automations[target_num].light_mode.state
                if light_mode.light_data is not None:
                    target_light_data = light_mode.light_data
                    found_light_data = True

        if not found_light_data:
            try:
                target_num = self.find_time(automations = self.automations)
            except TypeError:
                pass
            else:
                if hasattr(self.automations[target_num].light_mode, 'light_data'):
                    automations = self.automations
                    if light_mode is None:
                        light_mode = automations[target_num].light_mode
                    if light_mode.light_data is None:
                        if automations[target_num].light_mode.light_data is not None:
                            target_light_data = automations[target_num].light_mode.light_data

        if light_mode is not None:
            if current_state == 'none' and light_mode.state is not None:
                if light_mode.state != 'none':
                    current_state = light_mode.state
            if target_light_data is None and light_mode.light_data is not None:
                target_light_data = light_mode.light_data

        if (current_state == 'pass' and self.isON) or current_state == 'manual':
            if self.has_adaptive_state:
                self.setAdaptiveLightingOff()
            return
        if current_state == 'turn_off':
            if self.has_adaptive_state:
                self.setAdaptiveLightingOff()
            self.turn_off_lights()
            return

        if (
            (current_state == 'adjust' and self.isON)
            or current_state != 'adjust'
        ):

            if 'adaptive' in current_state:
                if self.isON is None or not self.isON:
                    self.turn_on_lights()
                self.setAdaptiveLightingOn()

                base_kwargs = {
                    'entity_id': self.adaptive_switch,
                    'namespace': self.HASS_namespace,
                }
                if not (light_mode.max_brightness_pct or light_mode.min_brightness_pct):
                    base_kwargs['use_defaults'] = 'configuration'
                else:
                    base_kwargs.update(light_mode.brightness_kwargs())

                self.ADapi.call_service(
                    'adaptive_lighting/change_switch_settings',
                    **base_kwargs
                )
                return

            elif self.has_adaptive_state:
                self.setAdaptiveLightingOff()

            if target_light_data is not None:
                target_brightness = light_mode.brightness
                if target_brightness is None:
                    target_brightness = target_light_data.get('brightness', 'value')

                if automations[target_num].dimrate is not None:
                    stoptime = automations[target_num + 1].time if target_num + 1 < len(automations) else '23:59:59'
                    if self.ADapi.now_is_between(
                        automations[target_num].time, stoptime
                    ):
                        target_brightness = (
                            self.findBrightnessWhenDimRate(automation=automations, target_num=target_num) + light_mode.offset
                        )

                light_mode_copy = copy.deepcopy(light_mode)

                if target_brightness is not None:
                    light_mode_copy.brightness = max(
                        1,
                        min(254, math.ceil(target_brightness + light_mode.offset))
                    )
                    self.turn_on_lights(light_data=light_mode_copy.light_data)
                    return
                self.ADapi.log(f"target_brightness was None for {self.lights[0]}") ###

            elif not self.isON or self.isON is None:
                self.turn_on_lights()
                return

        elif (
            current_state != "adjust"
            and (self.isON or self.isON is None)
            and not self.current_keep_on_Condition
        ):
            self.turn_off_lights()


    def getLightAutomationData(self, automations: List[Automation]) -> Tuple[LightMode, int]:
        """ Resolve the Automation that is active at the current moment and
        return a copy of that Automation together with the brightness
        that should be applied. """

        # TODO Check if needed to add offset
        try:
            target_num = self.find_time(automations = automations)
        except TypeError:
            self.ADapi.log(f"Did not find Target Num for automations: {automations} for {self.lights[0]}") ###
            return None, 0

        target = automations[target_num].light_mode
        stoptime = automations[target_num + 1].time if target_num + 1 < len(automations) else '23:59:59'

        if target.light_data is None:
            return target, 0

        target_copy: Automation = copy.deepcopy(target)

        dim_brightness: int = 0

        if automations[target_num].dimrate is not None:
            if self.ADapi.now_is_between(automations[target_num].time, stoptime):
                dim_brightness = self.findBrightnessWhenDimRate(automation=automations, target_num=target_num)

        if 'brightness' in target_copy.light_data and target_copy.light_data['brightness'] is not None:
            if dim_brightness > 0:
                target_copy.light_data['brightness'] = dim_brightness
                return target_copy, dim_brightness
            return target_copy, int(target_copy.light_data['brightness'])

        if 'value' in target_copy.light_data and target_copy.light_data['value'] is not None:
            if dim_brightness > 0:
                target_copy.light_data['value'] = dim_brightness
                return target_copy, dim_brightness
            return target_copy, int(target_copy.light_data['value'])

        if target_copy.state == 'adaptive':
            return target_copy, 0

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

        if prev is None or prev.light_mode.light_data is None or current.light_mode.light_data is None:
            return 0

        brightness_value = 'brightness'
        if 'brightness' in prev.light_mode.light_data:
            original = int(prev.light_mode.light_data['brightness'])
            target = int(current.light_mode.light_data['brightness'])
        elif 'value' in prev.light_mode.light_data:
            original = int(prev.light_mode.light_data['value'])
            target = int(current.light_mode.light_data['value'])
            brightness_value = 'value'

        new_brightness: int = 0

        if original > target:
            step = math.floor(minutes_elapsed / current.dimrate)
            new_brightness = math.ceil(original - step)

            if new_brightness < target or new_brightness > original:
                return target

            if self.dimHandler is None:
                runtime = now_notAware + timedelta(minutes=int(current.dimrate))
                self.dimHandler = self.ADapi.run_every(
                    self.dimBrightnessByOne,
                    runtime,
                    current.dimrate * 60,
                    targetBrightness=target,
                    brightnessvalue=brightness_value,
                )
                self.ADapi.run_at(self.StopDimByOne, current.stoptime)

        elif original < target:
            step = math.floor(minutes_elapsed / current.dimrate)
            new_brightness = math.ceil(original + step)

            if new_brightness > target or new_brightness < original:
                return target

            if self.dimHandler is None:
                runtime = now_notAware + timedelta(minutes=int(current.dimrate))
                self.dimHandler = self.ADapi.run_every(
                    self.increaseBrightnessByOne,
                    runtime,
                    current.dimrate * 60,
                    targetBrightness=target,
                    brightnessvalue=brightness_value,
                )
                self.ADapi.run_at(self.StopDimByOne, current.stoptime)

        if new_brightness == 0:
            new_brightness = target

        return new_brightness

    def dimBrightnessByOne(self, **kwargs) -> None:
        """ Dim by one dimming to have the light dim down
        by one brightness every given minute. """

        targetBrightness = kwargs['targetBrightness']
        brightnessvalue = kwargs['brightnessvalue']
        current_brigtness = self.current_light_data.get('brightness')
        if current_brigtness is not None and current_brigtness > targetBrightness:
            current_brigtness -= 1
            ld = {brightnessvalue: current_brigtness}
            self.turn_on_lights(light_data = ld)
        else:
            self._stop_dim_by_one()

    def increaseBrightnessByOne(self, **kwargs) -> None:
        """ Increase brightness by one every given minute. """

        targetBrightness = kwargs['targetBrightness']
        brightnessvalue = kwargs['brightnessvalue']
        current_brigtness = self.current_light_data.get('brightness')
        if current_brigtness is not None and current_brigtness < targetBrightness:
            current_brigtness += 1
            ld = {brightnessvalue: current_brigtness}
            self.turn_on_lights(light_data = ld)
        else:
            self._stop_dim_by_one()

    def StopDimByOne(self, kwargs) -> None:
        self._stop_dim_by_one()

    def _stop_dim_by_one(self) -> None:
        """ Stops dimming by one. """

        if self.dimHandler is not None:
            if self.ADapi.timer_running(self.dimHandler):
                try:
                    self.ADapi.cancel_timer(self.dimHandler)
                except Exception:
                    self.ADapi.log(f"Could not stop dim timer for {entity}.", level = 'DEBUG')
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
                self.correctBrightness(
                    oldBrightness=current_brigtness,
                    newBrightness=self.brightness,
                )

    def correctBrightness(self, oldBrightness: int, newBrightness: int) -> None:
        """ Correct brightness in the internal automation structures."""
        if self.automations:
            for automation in self.automations_original:
                if automation.dimrate is not None and automation.light_mode.brightness == oldBrightness:
                    self.ADapi.log(f"Update automation {self.lights[0]} brightness from {oldBrightness} to {newBrightness}") ###
                    automation.light_mode.brightness = newBrightness

        if self.motionlight:
            if isinstance(self.motionlight, List):
                motions = self.motions_original
                for automation in motions:
                    if automation.dimrate is not None and automation.light_mode.brightness == oldBrightness:
                        self.ADapi.log(f"Update Motion List {self.lights[0]} brightness from {oldBrightness} to {newBrightness}") ###
                        automation.light_mode.brightness = newBrightness
            elif isinstance(self.motionlight, LightMode):
                if self.motionlight.brightness == oldBrightness:
                    self.ADapi.log(f"Update LightMode {self.lights[0]} brightness from {oldBrightness} to {newBrightness}") ###
                    self.motionlight.brightness = newBrightness
                
                # Check nested automations if they exist
                if self.motionlight.automations:
                    self.ADapi.log(f"Nested automation exist..") ###
                    for automation in self.motionlight.automations:
                        if automation.dimrate is not None and automation.light_mode.brightness == oldBrightness:
                            self.ADapi.log(f"Update {self.lights[0]} brightness from {oldBrightness} to {newBrightness}") ###
                            automation.light_mode.brightness = newBrightness

        for mode in self.light_modes:
            if mode.automations:
                for automation in mode.original_automations:
                    if automation.dimrate is not None and automation.light_mode.brightness == oldBrightness:
                        self.ADapi.log(f"Update {self.lights[0]} {mode.mode} brightness from {oldBrightness} to {newBrightness}") ###
                        automation.light_mode.brightness = newBrightness

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

        self.ADapi.log(f"{entity} Attribute for isOn is {attribute}") ###
        if new == 'on':
            self.isON = True

        elif new == 'off':
            self.isON = False

    def toggle_light(self, kwargs) -> None:
        """ Toggles light on/off.  """

        for light in self.lights:
            self.ADapi.toggle(light)

    def turn_on_lights(self, light_data: dict = {}) -> None:
        """ Turns all lights in ``self.lights`` on with the supplied
        *light_data*. """

        if self._check_update_light_with_new_data(light_data=light_data):
            self.current_light_data = copy.deepcopy(light_data)

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

        if self.has_adaptive_state:
            self.setAdaptiveLightingOff()

        self.current_light_data = {'brightness' : 254}
        for light in self.lights:
            string:str = self.lights[0]
            if string[:6] == 'light.':
                if self.random_turn_on_delay == 0:
                    self.ADapi.turn_on(light, brightness = 254)
                else:
                    self.ADapi.run_in(self.turn_on_lights_with_delay, delay = 0,  random_start = 0, random_end = self.random_turn_on_delay, light = light, light_data = {'brightness': 254})
            if string[:7] == 'switch.':
                self.ADapi.turn_on(light)

    def turn_off_lights(self) -> None:
        """ Turns off lights. """

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
            not self.isON or
            self.isON is None
        )

    def _validate_light_data(self, data: dict) -> dict:
        if not isinstance(data, dict):
            raise TypeError(f"light_data must be a dict, got {type(data)!r}")

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
            self.ADapi.log(f"Could not get payload from topic for {data['topic']}. Exception: {e}", level = 'DEBUG')
            return

        """ Get your X / Y color from setting RGB light.
            Uncomment the if and log lines below """
        #if 'color' in lux_data:
        #    self.ADapi.log(f"{data['topic']} Color in lux: {lux_data['color']}")

        if 'brightness' in lux_data:
            self.isON = lux_data['state'] == 'ON'
            self.brightness = lux_data['brightness']
            self._check_brightness_value()

        elif 'value' in lux_data:
            if type(lux_data['value']) == bool:
                self.isON = lux_data['value']

            elif type(lux_data['value']) == int:
                self.brightness = int(lux_data['value'])
                if (
                    lux_data['value'] > 0
                    and lux_data['value'] <= 100
                ):
                    self._check_brightness_value()
                    self.isON = True
                elif lux_data['value'] == 0:
                    self.isON = False

        elif 'state' in lux_data:
            self.isON = lux_data['state'] == 'ON'

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

            for light in self.lights:
                if 'zigbee2mqtt' in light:
                    if not light_data:
                        light_data.update(
                            {'state' : 'ON'}
                        )

                if light in ('switch_multilevel', 'switch_binary'):
                    if not self.isON or self.isON is None:
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

        if self.has_adaptive_state:
            self.setAdaptiveLightingOff()

        light_data:dict = {}
        self.current_light_data = {'brightness' : 254}

        if not self.isON or self.isON is None:
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
        if self.isON or self.isON is None:

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

        if self.isOn:
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
                return

        if lightmode == translations.custom:
            self.lightmode = lightmode
            return

        mode = self.light_modes_by_name.get(lightmode)
        if mode is not None:
            self.lightmode = lightmode
            if mode.toggle:
                # Turns on light regardless of Lux and Conditions
                toggle_bulb = mode.toggle * 2 - 1
                self.calculateToggles(toggle_bulb = toggle_bulb)

            elif 'turn_off' in mode.state:
                # Turns off light
                self.turn_off_lights()
                self.current_toggle = 0

            return

        if (
            lightmode == translations.away
            or lightmode == translations.off
            or lightmode == translations.night
        ):
            self.lightmode = lightmode
            self.turn_off_lights()
            self.current_toggle = 0

            return

        elif (
            lightmode == translations.fire
            or lightmode == translations.wash
        ):
            self.lightmode = lightmode

            if self.current_toggle == 1:
                return

            self.calculateToggles(toggle_bulb = 1)

            return

        self.lightmode = translations.normal
        if self.current_OnCondition and self.current_LuxCondition:
            if self.current_toggle == self.toggle_lightbulb:
                return

            self.calculateToggles(toggle_bulb = self.toggle_lightbulb)

        elif not self.current_keep_on_Condition:
            self.turn_off_lights()
            self.current_toggle = 0


    def setMotion(self, lightmode:str = 'none') -> None:
        """ Sets motion lights when motion is detected insted of using setModeLight. """

        self.current_OnCondition = self.checkConditions(conditions = self.conditions) if self.conditions is not None else True
        self.current_LuxCondition = self.checkLuxConstraints()

        if lightmode == 'none':
            lightmode = self.lightmode

        if self.motionlight:
            if not self.current_OnCondition or not self.current_LuxCondition:
                return

            if (
                lightmode == translations.off
                or lightmode == translations.custom
            ):
                return

            mode = self.light_modes_by_name.get(lightmode)
            if mode is not None:
                if 'manual' in mode.state:
                    return

            self.motion = True

            # FIX: Check if motionlight is list before indexing [0]
            toggle_value = 0
            if isinstance(self.motionlight, list):
                if self.motionlight[0].toggle:
                    toggle_value = self.motionlight[0].toggle
            elif isinstance(self.motionlight, LightMode):
                if self.motionlight.toggle:
                    toggle_value = self.motionlight.toggle
            
            if toggle_value:
                # Turns on light regardless of Lux and Conditions
                toggle_bulb = toggle_value * 2 - 1

                if self.current_toggle == toggle_bulb:
                    return

                self.calculateToggles(toggle_bulb = toggle_bulb)


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