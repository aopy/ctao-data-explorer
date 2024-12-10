import React, { useState, useCallback } from 'react';
import SearchForm from './components/SearchForm';
import ResultsTable from './components/ResultsTable';
import AladinLiteViewer from './components/AladinLiteViewer';
import TimelineChart from './components/TimelineChart';
import EmRangeChart from './components/EmRangeChart';

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
    <div className="container-fluid p-3">
      {/* Top row: Sky map full width */}
      <div className="row mb-3">
        <div className="col-12">
          <div className="card">
            <div className="card-header bg-primary text-white">
              Sky Map
            </div>
            <div className="card-body p-0" style={{ height: '500px' }}>
              <AladinLiteViewer overlays={selectedCoordinates} />
            </div>
          </div>
        </div>
      </div>

      {/* Second row: Search form (left) and Charts (right) */}
      <div className="row">
        <div className="col-md-4 col-lg-3 mb-3">
          <div className="card">
            <div className="card-header bg-secondary text-white">
              Search Form
            </div>
            <div className="card-body">
              <SearchForm setResults={setResults} />
            </div>
          </div>
        </div>
        {results && (
          <div className="col-md-8 col-lg-9">
            <div className="card">
              <div className="card-header bg-dark text-white">
                Charts
              </div>
              <div className="card-body">
                <ul className="nav nav-tabs" id="chartTabs" role="tablist">
                  <li className="nav-item" role="presentation">
                    <button
                      className="nav-link active"
                      id="timeline-tab"
                      data-bs-toggle="tab"
                      data-bs-target="#timeline"
                      type="button"
                      role="tab"
                      aria-controls="timeline"
                      aria-selected="true"
                    >
                      Timeline
                    </button>
                  </li>
                  <li className="nav-item" role="presentation">
                    <button
                      className="nav-link"
                      id="emrange-tab"
                      data-bs-toggle="tab"
                      data-bs-target="#emrange"
                      type="button"
                      role="tab"
                      aria-controls="emrange"
                      aria-selected="false"
                    >
                      Electromagnetic Range
                    </button>
                  </li>
                </ul>
                <div className="tab-content p-2" id="chartTabsContent">
                  <div
                    className="tab-pane fade show active"
                    id="timeline"
                    role="tabpanel"
                    aria-labelledby="timeline-tab"
                  >
                    <TimelineChart results={results} selectedIds={selectedIds} />
                  </div>
                  <div
                    className="tab-pane fade"
                    id="emrange"
                    role="tabpanel"
                    aria-labelledby="emrange-tab"
                  >
                    <EmRangeChart results={results} selectedIds={selectedIds} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Third row: Results table full width */}
      {results && (
        <div className="row mt-3">
          <div className="col-12">
            <div className="card">
              <div className="card-header bg-info text-white">
                Search Results
              </div>
              <div className="card-body p-0">
                <ResultsTable results={results} onRowSelected={handleRowSelected} />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
