import { act, render } from "@testing-library/react";

import EmRangeChart from "./EmRangeChart";

let latestPlotProps;

jest.mock("react-plotly.js", () => {
  return function MockPlot(props) {
    latestPlotProps = props;
    return <div data-testid="energy-range-plot" />;
  };
});

function makeResults(count = 81) {
  return {
    columns: ["obs_id", "em_min", "em_max"],
    data: Array.from(
      { length: count },
      (_, index) => [
        `obs-${String(index + 1).padStart(3, "0")}`,
        1e-12,
        2e-12,
      ]
    ),
  };
}

describe("EmRangeChart", () => {
  beforeEach(() => {
    latestPlotProps = undefined;
  });

  test("groups similar energy ranges and selects all IDs when clicked", () => {
    const onSelectIds = jest.fn();

    render(
      <EmRangeChart
        results={makeResults()}
        selectedIds={[]}
        onSelectIds={onSelectIds}
      />
    );

    expect(latestPlotProps).toBeDefined();

    const scatterTrace = latestPlotProps.data[0];

    expect(scatterTrace.customdata).toHaveLength(1);

    expect(
      scatterTrace.customdata[0].ids
    ).toHaveLength(81);

    act(() => {
      latestPlotProps.onClick({
        points: [
          {
            customdata:
              scatterTrace.customdata[0],
          },
        ],
      });
    });

    expect(onSelectIds).toHaveBeenCalledTimes(1);

    expect(onSelectIds).toHaveBeenCalledWith(
      scatterTrace.customdata[0].ids
    );
  });

  test("keeps grouped counts in hover text", () => {
    render(
      <EmRangeChart
        results={makeResults()}
        selectedIds={[]}
        onSelectIds={jest.fn()}
      />
    );

    const scatterTrace = latestPlotProps.data[0];

    expect(scatterTrace.hovertext).toEqual([
      expect.stringContaining("81 observations"),
    ]);
  });

  test("clicking an already selected group deselects all its IDs", () => {
    const results = makeResults();
    const selectedIds = results.data.map(
      (row) => row[0]
    );
    const onSelectIds = jest.fn();

    render(
      <EmRangeChart
        results={results}
        selectedIds={selectedIds}
        onSelectIds={onSelectIds}
      />
    );

    const scatterTrace = latestPlotProps.data[0];

    act(() => {
      latestPlotProps.onClick({
        points: [
          {
            customdata:
              scatterTrace.customdata[0],
          },
        ],
      });
    });

    expect(onSelectIds).toHaveBeenCalledWith([]);
  });

  test("double-click clears the current selection", () => {
    const onSelectIds = jest.fn();

    render(
      <EmRangeChart
        results={makeResults(1)}
        selectedIds={["obs-001"]}
        onSelectIds={onSelectIds}
      />
    );

    act(() => {
      latestPlotProps.onDoubleClick();
    });

    expect(onSelectIds).toHaveBeenCalledWith([]);
  });
});
