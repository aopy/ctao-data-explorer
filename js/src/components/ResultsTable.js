import React, { useMemo } from 'react';
import DataTable from 'react-data-table-component';

const ResultsTable = ({ results, onRowSelected }) => {
  const { columns, data } = results;

    // Memoize columns
   const tableColumns = useMemo(() => {
    // Remove 'access_url' from its current position if it exists
    const normalCols = columns.filter(col => col !== 'access_url').map((col, index) => ({
      id: `column-${col}-${index}`,
      name: col,
      selector: (row) => row[col],
      sortable: true,
    }));

    // Add 'access_url' column at the end with a download button
    // This column displays a hyperlink with the 'download' attribute.
    normalCols.push({
      id: 'access_url-column',
      name: 'access_url',
      cell: (row) => (
        <a
          href={row.access_url}
          download
          target="_blank"
          rel="noopener noreferrer"
          className="download-button"
        >
          Download
        </a>
      ),
      sortable: false,
    });

    return normalCols;
  }, [columns]);

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

    return (
      <DataTable
        title="Search Results"
        columns={tableColumns}
        data={tableData}
        keyField="id"
        pagination
        selectableRows
        onSelectedRowsChange={onRowSelected}
        pointerOnHover
        highlightOnHover
      />
    );

};

export default ResultsTable;
