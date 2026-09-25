"""`markdown-specs`: a design system written down as a folder of spec files.

The layout the AI-readiness guides recommend -- foundations, tokens, atoms,
molecules, organisms, one Markdown file each -- read as it is, with no
inventory to generate. What it must not do is invent: a section the folder
does not have is absent, never filled from somewhere else.
"""

from __future__ import annotations

import json
import textwrap

import pytest


SPECS = {
    "foundations/spacing.md": """\
        # Spacing

        Space comes from the 4px scale, never an ad-hoc value.

        ## Do's
        - Use `space.*` tokens for padding and gaps.

        ## Don'ts
        - Hardcode pixel values.
        """,
    "foundations/breakpoints.md": """\
        # Breakpoints

        | Name | Min width |
        |------|-----------|
        | `sm` | 640px |
        | `md` | 768px |
        """,
    "tokens/color-tokens.md": """\
        # Color tokens

        | Token | Value | Use |
        |-------|-------|-----|
        | `--color-text` | `#172b4d` | Body text |
        | `--color-surface-raised` | `#ffffff` | Cards |
        """,
    "tokens/spacing-tokens.md": """\
        # Spacing tokens

        - `space.100`: 8px
        - `space.200`: 16px
        """,
    "atoms/button.md": """\
        ---
        status: stable
        ---
        # Button

        Triggers an action. Use for the primary action on a surface.

        ## When to use
        One primary button per view.

        ## Avoid
        Links styled as buttons.

        ```md
        # not a heading
        ```
        """,
    "molecules/modal-dialog.md": """\
        ---
        name: Modal Dialog
        status: deprecated
        ---
        # Modal dialog (legacy)

        Blocks the page for a decision.
        """,
    "organisms/page-header.md": """\
        # Page Header

        Title, breadcrumbs and page actions for every top-level page.
        """,
}


@pytest.fixture
def specs(project, write_config):
    root = project / ".design-system" / "specs"
    for name, text in SPECS.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text), encoding="utf-8")
    write_config({"adapter": "markdown-specs"})
    return root


def ask(design, capability, **params):
    return design.DesignSystem.resolve().ask(capability, **params)


def test_a_component_is_its_spec_file(design, specs):
    result = ask(design, "component", name="button")
    assert result["found"] is True
    button = result["data"]
    assert button["name"] == "Button"
    assert button["tier"] == "atoms"
    assert button["description"].startswith("Triggers an action.")
    assert button["usage"] == "One primary button per view."
    assert button["avoid"].startswith("Links styled as buttons.")
    assert button["status"] == "stable"
    assert button["path"] == ".design-system/specs/atoms/button.md"
    assert "# not a heading" in button["spec"]


def test_front_matter_names_the_component(design, specs):
    result = ask(design, "component", name="Modal Dialog")
    assert result["found"] is True and result["data"]["status"] == "deprecated"


def test_organisms_are_patterns_not_components(design, specs):
    assert ask(design, "pattern", name="Page Header")["found"] is True
    assert ask(design, "component", name="Page Header")["found"] is False
    names = {c["name"] for c in ask(design, "list_components")["data"]}
    assert names == {"Button", "Modal Dialog"}


def test_search_reaches_foundations_and_hands_back_hits_not_files(design, specs):
    result = ask(design, "search", query="spacing scale")
    top = result["data"][0]
    assert top["name"] == "Spacing" and top["kind"] == "foundations"
    assert "spec" not in top and top["path"].endswith("foundations/spacing.md")


def test_tokens_are_a_closed_set_named_the_way_the_scripts_spell_them(design, specs):
    tokens = ask(design, "tokens")["data"]
    assert tokens == {
        "color.text": "#172b4d",
        "color.surface.raised": "#ffffff",
        "space.100": "8px",
        "space.200": "16px",
    }


def test_breakpoints_come_from_the_file_that_states_them(design, specs):
    assert ask(design, "breakpoints")["data"] == {"sm": "640px", "md": "768px"}


def test_no_principles_file_means_the_default_set_not_the_foundations(
    design, specs, defaults_installed
):
    result = design.resolve_principles(design.DesignSystem.resolve())
    assert result["principles_source"] == "default"


def test_a_principles_file_is_the_systems_own_voice(design, specs):
    (specs / "principles.md").write_text(
        "# Principles\n\nClarity over density. Components MUST come from the system.\n",
        encoding="utf-8",
    )
    result = design.resolve_principles(design.DesignSystem.resolve())
    assert result["principles_source"] != "default"
    assert "Clarity over density" in result["prose"]


def test_a_missing_directory_is_unavailable_not_empty(design, project, write_config):
    write_config({"adapter": "markdown-specs"})
    result = ask(design, "component", name="Button")
    assert result["available"] is False and "not a directory" in result["reason"]


def test_an_empty_directory_is_unavailable_not_empty(design, project, write_config):
    (project / ".design-system" / "specs").mkdir(parents=True)
    write_config({"adapter": "markdown-specs"})
    assert ask(design, "search", query="button")["available"] is False


def test_auto_detects_a_spec_folder(design, specs, write_config):
    write_config({})
    assert design.DesignSystem.resolve().adapter_id == "markdown-specs"


def test_tiers_can_be_renamed_in_config(design, specs, write_config):
    (specs / "atoms").rename(specs / "primitives")
    write_config({"adapter": "markdown-specs", "tiers": {"primitives": "components"}})
    assert ask(design, "component", name="Button")["found"] is True


def test_the_gate_reaches_it_and_the_scan_reads_its_tokens(design, specs, project, write_config, feature):
    write_config({"adapter": "markdown-specs", "validation": {"source_globs": ["src/**/*"]}})
    src = project / "src" / "Card.css"
    src.parent.mkdir(parents=True)
    src.write_text(".card { padding: 8px; color: #172B4D; }\n", encoding="utf-8")
    ds = design.DesignSystem.resolve()
    assert ds.reachable is True
    by_value = {r["value"]: r for r in design.scan_implementation(ds)["raw_values"]}
    assert by_value["8px"]["tokens"] == ["space.100"]
    assert by_value["#172B4D"]["tokens"] == ["color.text"]


def test_spec_files_are_never_cached(design, specs):
    ds = design.DesignSystem.resolve()
    ds.ask("component", name="Button")
    assert ds.cache.stats()["calls"] == 0


def test_the_markdown_readers_know_markdown_not_any_system(design):
    assert design.token_key("--color-surface-raised") == "color.surface.raised"
    assert design.token_key("$space-100") == "space.100"
    assert design.token_key("var(--z-modal)") == "z.modal"
    assert design.token_key("color.text.subtle") == "color.text.subtle"
    assert design.markdown_pairs("| Token | Value |\n|---|---|\n| `a-b` | 4px |\n") == {"a-b": "4px"}


def test_a_principles_source_may_be_markdown(design, project, write_config, inventory):
    path = project / "docs" / "principles.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nversion: 3\n---\n# Principles\n\nForms SHOULD fit on one screen.\n")
    write_config({"adapter": "static-json", "principles": {"source": "docs/principles.md"}})
    result = design.resolve_principles(design.DesignSystem.resolve())
    assert result["principles_source"] == "docs"
    assert "Forms SHOULD fit on one screen." in result["prose"]
