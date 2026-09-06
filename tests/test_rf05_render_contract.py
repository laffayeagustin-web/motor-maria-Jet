"""T5c / RF-15 — el contrato del render bundle: `render_schema_version`."""
from pathlib import Path

from maria.render_bundle import load_bundle
from maria_common.render_contract import RENDER_SCHEMA_VERSION, RenderBundleEntry, schema_major


def _entry(**kw) -> RenderBundleEntry:
    base = dict(url="https://e.com", captured_utc="2026-09-05T00:00:00+00:00", rendered_words=100)
    base.update(kw)
    return RenderBundleEntry(**base)


def test_entry_v1_es_usable():
    assert _entry().usable is True


def test_entry_major_distinto_no_usable():
    assert _entry(render_schema_version="2.0").usable is False


def test_entry_minor_mayor_sigue_usable():
    assert _entry(render_schema_version="1.7").usable is True


def test_entry_status_error_no_usable():
    assert _entry(status="error", error="x").usable is False


def test_schema_major():
    assert schema_major(RENDER_SCHEMA_VERSION) == 1
    assert schema_major("bogus") == -1


def test_bundle_con_manifest_incompatible_se_ignora_entero(tmp_bundle_dir):
    d: Path = tmp_bundle_dir([_entry()], manifest_version="9.0")
    bundle = load_bundle(d)
    assert bundle.entry_for("https://e.com") is None


def test_bundle_ausente_no_rompe():
    bundle = load_bundle(Path("/no/existe"))
    assert bundle.loaded is False
    assert bundle.entry_for("https://e.com") is None
