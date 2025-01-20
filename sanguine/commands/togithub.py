import re

from sanguine.cache.available_files import AvailableFiles
from sanguine.cache.folder_cache import FolderCache
from sanguine.cache.whole_cache import WholeCache
from sanguine.common import *
from sanguine.helpers.archives import Archive, FileInArchive
from sanguine.helpers.arinstallers import ArInstaller, all_arinstaller_plugins
from sanguine.helpers.file_retriever import (FileRetriever, ArchiveFileRetriever,
                                             GithubFileRetriever, ZeroFileRetriever)
from sanguine.helpers.project_config import LocalProjectConfig
from sanguine.helpers.tools import ToolPluginBase, all_tool_plugins, CouldBeProducedByTool
from sanguine.plugins.arinstaller.x99simple import SimpleArInstaller


class _IgnoredTargetFiles:
    ignored_file_patterns: list

    def __init__(self, cfg: LocalProjectConfig) -> None:
        self.ignored_file_patterns = [re.compile(p) for p in cfg.root_modpack_config().ignored_file_patterns]

    def ignored(self, fpath: str) -> bool:
        for p in self.ignored_file_patterns:
            if p.match(fpath):
                return True
        return False


class _ArInstEx:
    ignored: set[str]
    skip: set[str]
    files: dict[str, FileInArchive]
    modified_since_install: set[str]

    def __init__(self) -> None:
        self.ignored = set()
        self.skip = set()
        self.files = {}
        self.modified_since_install = set()


