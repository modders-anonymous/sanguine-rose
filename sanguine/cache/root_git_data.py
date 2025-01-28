import sanguine.gitdata.git_data_file as gitdatafile
import sanguine.tasks as tasks
from sanguine.cache.pickled_cache import pickled_cache
from sanguine.common import *
from sanguine.gitdata.file_origin import (FileOrigin, GitTentativeArchiveNames,
                                          file_origin_plugins, file_origin_plugin_by_name, FileOriginPluginBase)
from sanguine.gitdata.root_git_archives import GitArchivesJson
from sanguine.helpers.archives import Archive, FileInArchive, normalize_archive_intra_path
from sanguine.helpers.archives import ArchivePluginBase, all_archive_plugins_extensions, archive_plugin_for
from sanguine.helpers.arinstallers import all_arinstaller_plugins, arinstaller_plugin_by_name, ExtraArchiveDataFactory, \
    arinstaller_plugin_add_extra_data
from sanguine.helpers.stable_json import write_stable_json_opened, to_stable_json
from sanguine.helpers.tmp_path import TmpPath

### RootGitData Helpers

_KNOWN_ARCHIVES_FNAME = 'known-archives.json5'
_KNOWN_TENTATIVE_ARCHIVE_NAMES_FNAME = 'known-tentative-archive-names.json5'


def _known_fo_plugin_fname(name: str) -> str:
    return 'known-fileorigin-{}-data.json5'.format(name)


def _known_arinst_plugin_fname(name: str) -> str:
    return 'known-arinstaller-{}-data.json'.format(name)


def _processing_archive_time_estimate(fsize: int):
    return float(fsize) / 1048576. / 10.  # 10 MByte/s


def _read_git_archives(params: tuple[str]) -> list[Archive]:
    (archivesgitfile,) = params
    assert is_normalized_file_path(archivesgitfile)
    with gitdatafile.open_git_data_file_for_reading(archivesgitfile) as rf:
        archives = GitArchivesJson().read_from_file(rf)
    return archives


def _read_cached_git_archives(rootgitdir: str, cachedir: str,
                              cachedata: ConfigData) -> tuple[list[Archive], ConfigData]:
    assert is_normalized_dir_path(rootgitdir)
    rootgitfile = rootgitdir + _KNOWN_ARCHIVES_FNAME
    return pickled_cache(cachedir, cachedata, 'known-archives', [rootgitfile],
                         _read_git_archives, (rootgitfile,))


def _write_git_archives(rootgitdir: str, archives: list[Archive]) -> None:
    assert is_normalized_dir_path(rootgitdir)
    fpath = rootgitdir + _KNOWN_ARCHIVES_FNAME
    with gitdatafile.open_git_data_file_for_writing(fpath) as wf:
        GitArchivesJson().write(wf, archives)


def _hash_archive(archives: list[Archive], extradata: dict[str, dict[bytes, Any]], by: str, tmppath: str,  # recursive!
                  plugin: ArchivePluginBase,
                  archivepath: str, arhash: bytes, arsize: int, extrafactories: list[ExtraArchiveDataFactory]) -> None:
    assert os.path.isdir(tmppath)
    plugin.extract_all(archivepath, tmppath)
    pluginexts = all_archive_plugins_extensions()  # for nested archives
    ar = Archive(arhash, arsize, by)
    archives.append(ar)
    for root, dirs, files in os.walk(tmppath):
        nf = 0
        for f in files:
            nf += 1
            fpath = os.path.join(root, f)
            s, h = calculate_file_hash(fpath)
            assert fpath.startswith(tmppath)
            ar.files.append(
                FileInArchive(truncate_file_hash(h), s, normalize_archive_intra_path(fpath[len(tmppath):])))

            ext = os.path.split(fpath)[1].lower()
            if ext in pluginexts:
                nested_plugin = archive_plugin_for(fpath)
                assert nested_plugin is not None
                newtmppath = TmpPath.tmp_in_tmp(tmppath,
                                                'T3lIzNDx.',  # tmp is not from root,
                                                # so randomly-looking prefix is necessary
                                                nf)
                assert not os.path.isdir(newtmppath)
                os.makedirs(newtmppath)
                _hash_archive(archives, extradata, by, newtmppath, nested_plugin, fpath, h, s, extrafactories)
    for xf in extrafactories:
        if xf.name() not in extradata:
            extradata[xf.name()] = {}
        xfbyname = extradata[xf.name()]
        assert arhash not in xfbyname

        try:
            xd = xf.extra_data(tmppath)
            xfbyname[arhash] = xd
        except Exception as e:
            xfbyname[arhash] = e


