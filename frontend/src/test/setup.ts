import "@testing-library/jest-dom";

// Stub window.matchMedia — not implemented in jsdom
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Stub MediaRecorder — not implemented in jsdom
class MockMediaRecorder {
  stream: MediaStream;
  state: string = "inactive";
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;

  constructor(stream: MediaStream) {
    this.stream = stream;
  }
  start() { this.state = "recording"; }
  stop() {
    this.state = "inactive";
    this.onstop?.();
  }
  static isTypeSupported() { return true; }
}

Object.defineProperty(window, "MediaRecorder", {
  writable: true,
  value: MockMediaRecorder,
});

// Stub navigator.mediaDevices.getUserMedia
Object.defineProperty(navigator, "mediaDevices", {
  writable: true,
  value: {
    getUserMedia: vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: vi.fn() }],
    }),
  },
});
