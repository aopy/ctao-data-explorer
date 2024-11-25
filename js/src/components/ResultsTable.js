import React from 'react';

function ResultsTable({ results }) {
  if (!results || results.data.length === 0) {
    return <div>No results to display.</div>;
  }

  const { columns, data } = results;

  return (
    <table>
      <thead>
        <tr>
          {columns.map((col, idx) => (
            <th key={`header-${idx}`}>{col}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, idx) => (
          <tr key={`row-${idx}`}>
            {row.map((cell, cellIdx) => (
              <td key={`cell-${idx}-${cellIdx}`}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default ResultsTable;