class _ModInProgress:
    name: str
    # all *_files members use intramod as 1st parameter
    unknown_files: set[str]
    zero_files: set[str]
    github_files: dict[str, list[GithubFileRetriever]]
    archive_files: dict[str, list[ArchiveFileRetriever]]

    # files: dict[str, list[FileRetriever]]  # intramod -> list of retrievers
    known_archives: dict[bytes, tuple[Archive, int]]
    required_archives: dict[bytes, tuple[Archive, int]] | None
    install_from: list[tuple[ArInstaller, _ArInstEx]] | None
    remaining_after_install_from: dict[str, list[ArchiveFileRetriever]] | None
    could_be_produced_by_tools: dict[str, tuple[str, CouldBeProducedByTool]] | None

    # modified_from_install: dict[str, tuple[str | None, CouldBeProducedByTool] | None] | None
    # skip_from_install: dict[str, bool] | None

    def __init__(self, name: str) -> None:
        self.name = name
        # self.files = {}
        self.unknown_files = set()
        self.zero_files = set()
        self.github_files = {}
        self.archive_files = {}

        self.known_archives = {}
        self.required_archives = None

        self.install_from = None
        # self.install_from_root = None
        self.remaining_after_install_from = None
        # self.modified_from_install = None
        # self.skip_from_install = None
        self.could_be_produced_by_tools = None

    def add_file(self, available: AvailableFiles, intramod: str, retrievers: list[FileRetriever]) -> None:
        assert intramod not in self.unknown_files
        assert intramod not in self.zero_files
        assert intramod not in self.github_files
        assert intramod not in self.archive_files

        if len(retrievers) == 0:
            self.unknown_files.add(intramod)
        else:
            r0 = retrievers[0]
            if isinstance(r0, ZeroFileRetriever):
                assert len(retrievers) == 1
                self.zero_files.add(intramod)
            elif isinstance(r0, GithubFileRetriever):
                if __debug__:
                    for r in retrievers:
                        assert r.file_hash == r0.file_hash
                        assert isinstance(r, GithubFileRetriever)
                # noinspection PyTypeChecker
                # we just asserted it in a loop above
                self.github_files[intramod] = retrievers
            else:
                assert isinstance(r0, ArchiveFileRetriever)
                for r in retrievers:
                    assert r.file_hash == r0.file_hash
                    assert isinstance(r, ArchiveFileRetriever)
                    arh = r.archive_hash()
                    if arh not in self.known_archives:
                        ar = available.archive_by_hash(arh)
                        self.known_archives[arh] = (ar, 1)
                    self.known_archives[arh] = (self.known_archives[arh][0], self.known_archives[arh][1] + 1)
                # noinspection PyTypeChecker
                # we just asserted it in a loop above
                self.archive_files[intramod] = retrievers

    def total_files(self) -> int:
        return len(self.unknown_files) + len(self.zero_files) + len(self.github_files) + len(self.archive_files)

    def modified_since_install(self) -> Iterable[str]:
        out = []
        for arinst, arext in self.install_from:
            out += arext.modified_since_install
        return out

    '''
    @staticmethod
    def _assert_arfh_in_arfiles_by_hash(arfh: bytes, arintra: str,
                                        arfiles_by_hash: dict[bytes, list[FileInArchive]]) -> None:
        assert arfh in arfiles_by_hash
        arfs = arfiles_by_hash[arfh]
        ok = False
        for arf in arfs:
            if arf.intra_path == arintra:
                ok = True
                break
        assert ok
    @staticmethod
    def _best_unmatched_from_arfiles_by_hash(arfh: bytes, arintra: str,
                                             arfiles_by_hash: dict[bytes, list[FileInArchive]]) -> str:
        assert arfh in arfiles_by_hash
        arfs = arfiles_by_hash[arfh]
        return arfs[0].intra_path  # TODO! - best matching name?
    '''

    def _process_aic_clearing_remaining_after(self, cfg: LocalProjectConfig, srccache: FolderCache, aic: _ArInstEx):
        for f in aic.files:
            mf = ModFile(self.name, f)
            src = cfg.modfile_to_source_vfs(mf)
            srcfile = srccache.file_by_path(src)
            assert srcfile is not None
            if aic.files[f].file_hash == truncate_file_hash(srcfile.file_hash):
                if f in self.remaining_after_install_from: # might have already been deleted if identical file is present in multiple archives
                    del self.remaining_after_install_from[f]
            else:
                aic.skip.add(f)
                aic.modified_since_install.add(f)

    def _inter_dependency(self, cfg: LocalProjectConfig, srccache: FolderCache, ar0: tuple[ArInstaller, _ArInstEx],
                          ar1: tuple[ArInstaller, _ArInstEx]) -> tuple[bool, bool]:
        aoverb = 0
        bovera = 0
        files0: dict[str, FileInArchive] = ar0[1].files
        files1: dict[str, FileInArchive] = ar1[1].files
        commonfiles: set[str] = set(files0).intersection(set(files1))
        for cf in commonfiles:
            if files0[cf].file_hash == files1[cf].file_hash:
                continue
            mf = ModFile(self.name, cf)
            src = cfg.modfile_to_source_vfs(mf)
            srcfile = srccache.file_by_path(src)
            assert srcfile is not None
            if files0[cf].file_hash == truncate_file_hash(srcfile.file_hash):
                aoverb += 1
            elif files1[cf].file_hash == truncate_file_hash(srcfile.file_hash):
                bovera += 1
        return aoverb, bovera

    def resolve_unique(self, cfg: LocalProjectConfig, itf: _IgnoredTargetFiles, srccache: FolderCache) -> None:
        assert self.required_archives is None
        assert self.install_from is None
        assert self.remaining_after_install_from is None
        assert self.could_be_produced_by_tools is None
        self.required_archives = {}

        for intra, rlist in self.archive_files.items():
            assert len(rlist) > 0
            if len(rlist) == 1:
                r0: ArchiveFileRetriever = rlist[0]
                arh = r0.archive_hash()
                assert arh in self.known_archives
                self.required_archives[arh] = self.known_archives[arh]

        self.install_from = []
        for rav in self.required_archives.values():
            ra: Archive = rav[0]
            for plugin in all_arinstaller_plugins():
                guess = plugin.guess_arinstaller_from_vfs(ra, self.name, self.archive_files)
                if guess is not None:
                    if isinstance(guess, SimpleArInstaller) and guess.install_from_root != '':
                        pass
                    aic = _ArInstEx()
                    self.install_from.append((guess, aic))
                    for f, fia in guess.all_desired_files():
                        if not f in self.archive_files:
                            aic.skip.add(f)
                            continue

                        mf = ModFile(self.name, f)
                        target = cfg.modfile_to_target_vfs(mf)
                        if itf.ignored(target):
                            aic.ignored.add(f)
                        else:
                            aic.files[f] = fia
                    break

        assert self.remaining_after_install_from is None
        self.remaining_after_install_from = self.archive_files.copy()
        if len(self.install_from) == 1:
            ar0: tuple[ArInstaller, _ArInstEx] = self.install_from[0]
            _, aic = ar0
            self._process_aic_clearing_remaining_after(cfg, srccache, aic)
        elif len(self.install_from) > 1:
            dependencies: set[tuple[int, int]] = set()
            for i in range(len(self.install_from)):
                for j in range(i + 1, len(self.install_from)):
                    assert j != i
                    ioverj, joveri = self._inter_dependency(cfg, srccache, self.install_from[i], self.install_from[j])
                    if ioverj:
                        dependencies.add((i, j))
                    if joveri:
                        dependencies.add((j, i))

            ordered: list[int] = []
            while len(ordered) < len(self.install_from):
                # looking for non-dependent one
                roundok = False
                for i in range(len(self.install_from)):
                    if i in ordered:
                        continue
                    iok = True
                    for j in range(len(self.install_from)):
                        if j not in ordered and (i, j) in dependencies:
                            iok = False
                            break  # for j
                    if iok:
                        ordered.append(i)
                        roundok = True
                        break  # for i
                abort_if_not(roundok)  # circular dependency, TODO: handle it

            assert len(ordered) == len(self.install_from)
            assert len(ordered) == len(set(ordered))
            newsif = [self.install_from[i] for i in ordered]
            assert len(newsif) == len(self.install_from)
            self.install_from = newsif

            for _, arx in self.install_from:
                self._process_aic_clearing_remaining_after(cfg, srccache, arx)

        if __debug__:
            fromarch: set[str] = set(self.remaining_after_install_from.keys())
            for arinst, arinstx0 in self.install_from:
                arinstx: _ArInstEx = arinstx0

                for f in arinstx.files:
                    if f not in arinstx.modified_since_install:
                        fromarch.add(f)

            if len(fromarch) != len(self.archive_files):
                assert False
            assert len(fromarch.intersection(self.archive_files)) == len(fromarch)

    def _has_skips(self) -> bool:
        for _, arext in self.install_from:
            if len(arext.skip) > 0:
                return True
        return False

    def is_fully_github(self) -> bool:
        return len(self.archive_files) == 0

    def is_trivially_installed(self) -> bool:
        return self.is_fully_installed() and not self._has_skips()

    def is_fully_installed(self) -> bool:
        return len(self.unknown_files) == 0 and len(self.remaining_after_install_from) == 0

    def is_healable_to_trivial_install(self) -> bool:
        return len(self.unknown_files) == 0 and len(self.remaining_after_install_from) == len(
            self.could_be_produced_by_tools) and not self._has_skips()


