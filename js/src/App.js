import React, { useState, useEffect, useRef, useCallback } from "react";
import { Routes, Route, Navigate, NavLink, useNavigate, useLocation } from "react-router-dom";
import OpusJobDetailPage from "./components/OpusJobDetailPage";
import OpusJobsPage from "./components/OpusJobsPage";
import axios from "axios";
import SearchForm from "./components/SearchForm";
import ResultsTable from "./components/ResultsTable";
import AladinLiteViewer from "./components/AladinLiteViewer";
import TimelineChart from "./components/TimelineChart";
import EmRangeChart from "./components/EmRangeChart";
import BasketPage from "./components/BasketPage";
import UserProfilePage from "./components/UserProfilePage";
import QueryStorePage from "./components/QueryStorePage";
import Header from "./components/Header";
import Footer from "./components/Footer";
import { AUTH_PREFIX } from "./index";
import { launchOidcLogin } from "./components/oidcHelper";

/* Guards */

function RequireAuth({ isLoggedIn, children }) {
  const location = useLocation();
  if (!isLoggedIn) {
    return <Navigate to="/search" replace state={{ from: location }} />;
  }
  return children;
}

function RequireResults({ results, children }) {
  const location = useLocation();
  if (!results) {
    return <Navigate to="/search" replace state={{ from: location }} />;
  }
  return children;
}

/* Modal */

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
    <div className="modal show" style={{ display: "block" }} role="dialog">
      <div className="modal-dialog modal-xl" role="document">
        <div className="modal-content">
          <div className="modal-header bg-primary text-white">
            <h5 className="modal-title">Basket Item: {rowData.obs_id || "N/A"}</h5>
            <button type="button" className="btn-close" onClick={onClose}></button>
          </div>

          <div className="modal-body">
            <div className="row">
              <div className="col-md-7 mb-3">
                <div className="card h-100">
                  <div className="card-header ctao-header-primary">Sky Map</div>
                  <div className="card-body p-0" style={{ height: "400px", overflow: "hidden" }}>
                    <AladinLiteViewer overlays={allCoordinates} selectedIds={[]} initialFov={initialFov} />
                  </div>
                </div>
              </div>

              <div className="col-md-5 mb-3">
                <div className="card h-100">
                  <div className="card-header ctao-header-primary">Charts</div>
                  <div className="card-body d-flex flex-column" style={{ height: "400px", overflow: "auto" }}>
                    <ul className="nav nav-tabs" id="modalChartTabs" role="tablist">
                      <li className="nav-item" role="presentation">
                        <button
                          className="nav-link active"
                          id="timeline-tab-modal"
                          data-bs-toggle="tab"
                          data-bs-target="#timelinePaneModal"
                          type="button"
                          role="tab"
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
                        >
                          EM Range
                        </button>
                      </li>
                    </ul>

                    <div className="tab-content flex-grow-1" id="modalChartTabsContent">
                      <div className="tab-pane fade show active mt-2" id="timelinePaneModal" role="tabpanel">
                        <TimelineChart results={fakeResults} selectedIds={[]} />
                      </div>
                      <div className="tab-pane fade mt-2" id="emrangePaneModal" role="tabpanel">
                        <EmRangeChart results={fakeResults} selectedIds={[]} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

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

/* Main Tabs App */

