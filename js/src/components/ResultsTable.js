import React, { useMemo } from 'react';
import DataTable from 'react-data-table-component';

const ResultsTable = ({ results, onRowSelected }) => {
  const { columns, data } = results;

    // Memoize columns
    const tableColumns = useMemo(
      () =>
        columns.map((col, index) => ({
          id: `column-${col}-${index}`, // Ensure uniqueness
          name: col,
          selector: (row) => row[col],
          sortable: true,
        })),
      [columns]
    );

  // Memoize data
    const tableData = useMemo(
      () =>
        data.map((row, rowIndex) => {
          const rowData = { id: `row-${rowIndex}` }; // Add unique id
          columns.forEach((col, index) => {
            rowData[col] = row[index];
          });
          return rowData;
        }),
      [data, columns]
    );

    return (
      <DataTable
        title="Search Results"
        columns={tableColumns}
        data={tableData}
        keyField="id" // Specify the unique key field
        pagination
        selectableRows
        onSelectedRowsChange={onRowSelected}
        pointerOnHover
        highlightOnHover
      />
    );

};

export default ResultsTable;
