# RFC: Narrow the booking list by period

## Problem
Users with many bookings cannot narrow the list by date range, so they scroll through everything.

## Proposal
A control for selecting a start and end date above the booking list, and a way to cancel a booking from the list with a confirmation step.

## Acceptance criteria
- [ ] The list narrows to bookings within the selected range
- [ ] Cancelling asks for confirmation and cannot be triggered accidentally
- [ ] The chosen period survives a page reload
- [ ] Operable from the keyboard alone
- [ ] Usable down to a 375 pixel wide viewport
