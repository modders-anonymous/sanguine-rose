import logging
import os
import re
import subprocess
import sys

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

from sanguine.install.install_common import *
from sanguine.install.install_helpers import (run_installer, download_file_nice_name,
                                              message_box, input_box, clone_github_project, safe_call)
from sanguine.install.simple_download import pattern_from_url

critical('This will install sanguine-rose from scratch, including, if necessary, installing python.')
choice = message_box('Do you want to proceed?', ['Yes', 'no'])
if choice == 'no':
    critical('Exiting.')
    sys.exit()

### download and install python
if safe_call(['py', '--version'], shell=True):
    info('py found, no need to download and install python')
else:
    info('py not found, need to download and install python')
    dlurl = pattern_from_url('https://python.org/downloads/',
                             r'(https://www\.python\.org/ftp/python/3\.[0-9.]*/python-3\.[0-9.]*-amd64.exe)')
    abort_if_not(len(dlurl) == 1)
    info('Downloading {}...'.format(dlurl[0]))
    pyinstallexe = download_file_nice_name(dlurl[0])
    run_installer([pyinstallexe, '/quiet', 'InstallAllUsers=1', 'PrependPath=1'], 'python.org',
                  'Make sure to find permission request window in your taskbar and allow proceeding with installation.\n'
                  + '    Afterwards, install will continue in silent mode and may take up to 5 minutes.')

if safe_call(['git', '--version']):
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
    gitinstallexe = download_file_nice_name(url)
    run_installer([gitinstallexe, '/SP-', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], 'github.com',
                  'Make sure to find permission request window in your taskbar and allow proceeding with installation.\n'
                  + '    Afterwards, install will continue in silent mode and may take up to 5 minutes.')

skiprepo = False
while True:
    githubdir = input_box('Where do you want to install Github projects (including sanguine-rose)?',
                          'C:\\Modding\\GitHub', level=logging.ERROR)
    if os.path.isdir(githubdir):
        sanguinedir = githubdir + '\\modders-anonymous\\sanguine-rose'
        sanguinelitmusdir = sanguinedir + '\\sanguine'
        if os.path.isdir(sanguinelitmusdir):
            info(
                'It seems that you already have sanguine-rose installed. Will proceed without downlading sanguine-rose.')
            skiprepo = True
            break
        if os.path.isdir(sanguinedir):
            alert('Folder {} already exists. Please choose another folder for GitHub projects.')
        else:
            break
    else:
        break

sanguinedir = githubdir + '\\modders-anonymous\\sanguine-rose'
if not skiprepo:
    clone_github_project(githubdir, 'modders-anonymous', 'sanguine-rose')

info(
    'Bootstrapping completed. Now you do not need {} anymore, and should use scripts in {} instead.'.format(sys.argv[0],
                                                                                                            sanguinedir))
info('You still need to run {}\\sanguine-install-dependencies.py'.format(sanguinedir))
choice = message_box('Do you want to run it now?', ['Yes', 'no'], level=logging.ERROR)
if choice == 'no':
    info('{}\\sanguine-install-dependencies.py was not run, make sure to run it before using sanguine-rose'.format(
        sanguinedir))
else:
    cmd = '{}\\sanguine-install-dependencies.py'.format(sanguinedir)
    info('Running {}...'.format(cmd))
    subprocess.check_call([cmd], shell=True)
    info('Dependencies installed successfully, you are ready to run sanguine-rose')
