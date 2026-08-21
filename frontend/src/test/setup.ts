import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(cleanup);

// Mantine reads both of these during layout; jsdom implements neither.
window.matchMedia ??= ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
})) as unknown as typeof window.matchMedia;

window.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// jsdom stops short of implementing scrolling.
Element.prototype.scrollIntoView ??= vi.fn();

// CameraScanner reads both; jsdom implements neither. `isSecureContext` has
// no setter, so it needs defineProperty rather than `??=`.
if (window.isSecureContext === undefined) {
  Object.defineProperty(window, "isSecureContext", { value: true, configurable: true });
}
if (!navigator.mediaDevices) {
  Object.defineProperty(navigator, "mediaDevices", {
    value: { getUserMedia: vi.fn() },
    configurable: true,
  });
}

// An autosizing Textarea waits for the font to load before measuring, and
// jsdom ships no FontFaceSet at all. `fonts` is read-only, so it has to be
// defined rather than assigned.
if (!document.fonts) {
  Object.defineProperty(document, "fonts", {
    value: { addEventListener: vi.fn(), removeEventListener: vi.fn() },
  });
}
