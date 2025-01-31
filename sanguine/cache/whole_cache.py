import sanguine.tasks as tasks
from sanguine.cache.available_files import FileRetriever, AvailableFiles
from sanguine.cache.folder_cache import FolderCache
from sanguine.common import *
from sanguine.common import SanguineJsonEncoder
from sanguine.helpers.project_config import LocalProjectConfig, GithubModpack
from sanguine.helpers.tmp_path import TmpPath


class WholeCache:
    # WholeCache, once ready_task_name() is reached, contains whole information about the folders, and available files
    #             all the information is in-memory, so it can work incredibly fast
    _project_config: LocalProjectConfig
    _cache_data: ConfigData
    _source_vfs_cache: FolderCache
    available: AvailableFiles
    _resolved_vfs: ResolvedVFS | None
    _SYNCOWNTASKNAME: str = 'sanguine.wholecache.sync'

    def __init__(self, projectcfg: LocalProjectConfig, tmp: TmpPath) -> None:
        self._project_config = projectcfg
        try:
            with open(self._cache_data_fname(), 'r') as f:
                self._cache_data = json.load(f)
        except Exception as e:
            warn('WholeCache: cannot load cachedata from {}: {}'.format(self._cache_data_fname, e))
            self._cache_data = {}

        rootmodpackdir = GithubModpack(projectcfg.root_modpack).folder(projectcfg.github_root_dir)
        self.available = AvailableFiles(projectcfg.github_username, projectcfg.cache_dir, tmp.tmpdir,
                                        projectcfg.github_root_dir, rootmodpackdir,
                                        projectcfg.download_dirs, projectcfg.github_folders(), self._cache_data)

        folderstocache: FolderListToCache = projectcfg.active_source_vfs_folders()
        self._source_vfs_cache = FolderCache(projectcfg.cache_dir, 'vfs', folderstocache)

        self._resolved_vfs = None

    def start_tasks(self, parallel: tasks.Parallel) -> None:
        self._source_vfs_cache.start_tasks(parallel)
        self.available.start_tasks(parallel)

        syncowntask = tasks.OwnTask(WholeCache._SYNCOWNTASKNAME,
                                    lambda _, _1, _2: self._start_sync_own_task_func(), None,
                                    [self._source_vfs_cache.ready_task_name(),
                                     self.available.ready_task_name()])
        parallel.add_task(syncowntask)

    @staticmethod
    def ready_task_name() -> str:
        return WholeCache._SYNCOWNTASKNAME

    def all_source_vfs_files(self) -> Iterable[FileOnDisk]:
        return self._source_vfs_cache.all_files()

    def file_retrievers_by_hash(self, h: bytes) -> list[FileRetriever]:  # resolved as fully as feasible
        return self.available.file_retrievers_by_hash(h)

    def archive_stats(self) -> dict[bytes, tuple[int, int]]:  # hash -> (n,total_size)
        return self.available.archive_stats()

    def resolved_vfs(self) -> ResolvedVFS:
        if self._resolved_vfs is None:
            self._resolved_vfs = self._project_config.mod_manager_config.resolve_vfs(self.all_source_vfs_files())
        return self._resolved_vfs

    def stats_of_interest(self) -> list[str]:
        return (self.available.stats_of_interest() + self._source_vfs_cache.stats_of_interest()
                + ['sanguine.wholecache.'])

    def done(self) -> None:
        with open(self._cache_data_fname(), 'w') as f:
            # noinspection PyTypeChecker
            json.dump(self._cache_data, f, indent=2, cls=SanguineJsonEncoder)

    ### private functions
    def _sync_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            ['sanguine.available.ready()',
             'sanguine.foldercache.vfs.ready()'],
            [],
            ['sanguine.wholecache.ready()'])

    def _start_sync_own_task_func(self) -> None:
        pass  # do nothing, this task is necessary only to synchronize

    def _cache_data_fname(self) -> str:
        return self._project_config.cache_dir + 'wholecache.cachedata.json'


if __name__ == '__main__':
    import sys
    import time
    from sanguine.install.install_github import clone_github_project, GithubFolder
    from sanguine.install.install_ui import InstallUI

    ui = InstallUI()
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        ttmppath = normalize_dir_path('../../../../sanguine.tmp\\')
        if not os.path.isdir(ttmppath):
            os.makedirs(ttmppath)
        if not os.path.isdir('../../../../KTAGirl/KTA'):
            clone_github_project('../../../../', GithubFolder('KTAGirl/KTA'), ui.network_error_handler(2))
        add_file_logging(ttmppath + 'sanguine.log.html')
        enable_ex_logging()
        check_sanguine_prerequisites(ui)

        cfgfname = normalize_file_path('../../../../local-sanguine-project.json5')
        tcfg = LocalProjectConfig(ui, cfgfname)

        with TmpPath(ttmppath) as ttmp:
            wcache = WholeCache(tcfg, ttmp)
            with tasks.Parallel(None, taskstatsofinterest=wcache.stats_of_interest(), dbg_serialize=False) as tparallel:
                t0 = time.perf_counter()
                wcache.start_tasks(tparallel)
                dt = time.perf_counter() - t0
                info('Whole Cache: starting tasks took {:.2f}s'.format(dt))
                tparallel.run([])
            wcache.done()

        info('whole_cache.py test finished ok')
