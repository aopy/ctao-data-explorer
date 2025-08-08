import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { API_PREFIX } from '../index';
import { mjdToDate, formatDateTimeStrings } from './datetimeUtils';

const formatTmin = (mjd) => {
  if (mjd == null || mjd === '') return '';
  const mjdNum = Number(String(mjd).replace(',', '.'));
  if (!Number.isFinite(mjdNum)) return '';
  const date = mjdToDate(mjdNum);
  if (!date) return '';
  const { dateStr, timeStr } = formatDateTimeStrings(date); // both UTC
  return `${dateStr} ${timeStr} UTC`;
};

function BasketPage({ isLoggedIn, onOpenItem, onActiveGroupChange, refreshTrigger,
onBasketGroupsChange, allBasketGroups = [], activeBasketGroupId }) {
  const [basketGroups, setBasketGroups] = useState([]);
  const [newGroupName, setNewGroupName] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [editingGroupName, setEditingGroupName] = useState('');

  const [tminTTLabels, setTminTTLabels] = useState({}); // { '53343.92': '04/12/2004 22:04:48 TT', ... }

  // Format "YYYY-MM-DDThh:mm:ss.sss" → "dd/MM/yyyy hh:mm:ss TT"
  const formatTtIso = (tt_isot) => {
    if (!tt_isot) return '';
    const [d, t] = tt_isot.split('T');
    const [y, m, day] = d.split('-');
    return `${day}/${m}/${y} ${t.slice(0, 8)} TT`;
  };

  const activeGroup = useMemo(() => {
      if (!activeBasketGroupId) return null;
      return allBasketGroups.find(group => group.id === activeBasketGroupId);
    }, [allBasketGroups, activeBasketGroupId]);

  // Refresh TT labels whenever the visible items change
  useEffect(() => {
    const items = (activeGroup ? activeGroup.saved_datasets || [] : []);
    const uniqueMjds = Array.from(
      new Set(
        items
          .map((it) => it?.dataset_json?.t_min)
          .filter((v) => v != null)
          .map((v) => Number(String(v).replace(',', '.')))
          .filter((n) => Number.isFinite(n))
      )
    );
    if (!uniqueMjds.length) { setTminTTLabels({}); return; }
    let cancelled = false;
    (async () => {
      try {
        const pairs = await Promise.all(
          uniqueMjds.map(async (m) => {
            const resp = await axios.post('/api/convert_time', {
              value: String(m),
              input_format: 'mjd',
              input_scale: 'tt'
            });
            return [String(m), formatTtIso(resp.data.tt_isot)];
          })
        );
        if (!cancelled) {
          const map = Object.fromEntries(pairs);
          setTminTTLabels(map);
        }
      } catch {
        if (!cancelled) setTminTTLabels({});
      }
    })();
    return () => { cancelled = true; };
  }, [activeGroup]);

  useEffect(() => {
    if (isLoggedIn) axios.get(`${API_PREFIX}/users/me_from_session`);
  }, [isLoggedIn, activeBasketGroupId]);


  useEffect(() => {
      setEditingGroupName(activeGroup?.name || '');
  }, [activeGroup]);

  const fetchBasketGroups = async () => {
     // Only fetch if logged in
     if (!isLoggedIn) {
       // setActiveGroup(null);
      setError(null);
      if (onBasketGroupsChange) onBasketGroupsChange([]);
      if (onActiveGroupChange) onActiveGroupChange(null, []);
      return;
     }

    setIsLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API_PREFIX}/basket/groups`);
      const groups = res.data || [];
      // Let parent know about the fetched groups
      if (onBasketGroupsChange) onBasketGroupsChange(groups);
      // Use the activeBasketGroupId passed via props as the source of truth
      let idToActivate = activeBasketGroupId;
      if ((!idToActivate || !groups.some(g => g.id === idToActivate)) && groups.length > 0) {
          // default to the first group's id
          idToActivate = groups[0].id;
      }
      const groupToActivate = groups.find(g => g.id === idToActivate);
      // Tell the parent component which group ID is active and its datasets
      if (onActiveGroupChange && groupToActivate) {
          onActiveGroupChange(groupToActivate.id, groupToActivate.saved_datasets || []);
      } else if (onActiveGroupChange) {
          // If no group ended up being activated
          onActiveGroupChange(null, []);
      }
    } catch (err) {
       console.error('Error fetching basket groups', err);
       setError('Failed to load basket data.');
       if (onBasketGroupsChange) onBasketGroupsChange([]);
       if (onActiveGroupChange) onActiveGroupChange(null, []);
    } finally {
      setIsLoading(false);
    }
  };

  // useEffect depends on isLoggedIn and refreshTrigger
  useEffect(() => {
    fetchBasketGroups();
  }, [isLoggedIn, refreshTrigger]);

  const handleSetActiveGroup = (group) => {
    // setActiveGroup(group);
    if (onActiveGroupChange) {
      onActiveGroupChange(group.id, group.saved_datasets || []);
    }
  };

  const createNewGroup = async () => {
    if (!newGroupName.trim()) {
        // Provide feedback to the user that name is needed?
        return;
    }
    setError(null);
    // Set loading state for the create button
    // setIsLoadingCreate(true);

    try {
      const name = newGroupName.trim();
      // Make the API call to create the group
      await axios.post(`${API_PREFIX}/basket/groups`, { name });

      setNewGroupName('');
      fetchBasketGroups();

    } catch (err) {
      console.error('Error creating new basket group', err);
      setError('Failed to create group. Please try again.');
    } finally {
      // Reset loading state
      // setIsLoadingCreate(false);
    }
  };

  const renameGroup = async (groupId, newName) => {
    const trimmedName = newName.trim();
    if (!trimmedName || !activeGroup || trimmedName === activeGroup.name) {
        setEditingGroupName(activeGroup?.name || '');
        return;
    }
    setError(null);
    try {
      await axios.put(`${API_PREFIX}/basket/groups/${groupId}`, { name: trimmedName });
      fetchBasketGroups();
    } catch (err) {
      console.error('Error renaming basket group', err);
      setError('Failed to rename group.');
      setEditingGroupName(activeGroup?.name || '');
    }
  };

  const deleteGroup = async (groupId) => {
    // Add confirmation dialog
    if (!window.confirm(`Are you sure you want to delete this basket group? This cannot be undone.`)) {
        return;
    }
    setError(null);
    try {
      await axios.delete(`${API_PREFIX}/basket/groups/${groupId}`);
      fetchBasketGroups();
    } catch (err) {
      console.error('Error deleting basket group', err);
      setError('Failed to delete group.');
    }
  };

  const deleteItem = async (itemId) => {
    if (!activeGroup) {
        setError("No active group selected to delete from.");
        return;
    }
    setError(null);
    try {
      await axios.delete(`${API_PREFIX}/basket/groups/${activeGroup.id}/items/${itemId}`);

      fetchBasketGroups();

    } catch (err) {
       if (err.response && err.response.status === 404) {
         setError(`Item or group not found.`);
         fetchBasketGroups();
       } else {
         console.error('Error deleting basket item link', err);
         setError('Failed to delete item from basket.');
       }
    }
  };

  const duplicateGroup = async (groupId) => {
  setError(null);
  try {
    await axios.post(`${API_PREFIX}/basket/groups/${groupId}/duplicate`);
    fetchBasketGroups();
  } catch (err) {
    console.error('Error duplicating basket group', err);
    setError('Failed to duplicate group.');
  }
  };

  const openItemModal = (item) => {
    onOpenItem(item);
  };

  // Determine items to show based on local activeGroup state
  const itemsToShow = activeGroup ? activeGroup.saved_datasets || [] : [];

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
                    value={editingGroupName}
                    onChange={(e) => setEditingGroupName(e.target.value)}
                    onBlur={() => renameGroup(activeGroup.id, editingGroupName)}// Rename on blur
                    onKeyPress={(e) => { if (e.key === 'Enter') renameGroup(activeGroup.id, editingGroupName); }}  // Rename on Enter
                    aria-label="Current basket name"
                    placeholder="Basket name..."
                />
                {/* Duplicate basket */}
                <button
                  className="btn btn-sm btn-outline-secondary me-2"
                  onClick={() => duplicateGroup(activeGroup.id)}
                  title="Duplicate this basket"
                >
                  <i className="bi bi-files me-1" />
                  Duplicate
                </button>
                <button
                    className="btn btn-sm btn-danger"
                    onClick={() => deleteGroup(activeGroup.id)}
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
                        const mjdKey = String(Number(String(ds.t_min).replace(',', '.')));
                        const tmin_str = tminTTLabels[mjdKey] || '…';
                        return (
                            <li key={item.id} className="list-group-item d-flex justify-content-between align-items-center">
                                <div>
                                    Obs. id: <strong>{item.obs_id}</strong> <small>| Target Name: {targetName} | T_min: {tmin_str}</small>
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
      {allBasketGroups.length > 1 && (
        <div className="mb-3">
          <h5>Other Baskets</h5>
          <div className="list-group">
            {allBasketGroups
              .filter((group) => !activeBasketGroupId || group.id !== activeBasketGroupId)
              .map((group) => (
                <button
                  key={group.id}
                  type="button"
                  className="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                  onClick={() => handleSetActiveGroup(group)}
                >
                  {group.name}
                  <span className="badge bg-secondary rounded-pill">{group.saved_datasets?.length || 0} items</span>
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