def _read_git_tentative_names(params: tuple[str]) -> dict[bytes, list[str]]:
    (tafile,) = params
    assert is_normalized_file_path(tafile)
    with gitdatafile.open_git_data_file_for_reading(tafile) as rf:
        tanames = GitTentativeArchiveNames().read_from_file(rf)
    return tanames


def _read_cached_git_tentative_names(rootgitdir: str, cachedir: str,
                                     cachedata: ConfigData) -> tuple[dict[bytes, list[str]], ConfigData]:
    assert is_normalized_dir_path(rootgitdir)
    rootgitfile = rootgitdir + _KNOWN_TENTATIVE_ARCHIVE_NAMES_FNAME
    return pickled_cache(cachedir, cachedata, 'known-tentative-archive-names', [rootgitfile],
                         _read_git_tentative_names, (rootgitfile,))


def _write_git_tentative_names(rootgitdir: str, tanames: dict[bytes, list[str]]) -> None:
    assert is_normalized_dir_path(rootgitdir)
    fpath = rootgitdir + _KNOWN_TENTATIVE_ARCHIVE_NAMES_FNAME
    with gitdatafile.open_git_data_file_for_writing(fpath) as wf:
        GitTentativeArchiveNames().write(wf, tanames)


# plugin data

def _read_some_plugin_data(params: tuple[str, str, Callable[[typing.TextIO], Any]]) -> Any:
    (name, rootgitfile, rdfunc) = params
    assert is_normalized_file_path(rootgitfile)
    with gitdatafile.open_git_data_file_for_reading(rootgitfile) as rf:
        return name, rdfunc(rf)


def _read_some_cached_plugin_data(rootgitdir: str, name: str, fname: str, rdfunc: Callable[[typing.TextIO], Any],
                                  cachedir: str, cachedata: ConfigData) -> tuple[Any, ConfigData]:
    assert is_normalized_dir_path(rootgitdir)
    rootgitfile = rootgitdir + fname.lower()
    pickledprefix = os.path.splitext(fname)[0]
    return pickled_cache(cachedir, cachedata, pickledprefix, [rootgitfile],
                         _read_some_plugin_data, (name, rootgitfile, rdfunc))


def _write_some_plugin_data(rootgitdir: str, fname: str, wrfunc: Callable[[typing.TextIO, Any], None],
                            wrdata: Any) -> None:
    assert is_normalized_dir_path(rootgitdir)
    fpath = rootgitdir + fname.lower()
    assert is_normalized_file_path(fpath)
    with gitdatafile.open_git_data_file_for_writing(fpath) as wf:
        wrfunc(wf, wrdata)


### RootGitData Tasks

def _append_archive(archives_by_hash, archived_files_by_hash, archived_files_by_name, ar: Archive) -> None:
    # warn(str(len(ar.files)))
    assert ar.archive_hash not in archives_by_hash
    archives_by_hash[ar.archive_hash] = ar
    for fi in ar.files:
        if fi.file_hash not in archived_files_by_hash:
            archived_files_by_hash[fi.file_hash] = []
        archived_files_by_hash[fi.file_hash].append((ar, fi))

        fname = os.path.split(fi.intra_path)[1]
        if fname not in archived_files_by_name:
            archived_files_by_name[fname] = []
        archived_files_by_name[fname].append((ar, fi))


