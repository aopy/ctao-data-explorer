import React, { useState, useCallback } from 'react';
import SearchForm from './components/SearchForm';
import ResultsTable from './components/ResultsTable';
import AladinLiteViewer from './components/AladinLiteViewer';

function App() {
  const [results, setResults] = useState(null);
  const [selectedCoordinates, setSelectedCoordinates] = useState([]);

  const handleRowSelected = useCallback(
    (selectedRowsChange) => {
      const { selectedRows } = selectedRowsChange || {};
      console.log('Selected Rows:', selectedRows);

      if (!selectedRows || !Array.isArray(selectedRows)) {
        console.error('selectedRows is not an array');
        return;
      }

      const coordinates = selectedRows.map((row) => ({
        ra: parseFloat(row['s_ra']),
        dec: parseFloat(row['s_dec']),
        id: row['obs_id'],
      }));
      console.log('Coordinates:', coordinates);
      setSelectedCoordinates(coordinates);
    },
    [setSelectedCoordinates]
  );

  return (
    <div>
      <SearchForm setResults={setResults} />
      {results && (
        <>
          <ResultsTable results={results} onRowSelected={handleRowSelected} />
          <AladinLiteViewer overlays={selectedCoordinates} />
        </>
      )}
    </div>
  );
}

export default App;