class _ModsInProgress:
    _cfg: LocalProjectConfig
    _available: AvailableFiles
    mods: dict[str, _ModInProgress]
    _all_retrievers: dict[bytes, list[FileRetriever]]

    def __init__(self, cfg: LocalProjectConfig, available: AvailableFiles) -> None:
        self.mods = {}
        self._cfg = cfg
        self._available = available
        self._all_retrievers = {}

    def has_retrievers_for(self, h: bytes) -> bool:
        return h in self._all_retrievers

    def add_new_file(self, mf: ModFile, retrievers: list[FileRetriever]) -> None:
        if len(retrievers) > 0:
            h0 = retrievers[0].file_hash
            assert not self.has_retrievers_for(h0)
            if __debug__:
                for r in retrievers:
                    assert r.file_hash == h0

            if h0 not in self._all_retrievers:
                self._all_retrievers[h0] = retrievers

        if mf.mod not in self.mods:
            self.mods[mf.mod] = _ModInProgress(mf.mod)
        self.mods[mf.mod].add_file(self._available, mf.intramod, retrievers)

    def add_dup_file(self, mf: ModFile, h: bytes) -> None:
        assert self.has_retrievers_for(h)
        if mf.mod not in self.mods:
            self.mods[mf.mod] = _ModInProgress(mf.mod)
        self.mods[mf.mod].add_file(self._available, mf.intramod, self._all_retrievers[h])

    def all_retrievers(self) -> Iterable[tuple[bytes, list[FileRetriever]]]:
        return self._all_retrievers.items()

    def resolve_unique(self, srccache: FolderCache) -> None:
        itf = _IgnoredTargetFiles(self._cfg)
        for mod in self.mods:
            self.mods[mod].resolve_unique(self._cfg, itf, srccache)


