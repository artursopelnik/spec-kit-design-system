"use client";

import { useState } from "react";
import { cancelBooking, type Booking } from "@/lib/bookings";
import styles from "./BookingRow.module.css";

export function BookingRow({ booking }: { booking: Booking }) {
  const [pending, setPending] = useState(false);

  // Cancelling takes effect the moment the control is pressed. This is the bug.
  async function onCancel() {
    setPending(true);
    await cancelBooking(booking.id);
    setPending(false);
  }

  return (
    <div className={styles.row}>
      <span className={styles.customer}>{booking.customer}</span>
      <span className={styles.dates}>
        {booking.start} to {booking.end}
      </span>
      <button className={styles.action} type="button">
        Open
      </button>
      <button className={styles.action} type="button">
        Duplicate
      </button>
      <button
        className={`${styles.action} ${styles.destructive}`}
        type="button"
        onClick={onCancel}
        disabled={pending}
      >
        Cancel booking
      </button>
    </div>
  );
}
