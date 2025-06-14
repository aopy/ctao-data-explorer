import React, { useMemo, useState } from 'react';
import DataTable from 'react-data-table-component';
import axios from 'axios';
import DataLinkDropdown from './DataLinkDropdown';
import { API_PREFIX } from '../index';

const ResultsTable = ({
  results,
  onRowSelected,
  isLoggedIn,
  onAddedBasketItem,
  allBasketGroups = [],
  activeBasketGroupId,
}) => {
  const { columns, data } = results;

  // State to track hidden columns
  const [hiddenColumns, setHiddenColumns] = useState([]);
  // Alert message state
  const [alertMessage, setAlertMessage] = useState(null);
  // State to track which row's dropdown is open (by row id).
  const [openDropdownId, setOpenDropdownId] = useState(null);

 // Find the currently active basket group object
  const activeBasketGroup = useMemo(() => {
    return allBasketGroups.find(group => group.id === activeBasketGroupId);
  }, [allBasketGroups, activeBasketGroupId]);

  // Check if an obs_id is already in the active basket group
  const isInActiveBasket = (obsId) => {
    if (!activeBasketGroup || !activeBasketGroup.saved_datasets) {
      return false;
    }
    return activeBasketGroup.saved_datasets.some((item) => item.obs_id === obsId);
  };

  // Add item to the currently active basket
  const addToBasket = async (rowData) => {
    if (!isLoggedIn) {
      setAlertMessage("You must be logged in to add to basket!");
      return;
    }
    if (!activeBasketGroupId) {
        setAlertMessage("Please select an active basket group first!");
        // disable the button if no group is active?
        return;
    }

    if (isInActiveBasket(rowData.obs_id)) {
      setAlertMessage(`obs_id=${rowData.obs_id} is already in the active basket.`);
      return; // Already present in the current basket
    }

    try {
      const payload = {
        obs_id: rowData.obs_id,
        dataset_dict: rowData,
        basket_group_id: activeBasketGroupId, // Send the active group ID
      };

      const response = await axios.post(`${API_PREFIX}/basket/items`, payload);
      console.log("Added to basket:", response.data);
      setAlertMessage(`Added obs_id=${rowData.obs_id} to active basket successfully!`);
      if (onAddedBasketItem) {
        // Pass the new item and the group it was added to
        onAddedBasketItem(response.data, activeBasketGroupId);
      }
    } catch (error) {
       if (error.response && error.response.status === 401) {
         setAlertMessage('Authentication error. Please log in again.');
       } else if (error.response && error.response.status === 409) {
        setAlertMessage(`obs_id=${rowData.obs_id} is already in the active basket.`);
      } else if (error.response && error.response.status === 404) {
        setAlertMessage(`Error: Active basket group not found.`);
      }
      else {
        console.error('Failed to add to basket:', error);
        setAlertMessage('Error adding item to basket.');
      }
    }
  };

  // Function to close alert messages
  const handleCloseAlert = () => setAlertMessage(null);

  // Define which columns are toggleable
  const toggleableColumns = columns.filter(col => col !== "datalink_url");

  // Fixed column width
  const colWidth = "150px";

  // Custom subheader for column visibility using Bootstrap dropdown
  const SubHeader = () => (
    <div className="p-2 border-bottom bg-light w-100 d-flex">
      <div className="dropdown ms-2">
        <button
          className="btn btn-secondary btn-sm dropdown-toggle"
          type="button"
          id="columnToggleButton"
          data-bs-toggle="dropdown"
          aria-expanded="false"
        >
          Toggle Columns
        </button>
        <div className="dropdown-menu p-2" aria-labelledby="columnToggleButton">
          {/* Bulk actions */}
          <div className="d-flex justify-content-between mb-2">
            <button
              type="button"
              className="btn btn-link btn-sm"
              onClick={() => setHiddenColumns(toggleableColumns)}
            >
              Hide All
            </button>
            <button
              type="button"
              className="btn btn-link btn-sm"
              onClick={() => setHiddenColumns([])}
            >
              Show All
            </button>
          </div>
          <div className="dropdown-divider"></div>
          {/* Individual column toggles */}
          {toggleableColumns.map((col) => (
            <div key={col} className="form-check">
              <input
                type="checkbox"
                className="form-check-input"
                id={`column-${col}`}
                checked={!hiddenColumns.includes(col)}
                onChange={() => {
                  setHiddenColumns((current) =>
                    current.includes(col)
                      ? current.filter((c) => c !== col)
                      : [...current, col]
                  );
                }}
              />
              <label className="form-check-label" htmlFor={`column-${col}`}>
                {col}
              </label>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // Build table columns
  const tableColumns = useMemo(() => {
    let cols = [];

    // Basket "Action" column
    cols.push({
      id: 'basket-column',
      name: 'Action',
      cell: (row) => {
        const inActive = isInActiveBasket(row.obs_id);
        const buttonDisabled = !isLoggedIn || !activeBasketGroupId || inActive;
        let title = "Add to active basket";
        if (!isLoggedIn) title = "Login to add";
        else if (!activeBasketGroupId) title = "Select a basket first";
        else if (inActive) title = "Already in active basket";

        return (
          <button
            className={`btn btn-sm ${inActive ? 'btn-secondary' : 'btn-primary'}`} // Style differently if already in
            onClick={() => addToBasket(row)}
            disabled={buttonDisabled}
            title={title}
          >
            {inActive ? 'In Basket' : 'Add'}
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
      cell: (row) =>
        row.datalink_url ? (
          <DataLinkDropdown
            datalink_url={row.datalink_url}
            isOpen={row.id === openDropdownId}
            onToggle={() =>
              setOpenDropdownId(row.id === openDropdownId ? null : row.id)
            }
          />
        ) : null,
      sortable: false,
      ignoreRowClick: true,
      allowOverflow: true,
      button: true,
    });

    // Toggleable columns from the original result
    toggleableColumns.forEach((col, index) => {
      if (col === "datalink_url") return;
      cols.push({
        id: `column-${col}-${index}`,
        name: (
          <div
            style={{
              width: colWidth,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}
            title={col}
          >
            {col}
          </div>
        ),
        selector: row => row[col],
        cell: (row) => (
          <div
            style={{
              width: colWidth,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}
            title={row[col]}
          >
            {row[col]}
          </div>
        ),
        sortable: true,
        sortFunction: (a, b) => {
          const aVal = parseFloat(a[col]);
          const bVal = parseFloat(b[col]);
          if (!isNaN(aVal) && !isNaN(bVal)) {
            return aVal - bVal;
          }
          return String(a[col]).localeCompare(String(b[col]));
        },
        omit: hiddenColumns.includes(col),
      });
    });

    return cols;
  }, [columns, hiddenColumns, isLoggedIn, activeBasketGroupId, allBasketGroups, toggleableColumns, openDropdownId]); // toggleableColumns?

  // Map raw data (array of arrays) to objects keyed by column names.
  const tableData = useMemo(() => {
    return data.map((row, rowIndex) => {
      const rowData = { id: `row-${rowIndex}` };
      columns.forEach((col, index) => {
        rowData[col] = row[index];
      });
      return rowData;
    });
  }, [data, columns]);

  // Custom styles for DataTable
  const customStyles = {
    subHeader: { style: { padding: 0, margin: 0 } },
  };

  return (
    <div style={{ overflowX: 'auto' }}>
      <div className="table-responsive">
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
          pagination
          selectableRows
          onSelectedRowsChange={onRowSelected}
          pointerOnHover
          highlightOnHover
          subHeader
          subHeaderComponent={<SubHeader />}
          customStyles={customStyles}
        />
      </div>
    </div>
  );
};

export default ResultsTable;
