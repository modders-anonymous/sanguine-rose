import logging

from sanguine.install.install_common import *
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

    def wizard_page(self, wizardpage: LinearUIGroup,
                    validator: Callable[[LinearUIGroup], str | None] | None = None) -> None:
        stack = []
        while True:
            if len(stack) == 0:
                curgrp = wizardpage
                curgrptype = 'wizard page'
            else:
                curgrp = wizardpage.find_control_by_path(stack)
                curgrptype = 'current group page'
                info('Current group: {}'.format(repr(stack)))
            assert curgrp is not None
            for i, ctrl in enumerate(curgrp.controls):
                InstallUI._print_control(i, ctrl)
            info('[p] to print the whole {}'.format(curgrptype))
            info('[x] to exit {} with current settings'.format(curgrptype))

            got = 'x' if self._silent_mode else input().lower().strip()
            if got == 'x':
                if len(stack) == 0:
                    if validator is not None:
                        errmsg = validator(wizardpage)
                    else:
                        errmsg = None
                    if errmsg is None:
                        break
                    else:
                        alert('Error validating wizard page: {}'.format(errmsg))
                else:
                    stack.pop()
            elif got == 'p':
                for i, ctrl in enumerate(curgrp.controls):
                    InstallUI._print_control(i, ctrl, True)
            elif got.isdigit():
                idx = int(got)
                if 0 <= idx <= len(curgrp.controls):
                    ctrl = curgrp.controls[idx]
                    if isinstance(ctrl, LinearUIGroup):
                        stack.append(ctrl.name)
                        continue
                    elif isinstance(ctrl, LinearUICheckbox):
                        if not ctrl.disabled:
                            if ctrl.is_radio:
                                assert curgrp.checkboxes_are_radio
                                for c2 in curgrp.controls:
                                    if isinstance(c2, LinearUICheckbox):
                                        c2.value = False
                                ctrl.value = True
                            else:
                                assert not curgrp.checkboxes_are_radio
                                ctrl.value = not ctrl.value
                    elif isinstance(ctrl, LinearUITextInput):
                        assert not self._silent_mode
                        if not ctrl.disabled:
                            got2 = input().strip()
                            ctrl.value = got2
            else:
                pass

    @staticmethod
    def _print_control(i: int | str, ctrl: LinearUIControl, recursive: bool = False) -> None:
        assert isinstance(i, (int, str))
        prefix = '[{}]'.format(i) if isinstance(i, int) else i
        if isinstance(ctrl, LinearUITextInput):
            info('{}{}:{}'.format(prefix, ctrl.name, ctrl.value))
        elif isinstance(ctrl, LinearUICheckbox):
            info('{}{}:[{}]'.format(prefix, ctrl.name, 'X' if ctrl.value else ' '))
        elif isinstance(ctrl, LinearUIGroup):
            if recursive:
                info('{}{{{}}}:'.format(prefix, ctrl.name))
                if isinstance(i, int):
                    for ctrl in ctrl.controls:
                        InstallUI._print_control('  ', ctrl)
                else:
                    for ctrl in ctrl.controls:
                        InstallUI._print_control(prefix + '  ', ctrl)
            else:
                info('{}{{{}}} (group of {} elements)'.format(prefix, ctrl.name, len(ctrl.controls)))
        else:
            assert False

    @staticmethod
    def _translate_level(level: LinearUIImportance = LinearUIImportance.Default) -> int:
        match level:
            case LinearUIImportance.Default:
                return logging.INFO
            case LinearUIImportance.Important:
                return logging.ERROR
            case LinearUIImportance.VeryImportant:
                return logging.CRITICAL
