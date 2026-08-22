"use client";

/**
 * Fires only when the root layout itself throws, so it cannot rely on
 * anything the layout provides (Mantine, next-intl) — it renders its own
 * <html>/<body> and stays deliberately plain. Inline styles are the
 * project's documented exception here: no MantineProvider exists at this
 * point in the tree for a Mantine prop or theme token to resolve against.
 */
export default function GlobalError({ reset }: { reset: () => void }) {
  return (
    <html lang="en">
      <body
        style={{
          display: "flex",
          minHeight: "100dvh",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ textAlign: "center" }}>
          <h1 style={{ fontSize: "1.25rem", marginBottom: "1rem" }}>
            Something went wrong. Please try again.
          </h1>
          <button
            onClick={reset}
            style={{
              padding: "0.5rem 1rem",
              fontSize: "1rem",
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
