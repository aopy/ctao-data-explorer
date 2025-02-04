import React, { useMemo, useState } from 'react';
import DataTable from 'react-data-table-component';

const ResultsTable = ({ results, onRowSelected }) => {
  const { columns, data } = results;

  // State to track hidden columns
  const [hiddenColumns, setHiddenColumns] = useState([]);

  // Custom subheader component for column visibility
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
                  setHiddenColumns(current =>
                    current.includes(col)
                      ? current.filter(c => c !== col)
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

  // Memoize columns with visibility control
  const tableColumns = useMemo(() => {
    const visibleColumns = columns.filter(col => !hiddenColumns.includes(col));

    // Create normal columns
    const normalCols = visibleColumns
      .filter(col => col !== 'access_url')
      .map((col, index) => ({
        id: `column-${col}-${index}`,
        name: col,
        selector: (row) => row[col],
        sortable: true,
        omit: hiddenColumns.includes(col),
      }));

    // Add access_url column if it's visible
    if (visibleColumns.includes('access_url')) {
      normalCols.push({
        id: 'access_url-column',
        name: 'access_url',
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

    return normalCols;
  }, [columns, hiddenColumns]);

  // Memoize data
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