class _ToolFinder:
    tools_by_ext: dict[str, list[tuple[ToolPluginBase, Any]]]

    def __init__(self, cfg: LocalProjectConfig, resolvedvfs: ResolvedVFS) -> None:
        self.tools_by_ext = {}
        for plugin in all_tool_plugins(cfg.root_modpack_config().game_universe):
            info('Preparing context for {} tool...'.format(plugin.name()))
            pluginex = (plugin, plugin.create_context(cfg, resolvedvfs))
            exts = plugin.extensions()
            assert len(exts) > 0
            for ext in exts:
                if ext not in self.tools_by_ext:
                    self.tools_by_ext[ext] = []
                self.tools_by_ext[ext].append(pluginex)

    def could_be_produced(self, srcfile: str, targetpath: str) -> tuple[CouldBeProducedByTool, str | None]:
        ext = os.path.splitext(srcfile)[1]
        assert ext == os.path.splitext(targetpath)[1]
        if ext in self.tools_by_ext:
            plugins = self.tools_by_ext[ext]
            besttool = None
            maxcbp = CouldBeProducedByTool.NotFound
            for plugin, ctx in plugins:
                cbp = plugin.could_be_produced(ctx, srcfile, targetpath)
                if cbp.is_greater_or_eq(maxcbp):
                    maxcbp = cbp
                    besttool = plugin.name()
            return maxcbp, besttool
        return CouldBeProducedByTool.NotFound, None


def _add_ext_stats(stats: dict[str, int], fpath: str) -> None:
    ext = os.path.splitext(fpath)[1]
    if len(ext) > 6:
        ext = '.longer.'
    if ext not in stats:
        stats[ext] = 1
    else:
        stats[ext] += 1


