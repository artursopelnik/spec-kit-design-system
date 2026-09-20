# Adapters

An adapter tells the extension how to ask your design system. It is declarative YAML, it holds no design knowledge of its own, and writing one is usually ten lines.

```yaml
id: acme
name: "Acme Design System"
bin: "npx acme-ds"
global_args: ["--json"]

capabilities:
  search:
    args: ["search", "{query}"]
    result_path: "data.results"
  component:
    args: ["show", "{name}"]
    result_path: "data"
    not_found_codes: ["ERR_NOT_FOUND"]
```

Save as `.specify/extensions/design/adapters/acme.yml`, then `adapter: acme` in your config. Done.

## Shipped adapters

| Adapter                                    | Basis                                                                                                                                                                                  |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `astryx`                                   | The Astryx CLI. Every command takes `--json`, and `manifest` self-describes, so nearly every capability maps one-to-one, including `guidelines` via `docs principles`.                 |
| `shadcn`                                   | The shadcn CLI. `docs` and `info` emit JSON; `search` and `view` print for humans, which is usable but less structured. No token command exists, so `tokens` is deliberately unmapped. |
| `mui`, `antd`, `chakra`, `radix`, `ark-ui` | Libraries with no query CLI. Each reads the same generated inventory as `static-json`, so `adapter: mui` names your system and `auto` can pick it from `package.json`.                 |
| `static-json`                              | No CLI at all. Reads a generated inventory file.                                                                                                                                       |
| `example`                                  | A template with invented flags. It will not run as-is, on purpose.                                                                                                                     |

If a shipped adapter drifts from its CLI, fix the YAML — that is the whole point of keeping it out of the code.

## The capability contract

The extension is written against these names only. Only `search` and `component` are strictly required; everything else improves what the workflow can do.

| Capability        | What it answers                                                | Without it                              |
| ----------------- | -------------------------------------------------------------- | --------------------------------------- |
| `search`          | Ranked search across components, patterns, docs                | The reuse ladder cannot run             |
| `component`       | Props, variants, states, accessibility notes for one component | Implementation guesses at the API       |
| `pattern`         | A composed arrangement: pattern, template, block, recipe       | Rung 2 is skipped                       |
| `tokens`          | Design tokens                                                  | "Use our tokens" is unenforceable       |
| `breakpoints`     | Breakpoint names and widths                                    | The agent invents breakpoint names      |
| `guidelines`      | The system's own principles and guidance                       | The default fallback set applies        |
| `list_components` | Full inventory                                                 | Search carries the load alone           |
| `describe`        | The CLI's own manifest                                         | Mapping drift is harder to diagnose     |
| `extend`          | The sanctioned way to customize a component                    | Rung 4 is advice rather than a check    |
| `validate`        | The system checking an implementation itself                   | Validation reasons rather than measures |
| `report_gap`      | The system's intake for a missing component                    | Rung 5 dead-ends in a document          |

An unmapped capability is reported `available: false` and the commands degrade. Nothing is faked.

## Two kinds of mapping

**A command**, for a CLI:

```yaml
tokens:
  args: ["tokens", "{theme}"]
  result_path: "data"
  defaults:
    theme: "default"
```

`{placeholders}` expand from the call's parameters. A list-valued one (like `registries`) splices into separate argv elements. A placeholder with no value drops its argument _and_ the flag before it, so no dangling flag swallows the next argument.

**A file**, for a system with no CLI:

```yaml
component:
  read_file: "{source}"
  result_path: "components"
  key_field: "name"
```

JSON or YAML, resolved against `cwd` if you set one. This is how the `static-json` adapter works, and it is often the fastest way in: most teams can generate an inventory from Storybook, a token pipeline or their component registry in a few lines of build script.

## Error semantics, which matter more than they look

```yaml
component:
  args: ["show", "{name}"]
  not_found_codes: ["ERR_NOT_FOUND"]
```

`not_found_codes` lists the error codes that mean _"asked successfully, and it does not exist"_. Everything else — a non-zero exit, an undeclared code, a missing binary — is a failure to ask, reported as `available: false`.

Get this backwards and a registry outage reads as an empty design system, which pushes the ladder toward building something new. That is the failure mode the whole extension exists to prevent, so it is worth the two minutes of reading your CLI's exit codes.

## Overriding without forking

Adapters are committed content. To change one call for your project, override it in `design-config.yml`:

```yaml
adapter: shadcn
capabilities:
  tokens:
    read_file: "app/design-tokens.json"
```

Only the named capability changes; the rest of the adapter stays.

## Writing one from what the CLI actually reports

If your CLI can describe itself, ask it first and map from what it says, not from its documentation:

```bash
npx your-ds manifest --json
```

Then map `describe` to that command. When a capability later starts failing in a way that looks like a flag change rather than an outage, `ds.sh query describe --json` tells you what the CLI's surface is now, and the mismatch is obvious.

Start with `search` and `component`, confirm they work:

```bash
DS=.specify/extensions/design/scripts/bash/ds.sh
$DS query search "date range" --json
$DS query component Button --json
$DS gate --json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['REACHABLE'], d['CAPABILITIES'])"
```

Then add capabilities one at a time. Each one makes the workflow sharper; none of them is required to start.

## Contributing an adapter

An adapter for a public design system is the most useful contribution to this repository. The bar is that you ran it against the real CLI. An adapter written from documentation is a guess, and a stale guess in `adapters/` is worse than no adapter, because it looks authoritative while being wrong. Say in the file's header comment which version you verified against and which capabilities you could not map honestly.
