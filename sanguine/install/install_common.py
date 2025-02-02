# part of common.py which can be used in install scripts too
# noinspection PyUnresolvedReferences
import os
import traceback
import typing
# noinspection PyUnresolvedReferences
from abc import ABC, abstractmethod
# noinspection PyUnresolvedReferences
from collections.abc import Callable, Generator, Iterable
# noinspection PyUnresolvedReferences
from enum import Enum, IntEnum, Flag, IntFlag
# noinspection PyUnresolvedReferences
from types import TracebackType

Type = typing.Type
Any = typing.Any
ConfigData = dict[str, Any]

# noinspection PyUnresolvedReferences
from sanguine.install.install_logging import (debug, info, perf_warn, warn, alert, critical,
                                              info_or_perf_warn, log_with_level,
                                              enable_ex_logging, add_file_logging)


### error-handling related

class NetworkErrorHandler:
    @abstractmethod
    def handle_error(self, op: str, errno: int) -> bool:
        pass


class SanguinicError(Exception):
    pass


def raise_if_not(cond: bool, msg: Callable[[], str] | str | None = None):
    # 'always assert', even if __debug__ is False.
    # msg is a string or lambda which returns error message
    if not cond:
        msg1 = 'raise_if_not() failed'
        if msg is not None:
            if callable(msg):
                msg1 += ': ' + msg()
            elif isinstance(msg, str):
                msg1 += ': ' + msg
            else:
                assert False
        where = traceback.extract_stack(limit=2)[0]
        critical(msg1 + ' @line ' + str(where.lineno) + ' of ' + os.path.split(where.filename)[1])
        raise SanguinicError(msg1)


# helpers

def open_3rdparty_txt_file_with_encoding(fname: str, encoding: str) -> typing.TextIO:
    return open(fname, 'rt', encoding=encoding, errors='replace')


#  all our dir and file names are always in lowercase, and always end with '\\'

def normalize_dir_path(path: str) -> str:
    path = os.path.abspath(path)
    assert '/' not in path
    assert not path.endswith('\\')
    return path.lower() + '\\'


def is_normalized_dir_path(path: str) -> bool:
    return path == os.path.abspath(path).lower() + '\\'


def normalize_file_path(path: str) -> str:
    assert not path.endswith('\\') and not path.endswith('/')
    path = os.path.abspath(path)
    assert '/' not in path
    return path.lower()


def is_normalized_file_path(path: str) -> bool:
    return path == os.path.abspath(path).lower()


def is_normalized_path(path: str) -> bool:
    return path == os.path.abspath(path).lower()


def to_short_path(base: str, path: str) -> str:
    assert path.startswith(base)
    return path[len(base):]


def is_short_file_path(fpath: str) -> bool:
    assert not fpath.endswith('\\') and not fpath.endswith('/')
    if not fpath.islower(): return False
    return not os.path.isabs(fpath)


def is_short_dir_path(fpath: str) -> bool:
    return fpath.islower() and fpath.endswith('\\') and not os.path.isabs(fpath)


def is_normalized_file_name(fname: str) -> bool:
    if '/' in fname or '\\' in fname: return False
    return fname.islower()


def normalize_file_name(fname: str) -> str:
    assert '\\' not in fname and '/' not in fname
    return fname.lower()


# UI

class LinearUIImportance(IntEnum):
    Default = 0
    Important = 1
    VeryImportant = 2


class LinearUITextInput:
    name: str
    value: str
    disabled: bool
    extra_data: Any

    def __init__(self, name: str, initvalue: str) -> None:
        self.name = name
        self.value = initvalue
        self.disabled = False
        self.extra_data = None


class LinearUICheckbox:
    name: str
    value: bool
    is_radio: bool
    disabled: bool
    extra_data: Any

    def __init__(self, name: str, initvalue: bool, isradio: bool = False) -> None:
        self.name = name
        self.value = initvalue
        self.is_radio = isradio
        self.disabled = False
        self.extra_data = None


type LinearUIControl = LinearUITextInput | LinearUICheckbox | "LinearUIGroup"


class LinearUIGroup:
    name: str
    controls: list[LinearUIControl]
    checkboxes_are_radio: bool | None
    extra_data: Any

    def __init__(self, name: str, controls: list[LinearUIControl]) -> None:
        self.name = name
        self.controls = controls
        self.checkboxes_are_radio = None
        self.extra_data = None
        for ctrl in controls:
            if isinstance(ctrl, LinearUICheckbox):
                if self.checkboxes_are_radio is None:
                    self.checkboxes_are_radio = ctrl.is_radio
                    if __debug__:
                        break
                else:
                    assert self.checkboxes_are_radio == ctrl.is_radio

    def add_control(self, ctrl: LinearUIControl) -> None:
        self.controls.append(ctrl)
        if isinstance(ctrl, LinearUICheckbox):
            if self.checkboxes_are_radio is None:
                self.checkboxes_are_radio = ctrl.is_radio
            else:
                assert self.checkboxes_are_radio == ctrl.is_radio

    def find_control(self, name: str) -> LinearUIControl | None:
        for ctrl in self.controls:
            if ctrl.name == name:
                return ctrl
        return None

    def find_control_by_path(self, path: list[str]) -> LinearUIControl | None:
        for ctrl in self.controls:
            if ctrl.name == path[0]:
                if isinstance(ctrl, LinearUIGroup):
                    return ctrl.find_control_by_path(path[1:])
                else:
                    return None
        return None


class LinearUI:
    @abstractmethod
    def set_silent_mode(self) -> None:
        pass

    @abstractmethod
    def message_box(self, prompt: str, spec: list[str], level: LinearUIImportance = LinearUIImportance.Default) -> str:
        pass

    @abstractmethod
    def input_box(self, prompt: str, default: str, level: LinearUIImportance = LinearUIImportance.Default) -> str:
        pass

    @abstractmethod
    def confirm_box(self, prompt: str, level: LinearUIImportance = LinearUIImportance.Default) -> None:
        pass

    @abstractmethod
    def network_error_handler(self, nretries: int) -> NetworkErrorHandler:
        pass

    @abstractmethod
    def wizard_page(self, wizardpage: LinearUIGroup,
                    validator: Callable[[LinearUIGroup], str | None] | None = None) -> None:
        pass
