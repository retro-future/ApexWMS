import { act, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CameraScanner } from "@/components/scan/CameraScanner";
import { renderWithProviders } from "@/test/render";

type Callback = (result: { getText: () => string } | undefined) => void;

const { decodeFromConstraints, stop } = vi.hoisted(() => ({
  decodeFromConstraints: vi.fn(),
  stop: vi.fn(),
}));

vi.mock("@zxing/browser", () => ({
  BrowserMultiFormatReader: vi.fn().mockImplementation(function BrowserMultiFormatReaderMock() {
    return { decodeFromConstraints };
  }),
}));

/** The decode callback is captured synchronously, the moment the effect calls it. */
function resolveWithControls() {
  let callback: Callback = () => {};
  decodeFromConstraints.mockImplementation(
    (_constraints: unknown, _preview: unknown, cb: Callback) => {
      callback = cb;
      return Promise.resolve({ stop });
    },
  );
  return {
    fire: (code: string) => act(() => callback({ getText: () => code })),
  };
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
    expect(decodeFromConstraints).not.toHaveBeenCalled();
  });

  it("shows a permission-denied message when getUserMedia is rejected", async () => {
    decodeFromConstraints.mockRejectedValue(new DOMException("denied", "NotAllowedError"));

    renderWithProviders(<CameraScanner opened onClose={vi.fn()} onDecode={vi.fn()} />);

    expect(
      await screen.findByText(
        "Camera access was denied. Allow it in your browser settings, or use the keyboard scanner instead.",
      ),
    ).toBeInTheDocument();
  });

  it("suppresses a repeated decode within the cooldown window", async () => {
    const { fire } = resolveWithControls();
    const onDecode = vi.fn();

    renderWithProviders(<CameraScanner opened onClose={vi.fn()} onDecode={onDecode} />);
    // Let decodeFromConstraints's promise resolve (real timers) before faking
    // the clock the duplicate-window check reads via Date.now().
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

  it("stops the camera when closed", async () => {
    resolveWithControls();

    const { rerender } = renderWithProviders(
      <CameraScanner opened onClose={vi.fn()} onDecode={vi.fn()} />,
    );
    // Let decodeFromConstraints's promise resolve so controls are captured.
    await act(async () => {});

    rerender(<CameraScanner opened={false} onClose={vi.fn()} onDecode={vi.fn()} />);

    expect(stop).toHaveBeenCalled();
  });
});