def _load_archives_task_func(param: tuple[str, str, dict[str, Any]]) -> tuple[dict, dict, dict, dict[str, Any]]:
    (rootgitdir, cachedir, cachedata) = param
    (archives, cacheoverrides) = _read_cached_git_archives(rootgitdir, cachedir, cachedata)
    archives_by_hash = {}
    archived_files_by_hash = {}
    archived_files_by_name = {}
    for ar in archives:
        _append_archive(archives_by_hash, archived_files_by_hash, archived_files_by_name, ar)
    return archives_by_hash, archived_files_by_hash, archived_files_by_name, cacheoverrides


def _archive_hashing_task_func(param: tuple[str, str, bytes, int, str, list[ExtraArchiveDataFactory]]) -> tuple[
    list[Archive], dict[str, dict[bytes, Any]]]:
    (by, arpath, arhash, arsize, tmppath, extrafactories) = param
    assert not os.path.isdir(tmppath)
    os.makedirs(tmppath)
    plugin = archive_plugin_for(arpath)
    assert plugin is not None
    archives = []
    extradata: dict[str, dict[bytes, Any]] = {}
    _hash_archive(archives, extradata, by, tmppath, plugin, arpath, arhash, arsize, extrafactories)
    debug('RootGitData: about to remove temporary tree {}'.format(tmppath))
    TmpPath.rm_tmp_tree(tmppath)
    return archives, extradata


def _debug_assert_eq_list(saved_loaded: list, sorted_data: list) -> None:
    assert len(saved_loaded) == len(sorted_data)
    for i in range(len(sorted_data)):
        olda: str = as_json(sorted_data[i])
        newa: str = as_json(saved_loaded[i])
        if olda != newa:
            warn(olda)
            warn(newa)
            warn(os.path.commonprefix([olda, newa]))
            assert False


def _save_archives_task_func(param: tuple[str, list[Archive]]) -> None:
    (rootgitdir, archives) = param
    _write_git_archives(rootgitdir, archives)
    if __debug__:
        saved_loaded = _read_git_archives((rootgitdir + _KNOWN_ARCHIVES_FNAME,))
        # warn(str(len(archives)))
        # warn(str(len(saved_loaded)))
        sorted_archives = sorted([Archive(ar.archive_hash, ar.archive_size, ar.by,
                                          sorted([fi for fi in ar.files], key=lambda f: f.intra_path))
                                  for ar in archives], key=lambda a: a.archive_hash)
        _debug_assert_eq_list(saved_loaded, sorted_archives)


def _load_tentative_names_task_func(param: tuple[str, str, ConfigData]) -> tuple[
    dict[bytes, list[str]], ConfigData]:
    (rootgitdir, cachedir, cachedata) = param
    (tanames, cacheoverrides) = _read_cached_git_tentative_names(rootgitdir, cachedir, cachedata)
    return tanames, cacheoverrides


def _save_tentative_names_task_func(param: tuple[str, dict[bytes, list[str]]]) -> None:
    (rootgitdir, tanames) = param
    # warn(repr(tanames))
    _write_git_tentative_names(rootgitdir, tanames)
    if __debug__:
        saved_loaded = list(_read_git_tentative_names((rootgitdir + _KNOWN_TENTATIVE_ARCHIVE_NAMES_FNAME,)).items())
        # warn(str(len(tanames)))
        # warn(str(len(saved_loaded)))
        sorted_tanames: list[tuple[bytes, list[str]]] = sorted(tanames.items())
        for i in range(len(sorted_tanames)):
            tan = sorted_tanames[i]
            sorted_tanames[i] = (tan[0], sorted(tan[1]))
        _debug_assert_eq_list(saved_loaded, sorted_tanames)


def _load_some_plugin_data_task_func(param: tuple[str, str, str, Callable, str, ConfigData]) -> Any:
    (rootgitdir, name, fname, rdfunc, cachedir, cachedata) = param
    return _read_some_cached_plugin_data(rootgitdir, name, fname, rdfunc, cachedir, cachedata)


