import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { listBookings } from "@/lib/bookings";

export default async function BookingsPage() {
  const bookings = await listBookings();

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-semibold tracking-tight">Bookings</h1>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Customer</TableHead>
            <TableHead>Room</TableHead>
            <TableHead>From</TableHead>
            <TableHead>To</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {bookings.map((booking) => (
            <TableRow key={booking.id}>
              <TableCell>{booking.customer}</TableCell>
              <TableCell>{booking.room}</TableCell>
              <TableCell>{booking.start}</TableCell>
              <TableCell>{booking.end}</TableCell>
              <TableCell>{booking.status}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </main>
  );
}
