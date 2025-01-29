import re

from sanguine.install.install_checks import safe_call
from sanguine.install.install_common import *


class GithubFolder:
    author: str
    project: str

    def __init__(self, combined: str) -> None:
        combined = combined.strip()
        spl = combined.split('/')
        assert len(spl) == 2
        self.author = spl[0].strip()
        self.project = spl[1].strip()

    @staticmethod
    def is_ok(combined: str) -> bool:
        combined = combined.strip()
        spl = combined.split('/')
        return len(spl) == 2

    @staticmethod
    def ghsplit(combined2or3: str) -> tuple[str, str] | None:
        spl = combined2or3.split('/')
        if len(spl) == 2:
            return spl[0] + '/' + spl[1], ''
        elif len(spl) == 3:
            return spl[0] + '/' + spl[1], spl[2]
        else:
            return None

    def folder(self, rootgitdir: str) -> str:
        assert is_normalized_dir_path(rootgitdir)
        return rootgitdir + self.author.lower() + '\\' + self.project.lower() + '\\'

    def to_str(self) -> str:
        return self.author + '/' + self.project


def github_project_exists(githubroot: str, ghfolder: GithubFolder) -> int:
    """
    returns 0 if target dir doesn't exist, -1 if folder exists but is not an expected GitHub project, 1 if folder is already a proper GitHub project
    """
    targetdir = ghfolder.folder(githubroot)
    if os.path.exists(targetdir):
        config = targetdir + '\\.git\\config'
        pattern = re.compile(r'\s*url\s*=\s*https://github.com/([^/]*)/(.*)\.git')
        if os.path.isfile(config):
            with open_3rdparty_txt_file_with_encoding(config, 'utf-8') as f:
                for ln in f:
                    m = pattern.match(ln.strip())
                    if m:
                        cfgauthor = m.group(1)
                        cfgproject = m.group(2)
                        if ghfolder.author == cfgauthor and ghfolder.project == cfgproject:
                            return 1
                        else:
                            return -1
                # no GitHub url is found in config
                return -1
        else:
            return -1
    else:
        return 0


def clone_github_project(githubdir: str, ghfolder: GithubFolder,
                         errhandler: NetworkErrorHandler | None, adjustpermissions: bool = False) -> None:
    targetdir = os.path.split(ghfolder.folder(githubdir))[0]
    raise_if_not(not os.path.exists(targetdir + '\\' + ghfolder.project))

    createddir = targetdir + '\\' + ghfolder.project  # we need it to adjust permissions properly
    if not os.path.isdir(targetdir):
        createddir = targetdir
        while True:
            spl = os.path.split(createddir)[0]
            if os.path.isdir(spl):
                break
            createddir = spl
        os.makedirs(targetdir)
    url = 'https://github.com/{}/{}.git'.format(ghfolder.author, ghfolder.project)
    cmd = ['git', 'clone', url]
    info(' '.join(cmd))
    while True:
        ok = safe_call(cmd, cwd=targetdir, shell=True)
        if ok:
            break
        alert('git clone of {} failed'.format(url))
        if errhandler and errhandler.handle_error('Cloning {}'.format(url), 99999):
            continue
        raise SanguinicError('Cloning of {} failed:'.format(url))

    info('{}/{} successfully cloned'.format(targetdir, ghfolder.project))
    if createddir and adjustpermissions:
        user = os.environ['userdomain'] + '\\' + os.environ['username']
        cmd2 = ['icacls', createddir, '/setowner', user, '/t', '/l']
        info('Adjusting permissions of {}...'.format(createddir))
        ok = safe_call(cmd2, shell=True)
        if not ok:
            alert(
                'Cannot adjust permissions on created folder {} (error in command {}), you may need to deal with it yourself'.format(
                    createddir, str(cmd2)))
