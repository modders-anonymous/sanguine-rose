import os.path

import sanguine.tasks as tasks
from sanguine.cache.folder_cache import FolderCache
from sanguine.cache.root_git_data import RootGitData
from sanguine.common import *
from sanguine.gitdata.file_origin import file_origins_for_file, FileOrigin, file_origin_plugins, FileOriginPluginBase
from sanguine.helpers.archives import all_archive_plugins_extensions, Archive
from sanguine.helpers.file_retriever import (FileRetriever, ZeroFileRetriever, GithubFileRetriever,
                                             ArchiveFileRetriever, ArchiveFileRetrieverHelper)
from sanguine.helpers.tmp_path import TmpPath
from sanguine.install.install_github import GithubFolder
from sanguine.install.install_ui import InstallUI


def _file_origins_task_func(param: tuple[list[bytes, str]]) -> tuple[
    list[tuple[bytes, list[FileOrigin]]], list[tuple[bytes, str]]]:
    (filtered_downloads,) = param
    allorigins: list[tuple[bytes, list[FileOrigin]]] = []
    alltentativefiles: list[tuple[bytes, str]] = []
    for fhash, fpath in filtered_downloads:
        # TODO/PERFORMANCE: multi-picklecache for file origins
        origins = file_origins_for_file(fpath)
        if origins is None:
            warn('Available: file without known origin {}'.format(fpath))
        else:
            allorigins.append((fhash, origins))
            alltentativefiles.append((fhash, os.path.split(fpath)[1]))
    return allorigins, alltentativefiles


