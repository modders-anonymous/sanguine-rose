import re

import json5

from sanguine.common import *
from sanguine.gitdata.file_origin import config_file_origin_plugins
from sanguine.helpers.plugin_handler import load_plugins
from sanguine.install.install_github import GithubFolder, clone_github_project, github_project_exists


def _normalize_config_dir_path(path: str, configdir: str) -> str:  # relative to config dir
    if os.path.isabs(path):
        return normalize_dir_path(path)
    else:
        return normalize_dir_path(configdir + path)


def config_dir_path(path: str, configdir: str, config: ConfigData):
    path = _normalize_config_dir_path(path, configdir)
    path = path.replace('{CONFIG-DIR}', configdir)
    replaced = False
    pattern = re.compile(r'\{(.*)}')
    m = pattern.search(path)
    if m:
        found = m.group(1)
        spl = found.split('.')
        cur = config
        for name in spl:
            raise_if_not(name in cur, lambda: 'unable to resolve {} in {}'.format(found, configdir))
            cur = cur[name]
        raise_if_not(isinstance(cur, str), lambda: '{} in {} must be a string'.format(found, configdir))
        path = pattern.sub(cur, path)
        replaced = True

    if replaced:
        return config_dir_path(path, configdir, config)
    else:
        return path


def normalize_source_vfs_dir_path(path: str, rootvfsdir: str) -> str:  # relative to vfs dir
    if os.path.isabs(path):
        out = normalize_dir_path(path)
    else:
        out = normalize_dir_path(rootvfsdir + path)
    raise_if_not(out.startswith(rootvfsdir), lambda: 'expected path within vfs, got ' + repr(path))
    return out


def make_dirs_for_file(fname: str) -> None:
    os.makedirs(os.path.split(fname)[0], exist_ok=True)


def folder_size(rootpath: str):
    total = 0
    for dirpath, dirnames, filenames in os.walk(rootpath):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            assert not os.path.islink(fp)
            total += os.path.getsize(fp)
    return total


class ModManagerConfig:
    mod_manager_name: str

    def __init__(self, modmanagername: str) -> None:
        self.mod_manager_name = modmanagername

    @abstractmethod
    def parse_config_section(self, section: ConfigData, configdir: str, fullconfig: ConfigData,
                             download_dirs: list[str]) -> None:
        pass

    @abstractmethod
    def default_download_dirs(self) -> list[str]:
        pass

    @abstractmethod
    def active_source_vfs_folders(self) -> FolderListToCache:
        pass

    @abstractmethod
    def modfile_to_target_vfs(self, mf: ModFile) -> str:  # returns path relative to target vfs root
        pass

    @abstractmethod
    def resolve_vfs(self, sourcevfs: Iterable[FileOnDisk]) -> ResolvedVFS:
        pass

    @abstractmethod
    def parse_source_vfs(self, path: str) -> ModFile:
        pass

    @abstractmethod
    def modfile_to_source_vfs(self, mf: ModFile) -> str:
        pass


class ModManagerPluginBase(ABC):
    def __init__(self) -> None:
        pass

    @abstractmethod
    def mod_manager_name(self) -> str:
        pass

    @abstractmethod
    def config_factory(self) -> ModManagerConfig:
        pass


_modmanager_plugins: list[ModManagerPluginBase] = []


def _found_plugin(plugin: ModManagerPluginBase):
    global _modmanager_plugins
    _modmanager_plugins.append(plugin)


load_plugins('plugins/modmanager/', ModManagerPluginBase, lambda plugin: _found_plugin(plugin))


def _find_config(name: str) -> ModManagerConfig | None:
    global _modmanager_plugins
    for mm in _modmanager_plugins:
        if mm.mod_manager_name() == name:
            mmc = mm.config_factory()
            assert mmc.mod_manager_name == name
            return mmc
    return None


def _all_config_names() -> list[str]:
    global _modmanager_plugins
    return [mm.mod_manager_name() for mm in _modmanager_plugins]


def _all_configs_string() -> str:
    global _modmanager_plugins
    out = ''
    for mm in _modmanager_plugins:
        if out != '':
            out += ','
        out += "'" + mm.mod_manager_name() + "'"
    return out


