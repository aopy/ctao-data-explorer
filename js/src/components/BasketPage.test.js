import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BasketPage from "./BasketPage";
import { apiClient } from "../apiClients";


jest.mock("../apiClients", () => {
  const mk = () => ({
    interceptors: { response: { use: jest.fn() } },
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

jest.mock("../index", () => ({
  API_PREFIX: "/api",
  AUTH_PREFIX: "/auth",
}));

jest.mock("./datetimeUtils", () => ({
  mjdToDate: jest.fn(() => new Date("2024-01-01T00:00:00Z")),
  formatDateTimeStrings: jest.fn(() => ({
    dateStr: "01/01/2024",
    timeStr: "00:00:00",
  })),
}));

jest.mock("./QuickLookModal", () => () => <div>Mock QuickLookModal</div>);

describe("BasketPage", () => {
  const baseProps = {
    isLoggedIn: true,
    onOpenItem: jest.fn(),
    onActiveGroupChange: jest.fn(),
    onBasketGroupsChange: jest.fn(),
    refreshTrigger: 0,
    allBasketGroups: [],
    activeBasketGroupId: null,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("fetches basket groups on mount", async () => {
    apiClient.get.mockResolvedValueOnce({
      data: [
        {
          id: 1,
          name: "Basket A",
          saved_datasets: [],
        },
      ],
    });

    render(<BasketPage {...baseProps} />);

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith("/basket/groups");
    });

    expect(baseProps.onBasketGroupsChange).toHaveBeenCalledWith([
      { id: "1", name: "Basket A", saved_datasets: [] },
    ]);
    expect(baseProps.onActiveGroupChange).toHaveBeenCalledWith("1");
  });

  test("creates a new basket", async () => {
    const user = userEvent.setup();

    apiClient.get.mockResolvedValueOnce({ data: [] });
    apiClient.post.mockResolvedValueOnce({});
    apiClient.get.mockResolvedValueOnce({
      data: [{ id: 2, name: "New Basket", saved_datasets: [] }],
    });

    render(<BasketPage {...baseProps} />);

    await waitFor(() => {
      expect(screen.getByText(/You have no baskets/i)).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText(/New basket name/i), "New Basket");
    await user.click(screen.getByRole("button", { name: /Create/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/basket/groups", { name: "New Basket" });
    });
  });

  test("deletes the active basket after confirmation", async () => {
  const user = userEvent.setup();

  const props = {
    ...baseProps,
    allBasketGroups: [
      {
        id: "1",
        name: "Basket A",
        saved_datasets: [],
      },
    ],
    activeBasketGroupId: "1",
  };

  apiClient.get.mockResolvedValueOnce({ data: [] });
  apiClient.delete.mockResolvedValueOnce({});
  apiClient.get.mockResolvedValueOnce({ data: [] });

  render(<BasketPage {...props} />);

  const deleteButton = await screen.findByRole("button", { name: /Delete Basket/i });
  await user.click(deleteButton);

  expect(screen.getByText(/This will permanently delete/i)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Yes, delete/i }));

  await waitFor(() => {
    expect(apiClient.delete).toHaveBeenCalledWith("/basket/groups/1");
  });
});
});
