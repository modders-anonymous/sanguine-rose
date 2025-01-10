import sanguine.tasks as tasks
from sanguine.cache.available_files import FileRetriever, AvailableFiles
from sanguine.cache.folder_cache import FileOnDisk, FolderCache
from sanguine.common import *
from sanguine.common import SanguineJsonEncoder
from sanguine.helpers.project_config import ProjectConfig


class WholeCache:
    # WholeCache, once ready_task_name() is reached, contains whole information about the folders, and available files
    #             all the information is in-memory, so it can work incredibly fast
    _cache_data_fname: str
    _cache_data: dict[str, any]
    _vfscache: FolderCache
    _available: AvailableFiles
    _SYNCOWNTASKNAME: str = 'sanguine.wholecache.sync'

    def __init__(self, by: str, projectcfg: ProjectConfig) -> None:
        self._cache_data_fname = projectcfg.cache_dir + 'wholecache.cachedata.json'
        try:
            with open(self._cache_data_fname, 'r') as f:
                self._cache_data = json.load(f)
        except Exception as e:
            warn('WholeCache: cannot load cachedata from {}: {}'.format(self._cache_data_fname, e))
            self._cache_data = {}
        self._available = AvailableFiles(by, projectcfg.cache_dir, projectcfg.tmp_dir, projectcfg.game_root_dir,
                                         projectcfg.download_dirs, projectcfg.github_folders, self._cache_data)

        folderstocache: FolderListToCache = projectcfg.active_vfs_folders()
        self._vfscache = FolderCache(projectcfg.cache_dir, 'vfs', folderstocache)

    def start_tasks(self, parallel: tasks.Parallel) -> None:
        self._vfscache.start_tasks(parallel)
        self._available.start_tasks(parallel)

        syncowntask = tasks.OwnTask(WholeCache._SYNCOWNTASKNAME,
                                    lambda _, _1, _2: self._start_sync_own_task_func(), None,
                                    [self._vfscache.ready_task_name(),
                                     self._available.ready_task_name()])
        parallel.add_task(syncowntask)

    @staticmethod
    def ready_task_name() -> str:
        return WholeCache._SYNCOWNTASKNAME

    def all_vfs_files(self) -> Iterable[FileOnDisk]:
        return self._vfscache.all_files()

    def file_retrievers_by_hash(self, h: bytes) -> list[FileRetriever]:  # resolved as fully as feasible
        return self._available.file_retrievers_by_hash(h)

    def archive_stats(self) -> dict[bytes, tuple[int, int]]:  # hash -> (n,total_size)
        return self._available.archive_stats()

    def stats_of_interest(self) -> list[str]:
        return (self._available.stats_of_interest() + self._vfscache.stats_of_interest()
                + ['sanguine.wholecache.'])

    def done(self) -> None:
        with open(self._cache_data_fname, 'w') as f:
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


if __name__ == '__main__':
    import sys
    import time
    from sanguine.install.install_helpers import clone_github_project
    from sanguine.install.install_ui import BoxUINetworkErrorHandler

    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        ttmppath = normalize_dir_path('../../../../sanguine.tmp\\')
        if not os.path.isdir(ttmppath):
            os.makedirs(ttmppath)
        if not os.path.isdir('../../../../KTAGirl/KTA'):
            clone_github_project('../../../../', 'KTAGirl', 'KTA', BoxUINetworkErrorHandler(2))
        add_file_logging(ttmppath + 'sanguine.log.html')
        enable_ex_logging()
        check_sanguine_prerequisites()

        cfgfname = normalize_file_path('../../../../KTAGirl/KTA\\KTA.json5')
        cfg = ProjectConfig(cfgfname)

        wcache = WholeCache('KTAGirl', cfg)
        with tasks.Parallel(None, taskstatsofinterest=wcache.stats_of_interest(), dbg_serialize=False) as tparallel:
            t0 = time.perf_counter()
            wcache.start_tasks(tparallel)
            dt = time.perf_counter() - t0
            info('Whole Cache: starting tasks took {:.2f}s'.format(dt))
            tparallel.run([])
        wcache.done()

        info('whole_cache.py test finished ok')
