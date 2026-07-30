import { Paper } from "@mantine/core";

import classes from "@/components/TableScrollArea.module.css";

/** Bordered card that lets a wide table scroll horizontally instead of the page. */
export function TableScrollArea({ children }: { children: React.ReactNode }) {
  return (
    <Paper withBorder radius="md" className={classes.root}>
      {children}
    </Paper>
  );
}
