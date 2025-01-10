# dash in the .py file name is non-Pythonic only for module files, and not for end-user scripts

import os
import sys
import time

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

from sanguine.install.install_github import github_project_exists, clone_github_project
from sanguine.install.install_ui import BoxUINetworkErrorHandler
from sanguine.common import *
from sanguine.install.install_checks import check_sanguine_prerequisites
from sanguine.install.install_ui import input_box
from sanguine.helpers.project_config import LocalProjectConfig
from sanguine.install.install_github import GithubFolder
import sanguine.tasks as tasks
from sanguine.cache.whole_cache import WholeCache
from sanguine.commands.togithub import togithub


def _usage() -> None:
    thisscriptcall = os.path.split(sys.argv[0])[0]
    info('usage:')
    info('-> {} <ProjectConfig.json5>'.format(thisscriptcall))


if __name__ == '__main__':
    argv = sys.argv[1:]
    if len(sys.argv) == 2 and sys.argv[1] == 'test':
        if not os.path.isdir('../../KTAGirl/KTA'):
            clone_github_project('../../', GithubFolder('KTAGirl/KTA'), BoxUINetworkErrorHandler(2))
        argv = ['../../KTAGirl/KTA\\KTA.json5']

    if len(argv) != 1:
        _usage()
        sys.exit(1)

    check_sanguine_prerequisites()

    cfgfname = argv[0]
    abort_if_not(os.path.isfile(cfgfname))
    cfgfname = normalize_file_path(cfgfname)
    cfg = LocalProjectConfig(cfgfname)
    add_file_logging(cfg.tmp_dir + 'sanguine.log.html')
    enable_ex_logging()

    wcache = WholeCache(cfg)
    with tasks.Parallel(None, taskstatsofinterest=wcache.stats_of_interest(), dbg_serialize=False) as tparallel:
        t0 = time.perf_counter()
        wcache.start_tasks(tparallel)
        tparallel.run([])
    wcache.done()

    while True:
        cmd = input_box('Enter Command:', '')
        try:
            info(cmd)
            command: list[str] = cmd.split(' ')
            if len(command) == 0:
                command = ['h']
            match command[0]:
                case 'x' | 'exit':
                    info('Exiting...')
                    sys.exit(0)

                case 'github.install':
                    if len(command) < 2:
                        alert('wrong number of parameters, use help to ask for syntax')
                    else:
                        authorproject = command[1]
                        gf = GithubFolder(authorproject)
                        ok = github_project_exists(cfg.github_root_dir, gf)
                        pd = gf.folder(cfg.github_root_dir)
                        if ok == 1:
                            info('Project {} already exists'.format(pd))
                        elif ok == -1:
                            alert('Folder {} already exists, but does not contain expected github project'.format(pd))
                        else:
                            assert ok == 0
                            info('Cloning {}...'.format(pd))
                            clone_github_project(cfg.github_root_dir, gf, BoxUINetworkErrorHandler(2))

                case 'togithub':
                    togithub(wcache)

                case 'h' | 'help' | '' | _:
                    info('commands:')
                    info('-> h|help')
                    info('-> x|exit')
                    info('-> github.install <author> <project>')
                    info('-> togithub')

        except Exception as e:
            alert('Exception {}: {!r}'.format(type(e), e.args))
            warn(traceback.format_exc())
