# RFC: The error on the login form cannot be read

## Problem

When a sign-in fails, the message under the password field is a pale red on
white. Two people on the support team cannot read it at all, and nobody can read
it outdoors. Someone reported it as "the form does nothing when the password is
wrong": the message was there, they just could not see it.

Screen reader users hit a second version of the same problem. The message is
rendered as a loose line of text below the field, so it is not announced when
the field is focused.

## Proposal

A failed sign-in says so in a way that can be read, and in a way that reaches
the person whether they are looking at the field or listening to it. The
failure is not carried by colour alone.

## Out of scope

Changing what counts as a failed sign-in, rate limiting, or the copy of the
message itself beyond what is needed to make it readable.

## Acceptance criteria

- [ ] The message is legible against its background for someone with low vision
- [ ] The failure is signalled by more than colour
- [ ] The message is announced when the field it belongs to takes focus
- [ ] A failure that belongs to the whole form, rather than one field, is
      presented as such
- [ ] The fix holds in both light and dark appearance

## Open questions

- Should a failed attempt move focus back to the field, or leave focus alone?
