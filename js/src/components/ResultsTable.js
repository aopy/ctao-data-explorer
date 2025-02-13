import React, { useMemo, useState, useCallback } from 'react';
import DataTable from 'react-data-table-component';
import axios from 'axios';

const ResultsTable = ({
  results,
  onRowSelected,
  authToken,
  onAddedBasketItem,
  basketItems = [],
}) => {
  const { columns, data } = results;

  // State to track hidden columns
  const [hiddenColumns, setHiddenColumns] = useState([]);
  // Alerts
  const [alertMessage, setAlertMessage] = useState(null);
  // Check if an obs_id is already in the user's basket
  const isAlreadyInBasket = (obsId) => {
    return basketItems.some((it) => it.obs_id === obsId);
  };

  // Function to add a row to the basket
  const addToBasket = async (rowData) => {
    if (!authToken) {
      setAlertMessage("You must be logged in to add to basket!");
      return;
    }

    // Check in front-end if it is already in basket:
    if (isAlreadyInBasket(rowData.obs_id)) {
      setAlertMessage(`obs_id=${rowData.obs_id} is already in your basket.`);
      return;
    }

    try {
      const payload = {
        obs_id: rowData.obs_id,
        dataset_dict: rowData, // the entire row or partial info
      };
      const response = await axios.post("/basket", payload, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      console.log("Added to basket:", response.data);
      setAlertMessage(`Added obs_id=${rowData.obs_id} to basket successfully!`);
      // Tell parent to refresh the basket
      if (onAddedBasketItem) {
        onAddedBasketItem();
      }
    } catch (error) {
      console.error('Failed to add to basket:', error);
      setAlertMessage('Error adding item to basket.');
    }
  };

  // Function to close alert messages
  const handleCloseAlert = () => {
    setAlertMessage(null);
  };

  /**
   * handleDataLink:
   * Fetches VOTable XML from the DataLink URL, extracts TABLEDATA rows,
   * and opens the first valid access_url in a new tab.
   */
  const handleDataLink = useCallback(async (row) => {
    if (!row.datalink_url) {
      alert("No DataLink URL available for this row");
      return;
    }
    try {
      const res = await axios.get(row.datalink_url, { responseType: 'text' });
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(res.data, "application/xml");
      const tabledata = xmlDoc.getElementsByTagName("TABLEDATA")[0];
      if (!tabledata) {
        alert("No TABLEDATA found in DataLink response");
        return;
      }
      const trElements = tabledata.getElementsByTagName("TR");
      let downloadUrl = null;
      for (let i = 0; i < trElements.length; i++) {
        const tdElements = trElements[i].getElementsByTagName("TD");
        // According to the backend VOTable, TD[0]: ID, TD[1]: access_url, TD[2]: error_message
        const errorMsg = tdElements[2]?.textContent;
        if (errorMsg && errorMsg.trim() !== "") {
          continue; // skip rows with an error message
        }
        downloadUrl = tdElements[1]?.textContent;
        if (downloadUrl && downloadUrl.trim() !== "") {
          break;
        }
      }
      if (downloadUrl) {
        window.open(downloadUrl, '_blank');
      } else {
        alert("No valid download URL found in DataLink response.");
      }
    } catch (error) {
      console.error("Error fetching DataLink:", error);
      alert("Error fetching DataLink information.");
    }
  }, []);

  // Custom subheader for toggling column visibility
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
          {columns.map((col) => (
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

  // Memoize table columns.
  // Exclude the raw "access_url" and "datalink_url" fields from the default columns,
  // then add custom columns for direct download and DataLink retrieval.
  const tableColumns = useMemo(() => {
    const visibleColumns = columns.filter((col) => !hiddenColumns.includes(col));

    // Create normal columns
    const normalCols = visibleColumns
      .filter((col) => col !== 'access_url' && col !== 'datalink_url')
      .map((col, index) => ({
        id: `column-${col}-${index}`,
        name: col,
        selector: (row) => row[col],
        sortable: true,
        omit: hiddenColumns.includes(col),
      }));

    // Add a column for direct download if an "access_url" field exists
    if (visibleColumns.includes('access_url')) {
      normalCols.push({
        id: 'access_url-column',
        name: 'Download',
        cell: (row) => (
          <a
            href={row.access_url}
            download
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-sm btn-success"
          >
            Download
          </a>
        ),
        sortable: false,
        omit: hiddenColumns.includes('access_url'),
      });
    }

    // Add a column for DataLink if a "datalink_url" field exists
    if (visibleColumns.includes('datalink_url')) {
      normalCols.push({
        id: 'datalink-column',
        name: 'DataLink',
        cell: (row) => (
          <button
            className="btn btn-sm btn-info"
            onClick={() => handleDataLink(row)}
          >
            Get DataLink
          </button>
        ),
        sortable: false,
        omit: hiddenColumns.includes('datalink_url'),
        ignoreRowClick: true,
        allowOverflow: true,
        button: true,
      });
    }

    // Prepend the "basket" column.
    normalCols.unshift({
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

    return normalCols;
  }, [columns, hiddenColumns, authToken, basketItems, handleDataLink]);

  // Map the raw data into an object with keys corresponding to column names
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
    subHeader: {
      style: {
        padding: 0,
        margin: 0,
      },
    },
  };

  return (
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
  );
};

export default ResultsTable;