class AvailableFiles:
    _root_git_dir: str
    _github_cache: FolderCache
    _github_cache_by_hash: dict[bytes, list[FileOnDisk]] | None
    _downloads_cache: FolderCache
    _root_data: RootGitData
    _github_folders: list[GithubFolder]
    _HASHMAPPINGSTASKNAME = 'sanguine.available.ownhashmappings'
    _READYOWNTASKNAME = 'sanguine.available.ownready'
    _is_ready: bool
    _hash_remapping_plugins: list[FileOriginPluginBase]

    def __init__(self, by: str, cachedir: str, tmpdir: str, rootgitdir: str, rootmodpackdir: str, downloads: list[str],
                 github_folders: list[GithubFolder], cache_data: ConfigData) -> None:
        self._root_git_dir = rootgitdir
        self._hash_remapping_plugins = []
        extrahashfactories = []
        for plugin in file_origin_plugins():
            xf = plugin.extra_hash_factory()
            if xf is not None:
                assert callable(xf) and not tasks.is_lambda(xf)
                self._hash_remapping_plugins.append(plugin)
                extrahashfactories.append(xf)
        assert len(self._hash_remapping_plugins) == len(extrahashfactories)

        self._downloads_cache = FolderCache(cachedir, 'downloads',
                                            FolderListToCache([FolderToCache(d, []) for d in downloads]),
                                            extrahashfactories=extrahashfactories)
        self._github_cache = FolderCache(cachedir, 'github',
                                         FolderListToCache(
                                             [FolderToCache(g.folder(rootgitdir), []) for g in github_folders]))
        self._github_cache_by_hash = None
        self._github_folders = github_folders
        self._root_data = RootGitData(by, rootmodpackdir, cachedir, tmpdir, cache_data)
        self._is_ready = False

    # public interface

    def start_tasks(self, parallel: tasks.Parallel):
        self._downloads_cache.start_tasks(parallel)
        self._github_cache.start_tasks(parallel)
        self._root_data.start_tasks(parallel)

        starthashingowntaskname = 'sanguine.available.ownstarthashing'
        starthashingowntask = tasks.OwnTask(starthashingowntaskname,
                                            lambda _, _1, _2: self._start_hashing_own_task_func(parallel), None,
                                            [self._downloads_cache.ready_task_name(),
                                             RootGitData.ready_to_start_hashing_task_name()],
                                            datadeps=self._starthashing_owntask_datadeps())
        parallel.add_task(starthashingowntask)

        startoriginsowntaskname = 'sanguine.available.ownstartfileorigins'
        startoriginsowntask = tasks.OwnTask(startoriginsowntaskname,
                                            lambda _, _1: self._start_origins_own_task_func(parallel), None,
                                            [self._downloads_cache.ready_task_name()],
                                            datadeps=self._startorigins_owntask_datadeps())
        parallel.add_task(startoriginsowntask)

        hashmappingsowntaskname = AvailableFiles._HASHMAPPINGSTASKNAME
        hashmappingsowntask = tasks.OwnTask(hashmappingsowntaskname,
                                            lambda _, _1, _2: self._hash_mappings_own_task_func(), None,
                                            [self._downloads_cache.ready_task_name(),
                                             self._root_data.ready_to_start_adding_file_origins_task_name()])
        parallel.add_task(hashmappingsowntask)

        readyowntaskname = AvailableFiles._READYOWNTASKNAME
        fakereadyowntask = tasks.TaskPlaceholder(readyowntaskname)
        parallel.add_task(fakereadyowntask)

    @staticmethod
    def ready_task_name() -> str:
        return AvailableFiles._READYOWNTASKNAME

    def file_retrievers_by_hash(self, h: bytes) -> list[FileRetriever]:
        zero = ZeroFileRetriever.make_retriever_if(h)
        if zero is not None:
            return [zero]  # if it is zero file, we won't even try looking elsewhere
        github = self._github_file_retrievers_by_hash(h)
        if len(github) > 0:
            return github
        return self._archived_file_retrievers_by_hash(h)

    def archive_stats(self) -> dict[bytes, tuple[int, int]]:  # hash -> (n,total_size)
        return self._root_data.archive_stats()

    def archive_by_hash(self, h: bytes) -> Archive | None:
        return self._root_data.archive_by_hash(h)

    def downloaded_file_by_hash(self, h: bytes) -> list[FileOnDisk] | None:
        return self._downloads_cache.file_by_hash(h)

    def tentative_names_for_archive(self, h: bytes) -> list[str]:
        return self._root_data.tentative_names_for_archive(h)

    def stats_of_interest(self) -> list[str]:
        return (self._downloads_cache.stats_of_interest() + self._github_cache.stats_of_interest()
                + self._root_data.stats_of_interest()
                + ['sanguine.available.own', 'sanguine.available.fileorigins', 'sanguine.available.'])

    ### private functions
    # lists of file retrievers
    def _single_archive_retrievers(self, h: bytes) -> list[ArchiveFileRetrieverHelper]:
        found = self._root_data.archived_file_by_hash(h)
        if found is None:
            return []
        assert len(found) > 0
        return [ArchiveFileRetrieverHelper((h, fi.file_size), ar.archive_hash, ar.archive_size, fi)
                for ar, fi in found]

    def _add_nested_archives(self, out: list[ArchiveFileRetriever],
                             singles: list[ArchiveFileRetrieverHelper]) -> None:
        # resolving nested archives
        for r in singles:
            out.append(ArchiveFileRetriever((r.file_hash, r.file_size), [r]))
            found2 = self._archived_file_retrievers_by_hash(r.archive_hash)
            for r2 in found2:
                out.append(
                    ArchiveFileRetriever((r2.file_hash, r2.file_size), r2.constructor_parameter_appending_child(r)))

    def _archived_file_retrievers_by_hash(self, h: bytes) -> list[ArchiveFileRetriever]:  # recursive
        singles = self._single_archive_retrievers(h)
        if len(singles) == 0:
            return []
        assert len(singles) > 0

        out = []
        self._add_nested_archives(out, singles)
        assert len(out) > 0
        return out

    def _github_file_retrievers_by_hash(self, h: bytes) -> list[GithubFileRetriever]:
        ghlist = self._github_cache_by_hash.get(h)
        if ghlist is None:
            return []

        out = []
        for gh in ghlist:
            fpath = gh.file_path
            author = None
            projectname = None
            intrapath = None
            for d in self._github_folders:
                dlocal = d.folder(self._root_git_dir)
                if fpath.startswith(dlocal):
                    assert author is None
                    assert projectname is None
                    assert intrapath is None
                    author = d.author
                    projectname = d.project
                    intrapath = fpath[len(dlocal):]
                    if not __debug__:
                        break

            assert author is not None
            assert projectname is not None
            assert intrapath is not None

            out.append(GithubFileRetriever((h, gh.file_size), author, projectname, intrapath))

        return out

    # own tasks

    def _starthashing_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            ['sanguine.foldercache.downloads._files_by_path',
             'sanguine.rootgit._archives_by_hash'],
            [],
            ['sanguine.available.start_hashing()'])

    def _start_hashing_own_task_func(self, parallel: tasks.Parallel) -> None:
        for ar in self._downloads_cache.all_files():
            ext = os.path.splitext(ar.file_path)[1]
            if ext == '.meta':
                continue

            if not self._root_data.archive_by_hash(ar.file_hash, partialok=True):
                if ext in all_archive_plugins_extensions():
                    self._root_data.start_hashing_archive(parallel, ar.file_path, ar.file_hash, ar.file_size)
                else:
                    warn('Available: file with unknown extension {}, ignored'.format(ar.file_path))

    def _startorigins_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            ['sanguine.foldercache.downloads._files_by_path'],
            [],
            ['sanguine.available.start_origins()'])

    def _start_origins_own_task_func(self, parallel: tasks.Parallel) -> None:
        filtered_downloads: list[tuple[bytes, str]] = []
        for ar in self._downloads_cache.all_files():
            ext = os.path.splitext(ar.file_path)[1]
            if ext == '.meta':
                continue

            filtered_downloads.append((ar.file_hash, ar.file_path))

        originstaskname = 'sanguine.available.fileorigins'
        originstask = tasks.Task(originstaskname, _file_origins_task_func,
                                 (filtered_downloads,), [])
        parallel.add_task(originstask)
        startoriginsowntaskname = 'sanguine.available.ownfileorigins'
        originsowntask = tasks.OwnTask(startoriginsowntaskname,
                                       lambda _, out, _1, _2: self._file_origins_own_task_func(parallel, out), None,
                                       [originstaskname,
                                        RootGitData.ready_to_start_adding_file_origins_task_name(),
                                        RootGitData.archives_ready_task_name()],
                                       datadeps=self._fileorigins_owntask_datadeps())
        parallel.add_task(originsowntask)

    def _fileorigins_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            ['sanguine.rootgit._tentative_archive_names',
             'sanguine.rootgit._archives_by_hash',
             'sanguine.available.start_origins()'],
            [],
            ['sanguine.available.file_origins()'])

    def _file_origins_own_task_func(self, parallel: tasks.Parallel,
                                    out: tuple[list[tuple[bytes, list[FileOrigin]]], list[tuple[bytes, str]]]) -> None:
        (origins, tentativefiles) = out
        for fox in origins:
            for fo in fox[1]:
                self._root_data.add_file_origin(fox[0], fo)
        for tf in tentativefiles:
            self._root_data.add_tentative_name(tf[0], tf[1])
        self._root_data.start_done_adding_file_origins_task(parallel)  # no need to wait for it

        gitarchivesdonehashingtaskname: str = self._root_data.start_done_hashing_task(parallel)
        readyowntaskname = AvailableFiles._READYOWNTASKNAME
        readyowntask = tasks.OwnTask(readyowntaskname,
                                     lambda _, _1, _2, _3: self._ready_own_task_func(), None,
                                     [gitarchivesdonehashingtaskname,
                                      self._github_cache.ready_task_name(),
                                      AvailableFiles._HASHMAPPINGSTASKNAME])
        parallel.replace_task_placeholder(readyowntask)

    def _hash_mappings_own_task_func(self):
        for h, xh in self._downloads_cache.extra_hashes.items():
            assert len(xh) == len(self._hash_remapping_plugins)
            self._root_data.add_hash_mappings(h, self._hash_remapping_plugins, xh)

    def _ready_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            ['sanguine.foldercache.github._files_by_path'],
            [],
            ['sanguine.available.ready()'])

    def _ready_own_task_func(self) -> None:
        assert self._github_cache_by_hash is None
        self._github_cache_by_hash = {}
        for f in self._github_cache.all_files():
            add_to_dict_of_lists(self._github_cache_by_hash, f.file_hash, f)
        self._is_ready = True


if __name__ == '__main__':
    import sys

    ui = InstallUI()
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        ttmppath = normalize_dir_path('../../../sanguine.tmp\\')
        add_file_logging(ttmppath + 'sanguine.log.html')

        check_sanguine_prerequisites(ui)
        perf_warn('Test performance warning')

        with TmpPath(ttmppath) as ttmpdir:
            tavailable = AvailableFiles('KTAGirl',
                                        normalize_dir_path('../../../sanguine.cache\\'),
                                        ttmpdir.tmp_dir(),
                                        normalize_dir_path('../..'),
                                        normalize_dir_path('../../../sanguine-skyrim-root\\'),
                                        [normalize_dir_path('../../../../MO2/downloads')],
                                        [GithubFolder('KTAGirl/KTA')], {})
            with tasks.Parallel(None, dbg_serialize=False,
                                taskstatsofinterest=tavailable.stats_of_interest()) as tparallel:
                tavailable.start_tasks(tparallel)
                tparallel.run([])  # all necessary tasks were already added in acache.start_tasks()

        info('available_files.py test finished ok')
