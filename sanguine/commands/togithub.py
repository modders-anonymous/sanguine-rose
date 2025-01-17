import re

from sanguine.cache.available_files import AvailableFiles
from sanguine.cache.whole_cache import WholeCache
from sanguine.common import *
from sanguine.helpers.archives import Archive, FileInArchive
from sanguine.helpers.file_retriever import (FileRetriever, ArchiveFileRetriever,
                                             ToolFileRetriever, GithubFileRetriever, ZeroFileRetriever)
from sanguine.helpers.project_config import LocalProjectConfig
from sanguine.helpers.tools import ToolPluginBase, all_tool_plugins, CouldBeProducedByTool


class _ModInProgress:
    cfg: LocalProjectConfig
    available: AvailableFiles
    name: str
    files: dict[str, list[FileRetriever]]  # intramod -> list of retrievers
    known_archives: dict[bytes, tuple[Archive, int]]
    required_archives: dict[bytes, tuple[Archive, int]] | None
    unresolved_retrievers: dict[str, list[FileRetriever]] | None
    install_from: Archive | None
    install_from_root: str | None
    remaining_after_install_from: dict[str, list[FileRetriever]] | None
    may_be_modified_by_tools: dict[str, bool] | None
    skip_from_install: dict[str, bool] | None

    def __init__(self, cfg: LocalProjectConfig, available: AvailableFiles, name: str) -> None:
        self.cfg = cfg
        self.available = available
        self.name = name
        self.files = {}
        self.known_archives = {}
        self.unresolved_retrievers = None
        self.required_archives = None

        self.install_from = None
        self.install_from_root = None
        self.remaining_after_install_from = None
        self.may_be_modified_by_tools = None
        self.skip_from_install = None

    def add_file(self, intramod: str, retrievers: list[FileRetriever]) -> None:
        assert intramod not in self.files
        self.files[intramod] = retrievers
        for r in retrievers:
            if isinstance(r, ArchiveFileRetriever):
                arh = r.archive_hash()
                if arh not in self.known_archives:
                    ar = self.available.archive_by_hash(arh)
                    self.known_archives[arh] = (ar, 1)
                self.known_archives[arh] = (self.known_archives[arh][0], self.known_archives[arh][1] + 1)

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

    def resolve_unique(self) -> None:
        assert self.required_archives is None
        assert self.unresolved_retrievers is None
        assert self.install_from is None
        assert self.install_from_root is None
        assert self.remaining_after_install_from is None
        assert self.skip_from_install is None
        assert self.may_be_modified_by_tools is None
        self.required_archives = {}
        self.unresolved_retrievers = {}
        for intra, rlist in self.files.items():
            if len(rlist) == 0:
                pass
            elif len(rlist) == 1:
                r0 = rlist[0]
                if isinstance(r0, ArchiveFileRetriever):
                    arh = r0.archive_hash()
                    assert arh in self.known_archives
                    self.required_archives[arh] = self.known_archives[arh]
            else:
                if __debug__:
                    for r in rlist:
                        assert isinstance(r, ArchiveFileRetriever)

                assert intra not in self.unresolved_retrievers
                self.unresolved_retrievers[intra] = rlist

        if len(self.required_archives) == 1:
            install_from_candidate: Archive = next(iter(self.required_archives.values()))[0]
            candidate_roots: dict[str, int] = {}
            for modpath, rlist in self.files.items():
                if len(rlist) == 0:
                    continue
                r0 = rlist[0]
                if __debug__:
                    for r in rlist:
                        assert r.file_hash == r0.file_hash
                assert len(rlist) == 1 or isinstance(r0, ArchiveFileRetriever)
                if isinstance(r0, ArchiveFileRetriever):
                    for r in rlist:
                        assert isinstance(r, ArchiveFileRetriever)
                        if r.archive_hash() == install_from_candidate.archive_hash:
                            inarrpath = r.single_archive_retrievers[0].file_in_archive.intra_path
                            if inarrpath.endswith(modpath):
                                candidate_root = inarrpath[:-len(modpath)]
                                if candidate_root == '' or candidate_root.endswith('\\'):
                                    if candidate_root not in candidate_roots:
                                        candidate_roots[candidate_root] = 1
                                    else:
                                        candidate_roots[candidate_root] += 1

            if len(candidate_roots) > 0:
                best_candidate_root = sorted(candidate_roots.items(), key=lambda x: x[1])[-1]
                ratio = float(best_candidate_root[1]) / float(len(self.files))
                assert ratio <= 1.
                if ratio > 0.7:  # quite arbitrary, though should be bigger than 0.5 to ensure that it is the best anyway
                    self.install_from = install_from_candidate
                    self.install_from_root = best_candidate_root[0]
                    self.remaining_after_install_from = {}
                    self.may_be_modified_by_tools = {}

                    arfiles_by_name: dict[str, tuple[FileInArchive, bool]] = {arf.intra_path: (arf, False) for arf in
                                                                              install_from_candidate.files}
                    arfiles_by_hash: dict[bytes, list[FileInArchive]] = {}
                    for arf in install_from_candidate.files:
                        if arf.file_hash not in arfiles_by_hash:
                            arfiles_by_hash[arf.file_hash] = []
                        arfiles_by_hash[arf.file_hash].append(arf)

                    file_overrides: dict[str, list[FileRetriever]] = {}
                    for intra, rlist in self.files.items():
                        # if intra == 'meshes\\actors\\character\\animations\\openanimationreplacer\\evg animated traversal\\deep walk\\evgat - deep walk.txt':
                        #    pass
                        processed = False
                        if len(rlist) == 1:
                            r0 = rlist[0]
                            if isinstance(r0, ArchiveFileRetriever):
                                if r0.archive_hash() == install_from_candidate.archive_hash:
                                    arintra = r0.single_archive_retrievers[0].file_in_archive.intra_path
                                    if arintra == self.install_from_root + intra:
                                        if __debug__:
                                            arfh = truncate_file_hash(r0.single_archive_retrievers[0].file_hash)
                                            _ModInProgress._assert_arfh_in_arfiles_by_hash(arfh, arintra,
                                                                                           arfiles_by_hash)
                                        assert arfiles_by_name[arintra][1] == False
                                        arfiles_by_name[arintra] = (arfiles_by_name[arintra][0], True)
                                        processed = True
                                    else:
                                        # arfh = truncate_file_hash(r0.single_archive_retrievers[0].file_hash)
                                        # bestname = _ModInProgress._best_unmatched_from_arfiles_by_hash(arfh, arintra,
                                        #                                                               arfiles_by_hash)
                                        # arfiles_by_name[bestname] = (arfiles_by_name[bestname][0], True)
                                        # self.remaining_after_install_from[intra] = [r0]
                                        pass
                        elif len(rlist) > 1:
                            for r in rlist:
                                assert isinstance(r, ArchiveFileRetriever)
                                if r.archive_hash() == install_from_candidate.archive_hash:
                                    arintra = r.single_archive_retrievers[0].file_in_archive.intra_path
                                    if arintra == self.install_from_root + intra:
                                        if __debug__:
                                            arfh = truncate_file_hash(r.single_archive_retrievers[0].file_hash)
                                            _ModInProgress._assert_arfh_in_arfiles_by_hash(arfh, arintra,
                                                                                           arfiles_by_hash)
                                        file_overrides[intra] = [r]
                                        assert arfiles_by_name[arintra][1] == False
                                        arfiles_by_name[arintra] = (arfiles_by_name[arintra][0], True)
                                        processed = True
                                    else:
                                        # arfh = truncate_file_hash(r.single_archive_retrievers[0].file_hash)
                                        # bestname = _ModInProgress._best_unmatched_from_arfiles_by_hash(arfh, arintra,
                                        #                                                               arfiles_by_hash)
                                        # arfiles_by_name[bestname] = (arfiles_by_name[bestname][0], True)
                                        # self.remaining_after_install_from[intra] = [r]
                                        pass
                                if processed:
                                    break  # for r in rlist
                        else:
                            assert len(rlist) == 0
                            if self.install_from_root + intra in arfiles_by_name:  # file with such a path exists in archive, but is modified
                                self.may_be_modified_by_tools[intra] = True
                            self.remaining_after_install_from[intra] = rlist

                        if not processed:
                            self.remaining_after_install_from[intra] = rlist

                    self.files |= file_overrides

                    self.skip_from_install = {}
                    for arfile in arfiles_by_name.values():
                        if not arfile[1]:
                            self.skip_from_install[arfile[0].intra_path] = True

                    if __debug__:
                        fromarch: list[str] = []
                        for f in self.install_from.files:
                            if f.intra_path not in self.skip_from_install:
                                if not f.intra_path.startswith(self.install_from_root):
                                    assert False
                                fromarch.append(f.intra_path[len(self.install_from_root):])
                        assert len(fromarch) == len(self.install_from.files) - len(self.skip_from_install)
                        for fname in self.remaining_after_install_from.keys():
                            fromarch.append(fname)
                        assert len(fromarch) == len(self.install_from.files) - len(self.skip_from_install) + len(
                            self.remaining_after_install_from)

                        fromarch = sorted(fromarch)
                        origf = sorted(self.files.keys())
                        assert len(origf) == len(self.files)
                        if len(fromarch) != len(origf):
                            assert False
                        for i in range(len(fromarch)):
                            if fromarch[i] != origf[i]:
                                assert False

                        assert len(self.files) == len(self.install_from.files) - len(self.skip_from_install) + len(
                            self.remaining_after_install_from)


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
            self.mods[mf.mod] = _ModInProgress(self._cfg, self._available, mf.mod)
        self.mods[mf.mod].add_file(mf.intramod, retrievers)

    def add_dup_file(self, mf: ModFile, h: bytes) -> None:
        assert self.has_retrievers_for(h)
        if mf.mod not in self.mods:
            self.mods[mf.mod] = _ModInProgress(self._cfg, self._available, mf.mod)
        self.mods[mf.mod].add_file(mf.intramod, self._all_retrievers[h])

    def all_retrievers(self) -> Iterable[tuple[bytes, list[FileRetriever]]]:
        return self._all_retrievers.items()

    def resolve_unique(self) -> None:
        for mod in self.mods:
            self.mods[mod].resolve_unique()


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

    def find_tool_retriever(self, srcfile: FileOnDisk, targetpath: str) -> ToolFileRetriever | None:
        ext = os.path.splitext(srcfile.file_path)[1]
        assert ext == os.path.splitext(targetpath)[1]
        if ext in self.tools_by_ext:
            plugins = self.tools_by_ext[ext]
            for plugin, ctx in plugins:
                cbp = plugin.could_be_produced(ctx, srcfile.file_path, targetpath)
                if cbp.is_greater_or_eq(CouldBeProducedByTool.Maybe):
                    return ToolFileRetriever((srcfile.file_hash, srcfile.file_size), plugin.name())
        return None


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
    # possibleretrievers: dict[bytes, list[FileRetriever]] = {}
    ntools = 0
    nzero = 0
    nzerostats = {}
    ndup = 0
    toolstats = {}
    nignored = 0
    ignored_file_patterns = [re.compile(p) for p in cfg.root_modpack_config().ignored_file_patterns]
    for f in wcache.all_source_vfs_files():
        mf = cfg.parse_source_vfs(f.file_path)

        target = cfg.mod_manager_config.modfile_to_target_vfs(mf)
        ignored = False
        for p in ignored_file_patterns:
            if p.match(target):
                ignored = True
                break

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
            '''
            if len(retr) == 0:
                mf: ModFile = cfg.parse_source_vfs(f.file_path)
                targetpath = cfg.modfile_to_target_vfs(mf)
                assert targetpath is not None
                r = toolsfinder.find_tool_retriever(f, targetpath)
                if r is not None:
                    retr = [r]
                    ntools += 1
                    tool = r.tool_name
                    if tool not in toolstats:
                        toolstats[tool] = {}
                    _add_ext_stats(toolstats[tool], f.file_path)
            '''
            if len(retr) == 0:
                nzero += 1
                _add_ext_stats(nzerostats, f.file_path)
                mip.add_new_file(mf, [])
            else:
                mip.add_new_file(mf, retr)

    info('{} files ignored, found {} duplicate files, {} files likely generated by tools'.format(
        nignored, ndup, ntools))
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
    mip.resolve_unique()

    ninstallfrom = 0
    info('per-mod stats:')
    for modname, mod in mip.mods.items():
        if mod.install_from is not None:
            names = wcache.available.tentative_names_for_archive(mod.install_from.archive_hash)
            info("-> {}: install_from {}, root='{}', installed={}/{}".format(
                modname, str(names), mod.install_from_root, len(mod.files) - len(mod.remaining_after_install_from),
                len(mod.files)))
            ninstallfrom += 1
    info('found install_from archives for {} mods out of {}, {:.1f}%'.format(ninstallfrom, len(mip.mods),
                                                                             ninstallfrom / len(mip.mods) * 100.))

    '''
    archives: dict[bytes, int] = {}  # for now, it is archives for unique files
    remainingretrievers: list[tuple[bytes, list[FileRetriever]]] = []
    nzerogithub = 0
    for h,rlist in mip.all_retrievers():
        assert len(rlist) > 0
        rr0 = rlist[0]
        if isinstance(rr0, (ZeroFileRetriever, GithubFileRetriever, ToolFileRetriever, UnknownFileRetriever)):
            assert h not in retrievers
            retrievers[h] = rr0
            nzerogithub += 1
        elif len(rlist) == 1:
            assert isinstance(rr0, ArchiveFileRetriever)
            assert h not in retrievers
            retrievers[h] = rr0
            if rr0.archive_hash() not in archives:
                archives[rr0.archive_hash()] = 1
            else:
                archives[rr0.archive_hash()] += 1
        else:
            assert isinstance(rr0, ArchiveFileRetriever)
            remainingretrievers.append((h,rlist))
    assert len(possibleretrievers) == len(remainingretrievers) + len(retrievers)

    info('Stage 1: {} files from Zero, Github, and Tools; {} unique files in Archives'.format(nzerogithub,
                                                                                              len(retrievers) - nzerogithub))
    info('Stage 1: {} archives necessary to cover unique files'.format(len(archives)))
    info('Stage 1: {} files remaining'.format(len(remainingretrievers)))

    remainingretrievers2: list[tuple[bytes, list[FileRetriever]]] = []
    for r in remainingretrievers:
        assert len(r[1]) > 0
        bestar = None
        bestarn = -1
        for rr in r[1]:
            assert isinstance(rr, ArchiveFileRetriever)
            rah = rr.archive_hash()
            if rah in archives and archives[rah] > bestarn:
                bestar = rr
                bestarn = archives[rah]

        if bestar is not None:
            assert bestarn > 0
            assert r[0] not in retrievers
            retrievers[r[0]] = bestar
            assert isinstance(bestar, ArchiveFileRetriever)
            archives[bestar.archive_hash()] += 1
        else:
            remainingretrievers2.append(r)

    if __debug__:
        assert len(possibleretrievers) == len(remainingretrievers2) + len(retrievers)
        for r in retrievers.items():
            retr: FileRetriever = r[1]
            assert isinstance(retr, (
                UnknownFileRetriever, ToolFileRetriever, ArchiveFileRetriever, GithubFileRetriever, ZeroFileRetriever))
            if isinstance(retr, ArchiveFileRetriever):
                assert retr.archive_hash() in archives

    info('Stage 2: accounted for already required {} archives, remaining {} files'.format(len(archives),
                                                                                          len(remainingretrievers2)))

    arstats = wcache.archive_stats()
    arusage: list[tuple[bytes, int, int]] = []
    for arh, arn in archives.items():
        assert arh in arstats
        arusage.append((arh, arn, arstats[arh][0]))

    arusage.sort(key=lambda x: x[1] / x[2])
    warn('Stage 2: archives with usage <= 10%:')
    for aru in arusage:
        if aru[1] / aru[2] > 0.1:
            break
        warn('-> h={} n={}/{} ({:.1f}%)'.format(to_json_hash(truncate_file_hash(aru[0])),
                                                aru[1], aru[2], aru[1] / aru[2] * 100))

    if len(remainingretrievers2) != 0:
        raise SanguinicError(
            'handling of non-unique retrievers is NOT IMPLEMENTED YET')  # TODO! - this is possible, when encounter - will need to process

    retrievers_by_path: list[tuple[str, FileRetriever]] = []
    nzero2 = 0
    for f in wcache.all_source_vfs_files():
        if not f.file_hash in retrievers:
            nzero2 += 1
        else:
            mod, intramod = cfg.parse_source_vfs(f.file_path)
            assert mod is None or '\\' not in mod
            assert intramod[0] != '\\'
            fp = (mod if mod is not None else '<overwrite>') + '\\' + intramod
            retrievers_by_path.append((fp, retrievers[f.file_hash]))
    assert nzero2 == 0

    info('Stage 2 done, writing...')

    fname = cfg.this_modpack_folder() + 'project.json5'
    with open_git_data_file_for_writing(fname) as f:
        jsonwriter = GitProjectJson()
        jsonwriter.write(f, retrievers_by_path)

    info('togithub processed successfully.')
    '''


