import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import PropTypes from "prop-types";
import DataTable from "react-data-table-component";

import { apiClient } from "../apiClients";
import { getColumnDisplayInfo } from "./columnConfig";
import { prepareAndDownloadFile } from "./downloadFileWithToken";
import { resolveDownloadUrlForRow } from "./downloadTargetUtils";

const DEFAULT_VISIBLE_COLUMNS = [
  "obs_collection",
  "obs_id",
  "dataproduct_type",
  "dataproduct_subtype",
  "ra_obj",
  "dec_obj",
  "target_name",
  "offset_obj",
  "t_min",
  "t_max",
  "t_exptime",
  "em_min",
  "em_max",
  "facility_name",
  "instrument_name",
  "zen_pnt",
  "alt_pnt",
  "az_pnt",
];

const DEFAULT_ROWS_PER_PAGE = 25;
const ROWS_PER_PAGE_OPTIONS = [10, 25, 50, 100];

function normalizeForSearch(value) {
  if (value == null) return "";
  return String(value).toLowerCase();
}

function rowObsId(row) {
  return String(row?.obs_id ?? "");
}

function ResultsPagination({
  currentPage,
  rowCount,
  rowsPerPage,
  onChangePage,
  onChangeRowsPerPage,
  totalCount,
  filterActive,
}) {
  const pageCount = Math.max(
    1,
    Math.ceil(rowCount / rowsPerPage)
  );

  const startIndex =
    rowCount === 0
      ? 0
      : (currentPage - 1) * rowsPerPage + 1;

  const endIndex =
    rowCount === 0
      ? 0
      : Math.min(
          currentPage * rowsPerPage,
          rowCount
        );

  const hasPreviousPage = currentPage > 1;
  const hasNextPage = currentPage < pageCount;

  return (
    <div className="results-table-pagination">
      <div
        className="results-table-pagination-summary"
        data-testid="pagination-summary"
        aria-live="polite"
      >
        {rowCount === 0 ? (
          "No results to display."
        ) : (
          <>
            <span>
              Showing <strong>{startIndex}</strong>
              {"–"}
              <strong>{endIndex}</strong>
              {" of "}
              <strong>{rowCount}</strong>
            </span>

            {filterActive ? (
              <>
                {" "}
                (filtered from {totalCount} returned
                rows)
              </>
            ) : (
              <> returned rows</>
            )}

            {" — page "}
            <strong>{currentPage}</strong>
            {" of "}
            <strong>{pageCount}</strong>
          </>
        )}
      </div>

      <div className="results-table-pagination-controls">
        <label
          className="results-table-page-size"
          htmlFor="results-rows-per-page"
        >
          <span>Rows per page:</span>

          <select
            id="results-rows-per-page"
            className="form-select form-select-sm"
            value={rowsPerPage}
            onChange={(event) =>
              onChangeRowsPerPage(
                Number(event.target.value)
              )
            }
          >
            {ROWS_PER_PAGE_OPTIONS.map((option) => (
              <option
                key={option}
                value={option}
              >
                {option}
              </option>
            ))}
          </select>
        </label>

        <div
          className="btn-group btn-group-sm"
          role="group"
          aria-label="Result pages"
        >
          <button
            className="btn btn-outline-secondary"
            type="button"
            aria-label="First page"
            title="First page"
            disabled={!hasPreviousPage}
            onClick={() => onChangePage(1)}
          >
            «
          </button>

          <button
            className="btn btn-outline-secondary"
            type="button"
            aria-label="Previous page"
            title="Previous page"
            disabled={!hasPreviousPage}
            onClick={() =>
              onChangePage(currentPage - 1)
            }
          >
            ‹
          </button>

          <button
            className="btn btn-outline-secondary"
            type="button"
            aria-label="Next page"
            title="Next page"
            disabled={!hasNextPage}
            onClick={() =>
              onChangePage(currentPage + 1)
            }
          >
            ›
          </button>

          <button
            className="btn btn-outline-secondary"
            type="button"
            aria-label="Last page"
            title="Last page"
            disabled={!hasNextPage}
            onClick={() =>
              onChangePage(pageCount)
            }
          >
            »
          </button>
        </div>
      </div>
    </div>
  );
}

