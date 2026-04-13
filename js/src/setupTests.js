import "@testing-library/jest-dom";

jest.mock("date-fns-tz", () => ({
  formatInTimeZone: jest.fn((date, tz, formatStr) => {
    if (formatStr === "dd/MM/yyyy") return "01/01/2024";
    if (formatStr === "HH:mm:ss") return "00:00:00";
    return "mock-format";
  }),
}));

global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
