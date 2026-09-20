# RFC: Filter invoices by billing period

## Problem
Accounting team members need to see invoices for a specific billing cycle without manually paging through months of data.

## Proposal
Add a date range filter to the invoices page so accounting can isolate a billing period, see all invoices for that span, and track down any discrepancies.

## Acceptance criteria
- [ ] A valid date range can be submitted and the invoices list updates
- [ ] An invalid range (end before start) is rejected with guidance on the filter
- [ ] The selected period persists across page reloads
- [ ] Fully keyboard navigable
- [ ] Works on mobile devices (375px viewports and up)