class GithubModpack(GithubFolder):
    subfolder: str

    def __init__(self, combined2or3: str) -> None:
        spl = GithubFolder.ghsplit(combined2or3)
        super().__init__(spl[0])
        self.subfolder = spl[1]

    @staticmethod
    def is_ok(combined2or3: str) -> bool:
        return GithubFolder.ghsplit(combined2or3) is not None

    def mpfolder(self, rootgitdir: str) -> str:
        parentdir = self.folder(rootgitdir)
        return parentdir if self.subfolder == '' else parentdir + self.subfolder.lower() + '\\'

    def mpto_str(self) -> str:
        parent = self.to_str()
        return parent if self.subfolder == '' else parent + '/' + self.subfolder


class GithubModpackConfig:
    is_root: bool
    # for root:
    game_universe: str | None
    origin_configs: ConfigData | None
    ignored_file_patterns: list[str]

    # for non-root:
    dependencies: list[GithubModpack]
    own_mod_names: list[str]

    def __init__(self, jsonconfigfname: str, jsonconfig: ConfigData) -> None:
        is_root = jsonconfig.get('isroot', 0)
        raise_if_not(is_root == 1 or is_root == 0)
        self.is_root = is_root != 0
        if self.is_root:
            unused_config_warning(jsonconfigfname, jsonconfig, ['isroot', 'origins', 'gameuniverse', 'ignorepatterns'])
            self.origin_configs = jsonconfig.get('origins', {})
            raise_if_not('gameuniverse' in jsonconfig)
            self.game_universe = jsonconfig['gameuniverse']
            self.dependencies = []
            self.own_mod_names = []
            self.ignored_file_patterns = jsonconfig.get('ignorepatterns', [])
            if isinstance(self.ignored_file_patterns, str):
                self.ignored_file_patterns = [self.ignored_file_patterns]
            raise_if_not(isinstance(self.ignored_file_patterns, list))
            self.ignored_file_patterns = self.ignored_file_patterns
        else:
            unused_config_warning('ModpackConfig', jsonconfig, ['isroot', 'dependencies', 'ownmods'])
            self.origin_configs = None
            self.game_universe = None
            self.dependencies = [GithubModpack(d) for d in jsonconfig['dependencies']]
            self.own_mod_names = [normalize_file_name(om) for om in jsonconfig.get('ownmods', [])]


def install_github_project_with_dependencies(ui: LinearUI, ghproject: str, githubrootdir: str,
                                             allmodpackconfigs: ConfigData) -> str | None:
    rootmodpack: str | None = None
    if ghproject in allmodpackconfigs:
        return

    gh = GithubModpack(ghproject)
    ok = github_project_exists(githubrootdir, gh)
    if ok == -1:
        critical(
            'Fatal error: folder {} exists, but does not contain {}/{}'.format(gh.folder(githubrootdir),
                                                                               gh.author, gh.project))
        raise_if_not(False)

    if ok == 0:
        info('Cloning GitHub project: {}'.format(ghproject))
        clone_github_project(githubrootdir, gh, ui.network_error_handler(2))
        info('GitHub project {} cloned successfully'.format(ghproject))

    assert ok == 1
    jsonconfigfname = gh.mpfolder(githubrootdir) + 'sanguine.json5'
    with open_3rdparty_txt_file_autodetect(jsonconfigfname) as rf:
        jsonconfig = json5.load(rf)
        mpcfg = GithubModpackConfig(jsonconfigfname, jsonconfig)
        allmodpackconfigs[ghproject] = mpcfg

        if mpcfg.is_root:
            raise_if_not(rootmodpack is None)
            rootmodpack = ghproject

        for d in mpcfg.dependencies:
            rmp = install_github_project_with_dependencies(ui, d.mpto_str(), githubrootdir, allmodpackconfigs)
            raise_if_not(rmp is None or rootmodpack is None)
            if rmp is not None:
                rootmodpack = rmp

    return rootmodpack


