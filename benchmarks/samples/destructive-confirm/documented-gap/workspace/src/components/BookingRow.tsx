"use client";

import { useState } from "react";
import * as Toast from "@radix-ui/react-toast";
import { cancelBooking, type Booking } from "@/lib/bookings";
import { ConfirmSurface } from "./ConfirmSurface";
import styles from "./BookingRow.module.css";

export function BookingRow({ booking }: { booking: Booking }) {
  const [asking, setAsking] = useState(false);
  const [done, setDone] = useState(false);
  const [pending, setPending] = useState(false);

  async function confirm() {
    setPending(true);
    await cancelBooking(booking.id);
    setPending(false);
    setAsking(false);
    setDone(true);
  }

  return (
    <div className={styles.row}>
      <span className={styles.customer}>{booking.customer}</span>
      <button
        className={`${styles.action} ${styles.destructive}`}
        type="button"
        onClick={() => setAsking(true)}
        disabled={pending}
      >
        Cancel booking
      </button>

      <ConfirmSurface
        open={asking}
        title={`Cancel ${booking.customer}'s booking?`}
        description="The slot is released immediately and cannot be restored from here."
        onConfirm={confirm}
        onCancel={() => setAsking(false)}
      />

      <Toast.Root open={done} onOpenChange={setDone}>
        <Toast.Title>Booking cancelled</Toast.Title>
      </Toast.Root>
    </div>
  );
}
