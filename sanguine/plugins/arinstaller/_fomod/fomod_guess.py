from sanguine.helpers.archives import Archive
from sanguine.helpers.arinstallers import ArInstaller
from sanguine.helpers.file_retriever import ArchiveFileRetriever
from sanguine.plugins.arinstaller._fomod.fomod_common import *
from sanguine.plugins.arinstaller._fomod.fomod_engine import FomodEngine


class _FomodInstallerSelection:
    step: str
    group: str
    plugin: str

    def __init__(self, step: str, group: str, plugin: str) -> None:
        self.step = step
        self.group = group
        self.plugin = plugin

class _FomodReplayStep(_FomodInstallerSelection):
    value: bool

    def __init__(self, step: str, group: str, plugin: str,value:bool) -> None:
        super().__init__(step,group,plugin)
        self.value = value

type _FomodReplaySteps = list[_FomodReplayStep]
type _FomodGuessFileVariants = list[tuple[_FomodInstallerSelection, FomodFilesAndFolders]]

class _FomodGuessFakeUI(LinearUI):
    start_step: _FomodReplaySteps
    current_step: _FomodReplaySteps
    files_variants: _FomodGuessFileVariants
    forks: list[tuple[_FomodReplaySteps, _FomodGuessFileVariants]]

    def __init__(self, startingfork: list[_FomodReplayStep]) -> None:
        self.start_step = startingfork
        self.current_step = []
        self.files_variants = []
        self.forks = []

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
        if len(self.current_step) < len(self.start_step):
            for ctrl in wizardpage.controls:
                assert isinstance(ctrl, LinearUIGroup)
                tag, istep = ctrl.extra_data
                assert tag == 0
                for c2 in ctrl.controls:
                    assert isinstance(c2, LinearUIGroup)
                    tag, grp = c2.extra_data
                    assert tag == 1
                    assert isinstance(grp, FomodGroup)
                    sel = grp.select
                    nsel = 0
                    for c3 in c2.controls:
                        tag, plugin = c3.extra_data
                        assert tag == 2
                        assert isinstance(plugin, FomodPlugin)
                        assert isinstance(c3, LinearUICheckbox)
                        if c3.value:
                            nsel += 1

                    assert nsel >= 0
                    match sel:
                        case FomodGroupSelect.SelectAll:
                            assert nsel == len(c2.controls)
                        case FomodGroupSelect.SelectAny:
                            pass
                        case FomodGroupSelect.SelectExactlyOne:
                            assert nsel == 1
                        case FomodGroupSelect.SelectAtMostOne:
                            if nsel > 1:
                                return 'Too many selections in group {}'.format(c2.name)
                        case FomodGroupSelect.SelectAtLeastOne:
                            if nsel < 1:
                                return 'Too few selections in group {}'.format(c2.name)
            return None


def fomod_guess(modulecfg: FomodModuleConfig, archive: Archive, modname: str,
                modfiles: dict[str, list[ArchiveFileRetriever]]) -> ArInstaller | None:
    known_forks = [[]]
    while len(known_forks) > 0:
        startingfork = known_forks[0]
        known_forks = known_forks[1:]
        fakeui = _FomodGuessFakeUI(startingfork)
        engine = FomodEngine(modulecfg)
        engine.run(fakeui)
