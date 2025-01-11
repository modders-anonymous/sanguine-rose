# dash in the .py file name is non-Pythonic only for module files, and not for end-user scripts

import os
import sys
import time

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

from sanguine.common import *
from sanguine.install.install_checks import check_sanguine_prerequisites
from sanguine.install.install_ui import input_box
from sanguine.helpers.project_config import LocalProjectConfig, install_github_project_with_dependencies, \
    GithubModpackConfig
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
        argv = ['../../local-sanguine-project.json5']

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
                        allmodpackconfigs: dict[
                            str, GithubModpackConfig] = {}  # have to use temporary one to avoid changing our main cfg
                        rootmodpack = install_github_project_with_dependencies(command[1], cfg.github_root_dir,
                                                                               allmodpackconfigs)
                        info('{} installed, root={}'.format(command[1], rootmodpack))

                case 'togithub':
                    togithub(cfg, wcache)

                case 'h' | 'help' | '' | _:
                    info('commands:')
                    info('-> h|help')
                    info('-> x|exit')
                    info('-> github.install <author> <project>')
                    info('-> togithub')

        except Exception as e:
            alert('Exception {}: {!r}'.format(type(e), e.args))
            warn(traceback.format_exc())
