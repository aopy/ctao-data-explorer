import React from 'react';
import DataTable from 'react-data-table-component';

const ResultsTable = ({ results, onRowSelected }) => {
  const { columns, data } = results;

  // Define table columns
  const tableColumns = columns.map((col) => ({
    name: col,
    selector: (row) => row[col],
    sortable: true,
  }));

  // Transform data into array of objects
  const tableData = data.map((row) => {
    const rowData = {};
    columns.forEach((col, index) => {
      rowData[col] = row[index];
    });
    return rowData;
  });

  return (
    <DataTable
      title="Search Results"
      columns={tableColumns}
      data={tableData}
      pagination
      selectableRows
      onSelectedRowsChange={({ selectedRows }) => onRowSelected(selectedRows)}
      onRowClicked={(row) => console.log('Row clicked:', row)}
      pointerOnHover
      highlightOnHover
    />
  );
};

export default ResultsTable;
