# dash in the .py file name is non-Pythonic only for module files, and not for end-user scripts

import os
import sys
import time

sys.path.append(os.path.split(os.path.abspath(__file__))[0])

from sanguine.install.install_helpers import github_project_exists, github_project_dir, clone_github_project
from sanguine.install.install_ui import BoxUINetworkErrorHandler
from sanguine.common import *
from sanguine.install.install_checks import check_sanguine_prerequisites
from sanguine.install.install_ui import input_box
from sanguine.helpers.project_config import ProjectConfig
import sanguine.tasks as tasks
from sanguine.cache.whole_cache import WholeCache
from sanguine.helpers.file_retriever import FileRetriever
from sanguine.choose_retrievers import choose_retrievers


def _usage() -> None:
    thisscriptcall = os.path.split(sys.argv[0])[0]
    info('usage:')
    info('-> {} <ProjectConfig.json5>'.format(thisscriptcall))


if __name__ == '__main__':
    argv = sys.argv[1:]
    if len(sys.argv) == 2 and sys.argv[1] == 'test':
        if not os.path.isdir('../../KTAGirl/KTA'):
            clone_github_project('../../', 'KTAGirl', 'KTA', BoxUINetworkErrorHandler(2))
        argv = ['../../KTAGirl/KTA\\KTA.json5']

    if len(argv) != 1:
        _usage()
        sys.exit(1)

    check_sanguine_prerequisites()

    cfgfname = argv[0]
    abort_if_not(os.path.isfile(cfgfname))
    cfgfname = normalize_file_path(cfgfname)
    cfg = ProjectConfig(cfgfname)
    add_file_logging(cfg.tmp_dir + 'sanguine.log.html')
    enable_ex_logging()

    wcache = WholeCache('KTAGirl', cfg)
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
                    if len(command) < 3:
                        alert('wrong number of parameters, use help to ask for syntax')
                    else:
                        author = command[1]
                        project = command[2]
                        ok = github_project_exists(cfg.github_root_dir, author, project)
                        pd = github_project_dir(cfg.github_root_dir, author, project)
                        if ok == 1:
                            info('Project {} already exists'.format(pd))
                        elif ok == -1:
                            alert('Folder {} already exists, but does not contain expected github project'.format(pd))
                        else:
                            assert ok == 0
                            info('Cloning {}...'.format(pd))
                            clone_github_project(cfg.github_root_dir, author, project, BoxUINetworkErrorHandler(2))

                case 'togithub':
                    possible_retrievers: dict[bytes, list[FileRetriever]] = {}
                    nzero = 0
                    ndup = 0
                    for f in wcache.all_vfs_files():
                        if f.file_hash in possible_retrievers:
                            ndup += 1
                        else:
                            retr: list[FileRetriever] = wcache.file_retrievers_by_hash(f.file_hash)
                            if len(retr) == 0:
                                nzero += 1
                            else:
                                possible_retrievers[f.file_hash] = retr

                    warn('found {} duplicate files, did not find retrievers for {} files'.format(ndup, nzero))
                    stats = {}
                    for r in possible_retrievers.items():
                        n = len(r[1])
                        if n not in stats:
                            stats[n] = 1
                        else:
                            stats[n] += 1
                    for n in sorted(stats.keys()):
                        info('{} -> {}'.format(n, stats[n]))

                    choose_retrievers(list(possible_retrievers.items()), {})

                case 'h' | 'help' | '' | _:
                    info('commands:')
                    info('-> h|help')
                    info('-> x|exit')
                    info('-> github.install <author> <project>')
                    info('-> togithub')

        except Exception as e:
            alert('Exception {}: {!r}'.format(type(e), e.args))
            warn(traceback.format_exc())
