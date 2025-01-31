import logging

from sanguine.install.install_common import NetworkErrorHandler, LinearUI, LinearUIImportance
from sanguine.install.install_logging import log_with_level


class _BoxUINetworkErrorHandler(NetworkErrorHandler):
    ui: "InstallUI"
    initial_retries: int
    remaining_retries: int

    def __init__(self, ui: "InstallUI", retries: int) -> None:
        self.ui = ui
        self.initial_retries = retries
        self.remaining_retries = retries

    def handle_error(self, op: str, errno: int) -> bool:
        self.remaining_retries -= 1
        if self.remaining_retries <= 0:
            choice = self.ui.message_box(
                '{} failed. Please check your Internet connection. Do you want to retry?'.format(op),
                ['Yes', 'no'])
            return choice != 'no'
        else:
            return True


class InstallUI(LinearUI):
    _silent_mode: bool

    def __init__(self) -> None:
        self._silent_mode = False

    def set_silent_mode(self) -> None:
        self._silent_mode = True

    def message_box(self, prompt: str, spec: list[str], level: LinearUIImportance = LinearUIImportance.Default) -> str:
        assert len(spec) > 0
        assert len(set([s[0].lower() for s in spec])) == len(spec)
        specstr = '/'.join(spec)
        while True:
            log_with_level(InstallUI._translate_level(level), '{} ({})'.format(prompt, specstr))
            got = '' if self._silent_mode else input().lower().strip()
            if got == '':
                log_with_level(level, spec[0])
                return spec[0]
            for i in range(len(spec)):
                if spec[i].lower() == got or spec[i][0].lower() == got:
                    return spec[i]

    def input_box(self, prompt: str, default: str, level: LinearUIImportance = LinearUIImportance.Default) -> str:
        log_with_level(InstallUI._translate_level(level), '{} [{}]'.format(prompt, default))
        got = '' if self._silent_mode else input()
        if got.strip() == '':
            log_with_level(InstallUI._translate_level(level), default)
            return default
        return got

    def confirm_box(self, prompt: str, level: LinearUIImportance = LinearUIImportance.Default) -> None:
        log_with_level(InstallUI._translate_level(level), prompt)
        if not self._silent_mode:
            input()

    def network_error_handler(self, nretries: int) -> NetworkErrorHandler:
        return _BoxUINetworkErrorHandler(self, nretries)

    @staticmethod
    def _translate_level(level: LinearUIImportance = LinearUIImportance.Default) -> int:
        match level:
            case LinearUIImportance.Default:
                return logging.INFO
            case LinearUIImportance.Important:
                return logging.ERROR
            case LinearUIImportance.VeryImportant:
                return logging.CRITICAL
