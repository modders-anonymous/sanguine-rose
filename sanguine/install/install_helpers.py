import re
import subprocess
import sys

import sanguine.install.simple_download as simple_download
from sanguine.install.install_checks import (REQUIRED_PIP_MODULES, check_sanguine_prerequisites,
                                             safe_call, find_command_and_add_to_path)
from sanguine.install.install_common import *
from sanguine.install.install_ui import message_box, confirm_box, BoxUINetworkErrorHandler


# for _install_helpers we cannot use any files with non-guaranteed dependencies, so we:
#                     1. may use only those Python modules installed by default, and
#                     2. may use only those sanguine modules which are specifically designated as install-friendly

### install helpers

def _install_pip_module(module: str) -> None:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', module])


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


def clone_github_project(githubdir: str, author: str, project: str,
                         errhandler: NetworkErrorHandler | None, adjustpermissions: bool = False) -> None:
    if not githubdir.endswith('\\'):
        githubdir += '\\'
    targetdir = githubdir + author
    abort_if_not(not os.path.exists(targetdir + '\\' + project))

    createddir = targetdir + '\\' + project  # we need it to adjust permissions properly
    if not os.path.isdir(targetdir):
        createddir = targetdir
        while True:
            spl = os.path.split(createddir)[0]
            if os.path.isdir(spl):
                break
            createddir = spl
        os.makedirs(targetdir)
    url = 'https://github.com/{}/{}.git'.format(author, project)
    cmd = ['git', 'clone', url]
    info(' '.join(cmd))
    while True:
        ok = safe_call(cmd, cwd=targetdir, shell=True)
        if ok:
            break
        alert('git clone of {} failed'.format(url))
        if errhandler and errhandler.handle_error('Cloning {}'.format(url), 99999):
            continue
        raise SanguinicError('Cloning of {} failed:'.format(url))

    info('{}/{} successfully cloned'.format(author, targetdir))
    if createddir and adjustpermissions:
        user = os.environ['userdomain'] + '\\' + os.environ['username']
        cmd2 = ['icacls', createddir, '/setowner', user, '/t', '/l']
        info('Adjusting permissions of {}...'.format(createddir))
        ok = safe_call(cmd2, shell=True)
        if not ok:
            alert(
                'Cannot adjust permissions on created folder {} (error in command {}), you may need to deal with it yourself'.format(
                    createddir, str(cmd2)))


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
    _install_vs_build_tools()  # should run before installing pip modules

    for m in REQUIRED_PIP_MODULES:
        _install_pip_module(m)
        info('pip module {} successfully installed.'.format(m))

    check_sanguine_prerequisites(True)
