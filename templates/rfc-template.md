# RFC: [short title]

<!--
  The one thing this extension needs from you. Where it came from does not
  matter: a file in the repo, a GitHub or GitLab issue, a Jira ticket, a page an
  MCP server handed you. Paste it, path to it, or pipe it in:

      /speckit.design.run docs/rfcs/booking-filters.md

  Nothing here is mandatory. A three-line RFC works; the clarify phase will ask
  about what is missing rather than guess. The headings below are the ones the
  workflow reads, so using them means fewer questions back.
-->

## Problem

What is wrong today, for whom, and how you know. Describe the situation, not the
solution.

## Proposal

What should change, in user-visible terms. Say what the user can do afterwards
that they cannot do now.

Describe surfaces by **capability, not by component**: "a control for picking a
start and end date", not "a DateRangePicker". Naming the component pre-decides
what gets built, and the point of the design system step is to find out what
already exists.

## Design guidelines (optional)

What it has to look like, if your team has already decided. Paste it straight
from your guidelines or wiki, in whatever form it is written there; no format
is expected. Name tokens where you know them (`color.surface.inverse`,
`space.6`): the workflow checks every name against your design system, asks
about any it does not have, and validation checks that the code uses them.

Do not name components here either. Which component delivers this look is what
the workflow finds out.

## Out of scope

What this explicitly does not cover. This is the cheapest section to write and
the one that saves the most rework.

## Acceptance criteria

How anyone can tell this is done. Observable and testable, one per line.

- [ ] …
- [ ] …

## Open questions

Anything you do not know yet. Listing it here is better than leaving it implicit:
the clarify phase starts from this list.

- …
