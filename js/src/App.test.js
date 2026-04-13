jest.mock("./index", () => ({
  AUTH_PREFIX: "/auth",
  API_PREFIX: "/api",
}));

import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import axios from "axios";
import App from "./App";

jest.mock("axios");

jest.mock("./components/SearchForm", () => {
  const React = require("react");
  return React.forwardRef(function MockSearchForm(props, ref) {
    React.useImperativeHandle(ref, () => ({
      saveState: jest.fn(),
    }));
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
    jest.clearAllMocks();

    axios.get.mockImplementation((url) => {
      if (String(url).includes("/me")) {
        return Promise.resolve({ status: 401, data: {} });
      }
      return Promise.resolve({ data: [] });
    });
  });

  test("renders search page", async () => {
    render(
      <MemoryRouter initialEntries={["/search"]}>
        <App />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Cone Search")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /Login/i })).toBeInTheDocument();
  });
});
