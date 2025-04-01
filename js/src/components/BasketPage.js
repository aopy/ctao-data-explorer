import React, { useState, useEffect } from 'react';
import axios from 'axios';

const formatTmin = (mjd) => {
  if (!mjd || isNaN(mjd)) return '';
  const MJD_UNIX_EPOCH = 40587;
  const msPerDay = 86400000;
  const unixTime = (mjd - MJD_UNIX_EPOCH) * msPerDay;
  return new Date(unixTime).toLocaleString();
};

function BasketPage({ authToken, onOpenItem, onActiveGroupChange, refreshTrigger, activeItems, onBasketGroupsChange }) {
  const [basketGroups, setBasketGroups] = useState([]);
  const [activeGroup, setActiveGroup] = useState(null);
  const [newGroupName, setNewGroupName] = useState('');

  const fetchBasketGroups = async () => {
    try {
      const res = await axios.get('/basket/groups');
      let groups = res.data;
      if (groups.length === 0) {
        // Create default basket group if none exist
        await axios.post('/basket/groups', { name: 'My Basket' });
        const res2 = await axios.get('/basket/groups');
        groups = res2.data;
      }
      setBasketGroups(groups);
      // Try to maintain the current active group if it still exists
      let newActive = activeGroup ? groups.find((g) => g.id === activeGroup.id) : groups[0];
      if (!newActive) newActive = groups[0];
      setActiveGroup(newActive);
      if (onActiveGroupChange) onActiveGroupChange(newActive.id, newActive.items);
      if (onBasketGroupsChange) onBasketGroupsChange(groups);
      return groups;
    } catch (err) {
      console.error('Error fetching basket groups', err);
    }
  };

  useEffect(() => {
    if (authToken) {
      fetchBasketGroups();
    }
  }, [authToken, refreshTrigger]);

  const handleSetActiveGroup = (group) => {
    setActiveGroup(group);
    if (onActiveGroupChange) {
      onActiveGroupChange(group.id, group.items);
    }
  };

  const createNewGroup = async () => {
    try {
      const name = newGroupName.trim() || 'New Basket';
      const res = await axios.post('/basket/groups', { name });
      // After creation, re-fetch groups
      const groups = await fetchBasketGroups();
      // Set the active group to the newly created group (which should be empty)
      const newGroup = groups.find(g => g.id === res.data.id);
      if (newGroup) {
        setActiveGroup(newGroup);
        if (onActiveGroupChange) {
          onActiveGroupChange(newGroup.id, newGroup.items);
        }
      }
      setNewGroupName('');
    } catch (err) {
      console.error('Error creating new basket group', err);
    }
  };

  const renameGroup = async (groupId, newName) => {
    try {
      await axios.put(`/basket/groups/${groupId}`, { name: newName });
      await fetchBasketGroups();
    } catch (err) {
      console.error('Error renaming basket group', err);
    }
  };

  const deleteGroup = async (groupId) => {
    try {
      await axios.delete(`/basket/groups/${groupId}`);
      const res = await axios.get('/basket/groups');
      setBasketGroups(res.data);
      if (onBasketGroupsChange) {
        onBasketGroupsChange(res.data);
      }
      if (res.data.length > 0) {
        const newActiveGroup = res.data[0];
        setActiveGroup(newActiveGroup);
        if (onActiveGroupChange) {
          onActiveGroupChange(newActiveGroup.id, newActiveGroup.items);
        }
      } else {
        await axios.post('/basket/groups', { name: 'My Basket' });
        const res2 = await axios.get('/basket/groups');
        setBasketGroups(res2.data);
        setActiveGroup(res2.data[0]);
        if (onActiveGroupChange) {
          onActiveGroupChange(res2.data[0].id, res2.data[0].items);
        }
        if (onBasketGroupsChange) {
          onBasketGroupsChange(res2.data);
        }
      }
    } catch (err) {
      console.error('Error deleting basket group', err);
    }
  };

  const deleteItem = async (itemId) => {
    try {
      await axios.delete(`/basket/${itemId}`);
      if (activeGroup) {
        const updatedItems = activeGroup.items.filter(item => item.id !== itemId);
        const updatedGroup = { ...activeGroup, items: updatedItems };
        setActiveGroup(updatedGroup);
        if (onActiveGroupChange) {
          onActiveGroupChange(updatedGroup.id, updatedGroup.items);
        }
      }
      await fetchBasketGroups();
    } catch (err) {
      if (err.response && err.response.status === 404) {
        console.warn(`Item ${itemId} not found; it may have been already deleted.`);
        await fetchBasketGroups();
      } else {
        console.error('Error deleting basket item', err);
      }
    }
  };

  const openItemModal = (item) => {
    onOpenItem(item);
  };

  const itemsToShow = activeItems || (activeGroup ? activeGroup.items : []);

  return (
    <div className="mt-3">
      {activeGroup && (
        <div className="card mb-3">
          <div className="card-header d-flex justify-content-between align-items-center">
            <div>
              <strong>Current Basket: </strong>
              <input
                type="text"
                value={activeGroup.name}
                onChange={(e) => setActiveGroup({ ...activeGroup, name: e.target.value })}
                onBlur={() => renameGroup(activeGroup.id, activeGroup.name)}
              />
            </div>
            <button className="btn btn-sm btn-danger" onClick={() => deleteGroup(activeGroup.id)}>
              Delete Basket
            </button>
          </div>
          <div className="card-body">
            {itemsToShow && itemsToShow.length > 0 ? (
              <ul className="list-group">
                {itemsToShow.map((item) => {
                  const ds = item.dataset_json || {};
                  const targetName = ds.target_name || 'Unknown Target';
                  const tmin_str = formatTmin(ds.t_min);
                  return (
                    <li key={item.id} className="list-group-item d-flex justify-content-between">
                      <div>
                        <strong>{item.obs_id}</strong> | {targetName} | {tmin_str}
                      </div>
                      <div>
                        <button className="btn btn-sm btn-outline-primary me-2" onClick={() => openItemModal(item)}>
                          Open
                        </button>
                        <button className="btn btn-sm btn-outline-danger" onClick={() => deleteItem(item.id)}>
                          Delete
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p>No items in this basket.</p>
            )}
          </div>
        </div>
      )}

      {basketGroups.length > 1 && (
        <div>
          <h5>Other Basket Groups</h5>
          {basketGroups
            .filter((group) => !activeGroup || group.id !== activeGroup.id)
            .map((group) => (
              <div key={group.id} className="card mb-2">
                <div className="card-header d-flex justify-content-between align-items-center">
                  <span>{group.name}</span>
                  <button className="btn btn-sm btn-outline-secondary" onClick={() => handleSetActiveGroup(group)}>
                    Set as Active
                  </button>
                </div>
                <div className="card-body">
                  {group.items && group.items.length > 0 ? (
                    <ul className="list-group">
                      {group.items.map((item) => {
                        const ds = item.dataset_json || {};
                        const targetName = ds.target_name || 'Unknown Target';
                        const tmin_str = formatTmin(ds.t_min);
                        return (
                          <li key={item.id} className="list-group-item d-flex justify-content-between">
                            <div>
                              <strong>{item.obs_id}</strong> | {targetName} | {tmin_str}
                            </div>
                            <div>
                              <button className="btn btn-sm btn-outline-primary me-2" onClick={() => openItemModal(item)}>
                                Open
                              </button>
                              <button className="btn btn-sm btn-outline-danger" onClick={() => deleteItem(item.id)}>
                                Delete
                              </button>
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  ) : (
                    <p>No items in this basket.</p>
                  )}
                </div>
              </div>
            ))}
        </div>
      )}

      <div className="mb-3">
        <h5>Create New Basket Group</h5>
        <div className="input-group">
          <input
            type="text"
            className="form-control"
            placeholder="Basket name"
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
          />
          <button className="btn btn-outline-primary" onClick={createNewGroup}>
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

export default BasketPage;