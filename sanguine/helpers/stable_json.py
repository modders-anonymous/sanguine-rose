from sanguine.common import *


class StableJsonFlags(Flag):
    NoFlags = 0x0
    Unsorted = 0x1


class _StableJsonType:
    typ: Any
    flags: StableJsonFlags

    def __init__(self, typ: Any, flags: StableJsonFlags):
        self.typ = typ
        self.flags = flags


def _get_type(sj: tuple) -> _StableJsonType:
    if len(sj) == 2:
        return _StableJsonType(None, StableJsonFlags.NoFlags)
    elif len(sj) == 3:
        return _StableJsonType(sj[2], StableJsonFlags.NoFlags)
    else:
        assert len(sj) == 4
        return _StableJsonType(sj[2], sj[3])


_PRIMITIVE_TYPES = (str, int, float, bytes)


def _create_from_typ(typ: Any) -> Any:
    if hasattr(typ, 'for_stable_json_load'):
        return typ.for_stable_json_load()
    else:
        return typ()


def _validate_sjdecl(obj: Any) -> None:
    assert hasattr(obj, 'SANGUINE_JSON')
    sjlist = obj.SANGUINE_JSON
    for sj in sjlist:
        assert sj[0] in obj.__dict__
        assert sj[1] is None or isinstance(sj[1], str)
        if sj[1] is None:
            assert len(sjlist) == 1
        target = obj.__dict__[sj[0]]
        if isinstance(target, list):
            if len(sj) != 3 and len(sj) != 4:
                assert False
            if len(sj) == 4:
                assert isinstance(sj[3], StableJsonFlags)
            instance = _create_from_typ(sj[2])
            assert isinstance(instance, _PRIMITIVE_TYPES) or hasattr(instance, 'SANGUINE_JSON')
        elif isinstance(target, dict):
            assert len(sj) == 3 or len(sj) == 4
            if len(sj) == 4:
                assert isinstance(sj[3], StableJsonFlags)
            assert isinstance(sj[2], tuple)
            assert len(sj[2]) == 2
            instance0 = _create_from_typ(sj[2][0])
            instance1 = _create_from_typ(sj[2][1])
            assert isinstance(instance0, _PRIMITIVE_TYPES) or hasattr(instance0, 'SANGUINE_JSON')
            assert isinstance(instance1, _PRIMITIVE_TYPES) or hasattr(instance1, 'SANGUINE_JSON')
        elif hasattr(target, 'SANGUINE_JSON'):
            assert len(sj) == 2
        else:
            if target is not None and not isinstance(target, _PRIMITIVE_TYPES):
                assert False
            assert len(sj) == 2


def _to_sort_key(jsonobj: Any, sjlist: list[tuple] | None) -> Any:
    if sjlist is not None:
        for sj in sjlist:
            if sj[1] in jsonobj:
                return _to_sort_key(jsonobj[sj[1]], None)
        assert False  # no field found
    elif isinstance(jsonobj, str):
        return 's' + jsonobj
    elif isinstance(jsonobj, int):
        return 'i{:09d}'.format(jsonobj)
    else:
        assert False


def _stable_json_list(data: list[Any], typ: _StableJsonType) -> list[Any]:
    assert isinstance(data, list)
    if len(data) == 0:
        return []
    d0 = data[0]
    if isinstance(d0, str):
        if __debug__:
            for i in data:
                assert isinstance(i, str)
        return data if (typ.flags & StableJsonFlags.Unsorted) else sorted(data)
    elif isinstance(d0, int):
        if __debug__:
            for i in data:
                assert isinstance(i, int)
        return data if (typ.flags & StableJsonFlags.Unsorted) else sorted(data)

    assert hasattr(d0, 'SANGUINE_JSON')
    if __debug__:
        for i in data:
            assert d0.SANGUINE_JSON == i.SANGUINE_JSON
    data2 = [to_stable_json(d) for d in data]
    if typ.flags & StableJsonFlags.Unsorted:
        return data2
    else:
        info(repr(data2))
        return sorted(data2, key=lambda x: _to_sort_key(x, d0.SANGUINE_JSON))


def to_stable_json(data: Any, typ: _StableJsonType | None = None) -> Any:
    assert data is not None
    if hasattr(data, 'to_sanguine_stable_json'):
        return data.to_sanguine_stable_json()
    if hasattr(data, 'SANGUINE_JSON'):
        if __debug__:
            _validate_sjdecl(data)
        out: dict[str, Any] = {}
        di = data.__dict__
        for sj in data.SANGUINE_JSON:  # len(sj) can be 2 or 3
            field = sj[0]
            jfield = sj[1]
            v = di[field]
            if v is None:
                pass
            elif isinstance(v, list) and len(v) == 0:
                pass
            elif isinstance(v, dict) and len(v) == 0:
                pass
            else:
                if jfield is None:
                    assert len(data.SANGUINE_JSON) == 1
                    return to_stable_json(v, _get_type(sj))
                out[jfield] = to_stable_json(v, _get_type(sj))
        return out
    elif isinstance(data, list):
        return _stable_json_list(data, typ)
    elif isinstance(data, dict):
        return {to_stable_json(k): to_stable_json(v) for k, v in sorted(data.items(), key=lambda x: x[0])}
    elif isinstance(data, bytes):
        return to_json_hash(data)
    elif isinstance(data, _PRIMITIVE_TYPES):
        return data
    assert False


