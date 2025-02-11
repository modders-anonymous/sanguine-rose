from sanguine.plugins.arinstaller._fomod.fomod_common import *


class FomodAutoplayFakeUI(LinearUI):
    selections: list[FomodInstallerSelection]
    pos: int

    def __init__(self, selections: list[FomodInstallerSelection]) -> None:
        self.selections = selections
        self.pos = 0

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
        for grp in wizardpage.controls:
            for chkbox in grp.controls:
                assert isinstance(chkbox, LinearUICheckbox)
                sel = FomodInstallerSelection(wizardpage.name, grp.name, chkbox.name)
                val = False
                if self.pos < len(self.selections) and sel == self.selections[self.pos]:
                    val = True
                    self.pos += 1
                if chkbox.disabled:
                    raise_if_not(val == chkbox.value)
                else:
                    chkbox.value = val

        if validator is not None:
            errstr = validator(wizardpage)
            raise_if_not(errstr is None)

    def check_done(self) -> None:
        raise_if_not(self.pos == len(self.selections))


class FomodEnginePluginSelector:
    istep_ctrl: LinearUIGroup
    istep: FomodInstallStep
    grp_ctrl: LinearUIGroup | None
    grp: FomodGroup | None
    plugin_ctrl: LinearUICheckbox | None
    plugin: FomodPlugin | None

    def __init__(self, ctrl: LinearUIGroup) -> None:
        assert isinstance(ctrl, LinearUIGroup)
        self.istep_ctrl = ctrl
        tag, self.istep = ctrl.extra_data
        assert tag == 0
        assert isinstance(self.istep, FomodInstallStep)
        self.grp_ctrl = None
        self.grp = None
        self.plugin_ctrl = None
        self.plugin = None

    def set_grp(self, c2: LinearUIGroup) -> None:
        # assert self.grp_ctrl is None
        # assert self.grp is None
        # assert self.plugin_ctrl is None
        # assert self.plugin is None

        assert isinstance(c2, LinearUIGroup)
        self.grp_ctrl = c2
        tag, self.grp = c2.extra_data
        assert tag == 1
        assert isinstance(self.grp, FomodGroup)
        self.plugin_ctrl = None
        self.plugin = None

    def set_chkbox(self, c3: LinearUICheckbox) -> None:
        assert self.grp_ctrl is not None
        assert self.grp is not None
        # assert self.plugin_ctrl is None
        # assert self.plugin is None

        assert isinstance(c3, LinearUICheckbox)
        self.plugin_ctrl = c3
        tag, self.plugin = c3.extra_data
        assert tag == 2
        assert isinstance(self.plugin, FomodPlugin)


def _fomod_wizard_page_validator(wizardpage: LinearUIGroup) -> str | None:
    it = FomodEnginePluginSelector(wizardpage)
    for grp in wizardpage.controls:
        it.set_grp(grp)
        sel = it.grp.select
        nsel = 0
        for chk in grp.controls:
            it.set_chkbox(chk)
            if chk.value:
                nsel += 1

        assert nsel >= 0
        match sel:
            case FomodGroupSelect.SelectAll:
                assert nsel == len(grp.controls)
            case FomodGroupSelect.SelectAny:
                pass
            case FomodGroupSelect.SelectExactlyOne:
                assert nsel == 1
            case FomodGroupSelect.SelectAtMostOne:
                if nsel > 1:
                    return 'Too many selections in group {}'.format(grp.name)
            case FomodGroupSelect.SelectAtLeastOne:
                if nsel < 1:
                    return 'Too few selections in group {}'.format(grp.name)
    return None


class FomodEngine:
    module_config: FomodModuleConfig
    select_no_radio_hack: bool  # for very specific _FomodGuessFakeUI use cases

    def __init__(self, modulecfg: FomodModuleConfig) -> None:
        self.module_config = modulecfg
        self.select_no_radio_hack = False

    def run(self, ui: LinearUI) -> tuple[list[FomodInstallerSelection], FomodFilesAndFolders]:
        flags: dict[str, str] = {}
        runtimedeps: FomodDependencyEngineRuntimeData = FomodDependencyEngineRuntimeData(flags)
        selections: list[FomodInstallerSelection] = []
        files = self.module_config.required.copy()  # copying, as we'll append to files
        for istep in self.module_config.install_steps:
            if not istep.visible.is_satisfied(runtimedeps):
                continue  # TODO: what about potential mandatory settings within non-visible pages?
            wizpage = LinearUIGroup(istep.name, [])
            wizpage.extra_data = (0, istep)
            for grp in istep.groups:
                wizpagegrp = LinearUIGroup(grp.name, [])
                wizpagegrp.extra_data = (1, grp)
                wizpage.add_control(wizpagegrp)
                for plugin in grp.plugins:
                    match grp.select:
                        case FomodGroupSelect.SelectAny | FomodGroupSelect.SelectAtMostOne | FomodGroupSelect.SelectAtLeastOne:
                            wizpageplugin = LinearUICheckbox(plugin.name, False, False)
                        case FomodGroupSelect.SelectExactlyOne:
                            wizpageplugin = LinearUICheckbox(plugin.name, False, True)
                        case FomodGroupSelect.SelectAll:
                            wizpageplugin = LinearUICheckbox(plugin.name, True, False)
                            wizpageplugin.disabled = True
                        case _:
                            assert False
                    wizpageplugin.extra_data = (2, plugin)
                    wizpagegrp.add_control(wizpageplugin)
            ui.wizard_page(wizpage, _fomod_wizard_page_validator)

            pgextra = FomodEnginePluginSelector(wizpage)
            for grp in wizpage.controls:
                pgextra.set_grp(grp)
                n = 0
                for chkbox in grp.controls:
                    pgextra.set_chkbox(chkbox)
                    if chkbox.value:
                        n += 1
                        if pgextra.plugin.files is not None:
                            files.merge(pgextra.plugin.files)
                        flags |= {dep.name: dep.value for dep in pgextra.plugin.condition_flags}
                        selections.append(
                            FomodInstallerSelection(pgextra.istep.name, pgextra.grp.name, pgextra.plugin.name))
                match pgextra.grp.select:
                    case FomodGroupSelect.SelectExactlyOne:
                        assert n == 1 or (self.select_no_radio_hack and n == 0)
                    case FomodGroupSelect.SelectAny:
                        pass
                    case FomodGroupSelect.SelectAtMostOne:
                        assert n <= 1
                    case FomodGroupSelect.SelectAtLeastOne:
                        assert n >= 1
                    case FomodGroupSelect.SelectAll:
                        assert n == len(grp.controls)
                    case _:
                        assert False
        for cond in self.module_config.conditional_file_installs:
            if cond.dependencies.is_satisfied(runtimedeps):
                files.merge(cond.files)
        return selections, files
