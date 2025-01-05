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

def confirm_box(prompt: str, level: int = logging.ERROR) -> None:
    log_with_level(level, prompt)
    input()


def safe_call(cmd: list[str], shell: bool = False, cwd: str | None = None) -> bool:
    try:
        ret = subprocess.call(cmd, shell=shell, cwd=cwd)
        return ret == 0
    except OSError:
        return False


def safe_call_with_double_check(cmd: list[str], shell: bool = False, cwd: str | None = None) -> bool:
    if safe_call(cmd, shell=shell, cwd=cwd):
        return True

    warn('Cannot run {} using current PATH, will try looking for PATH in registry...'.format(cmd[0]))
    out = subprocess.check_output(
        ['reg', 'query', 'HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment', '/v', 'PATH'])
    out = out.decode('ascii')
    # print('out:'+out+'\n')
    m = re.search(r'\s*PATH\s*REG_EXPAND_SZ\s*(.*)', out)
    if not m:
        return False

    reg_path = m.group(1).lower()
    # print(reg_path+'\n')
    for e in os.environ.keys():
        subst = '%' + e.lower() + '%'
        # print(subst+'->'+os.environ[e])
        reg_path = reg_path.replace(subst, os.environ[e])
    # print(reg_path+'\n')
    reg_path_split = reg_path.split(';')
    reg_path_split = [p.strip().lower() for p in reg_path_split]
    env_path = os.environ['PATH'].lower()
    env_path_split = env_path.split(';')
    env_path_split = [p.strip() for p in env_path_split]
    remainder = []
    for d in reg_path_split:
        if d not in env_path_split:
            remainder.append(d)
    for d in remainder:
        info('Found recently appended PATH in registry: {}'.format(d))
        if not d.endswith('\\'):
            d += '\\'
        cmd1 = [d + cmd[0]] + cmd[1:]
        # print(cmd1)
        if safe_call(cmd1, shell=shell, cwd=cwd):
            return True

    # last resort: direct search in Program Files
    warn('Cannot run {} using registry PATH, will try looking for executable in Program Files...'.format(cmd[0]))
    pf = os.environ['ProgramFiles']
    for curdir, _, files in os.walk(pf):
        for f in files:
            fname, fext = os.path.splitext(f)
            if fname == cmd[0] and (fext == '.exe' or fext == '.bat'):
                cmd1 = [curdir + '\\' + cmd[0]] + cmd[1:]
                if safe_call(cmd1, shell=shell, cwd=cwd):
                    return True
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
    ok = safe_call_with_double_check(['git', 'clone', url], cwd=targetdir, shell=True)
    abort_if_not(ok)
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
    alert('Please proceed with VC++ install and restart {} afterwards.'.format(sys.argv[0]))
    confirm_box('Press any key to exit {} now.'.format(sys.argv[0]))
    # noinspection PyProtectedMember, PyUnresolvedReferences
    os._exit(0)


def install_sanguine_prerequisites() -> None:
    ok = safe_call_with_double_check(['git', '--version'])
    abort_if_not(ok)
    _install_vs_build_tools()  # should run before installing pip modules

    for m in REQUIRED_PIP_MODULES:
        _install_pip_module(m)
        info('pip module {} successfully installed.'.format(m))

    check_sanguine_prerequisites(True)
