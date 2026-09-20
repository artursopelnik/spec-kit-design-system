export type Booking = {
  id: string;
  customer: string;
  room: string;
  start: string;
  end: string;
  status: "confirmed" | "pending" | "cancelled";
};

export async function cancelBooking(id: string): Promise<void> {
  await fetch(`/api/bookings/${id}`, { method: "DELETE" });
}
