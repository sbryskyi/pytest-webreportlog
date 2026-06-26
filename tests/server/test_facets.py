"""Unit tests for the env-metadata facet helpers."""

from types import SimpleNamespace

from webreportlog_server.utils import build_facets, scalar_env_facets


def _sess(env=None):
    """A minimal stand-in for a Session (only env_metadata is read)."""
    return SimpleNamespace(env_metadata=env)


def test_scalar_env_facets_keeps_and_stringifies_scalars() -> None:
    s = _sess({"Python": "3.13", "Count": 3, "Ratio": 1.5, "Flag": True})
    assert scalar_env_facets(s) == {
        "Python": "3.13",
        "Count": "3",
        "Ratio": "1.5",
        "Flag": "True",
    }


def test_scalar_env_facets_drops_nested_dicts_and_lists() -> None:
    s = _sess({"Python": "3.13", "Packages": {"pytest": "8"}, "Tags": ["a", "b"]})
    assert scalar_env_facets(s) == {"Python": "3.13"}


def test_scalar_env_facets_handles_missing_metadata() -> None:
    assert scalar_env_facets(_sess(None)) == {}
    assert scalar_env_facets(SimpleNamespace()) == {}


def test_build_facets_unions_and_sorts() -> None:
    sessions = [
        _sess({"Python": "3.12", "Platform": "linux"}),
        _sess({"Python": "3.11", "Platform": "linux"}),
        _sess({"Python": "3.12"}),
    ]
    facets = build_facets(sessions)
    assert facets == {"Platform": ["linux"], "Python": ["3.11", "3.12"]}
    # Attribute names are sorted for a stable UI.
    assert list(facets.keys()) == ["Platform", "Python"]


def test_build_facets_includes_attr_present_on_only_some_sessions() -> None:
    sessions = [_sess({"Python": "3.12"}), _sess({"Browser": "firefox"})]
    assert build_facets(sessions) == {"Browser": ["firefox"], "Python": ["3.12"]}


def test_build_facets_empty_when_no_scalar_attrs() -> None:
    assert build_facets([]) == {}
    assert build_facets([_sess(None), _sess({"Packages": {"x": "1"}})]) == {}
