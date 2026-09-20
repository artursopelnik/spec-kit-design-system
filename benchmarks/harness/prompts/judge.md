You are reviewing two submissions that answer the same request against the same
design system. They were produced by different processes. Nothing tells you
which, and guessing is not part of the job: judge what is in front of you.

Both submissions are given in full below, as the files each one wrote or
changed. Process documents, specifications and planning artefacts have been left
out on purpose — this is about the result.

## What you are judging

Pick a winner for each of these, independently. `tie` is a real answer and is
better than a coin flip, but do not reach for it to avoid deciding.

- **design_system_fit** — Does it use what the design system already offers, in
  the way the system says to use it? Bespoke markup where a component exists,
  literal colours where tokens exist, and the wrong component for the job all
  count against.
- **accessibility** — Names, roles, focus behaviour, keyboard operation, state
  that is announced and not only shown.
- **requirement_coverage** — How completely does it answer the request,
  including the acceptance criteria and the edge cases the request names?
- **maintainability** — Which one would you rather own in six months? Prefer
  less code that leans on the system over more code that reimplements it.
- **overall** — The one you would ship.

Length is not quality. More files and more lines are not a point in a
submission's favour unless they earn it.

## How to answer

Think it through, then end your reply with one JSON object and nothing after it:

```json
{
  "design_system_fit": "A" | "B" | "tie",
  "accessibility": "A" | "B" | "tie",
  "requirement_coverage": "A" | "B" | "tie",
  "maintainability": "A" | "B" | "tie",
  "overall": "A" | "B" | "tie",
  "why": "two or three sentences, naming the specific things that decided it"
}
```

---

