import mo2gitlib.tasks as tasks
import mo2gitlib.wjcompat.wjdb as wjdb
from mo2gitlib.aentriescache import ArchiveEntriesCache
from mo2gitlib.common import *
from mo2gitlib.files import File
from mo2gitlib.foldercache import FolderCache, FolderList
from mo2gitlib.folders import Folders
from mo2gitlib.pickledcache import pickled_cache


### Loading WJ HashCache

def _load_hc_add_fi(out: list[File], all_folders_list: FolderList, fi: File) -> None:
    fpath = fi.file_path

    if FolderCache.file_path_is_ok(fpath, all_folders_list):
        out.append(fi)


def _load_hc(params: tuple[FolderList]) -> list[File]:
    (all_folders_list,) = params
    out = []
    wjdb.load_hc(lambda fi: _load_hc_add_fi(out, all_folders_list, fi))
    return out


def _load_hc_task_func(param: tuple[str, FolderList, dict[str, any]]) -> tuple[list[File], dict[str, any]]:
    (cachedir, all_folders_list, cachedata) = param
    return pickled_cache(cachedir, cachedata, 'wjdb.hcfile', [wjdb.hc_file_path()],
                         _load_hc, (all_folders_list,))


def _own_hc2self_task_func(cache: "Cache", taskout: tuple[list[File], dict[str, any]]):
    (hcout, cachedataoverwrites) = taskout
    cache.cache_data |= cachedataoverwrites
    assert cache.underlying_files is None
    cache.underlying_files = hcout
    info('Cache: ' + str(len(cache.underlying_files_by_path)) + ' underlying files loaded')

def _own_downloads_ready_task_func(cache: "Cache"):
    pass

class Cache:
    cache_data: dict[str, any]  # for pickled_cache
    folders: Folders
    aentries: ArchiveEntriesCache
    downloads: FolderCache
    mo2: FolderCache
    ownmods: FolderCache
    underlying_files: list[File] | None

    def __init__(self, folders: Folders) -> None:
        self.cache_data = read_dict_from_json_file(folders.cache + 'cache-data.json')
        # TODO! : save cache_data
        self.folders = folders
        self.aentries = ArchiveEntriesCache(folders.cache, folders.tmp, self.cache_data)
        self.downloads = FolderCache(folders.cache, 'downloads', [(dl, []) for dl in folders.downloads])
        self.mo2 = FolderCache(folders.cache, 'mo2',
                               [(folders.mo2, folders.ignore + folders.downloads + [folders.mo2 + 'mods\\'])]
                               + [(mod, folders.ignore) for mod in folders.all_enabled_mod_dirs()])
        self.ownmods = FolderCache(folders.cache, 'ownmods',
                                   [(own, folders.ignore) for own in folders.all_own_mod_dirs()])
        self.underlying_files_by_path = None

    def start_tasks(self, parallel: tasks.Parallel) -> None:
        all_folders_list = self.downloads.folder_list + self.mo2.folder_list + self.ownmods.folder_list
        hctaskname = 'mo2git.cache.loadhc'
        hctask = tasks.Task(hctaskname, _load_hc_task_func,
                            (self.folders.cache, all_folders_list, self.cache_data), [])

        ownhctaskname = 'mo2git.cache.ownhc2self'
        owntaskhc2self = tasks.OwnTask(ownhctaskname,
                                       lambda _, out: _own_hc2self_task_func(self, out),
                                       None, [hctaskname])
        parallel.add_late_tasks([hctask, owntaskhc2self])

        self.downloads.start_tasks(parallel, iter(self.underlying_files), ownhctaskname)
        self.mo2.start_tasks(parallel, iter(self.underlying_files), ownhctaskname)
        self.ownmods.start_tasks(parallel, iter(self.underlying_files), ownhctaskname)

        owndlsreadytaskname = 'mo2git.cache.owndlsready'
        owndlsready = tasks.OwnTask(owndlsreadytaskname,
                                       lambda _, _1: _own_downloads_ready_task_func(self),
                                       None, [self.downloads.ready_task_name()])
        parallel.add_late_task(owndlsready)




