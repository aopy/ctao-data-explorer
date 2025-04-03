import React, { useState, useEffect } from 'react';
import axios from 'axios';

const formatTmin = (mjd) => {
  if (!mjd || isNaN(mjd)) return '';
  const MJD_UNIX_EPOCH = 40587;
  const msPerDay = 86400000;
  const unixTime = (mjd - MJD_UNIX_EPOCH) * msPerDay;
  return new Date(unixTime).toLocaleString();
};

function BasketPage({ isLoggedIn, onOpenItem, onActiveGroupChange, refreshTrigger, activeItems, onBasketGroupsChange }) {
  const [basketGroups, setBasketGroups] = useState([]);
  const [activeGroup, setActiveGroup] = useState(null);
  const [newGroupName, setNewGroupName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchBasketGroups = async () => {
     // Only fetch if logged in
     if (!isLoggedIn) {
       setBasketGroups([]);
       setActiveGroup(null);
       setError(null);
       if (onBasketGroupsChange) onBasketGroupsChange([]);
       if (onActiveGroupChange) onActiveGroupChange(null, []);
       return;
     }

    setIsLoading(true);
    setError(null);
    try {
      const res = await axios.get('/basket/groups');
      const groups = res.data || [];

      if (groups.length === 0) {
        setBasketGroups([]);
        setActiveGroup(null);
         if (onBasketGroupsChange) onBasketGroupsChange([]);
         if (onActiveGroupChange) onActiveGroupChange(null, []);

        console.log("No groups found, creating default 'My Basket'");
        await axios.post('/basket/groups', { name: 'My Basket' });
        const res2 = await axios.get('/basket/groups');
        const defaultGroups = res2.data || [];
        setBasketGroups(defaultGroups);
        const firstGroup = defaultGroups[0] || null;
        setActiveGroup(firstGroup);
        if (onBasketGroupsChange) onBasketGroupsChange(defaultGroups);
        if (onActiveGroupChange) onActiveGroupChange(firstGroup?.id, firstGroup?.items || []);

      } else {
        setBasketGroups(groups);
        // Maintain active group selection or default to first
        let currentActive = activeGroup ? groups.find(g => g.id === activeGroup.id) : null;
        if (!currentActive && groups.length > 0) {
            currentActive = groups[0]; // Default to first group if previous active is gone
        }
        setActiveGroup(currentActive);
        if (onBasketGroupsChange) onBasketGroupsChange(groups);
        if (onActiveGroupChange) onActiveGroupChange(currentActive?.id, currentActive?.items || []);
      }
    } catch (err) {
      console.error('Error fetching basket groups', err);
      setError('Failed to load basket data. Please try again later.');
      setBasketGroups([]);
      setActiveGroup(null);
      if (onBasketGroupsChange) onBasketGroupsChange([]);
       if (onActiveGroupChange) onActiveGroupChange(null, []);
    } finally {
      setIsLoading(false);
    }
  };

  // useEffect depends on isLoggedIn and refreshTrigger
  useEffect(() => {
    fetchBasketGroups();
  }, [isLoggedIn, refreshTrigger]); // Re-fetch if login status changes or refresh is triggered

  const handleSetActiveGroup = (group) => {
    setActiveGroup(group);
    if (onActiveGroupChange) {
      onActiveGroupChange(group.id, group.items || []);
    }
  };

  const createNewGroup = async () => {
    if (!newGroupName.trim()) return;
    setError(null);
    try {
      const name = newGroupName.trim();
      const res = await axios.post('/basket/groups', { name });
      // await fetchBasketGroups(); // fetchBasketGroups will update state
      setNewGroupName('');
      if (res.data) {
         // Add the new group locally
         setBasketGroups(prev => [...prev, res.data]);
         handleSetActiveGroup(res.data);
         // fetchBasketGroups();
         if (onBasketGroupsChange) onBasketGroupsChange([...basketGroups, res.data]);
      } else {
          fetchBasketGroups(); // Fallback refresh
      }

    } catch (err) {
      console.error('Error creating new basket group', err);
      setError('Failed to create group.');
    }
  };

  const renameGroup = async (groupId, newName) => {
    if (!newName.trim() || !activeGroup || newName === activeGroup.name) return;
    setError(null);
    try {
      await axios.put(`/basket/groups/${groupId}`, { name: newName }); // No headers
      // Update local state immediately for responsiveness
      const updatedGroups = basketGroups.map(g =>
        g.id === groupId ? { ...g, name: newName } : g
      );
      setBasketGroups(updatedGroups);
      setActiveGroup(prev => prev && prev.id === groupId ? { ...prev, name: newName } : prev);
       if (onBasketGroupsChange) onBasketGroupsChange(updatedGroups);
    } catch (err) {
      console.error('Error renaming basket group', err);
      setError('Failed to rename group.');
       // fetchBasketGroups();
    }
  };

  const deleteGroup = async (groupId) => {
     if (!window.confirm(`Are you sure you want to delete the basket group "${activeGroup?.name}" and all its items?`)) {
         return;
     }
     setError(null);
    try {
      await axios.delete(`/basket/groups/${groupId}`);
      // Trigger full refresh to get the new state
      fetchBasketGroups();
    } catch (err) {
      console.error('Error deleting basket group', err);
       setError('Failed to delete group.');
    }
  };

  const deleteItem = async (itemId) => {
    setError(null);
    try {
      await axios.delete(`/basket/${itemId}`); // No headers
      // Update local state immediately
      if (activeGroup) {
          const updatedItems = activeGroup.items.filter(item => item.id !== itemId);
          const updatedGroup = { ...activeGroup, items: updatedItems };
          setActiveGroup(updatedGroup); // Update active group state

          // Update the main basketGroups list state
          const updatedGroups = basketGroups.map(g =>
              g.id === activeGroup.id ? updatedGroup : g
          );
          setBasketGroups(updatedGroups);

          // Notify parent component
          if (onActiveGroupChange) {
              onActiveGroupChange(updatedGroup.id, updatedItems);
          }
          if (onBasketGroupsChange) {
              onBasketGroupsChange(updatedGroups);
          }
      } else {
          fetchBasketGroups(); // Fallback if something is out of sync
      }
    } catch (err) {
        if (err.response && err.response.status === 404) {
          console.warn(`Item ${itemId} not found; may have been deleted.`);
          fetchBasketGroups(); // Refresh state
        } else {
          console.error('Error deleting basket item', err);
          setError('Failed to delete item.');
        }
    }
  };

  const openItemModal = (item) => {
    onOpenItem(item);
  };

  // Determine items to show based on local activeGroup state
  const itemsToShow = activeGroup ? activeGroup.items || [] : [];

  // Handle loading and error states
  if (isLoading) {
      return <div className="mt-3 text-center">Loading basket...</div>;
  }

  if (error) {
      return <div className="alert alert-danger mt-3">{error}</div>;
  }

  if (!isLoggedIn) {
      return <div className="alert alert-warning mt-3">Please log in to view your basket.</div>;
  }


  return (
    <div className="mt-3">
       {/* Active Basket Section */}
       {activeGroup ? (
        <div className="card mb-3">
            <div className="card-header d-flex justify-content-between align-items-center">
                {/* Editable Name - using controlled input */}
                <input
                    type="text"
                    className="form-control form-control-sm w-50"
                    value={activeGroup.name}
                    onChange={(e) => setActiveGroup({ ...activeGroup, name: e.target.value })}
                    onBlur={() => renameGroup(activeGroup.id, activeGroup.name)} // Rename on blur
                    onKeyPress={(e) => { if (e.key === 'Enter') e.target.blur(); }} // Rename on Enter
                    aria-label="Current basket name"
                />
                <button
                    className="btn btn-sm btn-danger"
                    onClick={() => deleteGroup(activeGroup.id)}
                    disabled={basketGroups.length <= 1} // Disable delete if it's the only group
                    title={basketGroups.length <= 1 ? "Cannot delete the only basket" : "Delete this basket"}
                >
                    Delete Basket
                </button>
            </div>
            <div className="card-body">
                {itemsToShow.length > 0 ? (
                <ul className="list-group list-group-flush">
                    {itemsToShow.map((item) => {
                        const ds = item.dataset_json || {};
                        const targetName = ds.target_name || 'N/A';
                        const tmin_str = formatTmin(ds.t_min) || 'N/A';
                        return (
                            <li key={item.id} className="list-group-item d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>{item.obs_id}</strong> <small>| {targetName} | {tmin_str}</small>
                                </div>
                                <div>
                                    <button
                                        className="btn btn-sm btn-outline-primary me-2"
                                        onClick={() => openItemModal(item)}
                                    >
                                        View
                                    </button>
                                    <button
                                        className="btn btn-sm btn-outline-danger"
                                        onClick={() => deleteItem(item.id)}
                                    >
                                        Delete
                                    </button>
                                </div>
                            </li>
                        );
                    })}
                </ul>
                ) : (
                <p className="text-muted">No items in this basket.</p>
                )}
            </div>
        </div>
       ) : (
           <div className="alert alert-info">You have no baskets. Create one below.</div>
       )}


      {/* Other Basket Groups Section */}
      {basketGroups.length > 1 && (
        <div className="mb-3">
          <h5>Other Baskets</h5>
          <div className="list-group">
            {basketGroups
              .filter((group) => !activeGroup || group.id !== activeGroup.id)
              .map((group) => (
                <button
                  key={group.id}
                  type="button"
                  className="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                  onClick={() => handleSetActiveGroup(group)}
                >
                  {group.name}
                  <span className="badge bg-secondary rounded-pill">{group.items?.length || 0} items</span>
                </button>
              ))}
          </div>
        </div>
      )}


      {/* Create New Group Section */}
      <div className="mb-3">
        <h5>Create New Basket</h5>
        <div className="input-group">
          <input
            type="text"
            className="form-control"
            placeholder="New basket name"
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            onKeyPress={(e) => { if (e.key === 'Enter') createNewGroup(); }}
          />
          <button className="btn btn-outline-primary" onClick={createNewGroup} disabled={!newGroupName.trim()}>
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

export default BasketPage;
