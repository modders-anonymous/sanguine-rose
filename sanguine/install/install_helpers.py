import logging
import re
import shutil
import subprocess
import sys

import sanguine.install.simple_download as simple_download
from sanguine.install._install_checks import REQUIRED_PIP_MODULES, check_sanguine_prerequisites
from sanguine.install.install_common import *


# for _install_helpers we cannot use any files with non-guaranteed dependencies, so we:
#                     1. may use only those Python modules installed by default, and
#                     2. may use only those sanguine modules which are specifically designated as install-friendly


### helpers

def _install_pip_module(module: str) -> None:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', module])


def message_box(prompt: str, spec: list[str], level: int = logging.CRITICAL) -> str:
    assert len(spec) > 0
    assert len(set([s[0].lower() for s in spec])) == len(spec)
    specstr = '/'.join(spec)
    while True:
        log_with_level(level, '{} ({})'.format(prompt, specstr))
        got = input().lower().strip()
        if got == '':
            log_with_level(level, spec[0])
            return spec[0]
        for i in range(len(spec)):
            if spec[i].lower() == got or spec[i][0].lower() == got:
                return spec[i]


def input_box(prompt: str, default: str, level: int = logging.CRITICAL) -> str:
    log_with_level(level, '{} [{}]'.format(prompt, default))
    got = input()
    if got.strip() == '':
        log_with_level(level, default)
        return default
    return got


def safe_call(cmd: list[str], shell: bool = False) -> bool:
    try:
        ret = subprocess.call(cmd, shell=shell)
        return ret == 0
    except OSError:
        return False


def safe_call_with_double_check(cmd: list[str], shell: bool = False, cwd: str | None = None) -> bool:
    if safe_call(cmd, shell=shell):
        return True
    try:
        return subprocess.call(['start', '/I'] + cmd, shell=True, cwd=cwd) == 0
    except OSError:
        return False


### install

def run_installer(cmd: list[str], sitefrom: str, msg: str) -> None:
    critical("We're about to run the following installer: {}".format(cmd[0]))
    warn("It was downloaded from {}".format(sitefrom))
    warn("Feel free to run it through your favorite virus checker,")
    warn("     but when, after entering 'Y' below, Windows will ask you stupid questions,")
    critical("     please make sure to tell Windows that you're ok with it")

    choice = message_box('Do you want to proceed?', ['Yes', 'no'])
    if choice == 'no':
        critical('Aborting installation. sanguine-rose is likely to be unusable')
        # noinspection PyProtectedMember, PyUnresolvedReferences
        os._exit(1)

    if msg:
        critical(msg)

    subprocess.check_call(cmd, shell=True)


def _tools_dir() -> str:
    return os.path.abspath(os.path.split(os.path.abspath(__file__))[0] + '\\..\\tools')


def download_file_nice_name(url: str) -> str:
    tfname = simple_download.download_temp(url)
    desired_fname = url.split('/')[-1]
    new_fname = os.path.split(tfname)[0] + '\\' + desired_fname
    assert os.path.isfile(tfname)
    shutil.move(tfname, new_fname)
    assert os.path.isfile(new_fname)
    return new_fname


def clone_github_project(githubdir: str, author: str, project: str) -> None:
    targetdir = githubdir + '\\' + author
    abort_if_not(not os.path.exists(targetdir + '\\' + project))
    if not os.path.isdir(targetdir):
        os.makedirs(targetdir)
    url = 'https://github.com/{}/{}.git'.format(author, project)
    err = safe_call_with_double_check(['git', 'clone', url], cwd=targetdir, shell=True)
    abort_if_not(err == 0)
    info('{} successfully cloned'.format(author, targetdir))


### specific installers

def _install_vs_build_tools() -> None:
    # trying to find one
    programfiles = os.environ['ProgramFiles(x86)']
    vswhere = os.path.join(programfiles, 'Microsoft Visual Studio\\Installer\\vswhere.exe')
    if os.path.exists(vswhere):
        out = subprocess.run([vswhere, '-products', 'Microsoft.VisualStudio.Product.BuildTools',
                              'Microsoft.VisualStudio.Product.Community',
                              'Microsoft.VisualStudio.Product.Professional',
                              'Microsoft.VisualStudio.Product.Enterprise'], text=True, capture_output=True)

        if out.returncode == 0:
            outstr = out.stdout
            # _print_yellow(outstr)
            m = re.search(r'productId\s*:\s*(Microsoft.VisualStudio.Product.[a-zA-Z0-9]*)', outstr)
            if m:
                info('{} found, no need to download/install Visual Studio'.format(m.group(1)))
                return

    urls = simple_download.pattern_from_url('https://visualstudio.microsoft.com/visual-cpp-build-tools/',
                                            r'href="(https://aka.ms/vs/.*/release/vs_BuildTools.exe)"')
    assert len(urls) == 1
    url = urls[0]
    info('Downloading {}...'.format(url))
    exe = download_file_nice_name(url)
    info('Download complete.')
    run_installer([exe], url, 'Make sure to check "Desktop Development with C++" checkbox.')
    info('Visual C++ build tools install started.')
    info('Please proceed with VC++ and restart {} afterwards.'.format(sys.argv[0]))
    # noinspection PyProtectedMember, PyUnresolvedReferences
    os._exit(0)


def install_sanguine_prerequisites() -> None:
    subprocess.check_call(['git', '--version'])
    _install_vs_build_tools()  # should run before installing pip modules

    for m in REQUIRED_PIP_MODULES:
        _install_pip_module(m)
        info('pip module {} successfully installed.'.format(m))

    check_sanguine_prerequisites(True)
