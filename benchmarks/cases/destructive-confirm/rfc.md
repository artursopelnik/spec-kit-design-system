# RFC: Cancelling a booking is too easy to do by accident

## Problem

Support cancels bookings from the booking list. The cancel control sits in the
row, next to the controls that open and duplicate a booking, and it takes
effect immediately. Three cancellations last month were accidental. Two of them
were only noticed when the customer called.

A cancellation cannot be undone by the person who made it: it releases the slot,
and the slot may be gone by the time anyone notices.

## Proposal

Cancelling asks first. The question names the booking being cancelled and says
what cancelling does, and nothing happens until the person answers it. Walking
away, clicking elsewhere or pressing a key by reflex must not count as an
answer. Once a cancellation goes through, the person is told it did.

## Out of scope

Restoring a cancelled booking. Changing who is allowed to cancel.

## Acceptance criteria

- [ ] Cancelling cannot complete without an explicit confirmation
- [ ] The confirmation names the booking and the consequence
- [ ] Dismissing by clicking outside is not an answer
- [ ] The confirmation is operable from the keyboard, and focus returns to where
      it came from afterwards
- [ ] After a cancellation goes through, the person sees that it did

## Open questions

- Should the confirmation say how long the slot has been held?
