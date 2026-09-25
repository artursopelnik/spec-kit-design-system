# Publishing

How a version gets from `main` into the
[Spec Kit community catalog](https://github.com/github/spec-kit/blob/main/extensions/catalog.community.json),
so that `specify extension search design` finds it.

The catalog does not host anything. An entry points at the archive GitHub
builds for a tag, so the tag is the release: whatever it points at is what
every user installs.

## Before tagging

- `extension.yml` and `preset/preset.yml` carry the same version, the README
  badge names it, and `CHANGELOG.md` has a dated `## [X.Y.Z] - YYYY-MM-DD`
  section for it. `tests/test_packaging.py` checks all four, and the release
  workflow checks them again against the tag.
- CI is green on `main`, including the `integration` job, which installs the
  extension into a real Spec Kit project and checks that `.extensionignore`
  leaves out only what it should.

## Tagging

```bash
git checkout main && git pull
git tag v0.3.0
git push origin v0.3.0
```

`.github/workflows/release.yml` runs on the tag. It refuses a tag that
disagrees with the manifests or the changelog, runs the tests, and publishes
the GitHub release with the changelog section as its notes. A release already
created on the Releases page (which pushes the tag and so starts the workflow)
is kept and given those notes instead of being created a second time.

### Replacing a published tag

Only while no catalog entry points at it. A moved tag changes the archive under
an unchanged URL, so a recorded `sha256` would stop matching and anyone who
installed the old one would get something different on reinstall.

```bash
# delete the release first (Releases page, or: gh release delete v0.3.0 --yes)
git push origin :refs/tags/v0.3.0
git tag -d v0.3.0
git tag v0.3.0 origin/main
git push origin v0.3.0
```

## Checking the archive

```bash
specify init /tmp/check --integration claude --non-interactive --ignore-agent-tools
cd /tmp/check
specify extension add design --from https://github.com/artursopelnik/spec-kit-design-system/archive/refs/tags/v0.3.0.zip
specify preset add --dev .specify/extensions/design/preset
specify extension info design
ls .specify/extensions/design     # no tests/, no benchmarks/
```

The digest for the catalog entry's optional `sha256`:

```bash
curl -sL https://github.com/artursopelnik/spec-kit-design-system/archive/refs/tags/v0.3.0.zip | sha256sum
```

## Submitting

Open an issue on
[github/spec-kit](https://github.com/github/spec-kit/issues/new/choose) with
the **Extension Submission** template. Do not open a pull request against
`catalog.community.json`: maintainers add the entry themselves after triage.
The fields, ready to paste:

| Field                     | Value                                                                                               |
| ------------------------- | --------------------------------------------------------------------------------------------------- |
| Extension ID              | `design`                                                                                            |
| Extension Name            | `Spec Kit Design System`                                                                            |
| Version                   | `0.3.0`                                                                                             |
| Description               | `Give it an RFC. It runs the Spec Kit workflow and implements the change using your design system.` |
| Author                    | `artursopelnik`                                                                                     |
| Repository URL            | `https://github.com/artursopelnik/spec-kit-design-system`                                           |
| Download URL              | `https://github.com/artursopelnik/spec-kit-design-system/archive/refs/tags/v0.3.0.zip`              |
| License                   | `MIT`                                                                                               |
| Homepage                  | `https://github.com/artursopelnik/spec-kit-design-system`                                           |
| Documentation URL         | `https://github.com/artursopelnik/spec-kit-design-system/blob/main/README.md`                       |
| Changelog URL             | `https://github.com/artursopelnik/spec-kit-design-system/blob/main/CHANGELOG.md`                    |
| Required Spec Kit Version | `>=1.0.0,<2.0.0`                                                                                    |
| Number of Commands        | `3`                                                                                                 |
| Number of Hooks           | `2`                                                                                                 |
| Tags                      | `design-system, design-tokens, accessibility, autonomous, reuse`                                    |

**Required Tools**

```markdown
- python3 (>=3.9, with PyYAML) - required
- bash - required
- the project's design system CLI or inventory file - named per project in design-config.yml, not a fixed dependency
```

**Key Features**

```markdown
- One command, `/speckit.design.run <rfc>`, carries an RFC through clarify, specify, plan, implement, validate, fix and verify
- The project's own design system is the source of truth: components, patterns, tokens and principles are asked through a small YAML adapter (CLI, file or MCP), never guessed
- A blocking `before_plan` gate walks Recall → Reuse → Compose → Extend → Create, strict only where something new would be built, and fails closed when the design system cannot be reached
- Answers from the design system are cached per feature, so its CLI is asked each question once
- A committed decision ledger, keyed by UI capability, so later features reuse earlier decisions
- Validation after implement: a mechanical scan for raw values and token names, one independent review, and one round that checks only the fixes
- Adapters for shadcn/ui, MUI, Ant Design, Chakra UI, Radix UI, Ark UI and any generated JSON inventory
- A companion preset appends design sections to the spec, plan and constitution templates instead of replacing them
```

**Testing Details**

```markdown
**Tested on:**

- Linux, specify-cli 1.0.10: installed from the release archive, preset added, gate run
- Linux, specify-cli 1.0.11: 0.2.0 installed with `--dev`, preset added, manifests validated, hooks and preset composition checked
- Linux (Ubuntu, GitHub Actions), latest specify-cli: on every push and weekly
- Python 3.9 (local) and 3.11 (CI)

**Test scenarios:**

1. `specify extension add design --from <release archive>` and `specify preset add --dev .specify/extensions/design/preset`
2. Manifests validated with Spec Kit's own `ExtensionManifest` and `PresetManifest`
3. Hooks registered (`before_plan` non-optional, `after_implement`), preset append-composition resolved
4. Gate run against a fixture design system, and fails closed when it is unreachable
5. Unit suite (350+ tests) covering dispatch, principles, context, workflow, ledger and the command prose
```

**Example Usage**

```bash
specify extension add design --from https://github.com/artursopelnik/spec-kit-design-system/archive/refs/tags/v0.3.0.zip
specify preset add --dev .specify/extensions/design/preset

/speckit.design.run docs/rfcs/newsletter-footer.md
```

**Proposed Catalog Entry**

```json
{
  "design": {
    "name": "Spec Kit Design System",
    "id": "design",
    "description": "Give it an RFC. It runs the Spec Kit workflow and implements the change using your design system.",
    "author": "artursopelnik",
    "version": "0.3.0",
    "download_url": "https://github.com/artursopelnik/spec-kit-design-system/archive/refs/tags/v0.3.0.zip",
    "repository": "https://github.com/artursopelnik/spec-kit-design-system",
    "homepage": "https://github.com/artursopelnik/spec-kit-design-system",
    "documentation": "https://github.com/artursopelnik/spec-kit-design-system/blob/main/README.md",
    "changelog": "https://github.com/artursopelnik/spec-kit-design-system/blob/main/CHANGELOG.md",
    "license": "MIT",
    "category": "integration",
    "effect": "read-write",
    "requires": {
      "speckit_version": ">=1.0.0,<2.0.0",
      "tools": [
        { "name": "python3", "version": ">=3.9", "required": true },
        { "name": "bash", "required": true }
      ]
    },
    "provides": {
      "commands": 3,
      "hooks": 2
    },
    "tags": [
      "design-system",
      "design-tokens",
      "accessibility",
      "autonomous",
      "reuse"
    ],
    "verified": false,
    "downloads": 0,
    "stars": 0,
    "created_at": "2026-09-23T00:00:00Z",
    "updated_at": "2026-09-23T00:00:00Z"
  }
}
```

**Additional Context**

```markdown
The preset (`preset/`) ships inside the extension archive and installs from the
extension's own directory, because extensions can only replace templates while
presets can append. It is not submitted to the preset catalog separately.
```

## Updating the entry

For a new version: bump both manifests and the README badge, add the dated
changelog section, tag, and file a new Extension Submission issue with the new
version and download URL, saying it updates the existing `design` entry.
