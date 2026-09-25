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
| `shadcn`                                   | The shadcn CLI. `docs` and `info` emit JSON; `search` and `view` print for humans, which is usable but less structured. No token command exists, so `tokens` is deliberately unmapped. |
| `mui`, `antd`, `chakra`, `radix`, `ark-ui` | Libraries with no query CLI. Each reads the same generated inventory as `static-json`, so `adapter: mui` names your system and `auto` can pick it from `package.json`.                 |
| `static-json`                              | No CLI at all. Reads a generated inventory file.                                                                                                                                       |
| `markdown-specs`                           | No CLI and no inventory: a folder of Markdown spec files, one per foundation, token group and component, read as it is.                                                                |
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
| `principles`      | The system's own principles and guidance                       | The default fallback set applies        |
| `list_components` | Full inventory                                                 | Search carries the load alone           |
| `describe`        | The CLI's own manifest                                         | Mapping drift is harder to diagnose     |
| `extend`          | The sanctioned way to customize a component                    | Rung 4 is advice rather than a check    |
| `validate`        | The system checking an implementation itself                   | Validation reasons rather than measures |
| `report_gap`      | The system's intake for a missing component                    | Rung 5 dead-ends in a document          |

An unmapped capability is reported `available: false` and the commands degrade. Nothing is faked.

`ds.sh gate --json` reports `LADDER_SUPPORT`: per rung of the reuse ladder, what backs it and whether the design system can actually be asked. `extend` and `report_gap` are the two most CLIs do not have, so rungs 4 and 5 commonly come back `automated: false`. That is a supported degradation — rung 4 is walked against the component's documented extension points, and the rung 5 gap record is written and gated either way — but it is worth seeing at gate time rather than inferring from a thin ladder walk. Map them to whatever accepts the job: an eject or swizzle command for `extend`, an issue CLI or a webhook script for `report_gap`.

## Four kinds of mapping

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

**An MCP tool**, for a design system already exposed over MCP:

```yaml
search:
  mcp:
    server: "design-system"
    tool: "search_components"
    client: "npx @acme/mcp-call" # or set `mcp.client` once at adapter level
  args: ["--query", "{query}"]
  result_path: "results"
```

The call is handed to a client command you name, because this extension ships no MCP client and should not grow one: stdio framing, session handling and auth belong to whatever your project already uses to talk to its servers. The client is invoked as `<client> --server <server> --tool <tool> <args...>` and is expected to print the tool's result as JSON on stdout.

Everything downstream is identical to a CLI mapping — `result_path`, `pick`, `key_field`, the error semantics below — because the MCP transport reuses the CLI transport's failure handling rather than restating it. An MCP server that cannot be reached is exactly as `available: false` as a CLI that is not installed, and must never read as a design system with nothing in it.

**A directory of spec files**, for a design system written down in Markdown:

```yaml
component:
  read_dir: "{source}"
  result_path: "components"
  key_field: "name"
```

The folder is read into the same document `static-json` reads: `components`, `patterns` and `foundations` records (name, tier, description, usage, avoid, front matter keys, path and the whole file as `spec`), a flat `tokens` map, `principles` prose, and each file's named values under `values.<file stem>`, which is how `breakpoints` points at `breakpoints.md`. The adapter's `tiers` map says which top-level folder lands in which section; see [markdown-specs.yml](../adapters/markdown-specs.yml). On `search`, `hit_fields` keeps each hit to the fields named, so twenty hits do not carry twenty files.

> [!NOTE]
> An adapter uses **one** of these per capability, and they can be mixed within one adapter: read tokens from a generated file, ask an MCP server for components, shell out to `gh` to file a gap.

## One command, two questions

Most design systems have no breakpoint command; the breakpoints sit inside the token payload. Mapping both capabilities onto the same call is right. Leaving both mapped to the same _slice_ of it is not — `breakpoints` then answers with the whole token set, and every phase that asks for breakpoints pays for the tokens again:

```yaml
tokens:
  args: ["tokens"]
  result_path: "data"

breakpoints:
  args: ["tokens"] # same call
  result_paths: ["data.breakpoints", "data.screens", "data.theme.screens"]
```

| Key            | What it does                                                                                                  |
| -------------- | ------------------------------------------------------------------------------------------------------------- |
| `result_path`  | One dotted path. The common case.                                                                             |
| `result_paths` | Candidates in order, first hit wins. For names that differ between systems or versions.                       |
| `pick`         | Keep only these keys of the resolved mapping, for an answer that is several siblings rather than one subtree. |

`ds.sh context plan --json` names this when it happens: a `breakpoints` answer identical to the `tokens` answer is reported in `notes`, with its size, because nothing else about the run looks wrong — the breakpoint names really are in the payload, they just arrive twice.

When none of them resolve, the response comes back whole with `result_path_missed: true` rather than as a null — a payload is more use than a fabricated "nothing" — and `ds.sh context` puts it in `notes`. If a capability that should answer narrowly keeps returning the full payload, that flag is where to look.

## What an answer costs

Every capability result carries `bytes`, and `ds.sh context <phase>` carries a `sizes` block per section plus a total. Focused context is a claim about size, and an unmeasured claim drifts: a capability quietly answering with 50 KB looks exactly like one answering with 50 until something counts.

Large answers are reported, never trimmed behind your back. A context that dropped half a token set would make the agent confidently wrong, which is worse than an expensive run. Two levers, in this order:

1. **Narrow the mapping.** `result_path`, `result_paths`, `pick` — paid once in the adapter, saved on every run.
2. **Narrow the call.** `--fields` trims what one query returns:

   ```bash
   ds.sh query list_components --fields name,description --json
   ```

   A full inventory is the most expensive thing most systems will say, and surveying one rarely needs the props. The full record stays one call away; `bytes_unprojected` reports what the untrimmed answer would have cost.

If a capability is still expensive after both, it is a request to make of the design system itself: a narrower endpoint there is the largest single lever on context cost, because it removes the payload instead of moving it.

## When the capability belongs to another tool

`extend` and `report_gap` are the two most design system CLIs do not have, and the reason is usually that they are somebody else's job: a gap is filed in an issue tracker, a component is ejected by a codegen tool. A capability can name its own binary, so those mappings do not need a wrapper script:

```yaml
report_gap:
  bin: "gh"
  args:
    [
      "issue",
      "create",
      "--repo",
      "acme/design-system",
      "--title",
      "{title}",
      "--body",
      "{body}",
    ]

extend:
  bin: "./scripts/swizzle.sh"
  args: ["{name}", "--dry-run"]
```

This works on a file-backed adapter too, which is how a static inventory — no CLI anywhere — still gets a write side for rung 5.

A capability that names its own binary is invoked on its own terms: the adapter's `global_args` and `envelope` are the design system CLI's, and are not applied to it. Its exit code decides whether the call succeeded, so `not_found_codes` has no effect there either.

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
