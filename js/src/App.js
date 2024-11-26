import React, { useState } from 'react';
import SearchForm from './components/SearchForm';
import ResultsTable from './components/ResultsTable';

function App() {
  const [results, setResults] = useState(null);

  const handleRowSelected = (selectedRows) => {
    // Extract coordinates for Aladin Lite
    const coordinates = selectedRows.map((row) => ({
      ra: row['s_ra'],
      dec: row['s_dec'],
    }));
    console.log('Coordinates:', coordinates);
    // TODO: Pass coordinates to Aladin Lite component
  };

  return (
    <div>
      <SearchForm setResults={setResults} />
      {results && (
        <ResultsTable results={results} onRowSelected={handleRowSelected} />
      )}
    </div>
  );
}

export default App;