function ResultsTable({
  results,
  onRowSelected,
  selectedIds = [],
  isLoggedIn,
  onAddedBasketItem,
  allBasketGroups = [],
  activeBasketGroupId,
}) {
  const backendColumnNames = results?.columns ?? [];
  const backendData = results?.data ?? [];

  const [hiddenColumns, setHiddenColumns] = useState([]);
  const [filterText, setFilterText] = useState("");
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(
    DEFAULT_ROWS_PER_PAGE
  );
  const [resetPaginationToggle, setResetPaginationToggle] =
    useState(false);

  const [alertMessage, setAlertMessage] = useState(null);
  const [downloadingRowId, setDownloadingRowId] = useState(null);

  const didInitHiddenRef = useRef(false);

  const toggleableBackendCols = useMemo(
    () =>
      backendColumnNames.filter(
        (columnName) =>
          columnName !== "datalink_url" &&
          columnName !== "obs_publisher_did"
      ),
    [backendColumnNames]
  );

  const tableData = useMemo(() => {
    return backendData.map((rowArray, rowIndex) => {
      const rowObject = {};

      backendColumnNames.forEach((columnName, columnIndex) => {
        rowObject[columnName] = rowArray[columnIndex];
      });

      const obsId = String(rowObject.obs_id ?? "unknown");

      rowObject.__resultIndex = rowIndex;
      rowObject.__tableKey = `${obsId}-${rowIndex}`;

      return rowObject;
    });
  }, [backendColumnNames, backendData]);

  /*
   * Reset column visibility whenever a new result schema arrives
   * Also handles searches against different ObsCore tables
   */
  useEffect(() => {
    didInitHiddenRef.current = false;
  }, [backendColumnNames]);

  useEffect(() => {
    if (didInitHiddenRef.current) return;
    if (!toggleableBackendCols.length) return;

    setHiddenColumns(
      toggleableBackendCols.filter(
        (columnName) =>
          !DEFAULT_VISIBLE_COLUMNS.includes(columnName)
      )
    );

    didInitHiddenRef.current = true;
  }, [toggleableBackendCols]);

  useEffect(() => {
    setPage(1);
    setFilterText("");
    setResetPaginationToggle((current) => !current);
  }, [results]);

  const searchableColumns = useMemo(
    () =>
      toggleableBackendCols.filter(
        (columnName) => !hiddenColumns.includes(columnName)
      ),
    [toggleableBackendCols, hiddenColumns]
  );

  const filteredTableData = useMemo(() => {
    const query = filterText.trim().toLowerCase();

    if (!query) {
      return tableData;
    }

    return tableData.filter((row) =>
      searchableColumns.some((columnName) =>
        normalizeForSearch(row[columnName]).includes(query)
      )
    );
  }, [tableData, filterText, searchableColumns]);

  const totalCount = tableData.length;
  const filteredCount = filteredTableData.length;

  useEffect(() => {
    const lastPage = Math.max(
      1,
      Math.ceil(filteredCount / rowsPerPage)
    );

    if (page > lastPage) {
      setPage(lastPage);
      setResetPaginationToggle(
        (current) => !current
      );
    }
  }, [filteredCount, page, rowsPerPage]);

  const selectedIdSet = useMemo(
    () => new Set(selectedIds.map(String)),
    [selectedIds]
  );

  const selectedRowsByIds = useMemo(
    () =>
      tableData.filter((row) =>
        selectedIdSet.has(rowObsId(row))
      ),
    [tableData, selectedIdSet]
  );

  const activeBasketGroup = useMemo(
    () =>
      allBasketGroups.find(
        (group) =>
          String(group.id) ===
          String(activeBasketGroupId)
      ),
    [allBasketGroups, activeBasketGroupId]
  );

  const isInActiveBasket = useCallback(
    (obsId) =>
      Boolean(
        activeBasketGroup?.saved_datasets?.some(
          (item) =>
            String(item.obs_id) === String(obsId)
        )
      ),
    [activeBasketGroup]
  );

  const selectableRowSelected = useCallback(
    (row) => selectedIdSet.has(rowObsId(row)),
    [selectedIdSet]
  );

  const handleSelectedTableRowsChange = useCallback(
    (state) => {
      const nextSelectedIds = (
        state.selectedRows ?? []
      ).map(rowObsId);

      onRowSelected?.(nextSelectedIds);
    },
    [onRowSelected]
  );

  const downloadRow = useCallback(
    async (rowData) => {
      if (!isLoggedIn) {
        setAlertMessage("Please log in to download this file.");
        return;
      }

      setDownloadingRowId(rowData.__tableKey);
      setAlertMessage(null);

      try {
        const fileUrl = await resolveDownloadUrlForRow(rowData);
        await prepareAndDownloadFile(fileUrl);

        setAlertMessage(
          `Download started for obs_id=${rowData.obs_id}.`
        );
      } catch (error) {
        console.error("Download failed", error);

        const message =
          error.response?.data?.detail?.message ||
          error.response?.data?.detail?.error ||
          error.message ||
          "Download failed.";

        setAlertMessage(message);
      } finally {
        setDownloadingRowId(null);
      }
    },
    [isLoggedIn]
  );

  const addManyToBasket = useCallback(async () => {
    if (!isLoggedIn) {
      setAlertMessage("You must be logged in to add to basket!");
      return;
    }

    if (!activeBasketGroupId) {
      setAlertMessage(
        "Please select an active basket group first!"
      );
      return;
    }

    if (!selectedRowsByIds.length) {
      return;
    }

    const items = selectedRowsByIds.map((row) => ({
      obs_id: row.obs_id,
      dataset_dict: row,
    }));

    try {
      const response = await apiClient.post(
        "/basket/items/bulk",
        {
          basket_group_id: activeBasketGroupId,
          items,
        }
      );

      const addedItems = response.data ?? [];

      setAlertMessage(
        `Added ${addedItems.length} item(s) to basket!`
      );

      addedItems.forEach((item) =>
        onAddedBasketItem?.(item, activeBasketGroupId)
      );
    } catch (error) {
      console.error("Bulk add failed", error);
      setAlertMessage(
        "Error adding items. Some may already be present."
      );
    }
  }, [
    isLoggedIn,
    activeBasketGroupId,
    selectedRowsByIds,
    onAddedBasketItem,
  ]);

  const addToBasket = useCallback(
    async (rowData) => {
      if (!isLoggedIn) {
        setAlertMessage(
          "You must be logged in to add to basket!"
        );
        return;
      }

      if (!activeBasketGroupId) {
        setAlertMessage(
          "Please select an active basket group first!"
        );
        return;
      }

      if (isInActiveBasket(rowData.obs_id)) {
        setAlertMessage(
          `obs_id=${rowData.obs_id} is already in the active basket.`
        );
        return;
      }

      try {
        const payload = {
          obs_id: rowData.obs_id,
          dataset_dict: rowData,
          basket_group_id: activeBasketGroupId,
        };

        const response = await apiClient.post(
          "/basket/items",
          payload
        );

        setAlertMessage(
          `Added obs_id=${rowData.obs_id} to active basket successfully!`
        );

        onAddedBasketItem?.(
          response.data,
          activeBasketGroupId
        );
      } catch (error) {
        if (error.response?.status === 401) {
          setAlertMessage(
            "Authentication error. Please log in again."
          );
        } else if (error.response?.status === 409) {
          setAlertMessage(
            `obs_id=${rowData.obs_id} is already in the active basket.`
          );
        } else {
          console.error("Failed to add to basket:", error);
          setAlertMessage("Error adding item to basket.");
        }
      }
    },
    [
      isLoggedIn,
      activeBasketGroupId,
      isInActiveBasket,
      onAddedBasketItem,
    ]
  );

  const onFilterChange = useCallback((event) => {
    setFilterText(event.target.value);
    setPage(1);
    setResetPaginationToggle((current) => !current);
  }, []);

  const clearFilter = useCallback(() => {
    setFilterText("");
    setPage(1);
    setResetPaginationToggle((current) => !current);
  }, []);

  const subHeaderComponent = useMemo(
    () => (
      <div className="results-table-toolbar">
        <div className="dropdown">
          <button
            className="btn btn-ctao-galaxy btn-sm dropdown-toggle"
            type="button"
            id="columnToggleButton"
            data-bs-toggle="dropdown"
            aria-expanded="false"
          >
            Toggle Columns
          </button>

          <div
            className="dropdown-menu p-2"
            aria-labelledby="columnToggleButton"
          >
            <div className="d-flex justify-content-between mb-2">
              <button
                className="btn btn-link btn-sm"
                onClick={() =>
                  setHiddenColumns(toggleableBackendCols)
                }
                type="button"
              >
                Hide All
              </button>

              <button
                className="btn btn-link btn-sm"
                onClick={() => setHiddenColumns([])}
                type="button"
              >
                Show All
              </button>
            </div>

            <div className="dropdown-divider" />

            {toggleableBackendCols.map((columnName) => {
              const info = getColumnDisplayInfo(columnName);

              return (
                <div
                  key={columnName}
                  className="form-check"
                >
                  <input
                    className="form-check-input"
                    type="checkbox"
                    id={`col-${columnName}`}
                    checked={
                      !hiddenColumns.includes(columnName)
                    }
                    onChange={() =>
                      setHiddenColumns((current) =>
                        current.includes(columnName)
                          ? current.filter(
                              (item) =>
                                item !== columnName
                            )
                          : [...current, columnName]
                      )
                    }
                  />

                  <label
                    className="form-check-label"
                    htmlFor={`col-${columnName}`}
                  >
                    {info.displayName}
                  </label>
                </div>
              );
            })}
          </div>
        </div>

        <button
          className="btn btn-primary btn-sm"
          onClick={addManyToBasket}
          disabled={selectedRowsByIds.length === 0}
          type="button"
        >
          Add {selectedRowsByIds.length} selected
        </button>

        <div className="results-table-filter">
          <input
            className="form-control form-control-sm"
            type="search"
            aria-label="Filter results"
            placeholder="Filter results…"
            value={filterText}
            onChange={onFilterChange}
          />

          {filterText.trim() && (
            <button
              className="btn btn-outline-secondary btn-sm"
              onClick={clearFilter}
              type="button"
            >
              Clear
            </button>
          )}
        </div>
      </div>
    ),
    [
      toggleableBackendCols,
      hiddenColumns,
      addManyToBasket,
      selectedRowsByIds.length,
      filterText,
      onFilterChange,
      clearFilter,
    ]
  );

  const tableColumns = useMemo(() => {
    const columns = [];

    columns.push({
      id: "basket-column",
      name: "Action",
      cell: (row) => {
        const inBasket = isInActiveBasket(row.obs_id);
        const disabled =
          !isLoggedIn ||
          !activeBasketGroupId ||
          inBasket;

        return (
          <button
            className={`btn btn-sm ${
              inBasket ? "btn-secondary" : "btn-primary"
            }`}
            onClick={() => addToBasket(row)}
            disabled={disabled}
            title={
              !isLoggedIn
                ? "Login to add"
                : !activeBasketGroupId
                  ? "Select a basket first"
                  : inBasket
                    ? "Already in active basket"
                    : "Add to active basket"
            }
            type="button"
          >
            {inBasket ? "In Basket" : "Add"}
          </button>
        );
      },
      ignoreRowClick: true,
      allowOverflow: true,
      button: true,
    });

    columns.push({
      id: "download-column",
      name: "Download",
      cell: (row) => {
        const isDownloading =
          downloadingRowId === row.__tableKey;

        return (
          <button
            data-testid="download-button"
            className="btn btn-sm btn-primary"
            onClick={() => downloadRow(row)}
            disabled={isDownloading}
            title={
              isLoggedIn
                ? "Download file"
                : "Login to download"
            }
            type="button"
          >
            {isDownloading ? "Preparing…" : "Download"}
          </button>
        );
      },
      ignoreRowClick: true,
      allowOverflow: true,
      button: true,
    });

    const orderedBackendColumns = [
      ...DEFAULT_VISIBLE_COLUMNS.filter((columnName) =>
        toggleableBackendCols.includes(columnName)
      ),
      ...toggleableBackendCols.filter(
        (columnName) =>
          !DEFAULT_VISIBLE_COLUMNS.includes(columnName)
      ),
    ];

    orderedBackendColumns.forEach((columnName) => {
      const info = getColumnDisplayInfo(columnName);

      columns.push({
        id: `column-${columnName}`,
        name: (
          <div
            title={info.description || info.displayName}
          >
            {info.displayName}

            {info.unit && (
              <span className="text-muted small ms-1">
                [{info.unit}]
              </span>
            )}
          </div>
        ),
        selector: (row) => row[columnName],
        cell: (row) => (
          <div
            className="results-table-cell"
            title={String(row[columnName] ?? "")}
          >
            {String(row[columnName] ?? "")}
          </div>
        ),
        sortable: true,
        sortFunction: (firstRow, secondRow) => {
          const firstNumber = Number(
            firstRow[columnName]
          );
          const secondNumber = Number(
            secondRow[columnName]
          );

          if (
            Number.isFinite(firstNumber) &&
            Number.isFinite(secondNumber)
          ) {
            return firstNumber - secondNumber;
          }

          return String(
            firstRow[columnName] ?? ""
          ).localeCompare(
            String(secondRow[columnName] ?? "")
          );
        },
        omit: hiddenColumns.includes(columnName),
        width: info.unit
          ? "180px"
          : info.displayName.length > 15
            ? "200px"
            : "150px",
      });
    });

    return columns;
  }, [
    toggleableBackendCols,
    hiddenColumns,
    isLoggedIn,
    activeBasketGroupId,
    isInActiveBasket,
    addToBasket,
    downloadingRowId,
    downloadRow,
  ]);

  const changePage = useCallback((newPage) => {
    setPage(newPage);
    setResetPaginationToggle(
      (current) => !current
    );
  }, []);

  const changeRowsPerPage = useCallback(
    (newRowsPerPage) => {
      setRowsPerPage(newRowsPerPage);
      setPage(1);
      setResetPaginationToggle(
        (current) => !current
      );
    },
    []
  );

  const conditionalRowStyles = useMemo(
    () => [
      {
        when: selectableRowSelected,
        style: {
          backgroundColor: "rgba(100, 149, 237, 0.15)",
        },
      },
    ],
    [selectableRowSelected]
  );

  const customStyles = useMemo(
    () => ({
      tableWrapper: {
        style: {
          height: "100%",
          minHeight: 0,
        },
      },
      responsiveWrapper: {
        style: {
          height: "100%",
          minHeight: 0,
        },
      },
      headRow: {
        style: {
          flex: "0 0 auto",
          backgroundColor:
            "var(--bs-body-bg, #fff)",
          zIndex: 3,
        },
      },
      pagination: {
        style: {
          padding: 0,
          minHeight: "auto",
          borderTop: "none",
        },
      },
    }),
    []
  );

  return (
    <div className="results-table-shell">
      {results?.truncated && (
        <div
          className="alert alert-warning m-2 mb-0"
          role="alert"
        >
          {results.truncation_message ||
            "The TAP service truncated this result set. Additional matching rows may exist."}
        </div>
      )}

      {alertMessage && (
        <div
          className="alert alert-info alert-dismissible fade show m-2 mb-0"
          role="alert"
        >
          {alertMessage}

          <button
            type="button"
            className="btn-close"
            aria-label="Close"
            onClick={() => setAlertMessage(null)}
          />
        </div>
      )}

      <div className="results-table-toolbar-container">
        {subHeaderComponent}
      </div>

      <div className="results-table-content">
        <DataTable
          key={`results-table-${rowsPerPage}`}
          columns={tableColumns}
          data={filteredTableData}
          keyField="__tableKey"
          selectableRows
          selectableRowsHighlight
          selectableRowSelected={selectableRowSelected}
          conditionalRowStyles={conditionalRowStyles}
          onSelectedRowsChange={
            handleSelectedTableRowsChange
          }
          pointerOnHover
          highlightOnHover
          customStyles={customStyles}
          fixedHeader
          fixedHeaderScrollHeight="100%"
          pagination
          paginationDefaultPage={page}
          paginationResetDefaultPage={
            resetPaginationToggle
          }
          paginationPerPage={rowsPerPage}
          paginationComponent={() => null}
          onChangePage={(newPage) => {
            setPage(newPage);
          }}
        />
      </div>
      <ResultsPagination
        currentPage={page}
        rowCount={filteredCount}
        rowsPerPage={rowsPerPage}
        onChangePage={changePage}
        onChangeRowsPerPage={changeRowsPerPage}
        totalCount={totalCount}
        filterActive={Boolean(filterText.trim())}
      />
    </div>
  );
}

