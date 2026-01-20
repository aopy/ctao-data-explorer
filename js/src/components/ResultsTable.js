import React, { useMemo, useState } from 'react';
import DataTable from 'react-data-table-component';
import axios from 'axios';
import DataLinkDropdown from './DataLinkDropdown';
import { API_PREFIX } from '../index';
import { getColumnDisplayInfo } from './columnConfig';

const DEFAULT_VISIBLE_COLUMNS = [
  'obs_collection',
  'obs_id',
  'dataproduct_type',
  'dataproduct_subtype',
  'ra_obj',
  'dec_obj',
  'target_name',
  'offset_obj',
  't_min',
  't_max',
  't_exptime',
  //'em_energy_min_tev',
  //'em_energy_max_tev',
  //'em_min_tev',
  //'em_max_tev',
  'em_min',  // temporary
  'em_max',  // temporary
  'facility_name',
  'instrument_name',
  'zen_pnt',
  'alt_pnt',
  'az_pnt',
  // 'event_class',
  // 'event_type',
  // 'processing_date',
  // 'convergence',
  // 'obs_mode'
];

export default function ResultsTable({
  results,
  onRowSelected,
  selectedIds = [],
  isLoggedIn,
  onAddedBasketItem,
  allBasketGroups = [],
  activeBasketGroupId,
}) {
  const { columns: backendColumnNames, data } = results || {};

  // Which columns are toggleable
  const toggleableBackendCols = useMemo(() => {
    if (!backendColumnNames) return [];
    return backendColumnNames.filter(c =>
      c !== 'datalink_url' && c !== 'obs_publisher_did'
    );
  }, [backendColumnNames]);

  const tableData = useMemo(() => {
    if (!backendColumnNames || !data) return [];
    return data.map((rowArray, rowIndex) => {
      const rowObj = { id: `datatable-row-${rowIndex}` };
      backendColumnNames.forEach((colName, colIndex) => {
        rowObj[colName] = rowArray[colIndex];
      });
      return rowObj;
    });
  }, [backendColumnNames, data]);

  const selectedRowsByIds = useMemo(() => {
    return tableData.filter(r => selectedIds.includes(r.obs_id?.toString()));
  }, [tableData, selectedIds]);

  const rowCount = tableData.length;
  const USE_PAGINATION_THRESHOLD = 500;
  const usePagination = rowCount > USE_PAGINATION_THRESHOLD;

  const [hiddenColumns, setHiddenColumns] = useState(() =>
    toggleableBackendCols.filter(c => !DEFAULT_VISIBLE_COLUMNS.includes(c))
  );
  const [alertMessage, setAlertMessage] = useState(null);
  const [openDropdownId, setOpenDropdownId] = useState(null);

  // Row selection change
  const handleSelectedTableRowsChange = (state) => {
    const ids = (state.selectedRows || []).map(r => r.obs_id.toString());
    const same =
      ids.length === selectedIds.length &&
      ids.every(id => selectedIds.includes(id));
    if (!same) {
      onRowSelected?.(state);
    }
  };

  const addManyToBasket = async () => {
    if (!isLoggedIn) {
      setAlertMessage('You must be logged in to add to basket!');
      return;
    }
    if (!activeBasketGroupId) {
      setAlertMessage('Please select an active basket group first!');
      return;
    }
    if (!selectedRowsByIds.length) return;

    const items = selectedRowsByIds.map(row => ({
      obs_id: row.obs_id,
      dataset_dict: row,
    }));

    try {
      const res = await axios.post(`${API_PREFIX}/basket/items/bulk`, {
        basket_group_id: activeBasketGroupId,
        items,
      });
      const added = res.data || [];
      setAlertMessage(`Added ${added.length} item(s) to basket!`);
      added.forEach(item => onAddedBasketItem?.(item, activeBasketGroupId));
    } catch (err) {
      console.error('Bulk add failed', err);
      setAlertMessage('Error adding items. Some may already be present.');
    }
  };

  // Single-row add to basket
  const activeBasketGroup = useMemo(
    () => allBasketGroups.find(g => g.id === activeBasketGroupId),
    [allBasketGroups, activeBasketGroupId]
  );
  const isInActiveBasket = obsId =>
    !!activeBasketGroup?.saved_datasets?.some(item => item.obs_id === obsId);

  const addToBasket = async rowData => {
    if (!isLoggedIn) {
      setAlertMessage('You must be logged in to add to basket!');
      return;
    }
    if (!activeBasketGroupId) {
      setAlertMessage('Please select an active basket group first!');
      return;
    }
    if (isInActiveBasket(rowData.obs_id)) {
      setAlertMessage(`obs_id=${rowData.obs_id} is already in the active basket.`);
      return;
    }

    try {
      const payload = {
        obs_id: rowData.obs_id,
        dataset_dict: rowData,
        basket_group_id: activeBasketGroupId,
      };
      const response = await axios.post(`${API_PREFIX}/basket/items`, payload);
      setAlertMessage(`Added obs_id=${rowData.obs_id} to active basket successfully!`);
      onAddedBasketItem?.(response.data, activeBasketGroupId);
    } catch (error) {
      if (error.response?.status === 401) {
        setAlertMessage('Authentication error. Please log in again.');
      } else if (error.response?.status === 409) {
        setAlertMessage(`obs_id=${rowData.obs_id} is already in the active basket.`);
      } else {
        console.error('Failed to add to basket:', error);
        setAlertMessage('Error adding item to basket.');
      }
    }
  };

  const handleCloseAlert = () => setAlertMessage(null);

  const selectableRowSelected = row =>
    selectedIds.includes(row.obs_id?.toString());
  const conditionalRowStyles = [
    {
      when: selectableRowSelected,
      style: { backgroundColor: 'rgba(100, 149, 237, 0.15)' },
    },
  ];

  const SubHeader = () => (
    <div className="p-2 border-bottom bg-light d-flex align-items-center">
      <div className="dropdown me-2">
        <button
          className="btn btn-ctao-galaxy btn-sm dropdown-toggle"
          type="button"
          id="columnToggleButton"
          data-bs-toggle="dropdown"
          aria-expanded="false"
        >
          Toggle Columns
        </button>
        <div className="dropdown-menu p-2" aria-labelledby="columnToggleButton">
          <div className="d-flex justify-content-between mb-2">
            <button
              className="btn btn-link btn-sm"
              onClick={() => setHiddenColumns(toggleableBackendCols)}
            >
              Hide All
            </button>
            <button
              className="btn btn-link btn-sm"
              onClick={() => setHiddenColumns([])}
            >
              Show All
            </button>
          </div>
          <div className="dropdown-divider"></div>
          {toggleableBackendCols.map(col => {
            const info = getColumnDisplayInfo(col);
            return (
              <div key={col} className="form-check">
                <input
                  className="form-check-input"
                  type="checkbox"
                  id={`col-${col}`}
                  checked={!hiddenColumns.includes(col)}
                  onChange={() =>
                    setHiddenColumns(curr =>
                      curr.includes(col)
                        ? curr.filter(c => c !== col)
                        : [...curr, col]
                    )
                  }
                />
                <label className="form-check-label" htmlFor={`col-${col}`}>
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
      >
        Add {selectedRowsByIds.length} selected
      </button>
    </div>
  );

  const tableColumns = useMemo(() => {
    if (!backendColumnNames) return [];

    const cols = [];

    // Action column
    cols.push({
      id: 'basket-column',
      name: 'Action',
      cell: row => {
        const inBasket = isInActiveBasket(row.obs_id);
        const disabled = !isLoggedIn || !activeBasketGroupId || inBasket;
        return (
          <button
            className={`btn btn-sm ${inBasket ? 'btn-secondary' : 'btn-primary'}`}
            onClick={() => addToBasket(row)}
            disabled={disabled}
            title={
              !isLoggedIn
                ? 'Login to add'
                : !activeBasketGroupId
                ? 'Select a basket first'
                : inBasket
                ? 'Already in active basket'
                : 'Add to active basket'
            }
          >
            {inBasket ? 'In Basket' : 'Add'}
          </button>
        );
      },
      ignoreRowClick: true,
      allowOverflow: true,
      button: true,
    });

    // DataLink column
    cols.push({
      id: 'datalink-column',
      name: 'DataLink',
      cell: row =>
        row.datalink_url ? (
          <DataLinkDropdown
            datalink_url={row.datalink_url}
            isOpen={row.id === openDropdownId}
            onToggle={() =>
              setOpenDropdownId(row.id === openDropdownId ? null : row.id)
            }
          />
        ) : null,
      ignoreRowClick: true,
      allowOverflow: true,
      button: true,
    });

    const ordered = [
      ...DEFAULT_VISIBLE_COLUMNS.filter(c => toggleableBackendCols.includes(c)),
      ...toggleableBackendCols.filter(c => !DEFAULT_VISIBLE_COLUMNS.includes(c)),
    ];

    ordered.forEach(col => {
      const info = getColumnDisplayInfo(col);
      cols.push({
        id: `column-${col}`,
        name: (
          <div title={info.description || info.displayName}>
            {info.displayName}
            {info.unit && <span className="text-muted small ms-1">[{info.unit}]</span>}
          </div>
        ),
        selector: row => row[col],
        cell: row => (
          <div
            style={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={String(row[col] ?? '')}
          >
            {String(row[col] ?? '')}
          </div>
        ),
        sortable: true,
        sortFunction: (a, b) => {
          const aVal = parseFloat(a[col]);
          const bVal = parseFloat(b[col]);
          if (!isNaN(aVal) && !isNaN(bVal)) return aVal - bVal;
          return String(a[col]).localeCompare(String(b[col]));
        },
        omit: hiddenColumns.includes(col),
        width: info.unit ? '180px' : info.displayName.length > 15 ? '200px' : '150px',
      });
    });

    return cols;
  }, [
    backendColumnNames,
    hiddenColumns,
    isLoggedIn,
    activeBasketGroupId,
    allBasketGroups,
    openDropdownId,
    toggleableBackendCols,
  ]);

  const customStyles = {
    subHeader: { style: { padding: 0, margin: 0 } },
  };

  return (
    <div style={{ overflowX: 'auto' }}>
      {alertMessage && (
        <div className="alert alert-info alert-dismissible fade show" role="alert">
          {alertMessage}
          <button type="button" className="btn-close" onClick={handleCloseAlert} />
        </div>
      )}
      <DataTable
        columns={tableColumns}
        data={tableData}
        keyField="id"
        selectableRows
        selectableRowsHighlight
        selectableRowSelected={selectableRowSelected}
        conditionalRowStyles={conditionalRowStyles}
        onSelectedRowsChange={handleSelectedTableRowsChange}
        pointerOnHover
        highlightOnHover
        subHeader
        subHeaderComponent={<SubHeader />}
        subHeaderAlign="left"
        customStyles={customStyles}
        /* Scroll mode (default): shows more rows when pane is larger */
        fixedHeader={!usePagination}
        fixedHeaderScrollHeight={!usePagination ? "100%" : undefined}
        /* Pagination safeguard (large lists) */
        pagination={usePagination}
        paginationPerPage={25}
        paginationRowsPerPageOptions={[10, 25, 50, 100]}
      />
    </div>
  );
}
