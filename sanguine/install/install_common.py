# part of common.py which can be used in install scripts too

# noinspection PyUnresolvedReferences
import enum
import os
import traceback
import typing
# noinspection PyUnresolvedReferences
from abc import ABC, abstractmethod
# noinspection PyUnresolvedReferences
from collections.abc import Callable, Generator, Iterable
# noinspection PyUnresolvedReferences
from types import TracebackType

Type = typing.Type

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


def abort_if_not(cond: bool, msg: Callable[[], str] | str | None = None):
    # 'always assert', even if __debug__ is False.
    # msg is a string or lambda which returns error message
    if not cond:
        msg1 = 'abort_if_not() failed'
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

def open_3rdparty_txt_file(fname: str) -> typing.TextIO:
    return open(fname, 'rt', encoding='cp1252', errors='replace')


def open_3rdparty_txt_file_w(fname) -> typing.TextIO:
    return open(fname, 'wt', encoding='cp1252')


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