function TabsApp() {
  const navigate = useNavigate();

  const [results, setResults] = useState(null);
  const [allCoordinates, setAllCoordinates] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);

  const [user, setUser] = useState(null);
  const [isLoadingUser, setIsLoadingUser] = useState(true);

  const [showBasketModal, setShowBasketModal] = useState(false);
  const [basketModalItem, setBasketModalItem] = useState(null);
  const [activeBasketGroupId, setActiveBasketGroupId] = useState(null);
  const [basketRefreshCounter, setBasketRefreshCounter] = useState(0);
  const [allBasketGroups, setAllBasketGroups] = useState([]);

  const searchFormRef = useRef(null);

  // Results layout split positions
  const [resultsSplitX, setResultsSplitX] = useState(65);
  const [resultsSplitY, setResultsSplitY] = useState(55);

  const topRowRef = useRef(null);
  const resultsLayoutRef = useRef(null);

  const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

  const onDragSplitX = (e) => {
    const el = topRowRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = (x / rect.width) * 100;
    setResultsSplitX(clamp(pct, 0, 100));
  };

  const onDragSplitY = (e) => {
    const el = resultsLayoutRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const y = e.clientY - rect.top;
    const pct = (y / rect.height) * 100;
    setResultsSplitY(clamp(pct, 0, 100));
  };

  const startPointerDrag = (onMove) => (e) => {
    e.preventDefault();
    const target = e.currentTarget;
    target.setPointerCapture?.(e.pointerId);

    const move = (ev) => onMove(ev);
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const handleIdsSelected = useCallback((ids) => {
    const newIds = (ids || []).map(String);
    setSelectedIds((prev) => {
      const same = prev.length === newIds.length && prev.every((id) => newIds.includes(id));
      return same ? prev : newIds;
    });
  }, []);

  const handleBasketGroupsChange = useCallback((groups) => {
    const normalized = (groups || []).map(g => ({ ...g, id: String(g.id) }));

    setAllBasketGroups(normalized);

    setActiveBasketGroupId((prev) => {
      const prevStr = prev == null ? null : String(prev);
      if (!normalized.length) return null;
      if (prevStr && normalized.some((g) => g.id === prevStr)) return prevStr;
      return normalized[0].id;
    });
  }, []);

  const handleActiveGroupChange = useCallback((groupId) => {
    setActiveBasketGroupId(groupId == null ? null : String(groupId));
  }, []);

  const handleBasketItemAdded = (newItem, addedToGroupId) => {
    setAllBasketGroups((prevGroups) =>
      prevGroups.map((group) => {
        if (group.id === addedToGroupId) {
          const itemExists = group.saved_datasets?.some((item) => item.id === newItem.id);
          if (!itemExists) {
            return { ...group, saved_datasets: [...(group.saved_datasets || []), newItem] };
          }
        }
        return group;
      })
    );
  };

  // Restore after OIDC roundtrip
  useEffect(() => {
    try {
      const cached = sessionStorage.getItem("SavedResults");
      const coords = sessionStorage.getItem("SavedCoords");
      const ids = sessionStorage.getItem("SavedIds");

      if (coords) {
        setAllCoordinates(JSON.parse(coords));
        sessionStorage.removeItem("SavedCoords");
      }
      if (ids) {
        setSelectedIds(JSON.parse(ids));
        sessionStorage.removeItem("SavedIds");
      }

      if (cached) {
        const parsed = JSON.parse(cached);
        sessionStorage.removeItem("SavedResults");
        // set results then go to results route
        setTimeout(() => {
          setResults(parsed);
          navigate("/results", { replace: true });
        }, 0);
      }
    } catch {
      /* ignore */
    }
  }, [navigate]);

  // Session lost -> go back to search route
  useEffect(() => {
    function handleLost() {
      setUser(null);
      localStorage.removeItem("hadSession");
      navigate("/search", { replace: true });
    }
    window.addEventListener("session-lost", handleLost);
    return () => window.removeEventListener("session-lost", handleLost);
  }, [navigate]);

  // Check login status on mount
  useEffect(() => {
    setIsLoadingUser(true);
    const timer = setTimeout(() => {
      axios
        .get(`${AUTH_PREFIX}/users/me_from_session`, {
          skipAuthErrorHandling: true,
          validateStatus: (s) => s === 200 || s === 401,
        })
        .then((res) => {
          if (res.status === 200) {
            setUser(res.data);
            localStorage.setItem("hadSession", "true");
          } else {
            setUser(null);
          }
        })
        .catch(() => setUser(null))
        .finally(() => setIsLoadingUser(false));
    }, 100);

    return () => clearTimeout(timer);
  }, []);

  const isLoggedIn = !!user;
  const lastOpus = localStorage.getItem("lastOpusJobId");

  const handleLogin = () =>
    launchOidcLogin({
      AUTH_PREFIX,
      searchFormRef,
      results,
      coords: allCoordinates,
      ids: selectedIds,
    });

  const handleLogout = () => {
    axios
      .post(`${AUTH_PREFIX}/auth/logout_session`)
      .then(() => {
        setUser(null);
        localStorage.removeItem("hadSession");
        setResults(null);
        setAllCoordinates([]);
        setSelectedIds([]);
        setAllBasketGroups([]);
        navigate("/search", { replace: true });
      })
      .catch(() => {
        setUser(null);
        navigate("/search", { replace: true });
      });
  };

  const handleSearchResults = (data) => {
    setResults(null);
    setAllCoordinates([]);
    setSelectedIds([]);

    setTimeout(() => {
      setResults(data);

      if (data?.columns && data?.data) {
        const s_ra_index = data.columns.indexOf("s_ra");
        const s_dec_index = data.columns.indexOf("s_dec");
        const id_index = data.columns.indexOf("obs_id");
        const s_fov_index = data.columns.indexOf("s_fov");

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

      // Navigate to the results route
      navigate("/results");
    }, 0);
  };

  const handleRowSelected = (state) => {
    const ids = (state?.selectedRows || []).map((r) => r.obs_id.toString());
    handleIdsSelected(ids);
  };

  const handleOpenBasketItem = (item) => {
    setBasketModalItem(item);
    setShowBasketModal(true);
  };

  const closeBasketModal = () => {
    setShowBasketModal(false);
    setBasketModalItem(null);
  };

  const handleLoadHistory = (historyItem) => {
    if (historyItem?.results) {
      handleSearchResults(historyItem.results);
    }
  };

  // Loading state
  if (isLoadingUser) {
    return (
      <div className="container-fluid p-3 text-center">
        <h2>Loading...</h2>
      </div>
    );
  }

  return (
    <>
      <Header
        isLoggedIn={isLoggedIn}
        user={user}
        lastOpus={lastOpus}
        onLogin={handleLogin}
        onLogout={handleLogout}
        // if Header needs to navigate, give it this:
        onNavigate={(path) => navigate(path)}
      />

      <div className="app-page">
        {/* Tabs bar */}
        <div className="subnav">
          <ul className="nav nav-tabs nav-tabs-overflow">
            <li className="nav-item">
              <NavLink className="nav-link" to="/search">
                Search
              </NavLink>
            </li>

            <li className="nav-item">
              {/* Keep clickable but guarded by route */}
              <NavLink
                className={`nav-link ${!results ? "disabled" : ""}`}
                to="/results"
                onClick={(e) => {
                  if (!results) e.preventDefault();
                }}
              >
                Results
              </NavLink>
            </li>

            {isLoggedIn && (
              <>
                <li className="nav-item">
                  <NavLink className="nav-link" to="/basket">
                    My Basket
                  </NavLink>
                </li>
                <li className="nav-item">
                  <NavLink className="nav-link" to="/opus">
                    Preview Jobs
                  </NavLink>
                </li>
                <li className="nav-item">
                  <NavLink className="nav-link" to="/query-store">
                    Query Store
                  </NavLink>
                </li>
                <li className="nav-item">
                  <NavLink className="nav-link" to="/profile">
                    Profile
                  </NavLink>
                </li>
              </>
            )}
          </ul>
        </div>

        <main className="app-main container-fluid p-3">
          <Routes>
            {/* Default */}
            <Route path="/" element={<Navigate to="/search" replace />} />

            {/* Search */}
            <Route
              path="/search"
              element={
                <div className="card card-noheader">
                  <div className="card-body">
                    <SearchForm ref={searchFormRef} setResults={handleSearchResults} isLoggedIn={isLoggedIn} />
                  </div>
                </div>
              }
            />

            {/* Results (guarded) */}
            <Route
              path="/results"
              element={
                <RequireResults results={results}>
                  <div className="results-layout" ref={resultsLayoutRef}>
                    <div className="results-top" ref={topRowRef} style={{ height: `${resultsSplitY}%` }}>
                      <div className="results-pane" style={{ width: `${resultsSplitX}%` }}>
                        <div className="card card-noheader h-100">
                          <div className="card-body p-0 h-100" style={{ overflow: "hidden" }}>
                            <AladinLiteViewer
                              overlays={allCoordinates}
                              selectedIds={selectedIds}
                              onSelectIds={handleIdsSelected}
                            />
                          </div>
                        </div>
                      </div>

                      <div
                        className="splitter splitter-vertical"
                        onPointerDown={startPointerDrag(onDragSplitX)}
                        title="Drag to resize"
                      />

                      <div className="results-pane" style={{ width: `${100 - resultsSplitX}%` }}>
                        <div className="card card-noheader h-100">
                          <div className="card-body d-flex flex-column h-100" style={{ overflow: "hidden", minHeight: 0 }}>
                            <ul className="nav nav-tabs" id="chartTabs" role="tablist">
                              <li className="nav-item" role="presentation">
                                <button className="nav-link active" id="timeline-tab" data-bs-toggle="tab" data-bs-target="#timelinePane" type="button" role="tab">
                                  Timeline
                                </button>
                              </li>
                              <li className="nav-item" role="presentation">
                                <button className="nav-link" id="emrange-tab" data-bs-toggle="tab" data-bs-target="#emrangePane" type="button" role="tab">
                                  EM Range
                                </button>
                              </li>
                            </ul>

                            <div className="tab-content flex-grow-1" id="chartTabsContent" style={{ overflow: "hidden", minHeight: 0 }}>
                              <div className="tab-pane fade show active" id="timelinePane" role="tabpanel" style={{ height: "100%", minHeight: 0 }}>
                                <TimelineChart results={results} selectedIds={selectedIds} onSelectIds={handleIdsSelected} />
                              </div>
                              <div className="tab-pane fade" id="emrangePane" role="tabpanel" style={{ height: "100%", minHeight: 0 }}>
                                <EmRangeChart results={results} selectedIds={selectedIds} onSelectIds={handleIdsSelected} />
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div
                      className="splitter splitter-horizontal"
                      onPointerDown={startPointerDrag(onDragSplitY)}
                      title="Drag to resize"
                    />

                    <div className="results-bottom" style={{ height: `${100 - resultsSplitY}%` }}>
                      <div className="card card-noheader h-100">
                        <div className="card-body p-0 h-100" style={{ overflow: "hidden" }}>
                          <div style={{ height: "100%", overflow: "auto" }}>
                            <ResultsTable
                              results={results}
                              isLoggedIn={isLoggedIn}
                              selectedIds={selectedIds}
                              onRowSelected={handleRowSelected}
                              allBasketGroups={allBasketGroups}
                              activeBasketGroupId={activeBasketGroupId}
                              onAddedBasketItem={handleBasketItemAdded}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </RequireResults>
              }
            />

            {/* Basket (auth) */}
            <Route
              path="/basket"
              element={
                <RequireAuth isLoggedIn={isLoggedIn}>
                  <BasketPage
                    isLoggedIn={isLoggedIn}
                    onOpenItem={handleOpenBasketItem}
                    onActiveGroupChange={handleActiveGroupChange}
                    onBasketGroupsChange={handleBasketGroupsChange}
                    refreshTrigger={basketRefreshCounter}
                    allBasketGroups={allBasketGroups}
                    activeBasketGroupId={activeBasketGroupId}
                  />
                </RequireAuth>
              }
            />

            {/* Opus jobs (auth) */}
            <Route
              path="/opus"
              element={
                <RequireAuth isLoggedIn={isLoggedIn}>
                  <OpusJobsPage isActive={true} />
                </RequireAuth>
              }
            />

            <Route
              path="/opus/jobs/:jobId"
              element={
                <RequireAuth isLoggedIn={isLoggedIn}>
                  <OpusJobDetailPage />
                </RequireAuth>
              }
            />

            {/* Query Store (auth) */}
            <Route
              path="/query-store"
              element={
                <RequireAuth isLoggedIn={isLoggedIn}>
                  <QueryStorePage onLoadHistory={handleLoadHistory} isActive={true} isLoggedIn={isLoggedIn} />
                </RequireAuth>
              }
            />

            {/* Profile (auth) */}
            <Route
              path="/profile"
              element={
                <RequireAuth isLoggedIn={isLoggedIn}>
                  <UserProfilePage user={user} />
                </RequireAuth>
              }
            />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/search" replace />} />
          </Routes>
        </main>

        <Footer />
      </div>

      <BasketItemModal show={showBasketModal} onClose={closeBasketModal} basketItem={basketModalItem} />
    </>
  );
}

/* App top-level routes */

export default function App() {
  return (
    <Routes>
      <Route path="/*" element={<TabsApp />} />
    </Routes>
  );
}
