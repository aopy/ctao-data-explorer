import React, { useState, useCallback } from 'react';
import SearchForm from './components/SearchForm';
import ResultsTable from './components/ResultsTable';
import AladinLiteViewer from './components/AladinLiteViewer';
import TimelineChart from './components/TimelineChart';

function App() {
  const [results, setResults] = useState(null);
  const [selectedCoordinates, setSelectedCoordinates] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);

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
      id: row['obs_id'].toString(),
    }));
    console.log('Coordinates:', coordinates);
    setSelectedCoordinates(coordinates);

    const ids = selectedRows.map((row) => row['obs_id'].toString());
    setSelectedIds(ids);
  },
  [setSelectedCoordinates, setSelectedIds]
);


  return (
    <div>
      <SearchForm setResults={setResults} />
      {results && (
        <>
          <ResultsTable results={results} onRowSelected={handleRowSelected} />
          <AladinLiteViewer overlays={selectedCoordinates} />
          <TimelineChart results={results} selectedIds={selectedIds} />
        </>
      )}
    </div>
  );
}

export default App;