ResultsTable.propTypes = {
  results: PropTypes.shape({
    columns: PropTypes.arrayOf(PropTypes.string),
    data: PropTypes.arrayOf(
      PropTypes.arrayOf(PropTypes.any)
    ),
    truncated: PropTypes.bool,
    truncation_message: PropTypes.string,
  }),
  onRowSelected: PropTypes.func,
  selectedIds: PropTypes.arrayOf(
    PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.number,
    ])
  ),
  isLoggedIn: PropTypes.bool,
  onAddedBasketItem: PropTypes.func,
  allBasketGroups: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.oneOfType([
        PropTypes.string,
        PropTypes.number,
      ]),
      saved_datasets: PropTypes.arrayOf(
        PropTypes.shape({
          obs_id: PropTypes.oneOfType([
            PropTypes.string,
            PropTypes.number,
          ]),
        })
      ),
    })
  ),
  activeBasketGroupId: PropTypes.oneOfType([
    PropTypes.string,
    PropTypes.number,
  ]),
};

ResultsPagination.propTypes = {
  currentPage: PropTypes.number.isRequired,
  rowCount: PropTypes.number.isRequired,
  rowsPerPage: PropTypes.number.isRequired,
  onChangePage: PropTypes.func.isRequired,
  onChangeRowsPerPage: PropTypes.func.isRequired,
  totalCount: PropTypes.number.isRequired,
  filterActive: PropTypes.bool.isRequired,
};

export default ResultsTable;
