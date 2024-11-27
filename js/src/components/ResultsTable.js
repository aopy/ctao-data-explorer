import React, { useMemo } from 'react';
import DataTable from 'react-data-table-component';

const ResultsTable = ({ results, onRowSelected }) => {
  const { columns, data } = results;

  // Memoize columns
  const tableColumns = useMemo(
    () =>
      columns.map((col) => ({
        name: col,
        selector: (row) => row[col],
        sortable: true,
      })),
    [columns]
  );

  // Memoize data
  const tableData = useMemo(
    () =>
      data.map((row) => {
        const rowData = {};
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
      pagination
      selectableRows
      onSelectedRowsChange={onRowSelected}
      onRowClicked={(row) => console.log('Row clicked:', row)}
      pointerOnHover
      highlightOnHover
    />
  );
};

export default ResultsTable;
