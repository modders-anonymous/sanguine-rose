import os
import re
import tempfile
import urllib.request

# simple_download is used by _install_helpers, which means that we cannot use any files with non-guaranteed dependencies, so we:
#                 1. may use only those Python modules installed by default, and
#                 2. may use only those sanguine modules which are specifically designated as install-friendly


_MAX_PAGE_SIZE = 1000000


def pattern_from_url(url: str, pattern: str, encoding: str = 'utf-8') -> list[str]:
    rq = urllib.request.Request(url=url)
    with urllib.request.urlopen(rq) as f:
        b: bytes = f.read(_MAX_PAGE_SIZE)
        assert len(b) < _MAX_PAGE_SIZE
        html: str = b.decode(encoding)
        return re.findall(pattern, html, re.IGNORECASE)


def download_temp(url: str) -> str:
    wf, tfname = tempfile.mkstemp()
    rq = urllib.request.Request(url=url)
    with urllib.request.urlopen(rq) as rf:
        while True:
            b: bytes = rf.read(1048576)
            if not b:
                break
            os.write(wf, b)
    os.close(wf)

    return tfname
