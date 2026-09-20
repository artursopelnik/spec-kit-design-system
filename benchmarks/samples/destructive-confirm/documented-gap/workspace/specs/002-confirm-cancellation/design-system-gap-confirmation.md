# Gap: asking for a decision before something irreversible happens

**Feature**: 002-confirm-cancellation · **Design system**: Radix UI · **Version**: 1.1.0

## What is needed

A surface that interrupts, names what is about to happen, and cannot be left
without an answer.

## What was searched

| Candidate | Rung | Why it is insufficient |
|---|---|---|
| Dialog | reuse | Dismisses on outside click, so the decision can be lost |
| Popover | reuse | Dismissed by clicking away |
| Toast | reuse | After the fact, not before it |

## What we are building instead

A ConfirmSurface in this feature, holding focus until the person answers.

## What the design system could do

Ship the interruption surface with the role and the deliberate dismissal
already handled, so features stop rebuilding it.
