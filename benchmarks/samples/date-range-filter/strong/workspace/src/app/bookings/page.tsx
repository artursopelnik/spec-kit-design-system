"use client";

import { useSearchParams } from "next/navigation";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PeriodFilter } from "@/components/bookings/period-filter";
import { useBookings } from "@/lib/bookings";

export default function BookingsPage() {
  const params = useSearchParams();
  const { range, setRange, bookings } = useBookings(params);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Bookings</h1>
        <PeriodFilter value={range} onChange={setRange} />
      </div>

      <p className="text-sm text-muted-foreground" aria-live="polite">
        {bookings.length} booking(s) in the selected period
      </p>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Customer</TableHead>
            <TableHead>Room</TableHead>
            <TableHead>From</TableHead>
            <TableHead>To</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {bookings.map((booking) => (
            <TableRow key={booking.id}>
              <TableCell>{booking.customer}</TableCell>
              <TableCell>{booking.room}</TableCell>
              <TableCell>{booking.start}</TableCell>
              <TableCell>{booking.end}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </main>
  );
}
