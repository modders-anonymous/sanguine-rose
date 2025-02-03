from sanguine.helpers.archives import Archive
from sanguine.helpers.arinstallers import ArInstaller
from sanguine.helpers.file_retriever import ArchiveFileRetriever
from sanguine.plugins.arinstaller._fomod.fomod_common import *
from sanguine.plugins.arinstaller._fomod.fomod_engine import FomodEngine, FomodEngineWizardPlugin


class _FomodInstallerSelection:
    step_name: str
    group_name: str
    plugin_name: str

    def __init__(self, step: str, group: str, plugin: str) -> None:
        self.step_name = step
        self.group_name = group
        self.plugin_name = plugin


type _FomodReplaySteps = list[_FomodInstallerSelection]
type _FomodGuessPlugins = list[tuple[_FomodInstallerSelection, FomodFilesAndFolders]]
type _FomodGuessFlags = dict[str, FomodFlagDependency]


class _FomodGuessFork:
    start_step: _FomodReplaySteps
    selected_plugins: _FomodGuessPlugins  # selected for sure in current fork
    true_or_false_plugins: _FomodGuessPlugins
    flags: _FomodGuessFlags

    def __init__(self, start: _FomodReplaySteps, sel: _FomodGuessPlugins | None = None,
                 tof: _FomodGuessPlugins | None = None, flags: _FomodGuessFlags | None = None) -> None:
        self.start_step = start
        self.selected_plugins = sel if sel is not None else []
        self.true_or_false_plugins = tof if tof is not None else []
        self.flags = flags if flags is not None else {}

    def copy(self) -> "_FomodGuessFork":
        return _FomodGuessFork(self.start_step.copy(), self.selected_plugins.copy(), self.true_or_false_plugins.copy(),
                               self.flags.copy())


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
        for ctrl in wizardpage.controls:
            it = FomodEngineWizardPlugin(ctrl)
            for c2 in ctrl.controls:
                it.add_c2(c2)
                for c3 in c2.controls:
                    it.add_c3(c3)
                    if len(self.current_step) < len(self.current_fork.start_step):
                        nxt = self.current_fork.start_step[len(self.current_step)]
                        assert it.istep.name == nxt.step_name
                        assert it.grp.name == nxt.group_name
                        assert it.plugin.name == nxt.plugin_name

                        self.current_step.append(nxt)
                        continue
                    assert len(self.current_step) >= len(self.current_fork.start_step)

                    cur = _FomodInstallerSelection(it.istep.name, it.grp.name, it.plugin.name)
                    if len(it.plugin.condition_flags) > 0:
                        if it.plugin_ctrl.disabled:  # no choice, no fork
                            if it.plugin_ctrl.value:
                                self.current_fork.flags |= it.plugin.condition_flags
                                self.current_fork.selected_plugins.append((cur, it.plugin.files))
                        else:  # both are possible, will handle True in this run, will request fork with False
                            forked = self.current_fork.copy()
                            forked.start_step.append(cur)
                            self.requested_forks.append(forked)
                            self.current_fork.flags |= it.plugin.condition_flags
                            self.current_fork.selected_plugins.append((cur, it.plugin.files))
                    else:
                        self.current_step.append(cur)
                        self.current_fork.true_or_false_plugins.append((cur, it.plugin.files))


def fomod_guess(modulecfg: FomodModuleConfig, archive: Archive, modname: str,
                modfiles: dict[str, list[ArchiveFileRetriever]]) -> ArInstaller | None:
    processed_forks: list[_FomodGuessFork]
    remaining_forks: list[_FomodGuessFork] = [_FomodGuessFork([])]
    while len(remaining_forks) > 0:
        startingfork = remaining_forks[0]
        remaining_forks = remaining_forks[1:]
        fakeui = _FomodGuessFakeUI(startingfork)
        engine = FomodEngine(modulecfg)
        engine.run(fakeui)
        remaining_forks += fakeui.requested_forks
