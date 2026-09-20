"use client";

import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Button from "@mui/material/Button";
import Typography from "@mui/material/Typography";

type Props = {
  onCreate: () => void;
  onExport: () => void;
  onPrint: () => void;
  onAssign: () => void;
  onArchive: () => void;
  onRefresh: () => void;
  onSettings: () => void;
};

// Seven actions in one row. At 375px the last three are off screen and the rest
// are 8px apart.
export function BookingToolbar(props: Props) {
  return (
    <AppBar position="sticky" color="default" elevation={1}>
      <Toolbar sx={{ gap: 1 }}>
        <Typography variant="h6" component="h1" sx={{ mr: 2 }}>
          Bookings
        </Typography>
        <Button variant="contained" onClick={props.onCreate}>
          New booking
        </Button>
        <Button onClick={props.onExport}>Export</Button>
        <Button onClick={props.onPrint}>Print</Button>
        <Button onClick={props.onAssign}>Assign</Button>
        <Button onClick={props.onArchive}>Archive</Button>
        <Button onClick={props.onRefresh}>Refresh</Button>
        <Button onClick={props.onSettings}>Settings</Button>
      </Toolbar>
    </AppBar>
  );
}
