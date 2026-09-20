export type Booking = {
  id: string;
  customer: string;
  room: string;
  start: string; // ISO date
  end: string; // ISO date
  status: "confirmed" | "pending" | "cancelled";
};

export async function listBookings(): Promise<Booking[]> {
  const response = await fetch("/api/bookings");
  return response.json();
}
