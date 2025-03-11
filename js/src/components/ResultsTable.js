import React, { useMemo, useState } from 'react';
import DataTable from 'react-data-table-component';
import axios from 'axios';
import DataLinkDropdown from './DataLinkDropdown';

const ResultsTable = ({
  results,
  onRowSelected,
  authToken,
  onAddedBasketItem,
  basketItems = [],
  activeBasketGroupId,
}) => {
  const { columns, data } = results;

  // State to track hidden columns
  const [hiddenColumns, setHiddenColumns] = useState([]);
  // Alert message state
  const [alertMessage, setAlertMessage] = useState(null);
  // State to track which row's dropdown is open (by row id).
  const [openDropdownId, setOpenDropdownId] = useState(null);

  // Check if an obs_id is already in the user's basket
  const isAlreadyInBasket = (obsId) => {
    return basketItems.some((it) => it.obs_id === obsId);
  };

  // Function to add a row to the basket (including the active basket group ID)
  const addToBasket = async (rowData) => {
    if (!authToken) {
      setAlertMessage("You must be logged in to add to basket!");
      return;
    }

    if (isAlreadyInBasket(rowData.obs_id)) {
      setAlertMessage(`obs_id=${rowData.obs_id} is already in your basket.`);
      return;
    }

    try {
      const payload = {
        obs_id: rowData.obs_id,
        dataset_dict: rowData, // the entire row or partial info
        basket_group_id: activeBasketGroupId,
      };
      const response = await axios.post("/basket", payload, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      console.log("Added to basket:", response.data);
      setAlertMessage(`Added obs_id=${rowData.obs_id} to basket successfully!`);
      if (onAddedBasketItem) onAddedBasketItem(response.data);
    } catch (error) {
      if (error.response && error.response.status === 409) {
        setAlertMessage(`obs_id=${rowData.obs_id} is already in your basket.`);
      } else {
          console.error('Failed to add to basket:', error);
          setAlertMessage('Error adding item to basket.');
        }
      }
  };

  // Function to close alert messages
  const handleCloseAlert = () => {
    setAlertMessage(null);
  };

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
        const alreadyInBasket = isAlreadyInBasket(row.obs_id);
        return (
          <button
            className="btn btn-sm btn-primary"
            onClick={() => addToBasket(row)}
            disabled={!authToken || alreadyInBasket}
          >
            {alreadyInBasket ? 'In Basket' : 'Add'}
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
        omit: hiddenColumns.includes(col),
      });
    });

    return cols;
  }, [columns, hiddenColumns, authToken, basketItems, toggleableColumns, openDropdownId]);

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
