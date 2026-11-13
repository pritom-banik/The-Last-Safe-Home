import copy

import pytest
import yaml

from pipeline import cli
from pipeline.lsh.config import CONFIG_DIR, ConfigError, get_settings, list_sites, load_site, parse_site


def _manpura_raw() -> dict:
    with (CONFIG_DIR / "manpura.yaml").open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.mark.parametrize("site_id", ["manpura", "koyra", "demo"])
def test_all_site_files_load(site_id):
    site = load_site(site_id)
    assert site.id == site_id
    assert site.name["en"] and site.name["bn"]
    w, s, e, n = site.bounds
    assert w < site.center[0] < e and s < site.center[1] < n


def test_list_sites():
    assert {"manpura", "koyra", "demo"} <= set(list_sites())


def test_manpura_values_match_spec():
    site = load_site("manpura")
    assert site.utm_epsg == 32646
    assert site.bounds == (90.85, 22.12, 91.10, 22.42)
    assert site.score.weights == {"erosion": 0.6, "flood": 0.3, "motion": 0.1}
    assert site.nisar.known_gaps == [["2026-07-27", "2026-08-10"]]
    assert site.nisar.end is None and len(site.nisar.end_or_today) == 10
    assert site.validation["published_area_km2"] == {1973: 148, 2010: 114}
    assert not site.synthetic


def test_demo_is_synthetic():
    assert load_site("demo").synthetic is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.pop("aoi_wkt"),
        lambda d: d.update(aoi_wkt="POINT(90 22)"),
        lambda d: d.update(aoi_wkt="not wkt"),
        lambda d: d["score"].update(weights={"erosion": 0.7, "flood": 0.3, "motion": 0.1}),
        lambda d: d["score"].update(weights={"erosion": 1.0}),
        lambda d: d["analysis"].update(typo_key=1),
        lambda d: d.update(name={"en": "x"}),
    ],
)
def test_invalid_site_rejected(mutate):
    data = copy.deepcopy(_manpura_raw())
    mutate(data)
    with pytest.raises(ConfigError):
        parse_site(data)


def test_id_must_match_filename():
    with pytest.raises(ConfigError):
        parse_site(_manpura_raw(), expected_id="koyra")


def test_settings_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SITES", "demo, manpura")
    monkeypatch.setenv("EARTHDATA_USERNAME", "")
    s = get_settings(dotenv=False)
    assert s.data_dir == tmp_path
    assert s.sites == ["demo", "manpura"]
    assert not s.has_earthdata


def test_cli_unbuilt_step_exits_cleanly(capsys, monkeypatch):
    monkeypatch.delitem(cli.STEPS, "water-sar")  # every step is built now; simulate a missing one
    assert cli.main(["water-sar", "--site", "manpura"]) == 3
    assert "not built yet" in capsys.readouterr().err


def test_cli_demo_refuses_real_site():
    assert cli.main(["demo", "--site", "manpura"]) == 2


def test_cli_show_config(capsys):
    assert cli.main(["show-config", "--site", "demo"]) == 0
    assert '"synthetic": true' in capsys.readouterr().out
