// Jest global setup – run before all tests in every test file
import "@testing-library/jest-dom";

// Silence expected console.error/warn noise from React in tests
const originalError = console.error;
const originalWarn  = console.warn;

beforeAll(() => {
  console.error = (...args: unknown[]) => {
    const msg = String(args[0] ?? "");
    if (
      msg.includes("Warning: ReactDOM.render") ||
      msg.includes("act(") ||
      msg.includes("Warning: An update to")
    ) return;
    originalError.call(console, ...args);
  };
  console.warn = (...args: unknown[]) => {
    const msg = String(args[0] ?? "");
    if (msg.includes("React Router Future Flag Warning")) return;
    originalWarn.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
  console.warn  = originalWarn;
});
