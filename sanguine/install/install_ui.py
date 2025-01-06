import logging

from sanguine.install.install_common import NetworkErrorHandler
from sanguine.install.install_logging import log_with_level

_silent_mode: bool = False


def set_silent_mode() -> None:
    global _silent_mode
    _silent_mode = True


def message_box(prompt: str, spec: list[str], level: int = logging.ERROR) -> str:
    global _silent_mode
    assert len(spec) > 0
    assert len(set([s[0].lower() for s in spec])) == len(spec)
    specstr = '/'.join(spec)
    while True:
        log_with_level(level, '{} ({})'.format(prompt, specstr))
        got = '' if _silent_mode else input().lower().strip()
        if got == '':
            log_with_level(level, spec[0])
            return spec[0]
        for i in range(len(spec)):
            if spec[i].lower() == got or spec[i][0].lower() == got:
                return spec[i]


def input_box(prompt: str, default: str, level: int = logging.ERROR) -> str:
    global _silent_mode
    log_with_level(level, '{} [{}]'.format(prompt, default))
    got = '' if _silent_mode else input()
    if got.strip() == '':
        log_with_level(level, default)
        return default
    return got


def confirm_box(prompt: str, level: int = logging.ERROR) -> None:
    global _silent_mode
    log_with_level(level, prompt)
    if not _silent_mode:
        input()


class BoxUINetworkErrorHandler(NetworkErrorHandler):
    initial_retries: int
    remaining_retries: int

    def __init__(self, retries: int) -> None:
        self.initial_retries = retries
        self.remaining_retries = retries

    def handle_error(self, op: str, errno: int) -> bool:
        self.remaining_retries -= 1
        if self.remaining_retries <= 0:
            choice = message_box('{} failed. Please check your Internet connection. Do you want to retry?'.format(op),
                                 ['Yes', 'no'])
            return choice != 'no'
        else:
            return True