def togithub(cfg: LocalProjectConfig, wcache: WholeCache) -> None:
    toolsfinder: _ToolFinder = _ToolFinder(cfg, wcache.resolved_vfs())

    info('Stage 0: collecting retrievers')
    mip = _ModsInProgress(cfg, wcache.available)
    nzero = 0
    nzerostats = {}
    ndup = 0
    toolstats = {}
    nignored = 0
    itf = _IgnoredTargetFiles(cfg)
    for f in wcache.all_source_vfs_files():
        mf = cfg.parse_source_vfs(f.file_path)

        target = cfg.mod_manager_config.modfile_to_target_vfs(mf)
        ignored = itf.ignored(target)

        if ignored:
            nignored += 1
            continue

        if mip.has_retrievers_for(f.file_hash):
            ndup += 1
            mip.add_dup_file(mf, f.file_hash)
        else:
            retr: list[FileRetriever] = wcache.file_retrievers_by_hash(f.file_hash)
            if len(retr) > 0:
                for r in retr:
                    if isinstance(r, (ZeroFileRetriever, GithubFileRetriever)):
                        retr = [r]
                        break
            if len(retr) == 0:
                nzero += 1
                _add_ext_stats(nzerostats, f.file_path)
                mip.add_new_file(mf, [])
            else:
                mip.add_new_file(mf, retr)

    info('{} files ignored, found {} duplicate files'.format(
        nignored, ndup))
    for tool in toolstats:
        info('tool {}:'.format(tool))
        totaln = 0
        for text, tn in sorted(toolstats[tool].items(), key=lambda x: -x[1]):
            info('-> {} -> {}'.format(text, tn))
            totaln += tn
        info('-> total: {}'.format(totaln))
    if nzero > 0:
        warn('did not find retrievers for {} files'.format(nzero))
        for zext, zn in sorted(nzerostats.items(), key=lambda x: -x[1]):
            warn('-> {} -> {}'.format(zext, zn))

    info('stats (nretrievers->ntimes):')
    stats = {}
    for _, rlist in mip.all_retrievers():
        n = len(rlist)
        if n not in stats:
            stats[n] = 1
        else:
            stats[n] += 1
    srt = sorted(stats.keys())
    srtfirst = srt[:min(len(srt), 5)]
    for ss in srtfirst:
        info('-> {} -> {}'.format(ss, stats[ss]))
    info('-> ...')
    srtlast = srt[-min(len(srt), 5):]
    for ss in srtlast:
        info('{} -> {}'.format(ss, stats[ss]))

    ### processing unique retrievers, resolving per-mod install files, etc.
    info('Stage 1: resolve_unique()...')
    mip.resolve_unique(wcache._source_vfs_cache)

    ntools = 0
    for key, mod in mip.mods.items():
        assert mod.could_be_produced_by_tools is None
        mod.could_be_produced_by_tools = {}
        for ff in mod.modified_since_install():
            mf = ModFile(mod.name, ff)
            targetpath = cfg.modfile_to_target_vfs(mf)
            assert targetpath is not None
            srcf = cfg.mod_manager_config.modfile_to_source_vfs(mf)
            cbp, tool = toolsfinder.could_be_produced(srcf, targetpath)
            if cbp.is_greater_or_eq(CouldBeProducedByTool.Maybe):
                ntools += 1
                mod.could_be_produced_by_tools[ff] = (tool, cbp)

                if tool not in toolstats:
                    toolstats[tool] = {}
                _add_ext_stats(toolstats[tool], srcf)
    info('{} mod files could have been produced by tools'.format(ntools))

    ninstallfrom = 0
    info('per-mod stats:')
    triviallyinstalledmods: list[tuple[str, _ModInProgress]] = []
    healabletotrivialmods: list[tuple[str, _ModInProgress]] = []
    fullyinstalledmods: list[tuple[str, _ModInProgress]] = []
    fullygithubmods: list[tuple[str, _ModInProgress]] = []
    othermods: list[tuple[str, _ModInProgress]] = []
    for modname, mod in mip.mods.items():
        if mod.is_fully_github():
            fullygithubmods.append((modname, mod))
            continue

        processed = False
        if len(mod.install_from) > 0:
            names = [wcache.available.tentative_names_for_archive(arinst.archive.archive_hash) for arinst, _ in
                     mod.install_from]
            instdata = [arinst.install_data() for arinst, _ in mod.install_from]
            info("-> {}: install_from {}, install_data='{}'".format(
                modname, str(names), str(instdata)))
            ninstallfrom += 1
            if mod.is_trivially_installed():
                triviallyinstalledmods.append((modname, mod))
                processed = True
            elif mod.is_healable_to_trivial_install():
                healabletotrivialmods.append((modname, mod))
                processed = True
            elif mod.is_fully_installed():
                fullyinstalledmods.append((modname, mod))
                processed = True

        if processed:
            continue

        othermods.append((modname, mod))

    info('found install_from archives for {} mods out of {}, {:.1f}%'.format(ninstallfrom, len(mip.mods),
                                                                             ninstallfrom / len(mip.mods) * 100.))
    info(
        '{} mod(s) are github-only, {} mod(s) are trivially installed, {} mod(s) can probably be healed to trivial install'.format(
            len(fullygithubmods), len(triviallyinstalledmods), len(healabletotrivialmods)))
    info('{} mod(s) are fully installed (with unexplained skips)'.format(len(fullyinstalledmods)))
    alert('{} mod(s) remaining'.format(len(othermods)))
    pass
