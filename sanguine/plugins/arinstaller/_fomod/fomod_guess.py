from sanguine.helpers.file_retriever import ArchiveFileRetriever
from sanguine.plugins.arinstaller._fomod.fomod_common import *
from sanguine.plugins.arinstaller._fomod.fomod_engine import FomodEngine, FomodEnginePluginSelector

type _FomodReplaySteps = list[tuple[FomodInstallerSelection, bool | None]]
type _FomodGuessPlugins = list[tuple[FomodInstallerSelection, FomodFilesAndFolders]]


# type _FomodGuessFlags = dict[str, FomodFlagDependency]


class _FomodGuessFork:
    start_step: _FomodReplaySteps
    # selected_plugins: _FomodGuessPlugins  # selected for sure in current fork
    true_or_false_plugins: _FomodGuessPlugins

    def __init__(self, start: _FomodReplaySteps,
                 # sel: _FomodGuessPlugins | None = None,
                 tof: _FomodGuessPlugins | None = None) -> None:
        self.start_step = start
        # self.selected_plugins = sel if sel is not None else []
        self.true_or_false_plugins = tof if tof is not None else []

    def copy(self) -> "_FomodGuessFork":
        return _FomodGuessFork(self.start_step.copy(),
                               # self.selected_plugins.copy(),
                               self.true_or_false_plugins.copy())


