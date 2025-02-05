from sanguine.plugins.arinstaller._fomod.fomod_common import *


class FomodEngineWizardPlugin:
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
    for ctrl in wizardpage.controls:
        it = FomodEngineWizardPlugin(ctrl)
        for c2 in ctrl.controls:
            it.set_grp(c2)
            sel = it.grp.select
            nsel = 0
            for c3 in c2.controls:
                it.set_chkbox(c3)
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


class FomodEngine:
    module_config: FomodModuleConfig

    def __init__(self, modulecfg: FomodModuleConfig) -> None:
        self.module_config = modulecfg

    def run(self, ui: LinearUI) -> FomodFilesAndFolders:
        files = self.module_config.required.copy()  # copying just in case
        for istep in self.module_config.install_steps:
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
        return files
