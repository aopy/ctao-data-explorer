// src/App.js

import React, { useState } from 'react';
import SearchForm from './components/SearchForm';
import ResultsTable from './components/ResultsTable';

function App() {
  const [results, setResults] = useState(null);

  return (
    <div className="App">
      <h1>CTAO Data Explorer</h1>
      <SearchForm setResults={setResults} />
      <ResultsTable results={results} />
    </div>
  );
}

export default App;
