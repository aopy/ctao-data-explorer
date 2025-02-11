import React, { useState, useEffect } from 'react';
import axios from 'axios';
import SearchForm from './components/SearchForm';
import ResultsTable from './components/ResultsTable';
import AladinLiteViewer from './components/AladinLiteViewer';
import TimelineChart from './components/TimelineChart';
import EmRangeChart from './components/EmRangeChart';

// Helper function to convert numeric t_min to local date/time string
function formatTmin(mjd) {
  if (!mjd || isNaN(mjd)) return '';
  // MJD -> local time
  const MJD_UNIX_EPOCH = 40587;
  const msPerDay = 86400000;
  const unixTime = (mjd - MJD_UNIX_EPOCH) * msPerDay;
  const d = new Date(unixTime);
  return d.toLocaleString();
}

// The modal that displays sky map & charts for a single basket item
function BasketItemModal({ show, onClose, basketItem }) {
  if (!show || !basketItem) return null;

  // The entire object from DB => rowData
  const rowData = basketItem.dataset_json || {};

  // Prepare the overlay for Aladin
  const raNum = parseFloat(rowData.s_ra);
  const decNum = parseFloat(rowData.s_dec);
  const fovNum = parseFloat(rowData.s_fov); // if any

  // A single overlay array with marker + circle
  const allCoordinates = [];
  if (!isNaN(raNum) && !isNaN(decNum)) {
    allCoordinates.push({
      ra: raNum,
      dec: decNum,
      id: rowData.obs_id?.toString() || "??",
      s_fov: !isNaN(fovNum) ? fovNum : undefined, // pass s_fov if it exists
    });
  }

  // For charts
  const chartColumns = ["obs_id", "s_ra", "s_dec", "t_min", "t_max", "em_min", "em_max"];
  const chartData = [chartColumns.map((col) => rowData[col])];
  const fakeResults = { columns: chartColumns, data: chartData };

  // For the table: show all fields from rowData
  const allKeys = Object.keys(rowData).sort();

  return (
    <div className="modal show" style={{ display: 'block' }} role="dialog">
      <div className="modal-dialog modal-xl" role="document">
        <div className="modal-content">
          {/* MODAL HEADER */}
          <div className="modal-header bg-primary text-white">
            <h5 className="modal-title">
              Basket Item: {rowData.obs_id || "N/A"}
            </h5>
            <button type="button" className="btn-close" onClick={onClose}></button>
          </div>

          {/* MODAL BODY */}
          <div className="modal-body">
            {/* ROW #1 => SKY MAP (left), CHART TABS (right) */}
            <div className="row">
              {/* Sky map + circle overlay if s_fov is present */}
              <div className="col-md-7 mb-3">
                <div className="card h-100">
                  <div className="card-header bg-primary text-white">Sky Map</div>
                  <div
                    className="card-body p-0"
                    style={{ height: "400px", overflow: "hidden" }}
                  >
                    <AladinLiteViewer
                      overlays={allCoordinates}
                      selectedIds={[]}
                    />
                  </div>
                </div>
              </div>

              {/* Timeline / EM Range Tabs */}
              <div className="col-md-5 mb-3">
                <div className="card h-100">
                  <div className="card-header bg-dark text-white">Charts</div>
                  <div
                    className="card-body d-flex flex-column"
                    style={{ height: '400px', overflow: 'auto' }}
                  >
                    {/* Unique IDs so it won't clash with other tabs */}
                    <ul className="nav nav-tabs" id="modalChartTabs" role="tablist">
                      <li className="nav-item" role="presentation">
                        <button
                          className="nav-link active"
                          id="timeline-tab-modal"
                          data-bs-toggle="tab"
                          data-bs-target="#timelinePaneModal"
                          type="button"
                          role="tab"
                          aria-controls="timelinePaneModal"
                          aria-selected="true"
                        >
                          Timeline
                        </button>
                      </li>
                      <li className="nav-item" role="presentation">
                        <button
                          className="nav-link"
                          id="emrange-tab-modal"
                          data-bs-toggle="tab"
                          data-bs-target="#emrangePaneModal"
                          type="button"
                          role="tab"
                          aria-controls="emrangePaneModal"
                          aria-selected="false"
                        >
                          EM Range
                        </button>
                      </li>
                    </ul>

                    <div
                      className="tab-content flex-grow-1"
                      id="modalChartTabsContent"
                    >
                      <div
                        className="tab-pane fade show active mt-2"
                        id="timelinePaneModal"
                        role="tabpanel"
                        aria-labelledby="timeline-tab-modal"
                      >
                        <TimelineChart results={fakeResults} selectedIds={[]} />
                      </div>
                      <div
                        className="tab-pane fade mt-2"
                        id="emrangePaneModal"
                        role="tabpanel"
                        aria-labelledby="emrange-tab-modal"
                      >
                        <EmRangeChart results={fakeResults} selectedIds={[]} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* ROW #2 => FULL TABLE of all fields */}
            <div className="row mt-3">
              <div className="col-12">
                <h6>All Fields</h6>
                <table className="table table-sm table-bordered">
                  <thead>
                    <tr>
                      <th>Key</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allKeys.map((key) => (
                      <tr key={key}>
                        <td>{key}</td>
                        <td>{rowData[key]?.toString() ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* MODAL FOOTER */}
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// The BasketPage that lists items with “Open”/“Remove”
function BasketPage({ authToken, basketItems, refreshBasket, onOpenItem, onRemoveItem }) {
  if (!authToken) {
    return <p>Please log in to view your basket.</p>;
  }

  return (
    <div className="mt-3">
      <h3>My Basket</h3>

      {/* "Refresh" button for manual refresh: */}
      {/* <button onClick={refreshBasket} className="btn btn-sm btn-outline-info mb-2">Refresh</button> */}

      <ul className="list-group">
        {basketItems.map((it) => {
          const ds = it.dataset_json || {};
          const targetName = ds.target_name || 'Unknown Target';
          const tmin_str = formatTmin(ds.t_min);
          //const createdStr = new Date(it.created_at).toLocaleString();

          return (
            <li key={it.id} className="list-group-item d-flex justify-content-between">
              <div>
                {/* Display obs_id + targetName + t_min */}
                <strong>{it.obs_id}</strong>{' '}
                | {targetName}{' '}
                | {tmin_str}{' '}
              </div>
              <div>
                <button
                  className="btn btn-sm btn-outline-primary me-2"
                  onClick={() => onOpenItem(it)}
                >
                  Open
                </button>
                <button
                  className="btn btn-sm btn-outline-danger"
                  onClick={() => onRemoveItem(it.id)}
                >
                  Remove
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// The main App component
function App() {
  // The entire search results from the backend
  const [results, setResults] = useState(null);

  // allCoordinates = all the RA/Dec points from the entire result set
  const [allCoordinates, setAllCoordinates] = useState([]);
  // selectedIds = only the IDs that the user has highlighted in the table
  const [selectedIds, setSelectedIds] = useState([]);
  const [activeTab, setActiveTab] = useState('search');

  // Auth token from OIDC or local login
  const [authToken, setAuthToken] = useState(null);
  // Current user info
  const [user, setUser] = useState(null);

  // BASKET STATE
  const [basketItems, setBasketItems] = useState([]);
  // For the modal
  const [showBasketModal, setShowBasketModal] = useState(false);
  const [basketModalItem, setBasketModalItem] = useState(null);

  // On mount, check if there's ?token= in URL
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    if (token) {
      setAuthToken(token);
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  // If we have an authToken, fetch the user's info from /users/me
  useEffect(() => {
    if (authToken) {
      axios
        .get('/users/me', {
          headers: {
            Authorization: `Bearer ${authToken}`,
          },
        })
        .then((res) => {
          setUser(res.data); // e.g. { id, email, first_name, last_name }
        })
        .catch((err) => {
          console.error('Failed to fetch current user:', err);
        });
    } else {
      setUser(null);
    }
  }, [authToken]);

  // Re-load the basket from the server
  const refreshBasket = async () => {
    if (!authToken) return;
    try {
      const res = await axios.get('/basket', {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      setBasketItems(res.data);
    } catch (err) {
      console.error('Failed to refresh basket:', err);
    }
  };

  // Whenever log in or out, refresh the basket
  useEffect(() => {
    if (authToken) {
      refreshBasket();
    } else {
      setBasketItems([]);
    }
  }, [authToken]);

  // Handler for user clicks login
  const handleLogin = () => {
    window.location.href = '/oidc/login';
  };

  // Handler for user clicks logout
  const handleLogout = () => {
    setAuthToken(null);
    setUser(null);
  };

  // Called when user does a search
  const handleSearchResults = (data) => {
    setResults(data);
    setActiveTab('results');

    if (data?.columns && data?.data) {
      const s_ra_index = data.columns.indexOf('s_ra');
      const s_dec_index = data.columns.indexOf('s_dec');
      const id_index = data.columns.indexOf('obs_id');
      const s_fov_index = data.columns.indexOf('s_fov');
      if (
        s_ra_index !== -1 &&
        s_dec_index !== -1 &&
        id_index !== -1 &&
        s_fov_index !== -1
      ) {
        const coords = data.data.map((row) => ({
          ra: parseFloat(row[s_ra_index]),
          dec: parseFloat(row[s_dec_index]),
          id: row[id_index].toString().trim(),
          s_fov: parseFloat(row[s_fov_index]),
        }));
        setAllCoordinates(coords);
      }
    }
  };

  // Called whenever user selects rows in results table
  const handleRowSelected = (selectedRowsChange) => {
    const { selectedRows } = selectedRowsChange || {};
    if (!selectedRows || !Array.isArray(selectedRows)) {
      return;
    }
    const ids = selectedRows.map((row) => row['obs_id'].toString());
    setSelectedIds(ids);
  };

  // Called by basket page when user clicks "Remove"
  const handleRemoveBasketItem = async (id) => {
    if (!authToken) return;
    try {
      await axios.delete(`/basket/${id}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      // filter out the removed
      setBasketItems(prev => prev.filter(b => b.id !== id));
    } catch (err) {
      console.error('Failed to remove from basket:', err);
      alert('Error removing item from basket.');
    }
  };

  // Called by basket page when user clicks "Open"
  const handleOpenBasketItem = (item) => {
    setBasketModalItem(item);
    setShowBasketModal(true);
  };

  // close the modal
  const closeBasketModal = () => {
    setShowBasketModal(false);
    setBasketModalItem(null);
  };

  return (
    <div className="container-fluid p-3">
      {/* TOP NAVBAR AREA */}
      <div className="d-flex justify-content-between mb-2">
        <h2>CTAO Data Explorer</h2>
        <div>
          {authToken ? (
            <>
              <span className="me-3 text-success">
                {user ? `Logged in as ${user.first_name || user.email}` : 'Logged in'}
              </span>
              <button className="btn btn-outline-danger" onClick={handleLogout}>
                Logout
              </button>
            </>
          ) : (
            <button type="button" className="btn btn-outline-primary" onClick={handleLogin}>
              Login
            </button>
          )}
        </div>
      </div>

      {/* TAB NAVIGATION */}
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
        <li className="nav-item" role="presentation">
          <button
            className={`nav-link ${activeTab === 'basket' ? 'active' : ''}`}
            onClick={() => setActiveTab('basket')}
            type="button"
            role="tab"
          >
            My Basket
          </button>
        </li>
      </ul>

      {/* TAB CONTENT */}
      <div className="tab-content mt-3">
        {/* SEARCH TAB */}
        <div className={`tab-pane fade ${activeTab === 'search' ? 'show active' : ''}`} role="tabpanel">
          <div className="card">
            <div className="card-header bg-secondary text-white">Search Form</div>
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
              {/* ROW: Sky Map (left) + Charts (right) */}
              <div className="row">
                {/* Sky map */}
                <div className="col-md-7 mb-3">
                  <div className="card h-100">
                    <div className="card-header bg-primary text-white">Sky Map</div>
                    <div className="card-body p-0" style={{ height: '400px', overflow: 'hidden' }}>
                      {/* Aladin sky map with your overlays */}
                      <AladinLiteViewer
                        overlays={allCoordinates}
                        selectedIds={selectedIds}
                      />
                    </div>
                  </div>
                </div>

                {/* Charts */}
                <div className="col-md-5 mb-3">
                  <div className="card h-100">
                    <div className="card-header bg-dark text-white">Charts</div>
                    <div
                      className="card-body d-flex flex-column"
                      style={{ height: '400px', overflow: 'auto' }}
                    >
                      {/* BOOTSTRAP TABS FOR TIMELINE VS EM RANGE */}
                      <ul className="nav nav-tabs" id="chartTabs" role="tablist">
                        <li className="nav-item" role="presentation">
                          <button
                            className="nav-link active"
                            id="timeline-tab"
                            data-bs-toggle="tab"
                            data-bs-target="#timelinePane"
                            type="button"
                            role="tab"
                            aria-controls="timelinePane"
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
                            data-bs-target="#emrangePane"
                            type="button"
                            role="tab"
                            aria-controls="emrangePane"
                            aria-selected="false"
                          >
                            EM Range
                          </button>
                        </li>
                      </ul>
                      <div className="tab-content flex-grow-1" id="chartTabsContent">
                        <div
                          className="tab-pane fade show active mt-2"
                          id="timelinePane"
                          role="tabpanel"
                          aria-labelledby="timeline-tab"
                        >
                          <TimelineChart results={results} selectedIds={selectedIds} />
                        </div>
                        <div
                          className="tab-pane fade mt-2"
                          id="emrangePane"
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

              {/* Results Table */}
              <div className="row mt-3">
                <div className="col-12">
                  <div className="card">
                    <div className="card-header bg-info text-white">Search Results</div>
                    <div className="card-body p-0">
                      <ResultsTable
                        results={results}
                        basketItems={basketItems}
                        onRowSelected={handleRowSelected}
                        authToken={authToken}
                        onAddedBasketItem={() => refreshBasket()}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div>No results yet. Please run a search first.</div>
          )}
        </div>

        {/* BASKET TAB */}
        <div className={`tab-pane fade ${activeTab === 'basket' ? 'show active' : ''}`} role="tabpanel">
          <BasketPage
            authToken={authToken}
            basketItems={basketItems}
            refreshBasket={refreshBasket}
            onOpenItem={handleOpenBasketItem}
            onRemoveItem={handleRemoveBasketItem}
          />
        </div>
      </div>

      {/* The modal for showing a single basket item with sky map and charts */}
      <BasketItemModal
        show={showBasketModal}
        onClose={closeBasketModal}
        basketItem={basketModalItem}
      />
    </div>
  );
}

export default App;
