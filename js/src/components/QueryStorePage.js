import React, { useState, useEffect } from 'react';
import axios from 'axios';

// generate a summary string
const generateSummary = (item) => {
    let summary = `${new Date(item.query_date).toLocaleString()}`;
    if (item.query_params) {
        const params = item.query_params;
        const coordSys = params.coordinate_system || 'N/A';
        const radius = parseFloat(params.search_radius) || NaN;
        const radiusStr = !isNaN(radius) ? radius.toString() : '?';

        let coordStr = 'N/A';
        const raNum = parseFloat(params.ra);
        const decNum = parseFloat(params.dec);
        const lNum = parseFloat(params.l);
        const bNum = parseFloat(params.b);

        if (coordSys === 'equatorial' && !isNaN(raNum) && !isNaN(decNum)) {
            coordStr = `RA=${raNum.toFixed(3)}, Dec=${decNum.toFixed(3)}, Rad=${radiusStr}°`;
        } else if (coordSys === 'galactic' && !isNaN(lNum) && !isNaN(bNum)) {
             coordStr = `l=${lNum.toFixed(3)}, b=${bNum.toFixed(3)}, Rad=${radiusStr}°`;
        } else if (!isNaN(raNum) && !isNaN(decNum)){
            coordStr = `RA=${raNum.toFixed(3)}, Dec=${decNum.toFixed(3)}, Rad=${radiusStr}°`;
        }
        summary += ` | ${coordStr}`;
        if (params.obs_start && params.obs_end) {
            summary += ` | Time: ${params.obs_start} - ${params.obs_end}`;
        }
    }
     const resultCount = Array.isArray(item.results?.data) ? item.results.data.length : '?';
     summary += ` | ${resultCount} results`;
     if(item.adql_query_hash) {
        summary += ` | Hash: ${item.adql_query_hash.substring(0, 8)}...`;
     }
    return summary;
};


function QueryStorePage({ onLoadHistory, isActive, isLoggedIn }) {
    const [history, setHistory] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    console.log("QueryStorePage: Rendering with history state:", history);

    const fetchHistory = () => {
        console.log("QueryStorePage: Attempting to fetch history...");
        setIsLoading(true);
        setError(null);
        axios.get('/query-history')
            .then(res => {
                console.log("QueryStorePage: History data received raw:", res);
                console.log("QueryStorePage: History data received:", res.data);
                setHistory(res.data || []);
            })
            .catch(err => {
                console.error("Error fetching query history:", err);
                setError("Failed to load query history.");
                setHistory([]);
            })
            .finally(() => {
                setIsLoading(false);
            });
    };

    // effect to fetch data when tab is active and user logged in
    useEffect(() => {
        console.log("QueryStorePage: useEffect run. isActive:", isActive, "isLoggedIn:", isLoggedIn);
        if (isActive && isLoggedIn) {
            fetchHistory();
        } else if (!isLoggedIn) {
            // clear history if user logs out
             setHistory([]);
             setError(null);
        }
    }, [isActive, isLoggedIn]);

    const handleDelete = (historyId) => {
        if (!window.confirm("Are you sure you want to delete this history item?")) {
            return;
        }
        setError(null);
        axios.delete(`/query-history/${historyId}`)
         .then(() => {
             console.log(`History item ${historyId} deleted successfully.`);
             fetchHistory();
         })
         .catch(err => {
             console.error("Error deleting history item:", err);
             setError("Failed to delete history item. Please try again.");
         });
    };

    // render loading state
    if (isLoading) {
        return (
            <div className="text-center p-5">
                <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading Query History...</span>
                </div>
                <p className="mt-2">Loading Query History...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="alert alert-danger d-flex justify-content-between align-items-center" role="alert">
                {error}
                <button className="btn btn-danger btn-sm" onClick={fetchHistory}>Retry</button>
            </div>
        );
    }

    return (
        <div className="query-store-page">
            <h4>Stored Queries</h4>
            {history.length > 0 ? (
                <ul className="list-group">
                    {history.map(item => {
                    let summaryContent = 'Error generating summary';
                        try {
                            summaryContent = generateSummary(item);
                        } catch (summaryError) {
                        console.error("Error in generateSummary for item:", item, summaryError);
                        }
                    return ( // 'item' is 't' in the error trace
                        <li key={item.id} className="list-group-item d-flex justify-content-between align-items-center flex-wrap">

                            <div className="me-3 flex-grow-1" style={{ minWidth: '200px' }}>
                                {generateSummary(item)}
                            </div>
                            <div className="mt-2 mt-md-0">
                                <button
                                    className="btn btn-sm btn-outline-primary me-2"
                                    onClick={() => onLoadHistory(item)}
                                    disabled={!item.results || !Array.isArray(item.results?.data) || item.results.data.length === 0}
                                    title={(item.results && Array.isArray(item.results?.data) && item.results.data.length > 0) ? "Load results" : "No results data stored"}
                                >
                                    Load Results
                                </button>
                                <button
                                    className="btn btn-sm btn-outline-danger"
                                     onClick={() => handleDelete(item.id)}
                                     title="Delete this history item"
                                >
                                    Delete
                                </button>
                            </div>
                        </li>
                        );
                    })}
                </ul>
            ) : (
                <p>No query history found.</p>
            )}
        </div>
    );
}

export default QueryStorePage;
