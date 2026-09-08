import {
  act,
  render,
  waitFor,
} from "@testing-library/react";

import AladinLiteViewer from "./AladinLiteViewer";

let handlers;
let addedSources;
let mockCatalog;
let mockAladin;

function makeCanvasSafeSource(ra, dec, data) {
  return {
    ra,
    dec,
    data,
    x: 0,
    y: 0,
  };
}

beforeEach(() => {
  handlers = {};
  addedSources = [];

  mockCatalog = {
    addSources: jest.fn((sources) => {
      addedSources = sources;
    }),
    removeAll: jest.fn(),
    deselectAll: jest.fn(),
    setSelectionColor: jest.fn(),
    setSelectionLineWidth: jest.fn(),
    setShape: jest.fn(),
  };

  mockAladin = {
    addCatalog: jest.fn(),
    on: jest.fn((eventName, callback) => {
      handlers[eventName] = callback;
    }),
    off: jest.fn(),
    gotoRaDec: jest.fn(),
    setFov: jest.fn(),
  };

  window.A = {
    init: Promise.resolve(),
    aladin: jest.fn(() => mockAladin),
    catalog: jest.fn(() => mockCatalog),
    source: jest.fn(makeCanvasSafeSource),
  };
});

afterEach(() => {
  delete window.A;
  jest.clearAllMocks();
});

describe("AladinLiteViewer", () => {
  test("groups observations at the same sky position", async () => {
    render(
      <AladinLiteViewer
        overlays={[
          {
            id: "obs-001",
            ra: 83.63,
            dec: 22.01,
            s_fov: 1,
          },
          {
            id: "obs-002",
            ra: 83.63,
            dec: 22.01,
            s_fov: 2,
          },
        ]}
        selectedIds={[]}
        onSelectIds={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(mockCatalog.addSources)
        .toHaveBeenCalled();
    });

    expect(addedSources).toHaveLength(1);

    expect(addedSources[0].data).toEqual(
      expect.objectContaining({
        ids: ["obs-001", "obs-002"],
        count: 2,
        ra: 83.63,
        dec: 22.01,
        s_fov: 2,
      })
    );
  });

  test("keeps different sky positions as separate markers", async () => {
    render(
      <AladinLiteViewer
        overlays={[
          {
            id: "obs-001",
            ra: 83.63,
            dec: 22.01,
          },
          {
            id: "obs-002",
            ra: 120.25,
            dec: -35.4,
          },
        ]}
        selectedIds={[]}
        onSelectIds={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(mockCatalog.addSources)
        .toHaveBeenCalled();
    });

    expect(addedSources).toHaveLength(2);
  });

  test("selects every ID in a grouped sky marker", async () => {
    const onSelectIds = jest.fn();

    render(
      <AladinLiteViewer
        overlays={[
          {
            id: "obs-001",
            ra: 83.63,
            dec: 22.01,
          },
          {
            id: "obs-002",
            ra: 83.63,
            dec: 22.01,
          },
        ]}
        selectedIds={[]}
        onSelectIds={onSelectIds}
      />
    );

    await waitFor(() => {
      expect(
        handlers.objectClicked
      ).toBeDefined();
    });

    act(() => {
      handlers.objectClicked(
        addedSources[0]
      );
    });

    expect(onSelectIds).toHaveBeenCalledWith([
      "obs-001",
      "obs-002",
    ]);
  });

  test("preserves existing selections when selecting a grouped marker", async () => {
    const onSelectIds = jest.fn();

    render(
      <AladinLiteViewer
        overlays={[
          {
            id: "obs-001",
            ra: 83.63,
            dec: 22.01,
          },
          {
            id: "obs-002",
            ra: 83.63,
            dec: 22.01,
          },
        ]}
        selectedIds={["obs-999"]}
        onSelectIds={onSelectIds}
      />
    );

    await waitFor(() => {
      expect(
        handlers.objectClicked
      ).toBeDefined();
    });

    act(() => {
      handlers.objectClicked(
        addedSources[0]
      );
    });

    expect(onSelectIds).toHaveBeenCalledWith([
      "obs-999",
      "obs-001",
      "obs-002",
    ]);
  });

  test("clicking an already selected group deselects that group only", async () => {
    const onSelectIds = jest.fn();

    render(
      <AladinLiteViewer
        overlays={[
          {
            id: "obs-001",
            ra: 83.63,
            dec: 22.01,
          },
          {
            id: "obs-002",
            ra: 83.63,
            dec: 22.01,
          },
        ]}
        selectedIds={[
          "obs-999",
          "obs-001",
          "obs-002",
        ]}
        onSelectIds={onSelectIds}
      />
    );

    await waitFor(() => {
      expect(
        handlers.objectClicked
      ).toBeDefined();
    });

    act(() => {
      handlers.objectClicked(
        addedSources[0]
      );
    });

    expect(onSelectIds).toHaveBeenCalledWith([
      "obs-999",
    ]);
  });

  test("ignores overlays with invalid coordinates", async () => {
    render(
      <AladinLiteViewer
        overlays={[
          {
            id: "obs-invalid",
            ra: "not-a-number",
            dec: 22.01,
          },
          {
            id: "obs-valid",
            ra: 83.63,
            dec: 22.01,
          },
        ]}
        selectedIds={[]}
        onSelectIds={jest.fn()}
      />
    );

    await waitFor(() => {
      expect(mockCatalog.addSources)
        .toHaveBeenCalled();
    });

    expect(addedSources).toHaveLength(1);

    expect(addedSources[0].data.ids).toEqual([
      "obs-valid",
    ]);
  });

  test("map click clears all selected IDs", async () => {
    const onSelectIds = jest.fn();

    render(
      <AladinLiteViewer
        overlays={[
          {
            id: "obs-001",
            ra: 83.63,
            dec: 22.01,
          },
        ]}
        selectedIds={["obs-001"]}
        onSelectIds={onSelectIds}
      />
    );

    await waitFor(() => {
      expect(
        handlers.mapClicked
      ).toBeDefined();
    });

    act(() => {
      handlers.mapClicked();
    });

    expect(onSelectIds).toHaveBeenCalledWith([]);
    expect(
      mockCatalog.deselectAll
    ).toHaveBeenCalled();
  });
});
