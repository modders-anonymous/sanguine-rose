import re
import subprocess
import sys

from sanguine.install.install_checks import (REQUIRED_PIP_MODULES, find_command_and_add_to_path)
from sanguine.install.install_common import *
from sanguine.install.install_ui import message_box, confirm_box, BoxUINetworkErrorHandler


# for _install_helpers we cannot use any files with non-guaranteed dependencies, so we:
#                     1. may use only those Python modules installed by default, and
#                     2. may use only those sanguine modules which are specifically designated as install-friendly

### install helpers

def _install_pip_module(module: str) -> None:
    subprocess.check_call(['py', '-m', 'pip', 'install', module])


### install

def run_installer(cmd: list[str], sitefrom: str, msg: str) -> None:
    alert("We're about to run the following installer: {}".format(cmd[0]))
    info("It was downloaded from {}".format(sitefrom))
    info("Feel free to run it through your favorite virus checker,")
    info("     but when, after entering 'Y' below, Windows will ask you stupid questions,")
    alert("     please make sure to tell Windows that you're ok with it")

    choice = message_box('Do you want to proceed?', ['Yes', 'no'])
    if choice == 'no':
        critical('Aborting installation. sanguine-rose is likely to be unusable')
        # noinspection PyProtectedMember, PyUnresolvedReferences
        os._exit(1)

    if msg:
        alert(msg)

    subprocess.check_call(cmd, shell=True)


def _tools_dir() -> str:
    return os.path.abspath(os.path.split(os.path.abspath(__file__))[0] + '\\..\\tools')


### specific installers

def _install_vs_build_tools() -> None:
    import sanguine.install.simple_download as simple_download
    # importing only here, not at the beginning, to ensure that we already have certifi installed

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
    exe = simple_download.download_temp(url, BoxUINetworkErrorHandler(2))
    info('Download complete.')
    run_installer([exe], url, 'Make sure to check "Desktop Development with C++" checkbox.')
    info('Visual C++ build tools install started.')
    alert('Please proceed with VC++ install and restart {} afterwards.'.format(sys.argv[0]))
    confirm_box('Press any key to exit {} now.'.format(sys.argv[0]))
    # noinspection PyProtectedMember, PyUnresolvedReferences
    os._exit(0)


def install_sanguine_prerequisites() -> None:
    gitok = find_command_and_add_to_path(['git', '--version'])
    abort_if_not(gitok)

    info('Installing certifi...')
    _install_pip_module('certifi')  # needed to run simple_download within _install_vs_build_tools()
    info('certifi installed.')

    _install_vs_build_tools()  # should run before installing pip modules

    for m in REQUIRED_PIP_MODULES:
        _install_pip_module(m)
        info('pip module {} successfully installed.'.format(m))

    # check_sanguine_prerequisites(True) - should not call check_sanguine_prerequisites() here, seems to fail if called right after install