'''
def _filter_with_used(inlist: list[tuple[bytes, list[ArchiveFileRetriever]]],
                      out: list[tuple[bytes, ArchiveFileRetriever | None]],
                      used_archives: dict[bytes, int]) -> list[tuple[bytes, list[ArchiveFileRetriever]]]:
    filtered: list[tuple[bytes, list[ArchiveFileRetriever]]] = []
    for x in inlist:
        (h, retrs) = x
        assert len(retrs) >= 2
        done = False
        for r in retrs:
            arh = r.archive_hash()
            assert arh is not None
            if arh in used_archives:
                out.append((h, r))
                used_archives[arh] += 1
                done = True
                break  # for r

        if not done:
            filtered.append((h, retrs))

    return filtered


def _separate_cluster_step(inlist: list[tuple[bytes, list[ArchiveFileRetriever]]],
                           cluster: list[tuple[bytes, list[ArchiveFileRetriever]]],
                           cluster_archives: dict[bytes, int]) -> list[tuple[bytes, list[ArchiveFileRetriever]]]:
    filtered: list[tuple[bytes, list[ArchiveFileRetriever]]] = []
    for x in inlist:  # this code is close, but not identical to the one in _filter_with_used()
        (h, retrs) = x
        assert len(retrs) >= 2
        found = False
        for r in retrs:
            arh = r.archive_hash()
            assert arh is not None
            if arh in cluster_archives:
                cluster_archives[arh] += 1
            else:
                cluster_archives[arh] = 1
            found = True
            # no break here

        if found:
            cluster.append((h, retrs))
        else:
            filtered.append((h, retrs))
    return filtered


def _separate_cluster(inlist: list[tuple[bytes, list[ArchiveFileRetriever]]],
                      cluster: list[tuple[bytes, list[ArchiveFileRetriever]]],
                      cluster_archives: dict[bytes, int]) -> list[tuple[bytes, list[ArchiveFileRetriever]]]:
    prev = inlist
    while True:
        oldclusterlen = len(cluster)
        filtered: list[tuple[bytes, list[ArchiveFileRetriever]]] = _separate_cluster_step(prev, cluster,
                                                                                          cluster_archives)
        assert len(filtered) <= len(prev)
        assert len(prev) - len(filtered) == len(cluster) - oldclusterlen
        if len(filtered) < len(prev):
            prev = filtered
            continue

        return prev


_MAX_EXPONENT_RETRIEVERS = 20  # 2**20 is a million, within reason


def _make_masked_set(cluster_archives: list[bytes], mask: int) -> dict[bytes, int]:
    filtered_archives = {}
    for i in range(len(cluster_archives)):
        if ((1 << i) & mask) != 0:
            h = cluster_archives[i]
            filtered_archives[h] = 1
    return filtered_archives


def _covers_set(cluster: list[tuple[bytes, list[ArchiveFileRetriever]]], filtered_archives: dict[bytes, int]) -> bool:
    for x in cluster:
        (h, retrs) = x
        for r in retrs:
            arh = r.archive_hash()
            assert arh is not None
            if arh not in filtered_archives:
                return False
    return True


def _cost_of_set(filtered_archives: dict[bytes, int], archive_weights: dict[bytes, int]) -> int:
    out = 0
    for arh in filtered_archives:
        out += archive_weights[arh]
    return out


def _full_search_retrievers(out: list[tuple[bytes, FileRetriever | None]],
                            cluster: list[tuple[bytes, list[ArchiveFileRetriever]]],
                            cluster_archives0: dict[bytes, int],
                            archive_weights: dict[bytes, int]):
    cluster_archives = [h for h in cluster_archives0.keys()]
    assert len(cluster_archives) <= _MAX_EXPONENT_RETRIEVERS
    bestcost = None
    bestset = None
    for mask in range(2 ** len(cluster_archives)):
        filtered_archives = _make_masked_set(cluster_archives, mask)
        if _covers_set(cluster, filtered_archives):
            cost = _cost_of_set(filtered_archives, archive_weights)
            if bestcost is None or cost < bestcost:
                bestcost = cost
                bestset = filtered_archives

    assert bestset is not None
    for x in cluster:
        (h, retrs) = x
        done = False
        for r in retrs:
            arh = r.archive_hash()
            assert arh is not None
            if arh in bestset:
                out.append((h, r))
                done = True
                break  # for x

        assert done


def _number_covered_by_archive(cluster: list[tuple[bytes, list[ArchiveFileRetriever]]], h0: bytes) -> int:
    out = 0
    for x in cluster:
        (h, retrs) = x
        for r in retrs:
            arh = r.archive_hash()
            assert arh is not None
            if arh == h0:
                out += 1
                break  # for r
    return out


def _retriever_key(fr: FileRetriever, archive_weights: dict[bytes, int]) -> str:
    if isinstance(fr, ZeroFileRetriever):
        return '0'
    elif isinstance(fr, GithubFileRetriever):
        return '1.' + str(fr.file_hash)
    elif isinstance(fr, ArchiveFileRetriever):
        arh = fr.archive_hash()
        assert arh is not None
        return '2.' + str(archive_weights[arh]) + '.' + str(fr.file_hash)
    else:
        assert False


def _choose_retrievers(inlist0: list[tuple[bytes, list[FileRetriever]]], archive_weights: dict[bytes, int]) -> list[
    tuple[bytes, FileRetriever | None]]:
    out: list[tuple[bytes, FileRetriever | None]] = []

    # sorting
    inlist: list[tuple[bytes, list[FileRetriever]]] = []
    for item in inlist0:
        inlist.append((item[0], sorted(item[1], key=lambda fr: _retriever_key(fr, archive_weights))))

    # first pass: choosing unique ones, as well as GitHub ones
    remaining: list[tuple[bytes, list[ArchiveFileRetriever]]] = []
    used_archives: dict[bytes, int] = {}
    for x in inlist:
        (h, retrs) = x
        if len(retrs) == 0:
            out.append((h, None))
            continue
        elif len(retrs) == 1:
            r0: FileRetriever = retrs[0]
            out.append((h, r0))
            arh = None
            if isinstance(r0, ArchiveFileRetriever):
                arh = r0.archive_hash()
            if arh is not None:
                if arh not in used_archives:
                    used_archives[arh] = 1
                else:
                    used_archives[arh] += 1
            continue

        done = False
        for r in retrs:
            if isinstance(r, GithubFileRetriever):
                out.append((h, r))
                done = True
                break  # for r

        if done:
            continue  # for x

        # cannot do much now, placing it to remaining[]
        if __debug__:
            for r in retrs:
                assert isinstance(r, ArchiveFileRetriever)

        # noinspection PyTypeChecker
        #              we just asserted that all members of retrs are ArchiveFileRetriever
        retrs1: list[ArchiveFileRetriever] = retrs
        remaining.append((h, retrs1))

    # separate into clusters
    remaining = _filter_with_used(remaining, out, used_archives)
    clusters: list[list[tuple[bytes, list[ArchiveFileRetriever]]]] = []
    clusters_archives: list[dict[bytes, int]] = []
    while len(remaining) > 0:
        cluster: list[tuple[bytes, list[ArchiveFileRetriever]]] = [remaining[0]]
        remaining = remaining[1:]
        cluster_archives = {}
        for x in cluster[0]:
            (h, retrs) = x
            if h in cluster_archives:
                cluster_archives[h] += 1
            else:
                cluster_archives[h] = 1

        oldremaininglen = len(remaining)
        oldclusterlen = len(cluster)
        remaining = _separate_cluster(remaining, cluster, cluster_archives)
        assert len(remaining) <= oldremaininglen
        assert len(cluster) - oldclusterlen == oldremaininglen - len(remaining)
        clusters.append(cluster)
        clusters_archives.append(cluster_archives)

    assert len(clusters_archives) == len(clusters)
    for i in range(len(clusters)):
        cluster = clusters[i]
        cluster_archives: dict[bytes, int] = clusters_archives[i]

        while len(cluster_archives) > _MAX_EXPONENT_RETRIEVERS:
            # "greedy" reduction of search space
            #           for the time being, we're just taking lowest-cost archives (starting from highest-use within lowest-cost)
            xarchives: list[tuple[bytes, int, int]] = sorted(
                [(arh, archive_weights[arh], _number_covered_by_archive(cluster, arh)) for arh in
                 cluster_archives.keys()],
                key=lambda x2: (x2[1], x2[2]))
            # we should not try cutting all (len(cluster_archives)-_MAX_EXPONENT) at once, as filtering can change
            #               the pattern
            arh = xarchives[0][0]
            assert arh not in cluster_archives
            cluster_archives[arh] = 1
            cluster = _filter_with_used(cluster, out, cluster_archives)

        assert len(cluster_archives) <= _MAX_EXPONENT_RETRIEVERS
        _full_search_retrievers(out, cluster, cluster_archives, archive_weights)

    return out
'''
