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
    mo2dir: str | None
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
                    'overwrite\\Root\\Logs',
                    'overwrite\\Root\\Backup',
                    'overwrite\\ShaderCache'
                ]]
            else:
                self.ignore_dirs.append(normalize_source_vfs_dir_path(ignore, mo2dir))

        assert self.mo2dir is None
        self.mo2dir = mo2dir

        assert self.master_profile is None
        assert self.generated_profiles is None
        self.master_profile = section.get('masterprofile')
        abort_if_not(self.master_profile is not None and isinstance(self.master_profile, str),
                     lambda: "'masterprofile' in config must be a string, got " + repr(self.master_profile))
        abort_if_not(os.path.isdir(self.mo2dir + 'profiles\\' + self.master_profile))

        self.generated_profiles = section.get('generatedprofiles')
        abort_if_not(self.generated_profiles is not None and isinstance(self.generated_profiles, dict),
                     lambda: "'generatedprofiles' in config must be a list, got " + repr(self.generated_profiles))
        for gp in self.generated_profiles.keys():
            abort_if_not(os.path.isdir(self.mo2dir + 'profiles\\' + gp))

        assert self.master_modlist is None
        self.master_modlist = ModList(
            normalize_dir_path(self.mo2dir + 'profiles\\' + self.master_profile + '\\'))

    def is_path_ignored(self, path: str) -> bool:
        for ig in self.ignore_dirs:
            if path.startswith(ig):
                return True
        return False

    def active_source_vfs_folders(self) -> FolderListToCache:
        overwritef = self.mo2dir + 'overwrite\\'
        if FolderToCache.ok_to_construct(overwritef, self.ignore_dirs):
            overwrite = [FolderToCache(overwritef, self.ignore_dirs)]
        else:
            overwrite = []
        out: FolderListToCache = FolderListToCache(overwrite)
        exdirs = self.ignore_dirs

        for mod in self.master_modlist.all_enabled():
            folder = normalize_dir_path(self.mo2dir + 'mods\\' + mod + '\\')
            if FolderToCache.ok_to_construct(folder, exdirs) and not self.is_path_ignored(folder):
                out.append(FolderToCache(folder, exdirs))
        return out

    def default_download_dirs(self) -> list[str]:
        return ['{mo2.mo2dir}downloads\\']

    def modfile_to_target_vfs(self, mf: ModFile) -> str:  # returns path relative to target vfs root
        if mf.mod is None:
            return mf.intramod

        # MO2 RootBuilder plugin
        if mf.intramod.startswith('root\\'):
            return mf.intramod[len('root\\'):]

        return 'data\\' + mf.intramod

    def resolve_vfs(self, sourcevfs: Iterable[FileOnDisk]) -> ResolvedVFS:
        info('MO2: Starting resolving VFS...')

        allenabled = list(self.master_modlist.all_enabled())
        modsrch = FastSearchOverPartialStrings(
            [(self.mo2dir + 'overwrite\\', -1)] + [(self.mo2dir + 'mods\\' + allenabled[i].lower() + '\\', i) for i in
                                                   range(len(allenabled))])

        source_to_target: dict[str, ModFile] = {}
        target_files0: dict[str, list[tuple[ModFile, int, FileOnDisk]]] = {}
        noverrides = 0
        nsourcevfs = 0
        for f in sourcevfs:
            mf: ModFile = self.parse_source_vfs(f.file_path)
            relpath = self.modfile_to_target_vfs(mf)
            assert relpath is not None
            nsourcevfs += 1

            res = modsrch.find_val_for_str(f.file_path)
            assert res is not None
            _, modidx = res
            assert isinstance(modidx, int)
            if __debug__:
                if modidx < 0:
                    assert modidx == -1
                    assert f.file_path.startswith(self.mo2dir + 'overwrite\\')
                else:
                    assert f.file_path.startswith(self.mo2dir + 'mods\\' + allenabled[modidx].lower() + '\\')

            if relpath not in target_files0:
                target_files0[relpath] = []
            else:
                noverrides += 1
            target_files0[relpath].append((mf, modidx, f))

            assert f.file_path not in source_to_target
            source_to_target[f.file_path] = mf

        assert nsourcevfs == len(source_to_target)

        target_files: dict[ModFile, list[FileOnDisk]] = {}
        for key, val in target_files0.items():
            val = sorted(val, key=lambda x: x[0])
            assert key not in target_files
            target_files[key] = [f[1] for f in val]
            assert (len(target_files[key]) == len(set(target_files[key])))

        assert nsourcevfs == len(target_files)
        info('MO2: ResolvedVFS: {} files resolved, with {} overrides'.format(nsourcevfs, noverrides))
        return ResolvedVFS(source_to_target, target_files)

    def parse_source_vfs(self, path: str) -> ModFile:
        assert is_normalized_file_path(path)
        overwrite = self.mo2dir + 'overwrite\\'
        if path.startswith(overwrite):
            return ModFile(None, path[len(overwrite):])
        modsdir = self.mo2dir + 'mods\\'
        assert path.startswith(modsdir)
        lmodsdir = len(modsdir)
        slash = path.find('\\', lmodsdir)
        assert slash >= 0
        return ModFile(path[lmodsdir:slash], path[slash + 1:])
