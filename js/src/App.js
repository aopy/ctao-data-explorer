import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import SearchForm from './components/SearchForm';
import ResultsTable from './components/ResultsTable';
import AladinLiteViewer from './components/AladinLiteViewer';
import TimelineChart from './components/TimelineChart';
import EmRangeChart from './components/EmRangeChart';
import BasketPage from './components/BasketPage';
import UserProfilePage from './components/UserProfilePage';
import QueryStorePage from './components/QueryStorePage';
import { API_PREFIX } from './index';

function formatTmin(mjd) {
  if (!mjd || isNaN(mjd)) return '';
  // MJD -> local time
  const MJD_UNIX_EPOCH = 40587;
  const msPerDay = 86400000;
  const unixTime = (mjd - MJD_UNIX_EPOCH) * msPerDay;
  return new Date(unixTime).toLocaleString();
}

function BasketItemModal({ show, onClose, basketItem }) {
  if (!show || !basketItem) return null;
  const rowData = basketItem.dataset_json || {};
  const raNum = parseFloat(rowData.s_ra);
  const decNum = parseFloat(rowData.s_dec);
  const fovNum = parseFloat(rowData.s_fov);
  const initialFov = !isNaN(fovNum) ? fovNum * 2.5 : 0.5;
  const allCoordinates = [];
  if (!isNaN(raNum) && !isNaN(decNum)) {
    allCoordinates.push({
      ra: raNum,
      dec: decNum,
      id: rowData.obs_id?.toString() || "??",
      s_fov: !isNaN(fovNum) ? fovNum : undefined,
    });
  }
  const chartColumns = ["obs_id", "s_ra", "s_dec", "t_min", "t_max", "em_min", "em_max"];
  const chartData = [chartColumns.map((col) => rowData[col])];
  const fakeResults = { columns: chartColumns, data: chartData };
  const allKeys = Object.keys(rowData).sort();
  return (
    <div className="modal show" style={{ display: 'block' }} role="dialog">
      {/* Modal header */}
      <div className="modal-dialog modal-xl" role="document">
        <div className="modal-content">
          <div className="modal-header bg-primary text-white">
            <h5 className="modal-title">Basket Item: {rowData.obs_id || "N/A"}</h5>
            <button type="button" className="btn-close" onClick={onClose}></button>
          </div>
          {/* Modal body */}
          <div className="modal-body">
            <div className="row">
              <div className="col-md-7 mb-3">
                <div className="card h-100">
                  <div className="card-header bg-primary text-white">Sky Map</div>
                  <div className="card-body p-0" style={{ height: "400px", overflow: "hidden" }}>
                    <AladinLiteViewer overlays={allCoordinates} selectedIds={[]} initialFov={initialFov} />
                  </div>
                </div>
              </div>
              <div className="col-md-5 mb-3">
                <div className="card h-100">
                  <div className="card-header bg-dark text-white">Charts</div>
                  <div className="card-body d-flex flex-column" style={{ height: '400px', overflow: 'auto' }}>
                    <ul className="nav nav-tabs" id="modalChartTabs" role="tablist">
                      <li className="nav-item" role="presentation">
                        <button className="nav-link active" id="timeline-tab-modal" data-bs-toggle="tab" data-bs-target="#timelinePaneModal" type="button" role="tab" aria-controls="timelinePaneModal" aria-selected="true">Timeline</button>
                      </li>
                      <li className="nav-item" role="presentation">
                        <button className="nav-link" id="emrange-tab-modal" data-bs-toggle="tab" data-bs-target="#emrangePaneModal" type="button" role="tab" aria-controls="emrangePaneModal" aria-selected="false">EM Range</button>
                      </li>
                    </ul>
                    <div className="tab-content flex-grow-1" id="modalChartTabsContent">
                      <div className="tab-pane fade show active mt-2" id="timelinePaneModal" role="tabpanel" aria-labelledby="timeline-tab-modal">
                        <TimelineChart results={fakeResults} selectedIds={[]} />
                      </div>
                      <div className="tab-pane fade mt-2" id="emrangePaneModal" role="tabpanel" aria-labelledby="emrange-tab-modal">
                        <EmRangeChart results={fakeResults} selectedIds={[]} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            {/* Full table */}
            <div className="row mt-3">
              <div className="col-12">
                <h6>All Fields</h6>
                <table className="table table-sm table-bordered">
                  <thead>
                    <tr><th>Key</th><th>Value</th></tr>
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
          {/* Modal footer */}
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [results, setResults] = useState(null);
  const [allCoordinates, setAllCoordinates] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [activeTab, setActiveTab] = useState('search');

  const [user, setUser] = useState(null);
  const [isLoadingUser, setIsLoadingUser] = useState(true);

  const [showBasketModal, setShowBasketModal] = useState(false);
  const [basketModalItem, setBasketModalItem] = useState(null);
  const [activeBasketGroupId, setActiveBasketGroupId] = useState(null);
  const [activeBasketItems, setActiveBasketItems] = useState([]);
  const [basketRefreshCounter, setBasketRefreshCounter] = useState(0);
  const [allBasketGroups, setAllBasketGroups] = useState([]);
  // const [showProfileModal, setShowProfileModal] = useState(false);

  const searchFormRef = useRef(null);

  const handleBasketGroupsChange = (groups) => {
      setAllBasketGroups(groups || []);
      // Persist active group ID if the active group still exists
      if (activeBasketGroupId && !groups.some(g => g.id === activeBasketGroupId)) {
          setActiveBasketGroupId(groups.length > 0 ? groups[0].id : null);
      } else if (!activeBasketGroupId && groups.length > 0) {
          setActiveBasketGroupId(groups[0].id); // Default to first if none active
      }
  };

  const handleBasketItemAdded = (newItem, addedToGroupId) => {
    setAllBasketGroups(prevGroups => {
        return prevGroups.map(group => {
            // Find the group the item was added to
            if (group.id === addedToGroupId) {
                // Check if item already exists locally
                const itemExists = group.saved_datasets?.some(item => item.id === newItem.id);
                if (!itemExists) {
                    // Add the new item to this group's datasets
                    return {
                        ...group,
                        saved_datasets: [...(group.saved_datasets || []), newItem]
                    };
                }
            }
            return group;
        });
    });
    // Trigger a refresh
    // setBasketRefreshCounter(prev => prev + 1);
  };

  // useEffect to check login status via /users/me on mount
  useEffect(() => {
  setIsLoadingUser(true);
  const timer = setTimeout(() => {
     axios.get(`${API_PREFIX}/users/me_from_session`)
       .then(res => {
         setUser(res.data);
       })
       .catch(err => {
         console.log('Not logged in or failed to fetch user:', err.response?.status);
         setUser(null);
       })
       .finally(() => {
          setIsLoadingUser(false);
       });
   }, 100); // 100ms delay

   return () => clearTimeout(timer); // Cleanup timeout
  }, []);

  // const handleLogin = () => { window.location.href = '/oidc/login'; };

const handleLogin = () => {
  // call the saveState method on the SearchForm instance via the ref
    if (searchFormRef.current && typeof searchFormRef.current.saveState === 'function') {
      searchFormRef.current.saveState();
    } else {
      console.warn("SearchForm ref not available or saveState not exposed.");
    }
  window.location.href = `${API_PREFIX}/oidc/login`;
};

  const handleLogout = () => {
    axios.post(`${API_PREFIX}/auth/logout_session`)
      .then(() => {
        setUser(null); // Clear user state
        setResults(null);
        setAllCoordinates([]);
        setSelectedIds([]);
        setActiveTab('search');
        setAllBasketGroups([]);
        // setAllBasketItems([]);
        // Trigger refresh if BasketPage is visible/active
        // setBasketRefreshCounter(prev => prev + 1);
      })
      .catch(err => {
        console.error('Logout failed:', err);
        setUser(null);
      });
  };

  const handleSearchResults = (data) => {
    setResults(null);
    setAllCoordinates([]);
    setSelectedIds([]);
    // use setTimeout to allow ui to clear before setting new results
    setTimeout(() => {
        setResults(data);
        setActiveTab('results');
        if (data?.columns && data?.data) { // Outer if starts
            const s_ra_index = data.columns.indexOf('s_ra');
            const s_dec_index = data.columns.indexOf('s_dec');
            const id_index = data.columns.indexOf('obs_id');
            const s_fov_index = data.columns.indexOf('s_fov');
            if (s_ra_index !== -1 && s_dec_index !== -1 && id_index !== -1 && s_fov_index !== -1) {
                const coords = data.data.map((row) => ({
                    ra: parseFloat(row[s_ra_index]),
                    dec: parseFloat(row[s_dec_index]),
                    id: row[id_index].toString().trim(),
                    s_fov: parseFloat(row[s_fov_index]),
                }));
                setAllCoordinates(coords);
            }
        }
    }, 0);
  };

  const handleRowSelected = (selectedRowsChange) => {
    const { selectedRows } = selectedRowsChange || {};
    if (!selectedRows || !Array.isArray(selectedRows)) return;
    const ids = selectedRows.map(row => row['obs_id'].toString());
    setSelectedIds(ids);
  };

  const handleOpenBasketItem = (item) => {
    setBasketModalItem(item);
    setShowBasketModal(true);
  };

  const closeBasketModal = () => {
    setShowBasketModal(false);
    setBasketModalItem(null);
  };

  const refreshBasketGroups = () => {
    setBasketRefreshCounter(prev => prev + 1);
  };

  const handleLoadHistory = (historyItem) => {
      if (historyItem && historyItem.results) {
          console.log("Loading history item:", historyItem.id);
          // Directly set the results state with the stored results
          handleSearchResults(historyItem.results);
          // switch to the results tab
          // setActiveTab('results');
      } else {
          console.warn("Cannot load history item - missing results data.");
      }
  };

  // Render loading indicator while checking auth status
  if (isLoadingUser) {
      return <div className="container-fluid p-3 text-center"><h2>Loading...</h2></div>;
  }

  const isLoggedIn = !!user; // boolean flag for logged-in status

  return (
    <div className="container-fluid p-3">
      {/* Top Navbar */}
      <div className="d-flex justify-content-between mb-2">
        <h2>CTAO Data Explorer</h2>
        <div>
          {/* isLoggedIn flag */}
          {isLoggedIn && user ? (
            <>
              <span className="me-3 text-success">
                Logged in as {user.first_name ? `${user.first_name}` : (user.email || `User ID: ${user.id}`)}
              </span>
              <button
                className="btn btn-outline-secondary me-2"
                onClick={() => setActiveTab('profile')} // Switch to profile tab
              >
                Profile
              </button>
              <button className="btn btn-outline-danger" onClick={handleLogout}>Logout</button>
            </>
          ) : ( <button className="btn btn-outline-primary" onClick={handleLogin}>Login</button> )}
        </div>
      </div>

      {/* Tab Navigation */}
      <ul className="nav nav-tabs" role="tablist">
        <li className="nav-item">
          <button className={`nav-link ${activeTab==='search'?'active':''}`} onClick={() => setActiveTab('search')} type="button">Search</button>
        </li>
        <li className="nav-item">
          <button className={`nav-link ${activeTab==='results'?'active':''}`} onClick={() => setActiveTab('results')} type="button" disabled={!results}>Results</button>
        </li>
        {isLoggedIn && ( // Show basket/history only if logged in
            <>
        <li className="nav-item">
          <button className={`nav-link ${activeTab==='basket'?'active':''}`} onClick={() => setActiveTab('basket')} type="button">My Basket</button>
        </li>
        <li className="nav-item">
        <button className={`nav-link ${activeTab==='queryStore'?'active':''}`} onClick={() => setActiveTab('queryStore')} type="button">Query Store</button>
        </li>
        <li className="nav-item">
        <button className={`nav-link ${activeTab==='profile'?'active':''}`} onClick={() => setActiveTab('profile')} type="button">Profile</button>
        </li>
        </>
        )}
      </ul>

      {/* Tab Content */}
      <div className="tab-content mt-3">
        {/* SEARCH TAB */}
        <div className={`tab-pane fade ${activeTab==='search'?'show active':''}`} role="tabpanel">
          <div className="card">
            <div className="card-header bg-secondary text-white">Search Form</div>
            {/* Pass isLoggedIn instead of authToken */}
            <div className="card-body"><SearchForm ref={searchFormRef} setResults={handleSearchResults} isLoggedIn={isLoggedIn} /></div>
          </div>
        </div>

        {/* RESULTS TAB */}
        <div className={`tab-pane fade ${activeTab==='results'?'show active':''}`} role="tabpanel">
          {results ? (
            <>
              <div className="row">
                <div className="col-md-7 mb-3">
                  <div className="card h-100">
                    <div className="card-header bg-primary text-white">Sky Map</div>
                    <div className="card-body p-0" style={{ height: '400px', overflow: 'hidden' }}>
                      <AladinLiteViewer overlays={allCoordinates} selectedIds={selectedIds} />
                    </div>
                  </div>
                </div>
                <div className="col-md-5 mb-3">
                  <div className="card h-100">
                    <div className="card-header bg-dark text-white">Charts</div>
                    <div className="card-body d-flex flex-column" style={{ height: '400px', overflow: 'auto' }}>
                      <ul className="nav nav-tabs" id="chartTabs" role="tablist">
                        <li className="nav-item" role="presentation">
                          <button className="nav-link active" id="timeline-tab" data-bs-toggle="tab" data-bs-target="#timelinePane" type="button" role="tab" aria-controls="timelinePane" aria-selected="true">Timeline</button>
                        </li>
                        <li className="nav-item" role="presentation">
                          <button className="nav-link" id="emrange-tab" data-bs-toggle="tab" data-bs-target="#emrangePane" type="button" role="tab" aria-controls="emrangePane" aria-selected="false">EM Range</button>
                        </li>
                      </ul>
                      <div className="tab-content flex-grow-1" id="chartTabsContent">
                        <div className="tab-pane fade show active mt-2" id="timelinePane" role="tabpanel" aria-labelledby="timeline-tab">
                          <TimelineChart results={results} selectedIds={selectedIds} />
                        </div>
                        <div className="tab-pane fade mt-2" id="emrangePane" role="tabpanel" aria-labelledby="emrange-tab">
                          <EmRangeChart results={results} selectedIds={selectedIds} />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="row mt-3">
                <div className="col-12">
                  <div className="card">
                    <div className="card-header bg-info text-white">Search Results</div>
                    <div className="card-body p-0">
                      <ResultsTable
                        results={results}
                        isLoggedIn={isLoggedIn}
                        onRowSelected={handleRowSelected}
                        allBasketGroups={allBasketGroups}
                        activeBasketGroupId={activeBasketGroupId}
                        onAddedBasketItem={handleBasketItemAdded}
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
        <div className={`tab-pane fade ${activeTab==='basket'?'show active':''}`} role="tabpanel">
          {/* isLoggedIn */}
          {isLoggedIn ? (
              <BasketPage
                  isLoggedIn={isLoggedIn}
                  onOpenItem={handleOpenBasketItem}
                  onActiveGroupChange={(groupId, items) => {
                      setActiveBasketGroupId(groupId);
                      // setActiveBasketItems(items);
                  }}
                  onBasketGroupsChange={handleBasketGroupsChange}
                  refreshTrigger={basketRefreshCounter}
                  allBasketGroups={allBasketGroups}
                  activeBasketGroupId={activeBasketGroupId}
                  // activeItems={activeBasketItems}
              />
          ) : (
              <div className="alert alert-warning">Please log in to manage your basket.</div>
          )}
        </div>
        {/* QUERY STORE TAB */}
        <div className={`tab-pane fade ${activeTab==='queryStore'?'show active':''}`} role="tabpanel">
           {isLoggedIn ? ( <QueryStorePage
                            onLoadHistory={handleLoadHistory}
                            isActive={activeTab === 'queryStore'}
                            isLoggedIn={isLoggedIn}
                          /> )
           : ( <div className="alert alert-warning">Please log in to view your query history.</div> )}
        </div>
        {/* PROFILE TAB PANE */}
        <div className={`tab-pane fade ${activeTab === 'profile' ? 'show active' : ''}`} role="tabpanel">
            {isLoggedIn && user ? (
                <UserProfilePage user={user} />
            ) : (
                <div className="alert alert-warning">Please log in to view your profile.</div>
            )}
        </div>

      </div>

       {/* isLoggedIn */}
      <BasketItemModal show={showBasketModal} onClose={closeBasketModal} basketItem={basketModalItem} />
    </div>
  );
}

export default App;
