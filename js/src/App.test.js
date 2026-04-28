import React from "react";
import { render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

jest.mock("./components/axiosSetup", () => ({
  __esModule: true,
  installAuthInterceptors: jest.fn(),
}));

jest.mock("./apiClients", () => {
  const mkAxiosInstance = () => {
    const inst = jest.fn(() => Promise.resolve({ status: 401, data: {} }));
    inst.get = jest.fn(() => Promise.resolve({ status: 401, data: {} }));
    inst.post = jest.fn(() => Promise.resolve({ data: {} }));
    inst.delete = jest.fn(() => Promise.resolve({ data: {} }));
    inst.interceptors = { response: { use: jest.fn() } };
    return inst;
  };

  return {
    authClient: mkAxiosInstance(),
    apiClient: mkAxiosInstance(),
    publicApiClient: mkAxiosInstance(),
  };
});

jest.mock("./components/SearchForm", () => {
  const React = require("react");
  return React.forwardRef(function MockSearchForm(_props, ref) {
    React.useImperativeHandle(ref, () => ({ saveState: jest.fn() }));
    return <div>Cone Search</div>;
  });
});

jest.mock("./components/Header", () => {
  return function MockHeader({ isLoggedIn, onLogin, onLogout }) {
    return (
      <div>
        {isLoggedIn ? (
          <button onClick={onLogout}>Logout</button>
        ) : (
          <button onClick={onLogin}>Login</button>
        )}
      </div>
    );
  };
});

jest.mock("./components/Footer", () => () => <div>Mock Footer</div>);
jest.mock("./components/AladinLiteViewer", () => () => <div>Mock Aladin</div>);
jest.mock("./components/TimelineChart", () => () => <div>Mock Timeline</div>);
jest.mock("./components/EmRangeChart", () => () => <div>Mock EM Range</div>);
jest.mock("./components/ResultsTable", () => () => <div>Mock Results Table</div>);
jest.mock("./components/BasketPage", () => () => <div>Mock Basket</div>);
jest.mock("./components/OpusJobsPage", () => () => <div>Mock Opus Jobs</div>);
jest.mock("./components/OpusJobDetailPage", () => () => <div>Mock Opus Job Detail</div>);
jest.mock("./components/QueryStorePage", () => () => <div>Mock Query Store</div>);
jest.mock("./components/UserProfilePage", () => () => <div>Mock User Profile</div>);

describe("App", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    document.cookie = "";
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("renders search page", async () => {
    const App = require("./App").default;

    const { authClient } = require("./apiClients");
    authClient.get.mockResolvedValueOnce({ status: 401, data: {} });

    render(
      <MemoryRouter initialEntries={["/search"]}>
        <App />
      </MemoryRouter>
    );

    await act(async () => {
      jest.advanceTimersByTime(150); // triggers the 100ms setTimeout
      await Promise.resolve();
      await Promise.resolve();
    });

    await waitFor(() => {
      expect(screen.getByText("Cone Search")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /Login/i })).toBeInTheDocument();
  });
});
