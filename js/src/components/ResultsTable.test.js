import React from "react";
import {
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ResultsTable from "./ResultsTable";

jest.mock("../apiClients", () => ({
  apiClient: {
    post: jest.fn(),
  },
}));

jest.mock("./downloadFileWithToken", () => ({
  prepareAndDownloadFile: jest.fn(),
}));

jest.mock("./downloadTargetUtils", () => ({
  resolveDownloadUrlForRow: jest.fn(),
}));

const NOOP = () => {};

function sameIds(first, second) {
  if (first.length !== second.length) {
    return false;
  }

  const firstSet = new Set(
    first.map(String)
  );

  return second.every(
    (id) => firstSet.has(String(id))
  );
}

function makeResults(count) {
  return {
    columns: [
      "obs_id",
      "target_name",
    ],
    data: Array.from(
      { length: count },
      (_, index) => {
        const number = index + 1;

        return [
          `obs-${String(number).padStart(
            3,
            "0"
          )}`,
          `Target ${number}`,
        ];
      }
    ),
    truncated: false,
    truncation_message: null,
  };
}

function ControlledResultsTable({
  results,
  initialSelectedIds = [],
  onSelectionChange = NOOP,
}) {
  const [selectedIds, setSelectedIds] =
    React.useState(initialSelectedIds);

  const selectedIdsRef =
    React.useRef(initialSelectedIds);

  const handleRowSelected =
    React.useCallback(
      (nextIds) => {
        if (
          sameIds(
            selectedIdsRef.current,
            nextIds
          )
        ) {
          return;
        }

        selectedIdsRef.current = nextIds;
        setSelectedIds(nextIds);
        onSelectionChange(nextIds);
      },
      [onSelectionChange]
    );

  return (
    <>
      <output data-testid="selected-ids">
        {selectedIds.join(",")}
      </output>

      <ResultsTable
        results={results}
        selectedIds={selectedIds}
        onRowSelected={handleRowSelected}
        isLoggedIn={false}
        allBasketGroups={[]}
        activeBasketGroupId={null}
      />
    </>
  );
}

function getVisibleDataRows() {
  return screen
    .getAllByRole("row")
    .filter((row) =>
      within(row).queryByText(/obs-\d{3}/i)
    );
}

function getRowForObservation(obsId) {
  const table = screen.getByRole("table");
  const cell = within(table).getByText(obsId);
  const row = cell.closest('[role="row"]');

  if (!row) {
    throw new Error(
      `Could not find table row for ${obsId}`
    );
  }

  return row;
}

function getRowCheckbox(obsId) {
  const row = getRowForObservation(obsId);

  if (!row) {
    throw new Error(
      `Could not find table row for ${obsId}`
    );
  }

  return within(row).getByRole("checkbox");
}

describe("ResultsTable pagination and selection", () => {
  test("shows 25 rows on the first page by default", () => {
    render(
      <ControlledResultsTable
        results={makeResults(60)}
      />
    );

    expect(getVisibleDataRows()).toHaveLength(25);

    expect(
      screen.getByText("obs-001")
    ).toBeInTheDocument();

    expect(
      screen.getByText("obs-025")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("obs-026")
    ).not.toBeInTheDocument();
  });

  test("moves to the next result page", async () => {
    const user = userEvent.setup();

    render(
      <ControlledResultsTable
        results={makeResults(30)}
      />
    );

    await user.click(
      screen.getByRole("button", {
        name: /next page/i,
      })
    );

    expect(
      await screen.findByText("obs-026")
    ).toBeInTheDocument();

    expect(
      screen.getByText("obs-030")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("obs-001")
    ).not.toBeInTheDocument();

    expect(
      screen.getByText(/showing/i)
    ).toHaveTextContent(
      /26\s*[–-]\s*30 of 30/i
    );
  });

  test("preserves selections made on previous pages", async () => {
    const user = userEvent.setup();
    const onSelectionChange = jest.fn();

    render(
      <ControlledResultsTable
        results={makeResults(30)}
        onSelectionChange={onSelectionChange}
      />
    );

    await user.click(
      getRowCheckbox("obs-001")
    );

    expect(
      screen.getByTestId("selected-ids")
    ).toHaveTextContent("obs-001");

    await user.click(
      screen.getByRole("button", {
        name: /next page/i,
      })
    );

    await user.click(
      getRowCheckbox("obs-026")
    );

    await waitFor(() => {
      const selectedIds = screen
      .getByTestId("selected-ids")
      .textContent
      .split(",")
      .filter(Boolean)
      .sort();

    expect(selectedIds).toEqual([
      "obs-001",
      "obs-026",
    ]);
  });

    const lastSelection =
      onSelectionChange.mock.calls.at(-1)[0];

    expect([...lastSelection].sort()).toEqual([
      "obs-001",
      "obs-026",
    ]);

    expect(
      screen.getByRole("button", {
        name: /add 2 selected/i,
      })
    ).toBeEnabled();
  });

  test("deselecting a current-page row preserves selections on other pages", async () => {
    const user = userEvent.setup();

    render(
      <ControlledResultsTable
        results={makeResults(30)}
        initialSelectedIds={[
          "obs-001",
          "obs-026",
          "obs-027",
        ]}
      />
    );

    await user.click(
      screen.getByRole("button", {
        name: /next page/i,
      })
    );

    expect(
      getRowCheckbox("obs-026")
    ).toBeChecked();

    expect(
      getRowCheckbox("obs-027")
    ).toBeChecked();

    await user.click(
      getRowCheckbox("obs-026")
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("selected-ids")
      ).toHaveTextContent(
        "obs-001,obs-027"
      );
    });

    expect(
      screen.getByTestId("selected-ids")
    ).not.toHaveTextContent("obs-026");

    expect(
      getRowCheckbox("obs-027")
    ).toBeChecked();
  });

  test("changes the number of rows displayed per page", async () => {
    const user = userEvent.setup();

    render(
      <ControlledResultsTable
        results={makeResults(60)}
      />
    );

    expect(getVisibleDataRows()).toHaveLength(25);

    await user.selectOptions(
      screen.getByLabelText(/rows per page/i),
      "50"
    );

    await waitFor(() => {
      expect(getVisibleDataRows()).toHaveLength(50);
    });

    expect(
      screen.getByText("obs-050")
    ).toBeInTheDocument();

    expect(
      screen.queryByText("obs-051")
    ).not.toBeInTheDocument();
  });

  test("header checkbox deselects all rows across pages", async () => {
    const user = userEvent.setup();

    render(
      <ControlledResultsTable
        results={makeResults(30)}
      />
    );

    await user.click(
      screen.getByRole("checkbox", {
        name: /select-all-rows/i,
      })
    );

    await waitFor(() => {
      expect(
        screen
          .getByTestId("selected-ids")
          .textContent.split(",")
          .filter(Boolean)
      ).toHaveLength(30);
    });

    expect(
      screen.getByRole("button", {
        name: /add 30 selected/i,
      })
    ).toBeEnabled();

    await user.click(
      screen.getByRole("checkbox", {
        name: /select-all-rows/i,
      })
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("selected-ids")
      ).toBeEmptyDOMElement();
    });

    expect(
      screen.getByRole("button", {
        name: /add 0 selected/i,
      })
    ).toBeDisabled();
  });

  test(
    "changes the number of displayed rows per page",
    async () => {
      const user = userEvent.setup();

      render(
        <ControlledResultsTable
          results={makeResults(60)}
        />
      );

      expect(getVisibleDataRows()).toHaveLength(25);

      expect(
        screen.getByTestId("pagination-summary")
      ).toHaveTextContent(
        /showing\s+1\s*[–-]\s*25\s+of\s+60/i
      );

      expect(
        screen.getByTestId("pagination-summary")
      ).toHaveTextContent(
        /page\s+1\s+of\s+3/i
      );

      await user.selectOptions(
        screen.getByLabelText(/rows per page/i),
        "10"
      );

      await waitFor(() => {
        expect(getVisibleDataRows()).toHaveLength(10);
      });

      expect(
        screen.getByTestId("pagination-summary")
      ).toHaveTextContent(
        /showing\s+1\s*[–-]\s*10\s+of\s+60/i
      );

      expect(
        screen.getByTestId("pagination-summary")
      ).toHaveTextContent(
        /page\s+1\s+of\s+6/i
      );

      await user.selectOptions(
        screen.getByLabelText(/rows per page/i),
        "50"
      );

      await waitFor(() => {
        expect(getVisibleDataRows()).toHaveLength(50);
      });

      expect(
        screen.getByTestId("pagination-summary")
      ).toHaveTextContent(
        /showing\s+1\s*[–-]\s*50\s+of\s+60/i
      );

      expect(
        screen.getByTestId("pagination-summary")
      ).toHaveTextContent(
        /page\s+1\s+of\s+2/i
      );

      expect(
        screen.getByLabelText(/rows per page/i)
      ).toHaveValue("50");
    }
  );

  test(
    "deselects a row correctly after sorting changes the visible page",
    async () => {
      const user = userEvent.setup();
      const onSelectionChange = jest.fn();

      render(
        <ControlledResultsTable
          results={makeResults(30)}
          onSelectionChange={onSelectionChange}
        />
      );

      await user.selectOptions(
        screen.getByLabelText(/rows per page/i),
        "10"
      );

      await waitFor(() => {
        expect(getVisibleDataRows()).toHaveLength(10);
      });

      // before sorting, page 1 contains obs-001 ... obs-010
      expect(
        screen.getByText("obs-001")
      ).toBeInTheDocument();

      expect(
        screen.getByText("obs-010")
      ).toBeInTheDocument();

      expect(
        screen.queryByText("obs-030")
      ).not.toBeInTheDocument();

      const obsIdHeader = screen.getByRole(
        "columnheader",
        {
          name: /obs\. id/i,
        }
      );

      // first click sorts ascending, second click descending
      await user.click(obsIdHeader);
      await user.click(obsIdHeader);

      // Descending page 1 should now contain rows that were
      // not on the original unsorted first page
      await waitFor(() => {
        expect(
          screen.getByText("obs-030")
        ).toBeInTheDocument();
      });

      expect(
        screen.queryByText("obs-001")
      ).not.toBeInTheDocument();

      const checkbox =
        getRowCheckbox("obs-030");

      // select the newly visible row
      await user.click(checkbox);

      await waitFor(() => {
        expect(
          screen.getByTestId("selected-ids")
        ).toHaveTextContent("obs-030");
      });

      expect(
        getRowCheckbox("obs-030")
      ).toBeChecked();

      expect(
        screen.getByRole("button", {
          name: /add 1 selected/i,
        })
      ).toBeEnabled();

      await user.click(
        getRowCheckbox("obs-030")
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("selected-ids")
        ).toBeEmptyDOMElement();
      });

      expect(
        getRowCheckbox("obs-030")
      ).not.toBeChecked();

      expect(
        screen.getByRole("button", {
          name: /add 0 selected/i,
        })
      ).toBeDisabled();

      expect(
        onSelectionChange
      ).toHaveBeenLastCalledWith([]);
    }
  );

});
