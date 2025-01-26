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

REQUIRED_PIP_MODULES = ['json5', 'bethesda-structs', 'pywin32', 'certifi', 'pyinstaller', 'chardet']
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


def safe_call(cmd: list[str], shell: bool = False, cwd: str | None = None) -> bool:
    try:
        ret = subprocess.call(cmd, shell=shell, cwd=cwd)
        return ret == 0
    except OSError:
        return False


def find_command_and_add_to_path(cmd: list[str], shell: bool = False) -> bool:
    """
    adjusts PATH environment variable to include a command if necessary
    it will be inherited by child processes too
    :return: success
    """
    if safe_call(cmd, shell=shell):
        return True

    warn('Cannot run {} using current PATH, will try looking for PATH in registry...'.format(cmd[0]))
    out = subprocess.check_output(
        ['reg', 'query', 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment', '/v', 'PATH'])
    out = out.decode('ascii')
    # print('out:'+out+'\n')
    m = re.search(r'\s*PATH\s*REG_EXPAND_SZ\s*(.*)', out)
    if m and len(m.group(1)) > len(os.environ['PATH']):
        info('registry PATH was recently changed, trying with registry PATH')
        os.environ['PATH'] = m.group(1)
        info('new PATH='.format(os.environ['PATH']))
        if safe_call(cmd, shell=shell):
            info('registry PATH did the trick')
            return True

    # last resort: direct search in Program Files
    warn('Cannot run {} using registry PATH, will try looking for executable in Program Files...'.format(cmd[0]))
    for pf in [os.environ['ProgramFiles'], os.environ['ProgramFiles(x86)']]:
        for curdir, _, files in os.walk(pf):
            for f in files:
                fname, fext = os.path.splitext(f)
                if fname == cmd[0] and (fext == '.exe' or fext == '.bat'):
                    info('found {} in {}, prepending it to PATH...'.format(cmd[0], pf))
                    os.environ['PATH'] = curdir + ';' + os.environ['PATH']
                    info('new PATH='.format(os.environ['PATH']))
                    if safe_call(cmd, shell=shell):
                        info('Adding {} to PATH did the trick'.format(curdir))
                        return True
    warn('My heuristics exhausted, cannot find {} to run'.format(cmd[0]))
    return False


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
                alert(
                    'Exiting. Please uninstall Norton antivirus, reboot, optionally enable Windows Defender, and re-launch {}.'.format(
                        sys.argv[0]))
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

    gitok = find_command_and_add_to_path(['git', '--version'])
    if not gitok:
        critical('git is not found in PATH.')
        critical(
            '{}Please make sure to install "Git for Windows" or "GitHub Desktop" (preferred) and include folder with git.exe into PATH.'.format(
                'Aborting. ' if frominstall else ''
            ))
        # noinspection PyProtectedMember, PyUnresolvedReferences
        os._exit(1)

    report_hostile_programs()

    info('All sanguine prerequisites are ok.')
