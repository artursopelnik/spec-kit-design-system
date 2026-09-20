# RFC: Narrow the booking list by period

## Problem

The operations team works through bookings all day. The list shows every
booking ever made, newest first, so finding the ones for a single week means
scrolling past months of them. People have started keeping their own
spreadsheets to avoid the list entirely.

## Proposal

Above the list, a way to say which period the list should cover, by naming a
start and an end. The list then shows only the bookings that fall inside it, and
says how many that is. The chosen period is still there after a reload, so
coming back from a booking does not mean choosing it again.

## Out of scope

Saving a period as a named preset. Exporting the filtered list.

## Acceptance criteria

- [ ] The list shows only the bookings inside the chosen period
- [ ] A period whose end falls before its start is refused, and the reason
      appears with the control rather than somewhere else on the page
- [ ] The chosen period survives a reload
- [ ] The whole thing can be operated from the keyboard alone
- [ ] It is usable on a phone, down to a 375 pixel wide viewport

## Open questions

- Should an empty period mean every booking, or none?
- Is there a longest period worth allowing?
