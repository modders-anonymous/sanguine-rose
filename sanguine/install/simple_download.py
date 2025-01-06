import gzip
import os
import re
import shutil
import tempfile
import urllib.request

from sanguine.install.install_common import abort_if_not, alert, NetworkErrorHandler

# simple_download is used by _install_helpers, which means that we cannot use any files with non-guaranteed dependencies, so we:
#                 1. may use only those Python modules installed by default, and
#                 2. may use only those sanguine modules which are specifically designated as install-friendly


_MAX_PAGE_SIZE = 1000000


def pattern_from_url(url: str, pattern: str, encoding: str = 'utf-8') -> list[str]:
    rq = urllib.request.Request(url=url)
    with urllib.request.urlopen(rq) as f:
        b: bytes = f.read(_MAX_PAGE_SIZE)
        assert len(b) < _MAX_PAGE_SIZE
        if f.getheader('content-encoding') == 'gzip':
            b = gzip.decompress(b)
        html: str = b.decode(encoding)
        return re.findall(pattern, html, re.IGNORECASE)


def _download_temp(url: str, errhandler: NetworkErrorHandler | None) -> str:
    wf, tfname = tempfile.mkstemp()
    while True:
        try:
            rq = urllib.request.Request(url=url)
            with urllib.request.urlopen(rq) as rf:
                while True:
                    b: bytes = rf.read(1048576)
                    if not b:
                        break
                    os.write(wf, b)
            os.close(wf)
            return tfname
        except OSError as e:
            alert('Exception {} while downloading {}'.format(e, url))
            os.close(wf)

            if errhandler is not None and errhandler.handle_error('Downloading {}'.format(url), e.errno):
                wf = open(tfname, 'wb')
                continue

            raise e


def download_temp(url: str, errhandler: NetworkErrorHandler | None) -> str:
    """
    Tries to preserve file name from url
    """
    tfname = _download_temp(url, errhandler)
    assert os.path.isfile(tfname)
    desired_fname = url.split('/')[-1]
    for i in range(9):
        new_fname = os.path.split(tfname)[0] + '\\' + desired_fname
        if i > 0:
            new_fname += ' (' + str(i) + ')'
        if os.path.exists(new_fname):
            continue
        try:
            shutil.move(tfname, new_fname)
            if os.path.isfile(new_fname):
                return new_fname
        except OSError:
            continue

        abort_if_not(os.path.isfile(tfname))
