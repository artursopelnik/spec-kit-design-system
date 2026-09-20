"use client";

import { useState } from "react";
import { DateRangePicker } from "@/components/ui/date-range-picker";
import { Button } from "@/components/ui/button";

export function BookingFilters({ bookings }) {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  function apply() {
    if (to && from && to < from) {
      alert("End date must be after start date");
      return;
    }
  }

  const filtered = bookings.filter((b) => (!from || b.start >= from) && (!to || b.end <= to));

  return (
    <div style={{ display: "flex", gap: "12px", padding: "16px", background: "#f5f5f5" }}>
      <label style={{ color: "#333", fontSize: "13px" }}>
        From
        <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
      </label>
      <label style={{ color: "#333", fontSize: "13px" }}>
        To
        <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
      </label>
      <DateRangePicker onChange={() => {}} />
      <Button variant="danger" onClick={apply}>
        Apply
      </Button>

      <table>
        <thead>
          <tr>
            <th style={{ padding: "8px", borderBottom: "1px solid #ddd" }}>Customer</th>
            <th style={{ padding: "8px" }}>From</th>
            <th style={{ padding: "8px" }}>To</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((b) => (
            <tr key={b.id}>
              <td style={{ padding: "8px" }}>{b.customer}</td>
              <td>{b.start}</td>
              <td>{b.end}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
