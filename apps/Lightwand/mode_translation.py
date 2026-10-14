""" ModeTranslation by Pythm

    Loads the mode names (and the event name) that Lightwand and every app that
    follows the MODE_CHANGE convention uses. You only need this app if you
    translate or rename modes. With English mode names nothing needs to be configured.

    Add it once and let the apps that use mode names depend on it, so it always starts first:

        mode_translation:
          module: mode_translation
          class: ModeTranslation
          language_file: /conf/persistent/lightwand/translations.json
          language: "no"

        your_room_name:
          module: lightwand
          class: Room
          dependencies: mode_translation

    Be careful with `dependencies`: AppDaemon will not start ANY app if a name in
    `dependencies` does not exist as an app in your configuration.

    @Pythm / https://github.com/Pythm
"""

__version__ = "1.0.0"

from appdaemon import adbase as ad

from translations_lightmodes import translations

class ModeTranslation(ad.ADBase):

    def initialize(self) -> None:
        self.ADapi = self.get_ad_api()

        language_file = self.args.get('language_file', None)
        # 'lightwand_language' is the name used by the room apps and is accepted here as well.
        language = self.args.get('language', self.args.get('lightwand_language', None))

        try:
            translations.configure(language_file = language_file, language = language)
        except Exception as e:
            self.ADapi.log(
                f"Not able to apply language_file {language_file} / language {language}: {e}. "
                f"Using language '{translations.language}' with the previously loaded file.",
                level = 'ERROR'
            )

        self.ADapi.log(
            f"Mode translation ready. Language: {translations.language}. "
            f"Event: {translations.MODE_CHANGE}. "
            f"automagical: {translations.automagical}, morning: {translations.morning}, "
            f"night: {translations.night}, away: {translations.away}, off: {translations.off}, "
            f"fire: {translations.fire}, false_alarm: {translations.false_alarm}, "
            f"custom: {translations.custom}, wash: {translations.wash}, reset: {translations.reset}",
            level = 'INFO'
        )