class LocalProjectConfig:
    config_dir: str
    mod_manager_config: ModManagerConfig
    download_dirs: list[str]
    cache_dir: str
    tmp_dir: str
    github_root_dir: str
    all_modpack_configs: dict[str, GithubModpackConfig]
    this_modpack: str
    root_modpack: str | None
    github_username: str | None

    # TODO: check that sanguine-rose itself, cache_dir, and tmp_dir don't overlap with any of the dirs
    def __init__(self, ui: LinearUI, jsonconfigfname: str) -> None:
        self.config_dir = normalize_dir_path(os.path.split(jsonconfigfname)[0])
        with (open_3rdparty_txt_file_autodetect(jsonconfigfname) as f):
            jsonconfig = json5.loads(f.read())
            unused_config_warning(jsonconfigfname, jsonconfig,
                                  ['modmanager', 'downloads', 'cache', 'tmp', 'githubroot', 'modpack',
                                   'githubusername'] + _all_config_names())

            raise_if_not('modmanager' in jsonconfig, "'modmanager' must be present in config")
            modmanager = jsonconfig['modmanager']
            self.mod_manager_config = _find_config(modmanager)
            raise_if_not(self.mod_manager_config is not None,
                         lambda: "config.modmanager must be one of [{}]".format(_all_configs_string()))

            raise_if_not(self.mod_manager_config.mod_manager_name in jsonconfig,
                         lambda: "'{}' must be present in config for modmanager={}".format(
                             self.mod_manager_config.mod_manager_name,
                             self.mod_manager_config.mod_manager_name))
            mmc_config = jsonconfig[self.mod_manager_config.mod_manager_name]
            raise_if_not(isinstance(mmc_config, dict),
                         lambda: "config.{} must be a dictionary, got {}".format(
                             self.mod_manager_config.mod_manager_name,
                             repr(mmc_config)))

            if 'downloads' not in jsonconfig:
                dls = self.mod_manager_config.default_download_dirs()
            else:
                dls = jsonconfig['downloads']
            if isinstance(dls, str):
                dls = [dls]
            raise_if_not(isinstance(dls, list),
                         lambda: "'downloads' in config must be a string or a list, got " + repr(dls))
            self.download_dirs = [config_dir_path(dl, self.config_dir, jsonconfig) for dl in dls]

            self.mod_manager_config.parse_config_section(mmc_config, self.config_dir, jsonconfig, self.download_dirs)

            self.cache_dir = config_dir_path(jsonconfig.get('cache', self.config_dir + '.\\sanguine.cache\\'),
                                             self.config_dir,
                                             jsonconfig)
            self.tmp_dir = config_dir_path(jsonconfig.get('tmp', self.config_dir + '.\\sanguine.tmp\\'),
                                           self.config_dir,
                                           jsonconfig)

            self.github_root_dir = config_dir_path(jsonconfig.get('githubroot', '.\\'), self.config_dir,
                                                   jsonconfig)

            raise_if_not('modpack' in jsonconfig)
            ghmodpack = jsonconfig['modpack']
            raise_if_not(isinstance(ghmodpack, str) and GithubModpack.is_ok(ghmodpack))

            self.all_modpack_configs = {}
            self.this_modpack = ghmodpack
            self.root_modpack = install_github_project_with_dependencies(ui, ghmodpack, self.github_root_dir,
                                                                         self.all_modpack_configs)
            raise_if_not(self.root_modpack is not None)
            raise_if_not(self.root_modpack != self.this_modpack)
            assert self.root_modpack in self.all_modpack_configs
            config_file_origin_plugins(self.all_modpack_configs[self.root_modpack].origin_configs)

            raise_if_not('githubusername' in jsonconfig)
            self.github_username = jsonconfig['githubusername']

    def root_modpack_config(self) -> GithubModpackConfig:
        assert self.root_modpack is not None
        assert self.root_modpack in self.all_modpack_configs
        return self.all_modpack_configs[self.root_modpack]

    def active_source_vfs_folders(self) -> FolderListToCache:
        return self.mod_manager_config.active_source_vfs_folders()

    def github_folders(self) -> list[GithubFolder]:
        return [GithubModpack(mp) for mp in self.all_modpack_configs.keys()]

    def this_modpack_folder(self) -> str:
        return GithubModpack(self.this_modpack).mpfolder(self.github_root_dir)

    def modfile_to_target_vfs(self, mf: ModFile) -> str:  # returns path relative to target vfs root
        return self.mod_manager_config.modfile_to_target_vfs(mf)

    def modfile_to_source_vfs(self, mf: ModFile) -> str:
        return self.mod_manager_config.modfile_to_source_vfs(mf)

    def resolve_vfs(self, srcfiles: Iterable[FileOnDisk]) -> ResolvedVFS:
        return self.mod_manager_config.resolve_vfs(srcfiles)

    def parse_source_vfs(self, path: str) -> ModFile:
        return self.mod_manager_config.parse_source_vfs(path)

    # private functions
