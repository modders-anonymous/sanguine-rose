import importlib
import logging
import re
import subprocess
import sys

# for install_checks we cannot use any files with non-guaranteed dependencies, so we:
#                    1. may use only those Python modules installed by default, and
#                    2. may use only those sanguine modules which are specifically designated as install-friendly
from sanguine.install.install_common import *
from sanguine.install.install_ui import message_box

REQUIRED_PIP_MODULES = ['json5', 'bethesda-structs', 'pywin32', 'pyinstaller']
PIP2PYTHON_MODULE_NAME_REMAPPING = {'bethesda-structs': 'bethesda_structs', 'pywin32': ['win32api', 'win32file'],
                                    'pyinstaller': []}


def _is_module_installed(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


def _not_installed(msg: str) -> None:
    critical(msg)
    critical('Aborting. Please make sure to run sanguine-rose/sanguine-install-dependencies.py')
    # noinspection PyProtectedMember, PyUnresolvedReferences
    os._exit(1)


def _check_module(m: str) -> None:
    if not _is_module_installed(m):
        _not_installed('Module {} is not installed.'.format(m))


def report_hostile_programs() -> None:
    try:
        tasklist = subprocess.check_output(['tasklist'])
        tasklist = tasklist.decode('ascii')
    except OSError:
        alert('Cannot run tasklist: hostile program detection may not work')
        tasklist = None

    if tasklist:
        norton = re.search('nortonsecurity.exe', tasklist, re.IGNORECASE)
        if norton:
            critical(
                'It seems that you have Norton antivirus running. It was reported to cause severe problems with modding.')
            critical('It is STRONGLY suggested to quit, uninstall Norton antivirus, reboot, and re-launch {}.'.format(
                sys.argv[0]))
            alert('After removing Norton antivirus, you may want to enable Windows Defender.')
            choice = message_box('Are you ok with this suggestion?',
                                 ['Yes', 'no'], level=logging.CRITICAL)
            if choice != 'no':
                alert('Exiting. Please uninstall Norton antivirus, reboot, optionally enable Windows Defender, and re-launch {}.'.format(sys.argv[0]))
                sys.exit(1)


def check_sanguine_prerequisites(frominstall: bool = False) -> None:
    if not sys.version_info >= (3, 10):
        critical('Sorry, sanguine-rose needs at least Python 3.10')
        sys.exit(1)

    # we don't really need to check for MSVC being installed, as without it some of the pip modules won't be available

    for m in REQUIRED_PIP_MODULES:
        if m in PIP2PYTHON_MODULE_NAME_REMAPPING:
            val = PIP2PYTHON_MODULE_NAME_REMAPPING[m]
            if isinstance(val, list):
                for v in val:
                    _check_module(v)
            else:
                _check_module(val)
        else:
            _check_module(m)

    if subprocess.call(['git', '--version']) != 0:
        critical('git is not found in PATH.')
        critical(
            '{}Please make sure to install "Git for Windows" or "GitHub Desktop" (preferred) and include folder with git.exe into PATH.'.format(
                'Aborting. ' if frominstall else ''
            ))
        # noinspection PyProtectedMember, PyUnresolvedReferences
        os._exit(1)

    report_hostile_programs()

    info('All sanguine prerequisites are ok.')
