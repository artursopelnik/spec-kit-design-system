"""`ds.sh scan`: what a validation round can settle without judgement.

Raw values and token names are string facts about files on disk. The scan
states them so the review can spend its attention on what needs a reader, and
so a fix round can re-check them without re-reading the whole change.
"""

from __future__ import annotations

import json
import textwrap

import pytest


TOKENS = {
    "color": {"surface": {"inverse": "#111111", "raised": "#ffffff"}, "fg": "#000000"},
    "space": {"3": "12px", "6": "32px"},
}


@pytest.fixture
def system(project, write_config):
    inventory = project / ".design-system" / "inventory.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(json.dumps({"components": [], "tokens": TOKENS}), encoding="utf-8")
    write_config({"adapter": "static-json", "validation": {"source_globs": ["src/**/*"]}})
    return project


def source(project, name: str, text: str):
    path = project / "src" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def contract(feature, text: str) -> None:
    (feature / "design-system.md").write_text(textwrap.dedent(text), encoding="utf-8")


def scan(design, paths=None):
    return design.scan_implementation(design.DesignSystem.resolve(), paths)


def test_raw_values_are_reported_with_file_and_line(design, system, feature):
    source(system, "Filter.css", """\
        .row {
          padding: 12px;
          color: #ff0000;
          background: rgba(0, 0, 0, 0.5);
          font-family: Helvetica, sans-serif;
        }
        """)
    result = scan(design)
    found = {(r["line"], r["kind"], r["value"]) for r in result["raw_values"]}
    assert (2, "length", "12px") in found
    assert (3, "color", "#ff0000") in found
    assert (4, "color", "rgba(0, 0, 0, 0.5)") in found
    assert any(kind == "font" and line == 5 for line, kind, _ in found)
    assert result["has_tokens"] is True
    assert result["raw_values"][0]["file"] == "src/Filter.css"


def test_zero_hairlines_tokens_and_comments_are_not_raw_values(design, system, feature):
    source(system, "Ok.tsx", """\
        // a comment mentioning 12px is not code
        const style = { margin: 0, border: "1px solid var(--color-fg)", padding: "0px" };
        export const Row = () => <div className="p-3 bg-surface-inverse" style={style} />;
        """)
    assert scan(design)["raw_values"] == []


def test_theme_files_are_where_literal_values_belong(design, system, feature, write_config):
    source(system, "theme.ts", 'export const fg = "#000000";\n')
    write_config({
        "adapter": "static-json",
        "validation": {"source_globs": ["src/**/*"], "theme_globs": ["src/theme.ts"]},
    })
    result = scan(design)
    assert result["raw_values"] == [] and result["theme_files_exempt"] == 1


def test_a_token_the_contract_names_but_the_system_lacks_is_unknown(design, system, feature):
    contract(feature, """\
        ## Surface: filter panel
        **Resolution**: Reuse
        **Decision**: Card with `color.surface.inverse`, `space.6`, `color.surfce.raised`
        """)
    result = scan(design)
    assert result["contract_tokens"] == ["color.surface.inverse", "space.6", "color.surfce.raised"]
    assert result["unknown_tokens"] == ["color.surfce.raised"]


def test_paths_and_props_are_not_mistaken_for_tokens(design, system, feature):
    contract(feature, "Lives in `src/components`, sets `aria-label`, uses `space.*`.\n")
    result = scan(design)
    assert result["contract_tokens"] == ["space.*"]
    assert result["unknown_tokens"] == []


def test_a_contract_token_is_seen_under_the_usual_spellings(design, system, feature):
    contract(feature, "Uses `color.surface.inverse`, `space.6` and `color.fg`.\n")
    source(system, "Panel.css", """\
        .panel { background: var(--color-surface-inverse); }
        .panel { padding: var(--space-6); }
        """)
    result = scan(design)
    assert result["tokens_not_seen"] == ["color.fg"]


def test_without_sources_it_says_so_instead_of_passing(design, project, write_config, feature):
    inventory = project / ".design-system" / "inventory.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(json.dumps({"components": [], "tokens": TOKENS}), encoding="utf-8")
    write_config({"adapter": "static-json"})
    result = scan(design)
    assert result["files_scanned"] == 0
    assert any("source_globs" in note for note in result["notes"])


def test_explicit_paths_win_over_the_config(design, system, feature):
    source(system, "a/One.css", ".x { padding: 12px; }\n")
    source(system, "b/Two.css", ".y { padding: 12px; }\n")
    result = scan(design, ["src/a/**/*.css"])
    assert result["files_scanned"] == 1
    assert {r["file"] for r in result["raw_values"]} == {"src/a/One.css"}


def test_a_system_without_tokens_reports_that_it_has_none(design, project, write_config, feature):
    inventory = project / ".design-system" / "inventory.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(json.dumps({"components": []}), encoding="utf-8")
    write_config({"adapter": "static-json", "validation": {"source_globs": ["src/**/*"]}})
    source(project, "A.css", ".x { padding: 12px; }\n")
    result = scan(design)
    # Reported, but validate.md only raises them when `has_tokens` is true.
    assert result["has_tokens"] is False and result["raw_value_count"] == 1


def test_dtcg_tokens_are_named_by_their_path(design):
    payload = {"color": {"bg": {"$value": "#fff", "$type": "color"}}, "space": {"1": {"value": "4px"}}}
    assert design.token_names(payload) == {"color.bg", "space.1"}


def test_scan_is_one_json_object(design, system, feature, capsys, monkeypatch):
    source(system, "A.css", ".x { padding: 12px; }\n")
    monkeypatch.setattr("sys.argv", ["design", "scan", "--path", "src/**/*.css", "--json"])
    design.main()
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1 and json.loads(out[0])["raw_value_count"] == 1


def test_a_token_named_without_its_group_is_still_a_token(design, project, write_config, feature):
    """A brief says `muted-foreground`, not `color.muted-foreground`. Shadcn's
    tokens are named that way in every class that uses them."""
    inventory = project / ".design-system" / "inventory.json"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text(json.dumps({"components": [], "tokens": {
        "color": {"muted-foreground": "hsl(var(--muted-foreground))", "primary": "hsl(var(--primary))"},
    }}), encoding="utf-8")
    write_config({"adapter": "static-json", "validation": {"source_globs": ["src/**/*"]}})
    contract(feature, "Helper text in `muted-foreground`; the old `muted-fg` name is gone.\n")
    source(project, "Help.tsx", 'export const Help = () => <p className="text-muted-foreground" />;\n')

    result = scan(design)
    assert result["contract_tokens"] == ["muted-foreground"]
    assert result["unknown_tokens"] == []
    assert result["tokens_not_seen"] == []