class _FomodGuessFakeUI(LinearUI):
    current_fork: _FomodGuessFork
    current_step: _FomodReplaySteps
    requested_forks: list[_FomodGuessFork]

    def __init__(self, startingfork: _FomodGuessFork) -> None:
        self.current_fork = startingfork
        self.current_step = []
        self.requested_forks = []

    def set_silent_mode(self) -> None:
        assert False

    # noinspection PyTypeChecker
    def message_box(self, prompt: str, spec: list[str],
                    level: LinearUIImportance = LinearUIImportance.Default) -> str:
        assert False

    # noinspection PyTypeChecker
    def input_box(self, prompt: str, default: str, level: LinearUIImportance = LinearUIImportance.Default) -> str:
        assert False

    def confirm_box(self, prompt: str, level: LinearUIImportance = LinearUIImportance.Default) -> None:
        assert False

    # noinspection PyTypeChecker
    def network_error_handler(self, nretries: int) -> NetworkErrorHandler:
        assert False

    def wizard_page(self, wizardpage: LinearUIGroup,
                    validator: Callable[[LinearUIGroup], str | None] | None = None) -> None:
        it = FomodEnginePluginSelector(wizardpage)
        for cgrp in wizardpage.controls:
            it.set_grp(cgrp)
            for c2idx, c2 in enumerate(cgrp.controls):
                it.set_chkbox(c2)
                if len(self.current_step) < len(self.current_fork.start_step):
                    nxt = self.current_fork.start_step[len(self.current_step)]
                    assert it.istep.name == nxt[0].step_name
                    if it.grp.name != nxt[0].group_name:
                        assert False
                    if it.plugin.name != nxt[0].plugin_name:
                        assert False

                    self.current_step.append(nxt)
                    if it.plugin_ctrl.disabled:
                        assert it.plugin_ctrl.value == nxt[1]
                    else:
                        it.plugin_ctrl.value = nxt[1]
                    continue
                assert len(self.current_step) >= len(self.current_fork.start_step)
                oldcurlen = len(self.current_step)

                cur = FomodInstallerSelection(it.istep.name, it.grp.name, it.plugin.name)
                match it.grp.select:
                    case FomodGroupSelect.SelectAny:
                        possible = (None,)
                    case FomodGroupSelect.SelectAll:
                        possible = (True,)
                    case FomodGroupSelect.SelectExactlyOne:
                        possible = (True, False)
                        for i in range(c2idx):
                            prevstep = self.current_step[-1 - i]
                            assert prevstep[0].step_name == it.istep.name and prevstep[0].group_name == it.grp.name
                            assert prevstep[1] is False or prevstep[1] is True
                            if prevstep[1] is True:
                                possible = (False,)
                                break
                        if len(possible) == 2 and c2idx == len(cgrp.controls) - 1:
                            possible = (True,)
                    case FomodGroupSelect.SelectAtLeastOne:
                        possible = (True, False)
                        found = False
                        for i in range(c2idx):
                            prevstep = self.current_step[-1 - i]
                            assert prevstep[0].step_name == it.istep.name and prevstep[0].group_name == it.grp.name
                            assert prevstep[1] is False or prevstep[1] is True

                            if prevstep[1] is True:
                                found = True
                                break
                        if not found and c2idx == len(cgrp.controls) - 1:
                            possible = (True,)
                    case FomodGroupSelect.SelectAtMostOne:
                        possible = (True, False)
                        found = False
                        for i in range(c2idx):
                            prevstep = self.current_step[-1 - i]
                            assert prevstep[0].step_name == it.istep.name and prevstep[0].group_name == it.grp.name
                            assert prevstep[1] is False or prevstep[1] is True

                            if prevstep[1] is True:
                                found = True
                                break
                        if found:
                            possible = (False,)
                    case _:
                        assert False

                assert isinstance(possible, tuple)
                assert len(possible) == 1 or len(possible) == 2
                predetermined = len(possible) == 1 and possible[0] is not None
                if it.plugin_ctrl.disabled:
                    assert predetermined
                    assert possible[0] == it.plugin_ctrl.value

                willfork = False
                if predetermined:  # no choice, no fork
                    assert len(possible) == 1
                    assert possible[0] is False or possible[0] is True
                    it.plugin_ctrl.value = possible[0]
                    # if possible[0]:
                    # self.current_fork.flags |= {dep.name: dep.value for dep in it.plugin.condition_flags}
                    #    if it.plugin.files is not None:
                    #        self.current_fork.selected_plugins.append((cur, it.plugin.files))
                    self.current_step.append((cur, possible[0]))
                elif len(it.plugin.condition_flags) > 0:
                    willfork = True
                elif possible[0] is None:
                    self.current_step.append((cur, None))
                    if it.plugin.files is not None:
                        self.current_fork.true_or_false_plugins.append((cur, it.plugin.files))
                else:
                    willfork = True

                if willfork:  # both are possible, will handle True in this run, will request fork with False
                    assert possible[0] is None or (possible[0] is True and possible[1] is False)
                    # (None,) is treated the same as (True,False) here
                    forked = self.current_fork.copy()
                    forked.start_step = self.current_step.copy()
                    forked.start_step.append((cur, False))
                    self.requested_forks.append(forked)
                    self.current_step.append((cur, True))
                    # self.current_fork.flags |= {dep.name: dep.value for dep in it.plugin.condition_flags}
                    assert not it.plugin_ctrl.disabled
                    it.plugin_ctrl.value = True
                    # if it.plugin.files is not None:
                    #    self.current_fork.selected_plugins.append((cur, it.plugin.files))

                assert len(self.current_step) == oldcurlen + 1


