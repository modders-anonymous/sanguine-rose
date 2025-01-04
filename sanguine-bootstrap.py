import os
import re
import subprocess
import sys

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

from sanguine.install.install_common import *
from sanguine.install.install_helpers import install_sanguine_prerequisites, _run_installer, _download_file_nice_name, \
    _yesno
from sanguine.install.simple_download import pattern_from_url

critical('This will install sanguine from scratch, including, if necessary, installing python and git.')
ok = _yesno('Do you want to proceed (Y/N)?')
if not ok:
    critical('Exiting.')

### download and install python
if subprocess.call(['py', '--version']) == 0:
    info('py found, no need to download and install python')
else:
    info('py not found, need to download and install python')
    dlurl = pattern_from_url('https://python.org/downloads/',
                             r'(https://www\.python\.org/ftp/python/3\.[0-9.]*/python-3\.[0-9.]*-amd64.exe)')
    abort_if_not(len(dlurl) == 1)
    info('Downloading {}...'.format(dlurl[0]))
    pyinstallexe = _download_file_nice_name(dlurl[0])
    _run_installer([pyinstallexe, '/quiet', 'InstallAllUsers=1', 'PrependPath=1'], 'python.org', '')

### download and install git
if subprocess.call(['git', '--version']) == 0:
    info('git found, no need to download and install git')
else:
    info('git not found, need to download and install git')
    tags = pattern_from_url('https://gitforwindows.org/',
                            r'https://github.com/git-for-windows/git/releases/tag/([a-zA-Z0-9.]*)"')
    abort_if_not(len(tags) == 1)
    tag = tags[0]
    m = re.match(r'v([0-9.]*)\.windows\.[0-9]*', tag)
    abort_if_not(bool(m))
    ver = m.group(1)
    url = 'https://github.com/git-for-windows/git/releases/download/{}/Git-{}-64-bit.exe'.format(tag, ver)
    info('Downloading {}...'.format(url))
    gitinstallexe = _download_file_nice_name(url)
    _run_installer([gitinstallexe, '/SP-', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], 'github.com', '')

install_sanguine_prerequisites()
