import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import SearchForm from "./SearchForm";
import { publicApiClient } from "../apiClients";
import {
  saveQueryHistoryIfLoggedIn,
} from "./history";

jest.mock("../apiClients", () => {
  const mk = () => ({
    interceptors: {
      request: {
        use: jest.fn(),
      },
      response: {
        use: jest.fn(),
      },
    },
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

function createDeferredPromise() {
  let resolve;
  let reject;

  const promise = new Promise(
    (resolvePromise, rejectPromise) => {
      resolve = resolvePromise;
      reject = rejectPromise;
    }
  );

  return {
    promise,
    resolve,
    reject,
  };
}

describe("SearchForm", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    sessionStorage.clear();
  });

  test("clear form resets TAP fields to backend configured defaults", async () => {
    const user = userEvent.setup();

    publicApiClient.get.mockResolvedValueOnce({
      data: {
        default_tap_url:
          "https://tap.example.test/tap",
        default_obscore_table:
          "ctao_sdc.obscore",
      },
    });

    render(
      <SearchForm
        setResults={jest.fn()}
        isLoggedIn={false}
      />
    );

    await user.click(
      screen.getByRole("button", {
        name: /show advanced settings/i,
      })
    );

    const tapInput =
      await screen.findByLabelText(
        /tap server url/i
      );

    const tableInput =
      screen.getByLabelText(
        /obscore table name/i
      );

    await waitFor(() => {
      expect(tapInput).toHaveValue(
        "https://tap.example.test/tap"
      );

      expect(tableInput).toHaveValue(
        "ctao_sdc.obscore"
      );
    });

    fireEvent.change(tapInput, {
      target: {
        value:
          "https://custom.example.test/tap",
      },
    });

    fireEvent.change(tableInput, {
      target: {
        value: "custom.obscore",
      },
    });

    await user.click(
      screen.getByRole("button", {
        name: /clear form/i,
      })
    );

    await user.click(
      screen.getByRole("button", {
        name: /show advanced settings/i,
      })
    );

    expect(
      screen.getByLabelText(
        /tap server url/i
      )
    ).toHaveValue(
      "https://tap.example.test/tap"
    );

    expect(
      screen.getByLabelText(
        /obscore table name/i
      )
    ).toHaveValue(
      "ctao_sdc.obscore"
    );
  });

  test("show all available data loads results without search criteria", async () => {
    const user = userEvent.setup();
    const setResults = jest.fn();

    const payload = {
      columns: [
        "obs_id",
        "s_ra",
        "s_dec",
        "em_min",
        "em_max",
      ],
      data: [
        [
          "obs-001",
          83.63,
          22.01,
          0.1,
          10.0,
        ],
        [
          "obs-002",
          120.25,
          -35.4,
          0.2,
          20.0,
        ],
      ],
      total_rows: 2,
      truncated: false,
      truncation_message: null,
    };

    publicApiClient.get.mockImplementation(
      (url) => {
        if (url === "/config/frontend") {
          return Promise.resolve({
            data: {
              default_tap_url:
                "https://tap.example.test/tap",
              default_obscore_table:
                "ctao_sdc.obscore",
            },
          });
        }

        if (url === "/search_coords") {
          return Promise.resolve({
            data: payload,
          });
        }

        return Promise.reject(
          new Error(
            `Unexpected GET request: ${url}`
          )
        );
      }
    );

    render(
      <SearchForm
        setResults={setResults}
        isLoggedIn={false}
      />
    );

    await waitFor(() => {
      expect(
        publicApiClient.get
      ).toHaveBeenCalledWith(
        "/config/frontend"
      );
    });

    await user.click(
      screen.getByRole("button", {
        name: /show all available data/i,
      })
    );

    await waitFor(() => {
      expect(
        publicApiClient.get
      ).toHaveBeenCalledWith(
        "/search_coords",
        {
          params: {
            show_all: true,
            tap_url:
              "https://tap.example.test/tap",
            obscore_table:
              "ctao_sdc.obscore",
          },
        }
      );
    });

    expect(setResults).toHaveBeenCalledWith(
      payload
    );

    expect(
      saveQueryHistoryIfLoggedIn
    ).toHaveBeenCalledWith({
      isLoggedIn: false,
      queryParams: {
        show_all: true,
        tap_url:
          "https://tap.example.test/tap",
        obscore_table:
          "ctao_sdc.obscore",
      },
      results: payload,
    });
  });

  test(
    "show all waits for frontend configuration before enabling the action",
    async () => {
      const user = userEvent.setup();
      const setResults = jest.fn();

      const deferredConfig =
        createDeferredPromise();

      const payload = {
        columns: ["obs_id"],
        data: [["obs-001"]],
        total_rows: 1,
        truncated: false,
        truncation_message: null,
      };

      publicApiClient.get.mockImplementation(
        (url) => {
          if (url === "/config/frontend") {
            return deferredConfig.promise;
          }

          if (url === "/search_coords") {
            return Promise.resolve({
              data: payload,
            });
          }

          return Promise.reject(
            new Error(
              `Unexpected GET request: ${url}`
            )
          );
        }
      );

      render(
        <SearchForm
          setResults={setResults}
          isLoggedIn={false}
        />
      );

      const showAllButton =
        screen.getByRole("button", {
          name: /show all available data/i,
        });

      // configuration has not finished loading yet
      expect(showAllButton).toBeDisabled();

      // a click while disabled must not start a search
      await user.click(showAllButton);

      expect(
        publicApiClient.get.mock.calls.some(
          ([url]) => url === "/search_coords"
        )
      ).toBe(false);

      // finish loading the deployment configuration
      deferredConfig.resolve({
        data: {
          default_tap_url:
            "https://configured.example.test/tap",
          default_obscore_table:
            "configured.obscore",
        },
      });

      await waitFor(() => {
        expect(showAllButton).toBeEnabled();
      });

      await user.click(showAllButton);

      await waitFor(() => {
        expect(
          publicApiClient.get
        ).toHaveBeenCalledWith(
          "/search_coords",
          {
            params: {
              show_all: true,
              tap_url:
                "https://configured.example.test/tap",
              obscore_table:
                "configured.obscore",
            },
          }
        );
      });

      expect(setResults).toHaveBeenCalledWith(
        payload
      );
    }
  );

  test("show all available data ignores values entered in search fields", async () => {
    const user = userEvent.setup();
    const setResults = jest.fn();

    const payload = {
      columns: ["obs_id"],
      data: [["obs-001"]],
      total_rows: 1,
      truncated: false,
      truncation_message: null,
    };

    publicApiClient.get.mockImplementation(
      (url) => {
        if (url === "/config/frontend") {
          return Promise.resolve({
            data: {
              default_tap_url:
                "https://tap.example.test/tap",
              default_obscore_table:
                "ctao_sdc.obscore",
            },
          });
        }

        if (url === "/search_coords") {
          return Promise.resolve({
            data: payload,
          });
        }

        return Promise.reject(
          new Error(
            `Unexpected GET request: ${url}`
          )
        );
      }
    );

    render(
      <SearchForm
        setResults={setResults}
        isLoggedIn={false}
      />
    );

    await waitFor(() => {
      expect(
        publicApiClient.get
      ).toHaveBeenCalledWith(
        "/config/frontend"
      );
    });

    fireEvent.change(
      screen.getByLabelText("RA (deg)"),
      {
        target: {
          value: "83.63",
        },
      }
    );

    fireEvent.change(
      screen.getByLabelText("Dec (deg)"),
      {
        target: {
          value: "22.01",
        },
      }
    );

    fireEvent.change(
      screen.getByLabelText(
        /radius \(deg\)/i
      ),
      {
        target: {
          value: "2.5",
        },
      }
    );

    await user.click(
      screen.getByRole("button", {
        name: /show all available data/i,
      })
    );

    await waitFor(() => {
      expect(setResults).toHaveBeenCalledWith(
        payload
      );
    });

    const searchCall =
      publicApiClient.get.mock.calls.find(
        ([url]) =>
          url === "/search_coords"
      );

    expect(searchCall).toBeDefined();

    expect(searchCall[1]).toEqual({
      params: {
        show_all: true,
        tap_url:
          "https://tap.example.test/tap",
        obscore_table:
          "ctao_sdc.obscore",
      },
    });
  });

  test("show all available data displays a warning when the table is empty", async () => {
    const user = userEvent.setup();
    const setResults = jest.fn();

    publicApiClient.get.mockImplementation(
      (url) => {
        if (url === "/config/frontend") {
          return Promise.resolve({
            data: {
              default_tap_url:
                "https://tap.example.test/tap",
              default_obscore_table:
                "ctao_sdc.obscore",
            },
          });
        }

        if (url === "/search_coords") {
          return Promise.resolve({
            data: {
              columns: [],
              data: [],
              total_rows: 0,
              truncated: false,
              truncation_message: null,
            },
          });
        }

        return Promise.reject(
          new Error(
            `Unexpected GET request: ${url}`
          )
        );
      }
    );

    render(
      <SearchForm
        setResults={setResults}
        isLoggedIn={false}
      />
    );

    await user.click(
      await screen.findByRole("button", {
        name: /show all available data/i,
      })
    );

    expect(
      await screen.findByText(
        /no data are available in the selected obscore table/i
      )
    ).toBeInTheDocument();

    expect(setResults).not.toHaveBeenCalled();

    expect(
      saveQueryHistoryIfLoggedIn
    ).not.toHaveBeenCalled();
  });

  test("show all available data displays the backend error", async () => {
    const user = userEvent.setup();
    const setResults = jest.fn();

    publicApiClient.get.mockImplementation(
      (url) => {
        if (url === "/config/frontend") {
          return Promise.resolve({
            data: {
              default_tap_url:
                "https://tap.example.test/tap",
              default_obscore_table:
                "ctao_sdc.obscore",
            },
          });
        }

        if (url === "/search_coords") {
          return Promise.reject({
            response: {
              data: {
                detail:
                  "The selected ObsCore table does not exist.",
              },
            },
          });
        }

        return Promise.reject(
          new Error(
            `Unexpected GET request: ${url}`
          )
        );
      }
    );

    render(
      <SearchForm
        setResults={setResults}
        isLoggedIn={false}
      />
    );

    await user.click(
      await screen.findByRole("button", {
        name: /show all available data/i,
      })
    );

    expect(
      await screen.findByText(
        /could not load the available data: the selected obscore table does not exist/i
      )
    ).toBeInTheDocument();

    expect(setResults).not.toHaveBeenCalled();

    expect(
      saveQueryHistoryIfLoggedIn
    ).not.toHaveBeenCalled();
  });

  test("show all available data disables form actions while loading", async () => {
    const user = userEvent.setup();
    const setResults = jest.fn();

    const deferredSearch =
      createDeferredPromise();

    publicApiClient.get.mockImplementation(
      (url) => {
        if (url === "/config/frontend") {
          return Promise.resolve({
            data: {
              default_tap_url:
                "https://tap.example.test/tap",
              default_obscore_table:
                "ctao_sdc.obscore",
            },
          });
        }

        if (url === "/search_coords") {
          return deferredSearch.promise;
        }

        return Promise.reject(
          new Error(
            `Unexpected GET request: ${url}`
          )
        );
      }
    );

    render(
      <SearchForm
        setResults={setResults}
        isLoggedIn={false}
      />
    );

    await user.click(
      await screen.findByRole("button", {
        name: /show all available data/i,
      })
    );

    expect(
      screen.getByRole("button", {
        name: /loading all data/i,
      })
    ).toBeDisabled();

    expect(
      screen.getByRole("button", {
        name: /clear form/i,
      })
    ).toBeDisabled();

    expect(
      screen.getByRole("button", {
        name: /^search$/i,
      })
    ).toBeDisabled();

    deferredSearch.resolve({
      data: {
        columns: ["obs_id"],
        data: [["obs-001"]],
        total_rows: 1,
        truncated: false,
        truncation_message: null,
      },
    });

    await waitFor(() => {
      expect(setResults).toHaveBeenCalledTimes(
        1
      );
    });

    expect(
      screen.getByRole("button", {
        name: /show all available data/i,
      })
    ).toBeEnabled();
  });
});
