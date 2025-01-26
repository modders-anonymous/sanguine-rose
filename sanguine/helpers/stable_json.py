from sanguine.common import *


def _stable_json_sort_list(data: list[Any]) -> list[Any]:
    if len(data) == 0:
        return []
    d0 = data[0]
    if isinstance(d0, str):
        if __debug__:
            for i in data:
                assert isinstance(i, str)
        return sorted(data)

    assert hasattr(d0, 'sanguine_json')
    if __debug__:
        for i in data:
            assert d0.sanguine_json == i.sanguine_json
    firstfield = d0.sanguine_json[0][1]
    data2 = [to_stable_json(d) for d in data]
    return sorted(data2, key=lambda x: 'i{:09d}'.format(x[firstfield]) if isinstance(x[firstfield], int) else 's' + x[
        firstfield])


def to_stable_json(data: Any) -> dict[str, Any] | list[Any] | str:
    if hasattr(data, 'sanguine_json'):
        out: dict[str, Any] = {}
        di = data.__dict__
        for field, jfield in data.sanguine_json:
            v = di[field]
            if v is None:
                pass
            elif isinstance(v, list) and len(v) == 0:
                pass
            elif isinstance(v, dict) and len(v) == 0:
                pass
            else:
                out[jfield] = to_stable_json(v)
        return out
    if isinstance(data, list):
        return _stable_json_sort_list(data)
    if isinstance(data, dict):
        # if __debug__:
        #    for k in data:
        #        assert isinstance(k, str)
        return {to_stable_json(k): to_stable_json(v) for k, v in sorted(data.items(), key=lambda x: x[0])}
    if isinstance(data, (str, int, float)):
        return data
    if isinstance(data, bytes):
        return to_json_hash(data)
    assert False


def write_stable_json(fname: str, data: dict[str, Any]) -> None:
    with open_git_data_file_for_writing(fname) as f:
        write_stable_json_opened(f, data)


def write_stable_json_opened(f: typing.TextIO, data: dict[str, Any]) -> None:
    # noinspection PyTypeChecker
    json.dump(data, f, indent=1)