def _find_required_tofs(archive: Archive, fomodroot: str, modfiles: dict[str, list[ArchiveFileRetriever]],
                        true_or_false_plugins: _FomodGuessPlugins) -> list[FomodInstallerSelection]:
    if len(true_or_false_plugins) == 0:
        return []
    assert not fomodroot.endswith('\\')
    fomodroot1 = '' if fomodroot == '' else fomodroot + '\\'

    fias: dict[str, FileInArchive] = {}
    for f in archive.files:
        assert f.intra_path not in fias
        fias[f.intra_path] = f

    tofs: dict[str, list[tuple[FomodInstallerSelection, FileInArchive]]] = {}
    for instsel, ff in true_or_false_plugins:
        if ff is not None:
            for f in ff.files:
                fsrc = FomodFilesAndFolders.normalize_file_path(fomodroot1 + f.src)
                fdst = FomodFilesAndFolders.normalize_file_path(f.dst)
                if fsrc not in fias:
                    assert False
                if fdst not in tofs:
                    tofs[fdst] = []
                tofs[fdst].append((instsel, fias[fsrc]))
            for f in ff.folders:
                fsrc = FomodFilesAndFolders.normalize_folder_path(f.src)
                fdst = FomodFilesAndFolders.normalize_folder_path(f.dst)
                for af in archive.files:
                    if af.intra_path.startswith(fsrc):
                        file = af.intra_path[len(fsrc):]
                        filedst = fdst + file
                        if filedst not in tofs:
                            tofs[filedst] = []
                        tofs[filedst].append((instsel, fias[af.intra_path]))

    required_tofs: set[FomodInstallerSelection] = set()
    for modfile, rlist in modfiles.items():
        r0: ArchiveFileRetriever = rlist[0]
        fh = r0.file_hash
        if modfile in tofs and len(tofs[modfile]) == 1 and tofs[modfile][0][1].file_hash == truncate_file_hash(fh):
            required_tofs.add(tofs[modfile][0][0])

    return list(required_tofs)


def fomod_guess(fomodroot: str, modulecfg: FomodModuleConfig, archive: Archive,
                modfiles: dict[str, list[ArchiveFileRetriever]]) -> tuple[ArInstaller, int] | None:
    processed_forks: list[tuple[_FomodGuessPlugins, list[FomodInstallerSelection], FomodFilesAndFolders]] = []
    remaining_forks: list[_FomodGuessFork] = [_FomodGuessFork([])]
    info('Running simulations for FOMOD installer {}...'.format(modulecfg.module_name))
    # if 'clear map' in modulecfg.module_name.lower():
    #    pass
    while len(remaining_forks) > 0:
        startingfork = remaining_forks[0]
        remaining_forks = remaining_forks[1:]
        fakeui = _FomodGuessFakeUI(startingfork)
        engine = FomodEngine(modulecfg)
        engselections, engfiles = engine.run(fakeui)
        processed_forks.append((fakeui.current_fork.true_or_false_plugins, engselections, engfiles))
        remaining_forks += fakeui.requested_forks
        if len(processed_forks) + len(remaining_forks) > 1000:
            alert('Too many simulations for {}, skipping'.format(modulecfg.module_name))
            return None
    info('{}: {} fork(s) found'.format(modulecfg.module_name, len(processed_forks)))

    best_arinstaller: ArInstaller | None = None
    best_coverage: int = 0
    for pf in processed_forks:
        selected_plugins: set[FomodInstallerSelection] = set(pf[1])
        known: dict[FomodInstallerSelection, FomodFilesAndFolders] = {}
        # for sel, selected in pf.selected_plugins:
        #    if sel in known:
        #        assert as_json(known[sel]) == as_json(selected)
        #    known[sel] = selected
        for sel, tof in pf[0]:
            assert sel not in known
            known[sel] = tof
        required_tofs: set[FomodInstallerSelection] = set(_find_required_tofs(archive, fomodroot, modfiles, pf[0]))

        selections: list[FomodInstallerSelection] = []
        files: FomodFilesAndFolders = pf[2].copy()
        for istep in modulecfg.install_steps:
            for group in istep.groups:
                for plugin in group.plugins:
                    sel = FomodInstallerSelection(istep.name, group.name, plugin.name)
                    if sel in required_tofs:
                        if sel not in known:
                            assert False
                        assert known[sel] is not None
                        selections.append(sel)
                        files.merge(known[sel])
                    elif sel in selected_plugins:
                        # if sel not in known:
                        #    assert False
                        # assert known[sel] is not None
                        selections.append(sel)
                    else:
                        pass

        candidate: FomodArInstaller = FomodArInstaller(archive, fomodroot, files, selections)
        n = 0
        for fpath, fia in candidate.all_desired_files():
            if fpath in modfiles and truncate_file_hash(modfiles[fpath][0].file_hash) == fia.file_hash:
                n += 1
        if n > best_coverage:
            best_coverage = n
            best_arinstaller = candidate

    return best_arinstaller, best_coverage