def write_stable_json(fname: str, data: dict[str, Any]) -> None:
    with open_git_data_file_for_writing(fname) as f:
        write_stable_json_opened(f, data)


def write_stable_json_opened(f: typing.TextIO, data: dict[str, Any]) -> None:
    # noinspection PyTypeChecker
    json.dump(data, f, indent=1)


def _from_stable_json_primitive(data: Any, target4typeonly: Any) -> Any:
    if isinstance(target4typeonly, bytes):
        abort_if_not(isinstance(data, str))
        return from_json_hash(data)
    abort_if_not(isinstance(data, _PRIMITIVE_TYPES) and not isinstance(data, bytes))
    return data


def from_stable_json(target: Any, data: Any, typ: _StableJsonType = None) -> None:
    assert target is not None
    if hasattr(target, 'from_sanguine_stable_json'):
        return target.from_sanguine_stable_json(data)
    if hasattr(target, 'SANGUINE_JSON'):
        if __debug__:
            _validate_sjdecl(target)
        abort_if_not(isinstance(data, dict))
        tgdi = target.__dict__
        for sj in target.SANGUINE_JSON:  # len(sj) can be 2 or 3
            field = sj[0]
            assert field in tgdi
            jfield = sj[1]
            sjtyp = _get_type(sj)
            tgt = tgdi[field]
            if hasattr(tgt, 'SANGUINE_JSON'):
                assert sjtyp.flags == StableJsonFlags.NoFlags
                if jfield is None:
                    assert len(target.SANGUINE_JSON) == 1
                    from_stable_json(tgt, data, sjtyp)
                else:
                    from_stable_json(tgt, data[jfield], sjtyp)
            elif isinstance(tgt, list):
                assert len(tgt) == 0
                if jfield is None:
                    assert len(target.SANGUINE_JSON) == 1
                    from_stable_json(tgt, data, sjtyp)
                elif jfield not in data:
                    assert tgt == []
                    pass  # leave tgt as []
                else:
                    from_stable_json(tgt, data[jfield], sjtyp)
            elif isinstance(tgt, dict):
                assert len(tgt) == 0
                assert sjtyp.flags == StableJsonFlags.NoFlags
                if jfield is None:
                    assert len(target.SANGUINE_JSON) == 1
                    from_stable_json(tgt, data, sjtyp)
                elif jfield not in data:
                    assert tgt == {}
                    pass  # leave tgt as {}
                else:
                    from_stable_json(tgt, data[jfield], sjtyp)
            else:
                if __debug__:
                    assert isinstance(tgt, _PRIMITIVE_TYPES)
                    assert sjtyp.flags == StableJsonFlags.NoFlags
                    if isinstance(tgt, (int, float)):
                        assert tgt == 0
                    elif isinstance(tgt, (str, bytes)):
                        assert len(tgt) == 0
                    else:
                        assert False
                assert jfield is not None
                if jfield not in data:
                    tgdi[field] = None
                else:
                    tgdi[field] = _from_stable_json_primitive(data[jfield], tgt)
                    assert type(tgdi[field]) == type(tgt)
    elif isinstance(target, list):
        assert len(target) == 0
        abort_if_not(isinstance(data, list))
        for d in data:
            e = _create_from_typ(typ.typ)
            if isinstance(e, _PRIMITIVE_TYPES):
                target.append(_from_stable_json_primitive(d, e))
            else:
                assert hasattr(e, 'SANGUINE_JSON')
                target.append(e)
                from_stable_json(e, d)
    elif isinstance(target, dict):
        assert len(target) == 0
        abort_if_not(isinstance(data, dict))
        for k, v in data.items():
            typ0, typ1 = typ.typ
            e0 = _create_from_typ(typ0)
            e1 = _create_from_typ(typ1)
            assert isinstance(e0, _PRIMITIVE_TYPES)
            ktgt = _from_stable_json_primitive(k, e0)
            if isinstance(e1, _PRIMITIVE_TYPES):
                vtgt = _from_stable_json_primitive(v, e1)
            else:
                assert hasattr(e1, 'SANGUINE_JSON')
                vtgt = e1
                from_stable_json(e1, v)
            assert ktgt not in target
            target[ktgt] = vtgt
    else:
        assert not isinstance(data, _PRIMITIVE_TYPES)  # no primitive types in from_stable_json
        assert False
