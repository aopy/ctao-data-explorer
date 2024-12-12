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

  // State for which main tab is active: "search" or "results"
  const [activeTab, setActiveTab] = useState('search');

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

  const handleSearchResults = (data) => {
    setResults(data);
    // Switch to results tab
    setActiveTab('results');
  };

  return (
    <div className="container-fluid p-3">
      <ul className="nav nav-tabs" role="tablist">
        <li className="nav-item" role="presentation">
          <button
            className={`nav-link ${activeTab === 'search' ? 'active' : ''}`}
            onClick={() => setActiveTab('search')}
            type="button"
            role="tab"
          >
            Search
          </button>
        </li>
        <li className="nav-item" role="presentation">
          <button
            className={`nav-link ${activeTab === 'results' ? 'active' : ''}`}
            onClick={() => setActiveTab('results')}
            type="button"
            role="tab"
          >
            Results
          </button>
        </li>
      </ul>

      <div className="tab-content mt-3">
        {/* SEARCH TAB */}
        <div
          className={`tab-pane fade ${activeTab === 'search' ? 'show active' : ''}`}
          role="tabpanel"
        >
          <div className="card">
            <div className="card-header bg-secondary text-white">
              Search Form
            </div>
            <div className="card-body">
              <SearchForm setResults={handleSearchResults} />
            </div>
          </div>
        </div>

        {/* RESULTS TAB */}
        <div
          className={`tab-pane fade ${activeTab === 'results' ? 'show active' : ''}`}
          role="tabpanel"
        >
          {results ? (
            <>
              {/* Top row: Sky map (left, wider) and Charts (right) */}
              <div className="row">
                {/* Sky map: Make it wider (7/12 columns) */}
                <div className="col-md-7 mb-3">
                  <div className="card h-100">
                    <div className="card-header bg-primary text-white">Sky Map</div>
                    <div
                      className="card-body p-0"
                      style={{ height: '400px', overflow: 'hidden' }}
                    >
                      <AladinLiteViewer overlays={selectedCoordinates} />
                    </div>
                  </div>
                </div>
                {/* Charts: Take up the remaining 5/12 columns */}
                <div className="col-md-5 mb-3">
                  <div className="card h-100">
                    <div className="card-header bg-dark text-white">Charts</div>
                    <div
                      className="card-body d-flex flex-column"
                      style={{ height: '400px', overflow: 'auto' }}
                    >
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
                      <div className="tab-content flex-grow-1" id="chartTabsContent">
                        <div
                          className="tab-pane fade show active mt-2"
                          id="timeline"
                          role="tabpanel"
                          aria-labelledby="timeline-tab"
                        >
                          <TimelineChart results={results} selectedIds={selectedIds} />
                        </div>
                        <div
                          className="tab-pane fade mt-2"
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
              </div>

              {/* Bottom row: Results table spanning full width */}
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
            </>
          ) : (
            <div>No results yet. Please run a search first.</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
