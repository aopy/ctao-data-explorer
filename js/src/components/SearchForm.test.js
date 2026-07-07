import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SearchForm from "./SearchForm";
import { publicApiClient } from "../apiClients";

jest.mock("../apiClients", () => {
  const mk = () => ({
    interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    get: jest.fn(),
    post: jest.fn(),
    delete: jest.fn(),
  });

  return {
    authClient: mk(),
    apiClient: mk(),
    publicApiClient: mk(),
  };
});

jest.mock("./history", () => ({
  saveQueryHistoryIfLoggedIn: jest.fn(),
}));

describe("SearchForm", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    sessionStorage.clear();
  });

  test("clear form resets TAP fields to backend configured defaults", async () => {
    const user = userEvent.setup();

    publicApiClient.get.mockResolvedValueOnce({
      data: {
        default_tap_url: "https://tap.example.test/tap",
        default_obscore_table: "ctao_sdc.obscore",
      },
    });

    render(<SearchForm setResults={jest.fn()} isLoggedIn={false} />);

    await user.click(screen.getByRole("button", { name: /show advanced settings/i }));

    const tapInput = await screen.findByLabelText(/tap server url/i);
    const tableInput = screen.getByLabelText(/obscore table name/i);

    await waitFor(() => {
      expect(tapInput).toHaveValue("https://tap.example.test/tap");
      expect(tableInput).toHaveValue("ctao_sdc.obscore");
    });

    fireEvent.change(tapInput, { target: { value: "https://custom.example.test/tap" } });
    fireEvent.change(tableInput, { target: { value: "custom.obscore" } });

    await user.click(screen.getByRole("button", { name: /clear form/i }));
    await user.click(screen.getByRole("button", { name: /show advanced settings/i }));

    expect(screen.getByLabelText(/tap server url/i)).toHaveValue("https://tap.example.test/tap");
    expect(screen.getByLabelText(/obscore table name/i)).toHaveValue("ctao_sdc.obscore");
  });
});
