# RFC: The booking toolbar is unusable on a phone

## Problem

The toolbar above the booking list carries seven actions. On a phone the row
runs off the side of the screen: the last three actions cannot be reached at
all, and the ones that are visible sit so close together that people hit the
wrong one. Half of support works from a phone on the way to a site visit.

## Proposal

At small widths the toolbar shows the action people came for and moves the rest
somewhere they can still be reached. Nothing disappears: an action that is not
in the bar is still one tap away, with the same label it has on a desktop. The
targets are big enough to hit while walking.

## Out of scope

Redesigning the actions themselves, or what they do. The desktop layout stays
as it is.

## Acceptance criteria

- [ ] Every action remains reachable at 375 pixels wide
- [ ] The toolbar does not scroll sideways or clip
- [ ] Nothing is reachable by keyboard while invisible on screen
- [ ] Touch targets are large enough to hit reliably
- [ ] The desktop layout is unchanged

## Open questions

- Which single action is the one that stays in the bar?
