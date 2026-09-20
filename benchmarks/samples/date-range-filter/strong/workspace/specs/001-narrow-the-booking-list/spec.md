# Feature Specification: Narrow the booking list by period

## User Scenarios

An operator opens the booking list, names a start and an end, and sees only the
bookings within the selected period, with a count of how many that is. Coming
back from a booking keeps the period: it is restored from the search params
after a reload.

## Requirements

- **DS-001**: The period control MUST be the Popover + Button + Calendar
  composition the design system documents, with the Calendar in `mode="range"`.
  A separate date picker dependency MUST NOT be added.
- **DS-002**: A period whose end falls before its start MUST be refused through
  FormMessage on the control itself, so it is announced as well as seen.
- **DS-003**: The list MUST stay on the system's Table primitives.
- **DS-004**: All colour and spacing MUST come from the theme variables and the
  spacing scale. Literal colours MUST NOT appear in component code.
- **DS-005**: The whole control MUST be operable from the keyboard: the trigger
  opens on Enter and Space, focus moves into the Calendar, Escape closes and
  returns focus to the trigger.
- **DS-006**: At the sm breakpoint and below the Calendar MUST show one month,
  and the trigger MUST keep a 44px target. Verified down to 375 pixels wide.

## Acceptance Criteria

- [ ] Only bookings within the selected period are listed
- [ ] An end before the start is refused, with the reason on the control
- [ ] The period is restored after a reload
- [ ] Operable from the keyboard alone, including focus return
- [ ] Usable at 375 pixels wide