def _save_some_plugin_data_task_func(param: tuple[str, str, Callable, Any]) -> None:
    (rootgitdir, fname, wrfunc, wrdata) = param
    _write_some_plugin_data(rootgitdir, fname, wrfunc, wrdata)


def _save_stable_json(f: typing.TextIO, data: Any) -> None:
    data1 = to_stable_json(data)
    write_stable_json_opened(f, data1)


def _load_stable_json(f: typing.TextIO) -> dict[str, Any]:
    return json.load(f)


### RootGitData itself

class RootGitData:
    _root_git_dir: str
    _cache_dir: str
    _tmp_dir: str
    _cache_data: ConfigData
    _archives_by_hash: dict[bytes, Archive] | None
    _archived_files_by_hash: dict[bytes, list[tuple[Archive, FileInArchive]]] | None  # all (ar,fi) pairs for given hash
    _archived_files_by_name: dict[str, list[tuple[Archive, FileInArchive]]] | None
    _tentative_archive_names: dict[bytes, list[str]] | None
    _nhashes_requested: int  # number of hashes already requested; used to make name of tmp dir
    _new_hashes_by: str
    _dirty_ar: bool
    _dirty_fo: bool
    _ar_is_ready: int  # 0 - not ready, 1 - partially ready, 2 - fully ready
    _fo_is_ready: int
    _n_ready_arinst_plugins: int  # counter

    _LOADAROWNTASKNAME = 'sanguine.rootgit.ownloadar'
    _LOADFOOWNTASKNAME = 'sanguine.rootgit.ownloadfo'

    def __init__(self, new_hashes_by: str, rootgitdir: str, cachedir: str, tmpdir: str,
                 cache_data: ConfigData) -> None:
        self._new_hashes_by = new_hashes_by
        self._root_git_dir = rootgitdir
        self._cache_dir = cachedir
        self._tmp_dir = tmpdir
        self._cache_data = cache_data
        self._archives_by_hash = None
        self._archived_files_by_hash = None
        self._archived_files_by_name = None
        self._tentative_archive_names = None
        self._nhashes_requested = 0
        self._dirty_ar = False
        self._dirty_fo = False
        self._ar_is_ready = 0
        self._fo_is_ready = 0
        self._n_ready_arinst_plugins = False

    def start_tasks(self, parallel: tasks.Parallel) -> None:
        load2taskname = 'sanguine.rootgit.loadtan'
        load2task = tasks.Task(load2taskname, _load_tentative_names_task_func,
                               (self._root_git_dir, self._cache_dir, self._cache_data), [])
        parallel.add_task(load2task)

        for plugin in file_origin_plugins():
            loadfotaskname = 'sanguine.rootgit.loadfo.' + plugin.name()
            rdfunc = plugin.load_json5_file_func()
            assert callable(rdfunc) and not tasks.is_lambda(rdfunc)
            loadfotask = tasks.Task(loadfotaskname, _load_some_plugin_data_task_func,
                                    (self._root_git_dir, plugin.name(), _known_fo_plugin_fname(plugin.name()),
                                     rdfunc, self._cache_dir, self._cache_data),
                                    [])
            parallel.add_task(loadfotask)

            loadfoowntaskname = 'sanguine.rootgit.ownloadfo.' + plugin.name()
            loadfoowntask = tasks.OwnTask(loadfoowntaskname,
                                          lambda _, out: self._load_own_fo_plugin_data_task_func(out), None,
                                          [loadfotaskname])
            parallel.add_task(loadfoowntask)

        loadarinstowntasknamepattern = 'sanguine.rootgit.loadarinst.*'
        for plugin in all_arinstaller_plugins():
            if plugin.extra_data_factory() is None:
                continue
            loadarinsttaskname = 'sanguine.rootgit.loadarinst.' + plugin.name()
            loadarinsttask = tasks.Task(loadarinsttaskname, _load_some_plugin_data_task_func,
                                        (self._root_git_dir, plugin.name(), _known_arinst_plugin_fname(plugin.name()),
                                         _load_stable_json, self._cache_dir, self._cache_data),
                                        [])
            parallel.add_task(loadarinsttask)

            loadarinstowntaskname = 'sanguine.rootgit.ownloadarinst.' + plugin.name()
            loadarinstowntask = tasks.OwnTask(loadarinstowntaskname,
                                              lambda _, out: self._load_own_arinst_plugin_data_task_func(out), None,
                                              [loadarinsttaskname])
            parallel.add_task(loadarinstowntask)

        loadartaskname = 'sanguine.rootgit.loadar'
        loadartask = tasks.Task(loadartaskname, _load_archives_task_func,
                                (self._root_git_dir, self._cache_dir, self._cache_data), [])
        parallel.add_task(loadartask)
        loadarowntaskname = RootGitData._LOADAROWNTASKNAME
        loadarowntask = tasks.OwnTask(loadarowntaskname,
                                      lambda _, out: self._load_archives_own_task_func(out), None,
                                      [loadartaskname, loadarinstowntasknamepattern],
                                      datadeps=self._loadar_owntask_datadeps())
        parallel.add_task(loadarowntask)

        load2owntaskname = RootGitData._LOADFOOWNTASKNAME
        load2owntask = tasks.OwnTask(load2owntaskname,
                                     lambda _, out: self._load_tentative_names_own_task_func(out), None,
                                     [load2taskname, 'sanguine.rootgit.ownloadfo.*'],
                                     datadeps=self._loadtan_owntask_datadeps())
        parallel.add_task(load2owntask)

    @staticmethod
    def ready_to_start_hashing_task_name() -> str:
        return RootGitData._LOADAROWNTASKNAME

    @staticmethod
    def archives_ready_task_name() -> str:
        return RootGitData._LOADAROWNTASKNAME

    @staticmethod
    def ready_to_start_adding_file_origins_task_name() -> str:
        return RootGitData._LOADFOOWNTASKNAME

    def start_hashing_archive(self, parallel: tasks.Parallel, arpath: str, arhash: bytes, arsize: int) -> None:
        assert self._ar_is_ready == 1 and self._n_ready_arinst_plugins == sum(
            1 if plg.extra_data_factory() else 0 for plg in all_arinstaller_plugins())
        hashingtaskname = 'sanguine.rootgit.hash.' + arpath
        self._nhashes_requested += 1
        tmp_dir = TmpPath.tmp_in_tmp(self._tmp_dir, 'ah.', self._nhashes_requested)
        extrafactories0 = [plugin.extra_data_factory() for plugin in all_arinstaller_plugins()]
        extrafactories = [xf for xf in extrafactories0 if xf is not None]
        hashingtask = tasks.Task(hashingtaskname, _archive_hashing_task_func,
                                 (self._new_hashes_by, arpath, arhash, arsize, tmp_dir, extrafactories), [])
        parallel.add_task(hashingtask)
        hashingowntaskname = 'sanguine.rootgit.ownhash.' + arpath
        hashingowntask = tasks.OwnTask(hashingowntaskname,
                                       lambda _, out: self._archive_hashing_own_task_func(out), None,
                                       [hashingtaskname],
                                       datadeps=self._arhashing_owntask_datadeps())
        parallel.add_task(hashingowntask)

    def add_file_origin(self, h: bytes, fo: FileOrigin) -> None:
        assert self._fo_is_ready == 1
        for plugin in file_origin_plugins():
            if plugin.add_file_origin(h, fo):
                self._dirty_fo = True

    def add_hash_mappings(self, h: bytes, plugins: list[FileOriginPluginBase], hashes: list[bytes]) -> None:
        assert len(plugins) == len(hashes)
        assert self._fo_is_ready == 1
        for i in range(len(plugins)):
            if plugins[i].add_hash_mapping(h, hashes[i]):
                self._dirty_fo = True

    def add_tentative_name(self, h: bytes, tentativename: str) -> None:
        tentativename = tentativename.lower()
        assert self._fo_is_ready == 1
        if h in self._tentative_archive_names:
            for tn in self._tentative_archive_names[h]:
                if tn == tentativename:
                    return
            self._tentative_archive_names[h].append(tentativename)
            self._dirty_fo = True
        else:
            self._tentative_archive_names[h] = [tentativename]
            self._dirty_fo = True

    def start_done_hashing_task(self,  # should be called only after all start_hashing_archive() calls are done
                                parallel: tasks.Parallel) -> str:
        assert self._ar_is_ready == 1
        donehashingowntaskname = 'sanguine.rootgit.donehashing'
        donehashingowntask = tasks.OwnTask(donehashingowntaskname,
                                           lambda _, _1: self._done_hashing_own_task_func(parallel), None,
                                           [RootGitData._LOADAROWNTASKNAME, 'sanguine.rootgit.ownhash.*'],
                                           datadeps=self._done_hashing_owntask_datadeps())
        parallel.add_task(donehashingowntask)

        return donehashingowntaskname

    def start_done_adding_file_origins_task(self,  # should be called only after all add_file_origin() calls are done
                                            parallel: tasks.Parallel) -> None:
        assert self._fo_is_ready == 1
        self._fo_is_ready = 2
        if self._dirty_fo:
            save2taskname = 'sanguine.rootgit.savetan'
            save2task = tasks.Task(save2taskname, _save_tentative_names_task_func,
                                   (self._root_git_dir, self._tentative_archive_names), [])
            parallel.add_task(save2task)

            for plugin in file_origin_plugins():
                savefotaskname = 'sanguine.rootgit.savefo.' + plugin.name()
                wrfunc = plugin.save_json5_file_func()
                assert callable(wrfunc) and not tasks.is_lambda(wrfunc)
                savefotask = tasks.Task(savefotaskname, _save_some_plugin_data_task_func,
                                        (self._root_git_dir, _known_fo_plugin_fname(plugin.name()),
                                         wrfunc, plugin.data_for_saving()),
                                        [])
                parallel.add_task(savefotask)

    def archived_file_by_hash(self, h: bytes) -> list[tuple[Archive, FileInArchive]] | None:
        assert self._ar_is_ready == 2
        return self._archived_files_by_hash.get(truncate_file_hash(h))

    def archive_by_hash(self, arh: bytes, partialok: bool = False) -> Archive | None:
        assert (self._ar_is_ready >= 1) if partialok else (self._ar_is_ready >= 2)
        return self._archives_by_hash.get(arh)

    def tentative_names_for_archive(self, h: bytes) -> list[str]:
        return self._tentative_archive_names.get(h, [])

    def archive_stats(self) -> dict[bytes, tuple[int, int]]:  # hash -> (n,total_size)
        assert self._ar_is_ready == 2
        out: dict[bytes, tuple[int, int]] = {}
        for arh, ar in self._archives_by_hash.items():
            assert ar.archive_hash == arh
            assert arh not in out
            out[arh] = (0, 0)
        for fh, arfilist in self._archived_files_by_hash.items():
            for ar, fina in arfilist:
                assert ar.archive_hash in out
                out[ar.archive_hash] = (out[ar.archive_hash][0] + 1, out[ar.archive_hash][1] + fina.file_size)
        for stats in out.values():
            assert stats[0] != 0

        return out

    def stats_of_interest(self) -> list[str]:
        return ['sanguine.rootgit.savear', 'sanguine.rootgit.loadar',
                'sanguine.rootgit.loadtan', 'sanguine.rootgit.savetan',
                'sanguine.rootgit.ownloadar', 'sanguine.rootgit.ownloadfo',
                'sanguine.rootgit.hash.', 'sanguine.rootgit.ownhash.'
                                          'sanguine.rootgit.donehashing',
                'sanguine.rootgit.']

    ### private functions
    # own tasks with helpers

    def _loadar_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            [],
            ['sanguine.rootgit.done_hashing()'],
            ['sanguine.rootgit._archives_by_hash',
             'sanguine.rootgit._archived_files_by_hash',
             'sanguine.rootgit._archived_files_by_name'])

    def _load_archives_own_task_func(self, out: tuple[dict, dict, dict, dict[str, Any]]) -> None:
        (archives_by_hash, archived_files_by_hash, archived_files_by_name, cacheoverrides) = out
        assert self._archives_by_hash is None
        assert self._archived_files_by_hash is None
        self._archives_by_hash = archives_by_hash
        self._archived_files_by_hash = archived_files_by_hash
        self._archived_files_by_name = archived_files_by_name
        self._cache_data |= cacheoverrides
        assert self._ar_is_ready == 0
        self._ar_is_ready = 1

    def _arhashing_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            ['sanguine.rootgit._archives_by_hash',
             'sanguine.rootgit._archived_files_by_hash',
             'sanguine.rootgit._archived_files_by_name'],
            ['sanguine.rootgit.done_hashing()'],
            [])

    def _archive_hashing_own_task_func(self, out: tuple[list[Archive], dict[str, dict[bytes, Any]]]):
        assert self._ar_is_ready == 1
        (archives, extradata) = out
        for ar in archives:
            _append_archive(self._archives_by_hash, self._archived_files_by_hash, self._archived_files_by_name, ar)
        for pluginname, data0 in extradata.items():
            for arh, data in data0.items():
                arinstaller_plugin_add_extra_data(pluginname, arh, data)
        self._dirty_ar = True

    def _done_hashing_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            ['sanguine.rootgit._archives_by_hash',
             'sanguine.rootgit._archived_files_by_hash',
             'sanguine.rootgit._archived_files_by_name'],
            [],
            ['sanguine.rootgit.done_hashing()'])

    def _done_hashing_own_task_func(self, parallel: tasks.Parallel) -> None:
        assert self._ar_is_ready == 1
        self._ar_is_ready = 2
        if self._dirty_ar:
            savetaskname = 'sanguine.rootgit.savear'
            savetask = tasks.Task(savetaskname, _save_archives_task_func,
                                  (self._root_git_dir, list(self._archives_by_hash.values())), [])
            parallel.add_task(savetask)

            for plugin in all_arinstaller_plugins():
                if plugin.extra_data_factory() is None:
                    continue
                savearinsttaskname = 'sanguine.rootgit.savearinst.' + plugin.name()
                savearinsttask = tasks.Task(savearinsttaskname, _save_some_plugin_data_task_func,
                                            (self._root_git_dir, _known_arinst_plugin_fname(plugin.name()),
                                             _save_stable_json, plugin.data_for_saving()),
                                            [])
                parallel.add_task(savearinsttask)

    def _loadtan_owntask_datadeps(self) -> tasks.TaskDataDependencies:
        return tasks.TaskDataDependencies(
            [],
            [],
            ['sanguine.rootgit._tentative_archive_names'])

    def _load_tentative_names_own_task_func(self, out: tuple[dict[bytes, list[str]], ConfigData]) -> None:
        assert self._fo_is_ready == 0
        self._fo_is_ready = 1
        (tanames, cacheoverrides) = out
        assert self._tentative_archive_names is None
        self._tentative_archive_names = tanames
        self._cache_data |= cacheoverrides

    def _load_own_fo_plugin_data_task_func(self, out: tuple[Any, ConfigData]) -> None:
        assert self._fo_is_ready == 0
        (loadret, cacheoverrides) = out
        (name, plugindata) = loadret
        plugin = file_origin_plugin_by_name(name)
        plugin.got_loaded_data(plugindata)
        self._cache_data |= cacheoverrides

    def _load_own_arinst_plugin_data_task_func(self, out: tuple[Any, ConfigData]) -> None:
        self._n_ready_arinst_plugins += 1
        (loadret, cacheoverrides) = out
        (name, plugindata) = loadret
        plugin = arinstaller_plugin_by_name(name)
        plugin.got_loaded_data(plugindata)
        self._cache_data |= cacheoverrides
