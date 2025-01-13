from sanguine.common import *
from sanguine.helpers.modlist import ModList
from sanguine.helpers.project_config import (ModManagerConfig, ModManagerPluginBase, config_dir_path,
                                             normalize_source_vfs_dir_path)


class Mo2Plugin(ModManagerPluginBase):
    def mod_manager_name(self) -> str:
        return 'mo2'

    def config_factory(self) -> ModManagerConfig:
        return Mo2ProjectConfig(self.mod_manager_name())


class Mo2ProjectConfig(ModManagerConfig):
    mo2dir: FolderToCache | None
    ignore_dirs: list[str]
    master_profile: str | None
    generated_profiles: dict[str, str] | None
    master_modlist: ModList | None
    _vfs_files: dict[str, list[str]] | None

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.mo2dir = None
        self.master_profile = None
        self.generated_profiles = None
        self.master_modlist = None
        self._vfs_files = None

    def parse_config_section(self, section: ConfigData, configdir: str, fullconfig: ConfigData,
                             download_dirs: list[str]) -> None:
        unused_config_warning('mo2', section,
                              ['mo2dir', 'ignores', 'masterprofile', 'generatedprofiles'])

        abort_if_not('mo2dir' in section, "'mo2dir' must be present in config.mo2 for modmanager=mo2")
        mo2dir = config_dir_path(section['mo2dir'], configdir, fullconfig)
        abort_if_not(isinstance(mo2dir, str), 'config.mo2.mo2dir must be a string')

        ignores = section.get('ignores', ['{DEFAULT-MO2-IGNORES}'])
        abort_if_not(isinstance(ignores, list), lambda: "config.mo2.ignores must be a list, got " + repr(ignores))
        self.ignore_dirs = []
        for ignore in ignores:
            if ignore == '{DEFAULT-MO2-IGNORES}':
                self.ignore_dirs += [normalize_dir_path(mo2dir + defignore) for defignore in [
                    'plugins\\data\\RootBuilder',
                    'crashDumps',
                    'logs',
                    'webcache',
                    'overwrite\\Root\\Logs',
                    'overwrite\\ShaderCache'
                ]]
            else:
                self.ignore_dirs.append(normalize_source_vfs_dir_path(ignore, mo2dir))

        assert self.mo2dir is None
        self.mo2dir = FolderToCache(mo2dir, self.ignore_dirs + [mo2dir + 'mods\\'] + download_dirs)

        assert self.master_profile is None
        assert self.generated_profiles is None
        self.master_profile = section.get('masterprofile')
        abort_if_not(self.master_profile is not None and isinstance(self.master_profile, str),
                     lambda: "'masterprofile' in config must be a string, got " + repr(self.master_profile))
        abort_if_not(os.path.isdir(self.mo2dir.folder + 'profiles\\' + self.master_profile))

        self.generated_profiles = section.get('generatedprofiles')
        abort_if_not(self.generated_profiles is not None and isinstance(self.generated_profiles, dict),
                     lambda: "'generatedprofiles' in config must be a list, got " + repr(self.generated_profiles))
        for gp in self.generated_profiles.keys():
            abort_if_not(os.path.isdir(self.mo2dir.folder + 'profiles\\' + gp))

        assert self.master_modlist is None
        self.master_modlist = ModList(
            normalize_dir_path(self.mo2dir.folder + 'profiles\\' + self.master_profile + '\\'))

    def is_path_ignored(self, path: str) -> bool:
        for ig in self.ignore_dirs:
            if path.startswith(ig):
                return True
        return False

    def active_source_vfs_folders(self) -> FolderListToCache:
        out: FolderListToCache = FolderListToCache([self.mo2dir])
        modsdir = self.mo2dir.folder + 'mods\\'
        assert modsdir in self.mo2dir.exdirs
        exdirs = [x for x in self.mo2dir.exdirs if x != modsdir]

        for mod in self.master_modlist.all_enabled():
            folder = normalize_dir_path(self.mo2dir.folder + 'mods\\' + mod + '\\')
            if FolderToCache.ok_to_construct(folder, exdirs) and not self.is_path_ignored(folder):
                out.append(FolderToCache(folder, exdirs))
        return out

    def default_download_dirs(self) -> list[str]:
        return ['{mo2.mo2dir}downloads\\']

    def source_vfs_to_target_vfs(self, path: str) -> str | None:  # returns path relative to target vfs root
        assert is_normalized_path(path)
        assert path.startswith(self.mo2dir.folder)
        mo2mods = self.mo2dir.folder + 'mods\\'
        if not path.startswith(mo2mods):
            return None
        relpath = path[len(mo2mods):]
        slash = relpath.find('\\')
        if slash == -1:
            return None
        relpath = relpath[slash + 1:]

        # MO2 Root plugin
        if relpath.startswith('root\\'):
            return relpath[len('root\\'):]

        return 'data\\' + relpath

    def resolve_vfs(self, sourcevfs: Iterable[FileOnDisk]) -> ResolvedVFS:
        info('MO2: Starting resolving VFS...')

        allenabled = list(self.master_modlist.all_enabled())
        modsrch = FastSearchOverPartialStrings(
            [(self.mo2dir.folder + 'mods\\' + allenabled[i].lower() + '\\', i) for i in range(len(allenabled))])

        source_to_target: dict[str, str] = {}
        target_files0: dict[str, list[tuple[int, FileOnDisk]]] = {}
        nfound = 0
        nnotfound = 0
        for f in sourcevfs:
            relpath = self.source_vfs_to_target_vfs(f.file_path)
            if relpath is None:
                nnotfound += 1
                continue
            nfound += 1

            res = modsrch.find_val_for_str(f.file_path)
            assert res is not None
            _, modidx = res
            assert isinstance(modidx, int)
            assert f.file_path.startswith(self.mo2dir.folder + 'mods\\' + allenabled[modidx].lower() + '\\')

            if relpath not in target_files0:
                target_files0[relpath] = []
            target_files0[relpath].append((modidx, f))

            assert f.file_path not in source_to_target
            source_to_target[f.file_path] = relpath

        assert nfound == len(source_to_target)

        target_files: dict[str, list[FileOnDisk]] = {}
        for key, val in target_files0.items():
            val = sorted(val, key=lambda x: x[0])
            assert key not in target_files
            target_files[key] = [f[1] for f in val]
            assert (len(target_files[key]) == len(set(target_files[key])))

        info('MO2: ResolvedVFS: {} files omitted, {} resolved, with {} overrides'.format(nnotfound, nfound,
                                                                                         nfound - len(target_files)))
        return ResolvedVFS(source_to_target, target_files)

    def source_vfs_to_relative_path(self, path: str) -> str:
        assert is_normalized_path(path)
        assert path.startswith(self.mo2dir.folder)
        return path[len(self.mo2dir.folder):]
