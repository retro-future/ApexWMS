import { act, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CameraScanner } from "@/components/scan/CameraScanner";
import { renderWithProviders } from "@/test/render";

type ScanHandler = (codes: { rawValue: string }[]) => void;
type ErrorHandler = (error: { kind: string; message: string; cause: unknown }) => void;

const { scannerProps } = vi.hoisted(() => ({
  scannerProps: { onScan: undefined as ScanHandler | undefined, onError: undefined as ErrorHandler | undefined },
}));

vi.mock("@yudiel/react-qr-scanner", () => ({
  Scanner: (props: { onScan: ScanHandler; onError: ErrorHandler }) => {
    scannerProps.onScan = props.onScan;
    scannerProps.onError = props.onError;
    return <div data-testid="scanner" />;
  },
  boundingBox: vi.fn(),
  prepareZXingModule: vi.fn(),
}));

function fire(code: string) {
  act(() => scannerProps.onScan?.([{ rawValue: code }]));
}

function setSecureContext(value: boolean) {
  Object.defineProperty(window, "isSecureContext", { value, configurable: true });
}

function setMediaDevices(getUserMedia: unknown) {
  Object.defineProperty(navigator, "mediaDevices", {
    value: getUserMedia ? { getUserMedia } : undefined,
    configurable: true,
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  scannerProps.onScan = undefined;
  scannerProps.onError = undefined;
  setSecureContext(true);
  setMediaDevices(vi.fn());
});

describe("CameraScanner", () => {
  it("never starts the camera without a secure context", async () => {
    setSecureContext(false);
    renderWithProviders(<CameraScanner opened onClose={vi.fn()} onDecode={vi.fn()} />);

    expect(
      await screen.findByText(
        "Camera scanning needs a secure connection. Use the keyboard scanner instead.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("scanner")).not.toBeInTheDocument();
  });

  it("shows a permission-denied message when the scanner reports it", async () => {
    renderWithProviders(<CameraScanner opened onClose={vi.fn()} onDecode={vi.fn()} />);

    act(() =>
      scannerProps.onError?.({ kind: "permission-denied", message: "denied", cause: null }),
    );

    expect(
      await screen.findByText(
        "Camera access was denied. Allow it in your browser settings, or use the keyboard scanner instead.",
      ),
    ).toBeInTheDocument();
  });

  it("suppresses a repeated decode within the cooldown window", async () => {
    const onDecode = vi.fn();

    renderWithProviders(<CameraScanner opened onClose={vi.fn()} onDecode={onDecode} />);
    await act(async () => {});
    vi.useFakeTimers();

    fire("490154203237518");
    fire("490154203237518");
    expect(onDecode).toHaveBeenCalledTimes(1);

    act(() => {
      vi.advanceTimersByTime(1600);
    });
    fire("490154203237518");
    expect(onDecode).toHaveBeenCalledTimes(2);

    vi.useRealTimers();
  });

  it("unmounts the scanner when closed, which stops the camera", async () => {
    const { rerender } = renderWithProviders(
      <CameraScanner opened onClose={vi.fn()} onDecode={vi.fn()} />,
    );
    await act(async () => {});
    expect(screen.getByTestId("scanner")).toBeInTheDocument();

    rerender(<CameraScanner opened={false} onClose={vi.fn()} onDecode={vi.fn()} />);

    expect(screen.queryByTestId("scanner")).not.toBeInTheDocument();
  });
});
