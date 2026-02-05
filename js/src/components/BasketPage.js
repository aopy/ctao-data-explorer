import React, { useState, useEffect, useMemo, useCallback } from "react";
import axios from "axios";
import { AUTH_PREFIX, API_PREFIX } from "../index";
import { mjdToDate, formatDateTimeStrings } from "./datetimeUtils";
import QuickLookModal from "./QuickLookModal";

// helpers
const asId = (v) => (v == null ? "" : String(v));

const formatTminUtc = (mjd) => {
  if (mjd == null || mjd === "") return "";
  const mjdNum = Number(String(mjd).replace(",", "."));
  if (!Number.isFinite(mjdNum)) return "";
  const date = mjdToDate(mjdNum);
  if (!date) return "";
  const { dateStr, timeStr } = formatDateTimeStrings(date); // UTC
  return `${dateStr} ${timeStr} UTC`;
};

// Format "YYYY-MM-DDThh:mm:ss.sss" → "dd/MM/yyyy hh:mm:ss TT"
const formatTtIso = (tt_isot) => {
  if (!tt_isot) return "";
  const [d, t] = tt_isot.split("T");
  const [y, m, day] = d.split("-");
  return `${day}/${m}/${y} ${t.slice(0, 8)} TT`;
};


function BasketTab({ obsIds }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        className="btn btn-sm btn-ctao-galaxy"
        onClick={() => setOpen(true)}
        disabled={!obsIds.length}
        title={!obsIds.length ? "Basket is empty" : "Create a preview job from this basket"}
      >
        Run Preview Job
      </button>
      <QuickLookModal isOpen={open} onClose={() => setOpen(false)} obsIds={obsIds} />
    </>
  );
}

function ConfirmModal({
  show,
  title = "Confirm",
  body,
  confirmText = "Confirm",
  cancelText = "Cancel",
  confirmVariant = "danger",
  isBusy = false,
  onCancel,
  onConfirm,
}) {
  if (!show) return null;

  // Bootstrap-like z-indexes
  const Z_BACKDROP = 1050;
  const Z_MODAL = 1055;

  const handleCancel = () => {
    if (!isBusy) onCancel?.();
  };

  return (
    <>
      <div className="modal-backdrop fade show" style={{ zIndex: Z_BACKDROP }} onClick={handleCancel} />
      <div
        className="modal show"
        style={{ display: "block", zIndex: Z_MODAL }}
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-dialog modal-dialog-centered" role="document">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">{title}</h5>
              <button
                type="button"
                className="btn-close"
                onClick={handleCancel}
                aria-label="Close"
                disabled={isBusy}
              />
            </div>

            <div className="modal-body">
              {typeof body === "string" ? <p className="mb-0">{body}</p> : body}
            </div>

            <div className="modal-footer">
              <button type="button" className="btn btn-outline-secondary" onClick={handleCancel} disabled={isBusy}>
                {cancelText}
              </button>
              <button
                type="button"
                className={`btn btn-${confirmVariant}`}
                onClick={() => onConfirm?.()}
                disabled={isBusy}
              >
                {isBusy ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                    Working…
                  </>
                ) : (
                  confirmText
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// main page

export default function BasketPage({
  isLoggedIn,
  onOpenItem,
  onActiveGroupChange,
  refreshTrigger,
  onBasketGroupsChange,
  allBasketGroups = [],
  activeBasketGroupId,
}) {
  const activeId = asId(activeBasketGroupId);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [newGroupName, setNewGroupName] = useState("");
  const [editingGroupName, setEditingGroupName] = useState("");

  // delete confirmation
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);

  // TT labels cache: { mjdStr: "dd/MM/yyyy hh:mm:ss TT" }
  const [tminTTLabels, setTminTTLabels] = useState({});

  const activeGroup = useMemo(() => {
    if (!activeId) return null;
    return (allBasketGroups || []).find((g) => asId(g.id) === activeId) || null;
  }, [allBasketGroups, activeId]);

  const otherGroups = useMemo(() => {
    const groups = allBasketGroups || [];
    if (!activeId) return groups;
    return groups.filter((g) => asId(g.id) !== activeId);
  }, [allBasketGroups, activeId]);

  // keep header input in sync with active group
  useEffect(() => {
    setEditingGroupName(activeGroup?.name || "");
  }, [activeGroup]);

  const fetchBasketGroups = useCallback(async () => {
    if (!isLoggedIn) {
      setError(null);
      onBasketGroupsChange?.([]);
      onActiveGroupChange?.(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const res = await axios.get(`${API_PREFIX}/basket/groups`);
      const rawGroups = res.data || [];

      // normalize IDs to string in the objects we send upward
      const groups = rawGroups.map((g) => ({
        ...g,
        id: asId(g.id),
      }));

      onBasketGroupsChange?.(groups);

      // decide which id should be active
      let idToActivate = activeId;
      if ((!idToActivate || !groups.some((g) => g.id === idToActivate)) && groups.length > 0) {
        idToActivate = groups[0].id;
      }
      onActiveGroupChange?.(idToActivate || null);
    } catch (err) {
      console.error("Error fetching basket groups", err);
      setError("Failed to load basket data.");
      onBasketGroupsChange?.([]);
      onActiveGroupChange?.(null);
    } finally {
      setIsLoading(false);
    }
  }, [isLoggedIn, onBasketGroupsChange, onActiveGroupChange, activeId]);

  useEffect(() => {
    fetchBasketGroups();
  }, [fetchBasketGroups, refreshTrigger]);

  // optional ping
  useEffect(() => {
    if (isLoggedIn) axios.get(`${AUTH_PREFIX}/users/me_from_session`).catch(() => {});
  }, [isLoggedIn]);

  // Update TT labels whenever active group's visible items change
  useEffect(() => {
    const items = activeGroup?.saved_datasets || [];
    const uniqueMjds = Array.from(
      new Set(
        items
          .map((it) => it?.dataset_json?.t_min)
          .filter((v) => v != null)
          .map((v) => Number(String(v).replace(",", ".")))
          .filter((n) => Number.isFinite(n))
      )
    );

    if (!uniqueMjds.length) {
      setTminTTLabels({});
      return;
    }

    let cancelled = false;

    (async () => {
      try {
        const pairs = await Promise.all(
          uniqueMjds.map(async (m) => {
            const resp = await axios.post("/api/convert_time", {
              value: String(m),
              input_format: "mjd",
              input_scale: "tt",
            });
            return [String(m), formatTtIso(resp.data.tt_isot)];
          })
        );
        if (!cancelled) setTminTTLabels(Object.fromEntries(pairs));
      } catch {
        if (!cancelled) setTminTTLabels({});
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [activeGroup]);

  const handleSetActiveGroup = (group) => {
    const id = asId(group?.id);
    if (!id) return;
    onActiveGroupChange?.(id);
  };

  const createNewGroup = async () => {
    const name = newGroupName.trim();
    if (!name) return;
    setError(null);

    try {
      await axios.post(`${API_PREFIX}/basket/groups`, { name });
      setNewGroupName("");
      await fetchBasketGroups();
    } catch (err) {
      console.error("Error creating new basket group", err);
      setError("Failed to create group. Please try again.");
    }
  };

  const renameGroup = async (groupId, newName) => {
    const id = asId(groupId);
    const trimmedName = (newName || "").trim();

    if (!id || !activeGroup) return;
    if (!trimmedName || trimmedName === activeGroup.name) {
      setEditingGroupName(activeGroup?.name || "");
      return;
    }

    setError(null);
    try {
      await axios.put(`${API_PREFIX}/basket/groups/${id}`, { name: trimmedName });
      await fetchBasketGroups();
    } catch (err) {
      console.error("Error renaming basket group", err);
      setError("Failed to rename group.");
      setEditingGroupName(activeGroup?.name || "");
    }
  };

  const requestDeleteGroup = () => setShowDeleteModal(true);

  const confirmDeleteGroup = async () => {
    if (!activeGroup) return;
    setDeleteBusy(true);
    setError(null);

    try {
      await axios.delete(`${API_PREFIX}/basket/groups/${activeGroup.id}`);
      setShowDeleteModal(false);
      await fetchBasketGroups();
    } catch (err) {
      console.error("Error deleting basket group", err);
      setError("Failed to delete group.");
    } finally {
      setDeleteBusy(false);
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
      await fetchBasketGroups();
    } catch (err) {
      if (err.response && err.response.status === 404) {
        setError("Item or group not found.");
        await fetchBasketGroups();
      } else {
        console.error("Error deleting basket item link", err);
        setError("Failed to delete item from basket.");
      }
    }
  };

  const duplicateGroup = async () => {
    if (!activeGroup) return;
    setError(null);

    try {
      await axios.post(`${API_PREFIX}/basket/groups/${activeGroup.id}/duplicate`);
      await fetchBasketGroups();
    } catch (err) {
      console.error("Error duplicating basket group", err);
      setError("Failed to duplicate group.");
    }
  };

  const openItemModal = (item) => onOpenItem?.(item);

  const itemsToShow = activeGroup?.saved_datasets || [];

  const obsIdsForQuickLook = useMemo(
    () => (itemsToShow || []).map((it) => asId(it.obs_id)).filter(Boolean),
    [itemsToShow]
  );

  // states

  if (isLoading) return <div className="mt-3 text-center">Loading basket...</div>;
  if (error) return <div className="alert alert-danger mt-3">{error}</div>;
  if (!isLoggedIn) return <div className="alert alert-warning mt-3">Please log in to view your basket.</div>;

  return (
    <div className="mt-3">
      <ConfirmModal
        show={showDeleteModal}
        title="Delete basket?"
        body={
          <div>
            <p className="mb-2">
              This will permanently delete <strong>{activeGroup?.name || "this basket"}</strong> and all its saved items.
            </p>
            <p className="mb-0 text-muted small">This action cannot be undone.</p>
          </div>
        }
        confirmText="Yes, delete"
        cancelText="Cancel"
        confirmVariant="danger"
        isBusy={deleteBusy}
        onCancel={() => setShowDeleteModal(false)}
        onConfirm={confirmDeleteGroup}
      />

      {/* Active basket */}
      {activeGroup ? (
        <div className="card mb-3">
          <div className="card-header d-flex justify-content-between align-items-center gap-2 flex-wrap">
            <div className="d-flex align-items-center gap-2 flex-grow-1" style={{ minWidth: 260 }}>
              <span className="text-muted small">Active basket</span>

              <input
                type="text"
                className="form-control form-control-sm"
                value={editingGroupName}
                onChange={(e) => setEditingGroupName(e.target.value)}
                onBlur={() => renameGroup(activeGroup.id, editingGroupName)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    renameGroup(activeGroup.id, editingGroupName);
                    e.currentTarget.blur();
                  }
                  if (e.key === "Escape") {
                    setEditingGroupName(activeGroup.name || "");
                    e.currentTarget.blur();
                  }
                }}
                aria-label="Current basket name"
                placeholder="Basket name..."
              />
            </div>

            <div className="d-flex align-items-center gap-2">
              <BasketTab obsIds={obsIdsForQuickLook} />

              <button
                type="button"
                className="btn btn-sm btn-outline-secondary"
                onClick={duplicateGroup}
                title="Duplicate this basket"
              >
                <i className="bi bi-files me-1" />
                Duplicate
              </button>

              <button type="button" className="btn btn-sm btn-danger" onClick={requestDeleteGroup}>
                Delete Basket
              </button>
            </div>
          </div>

          <div className="card-body p-0">
            {itemsToShow.length > 0 ? (
              <ul className="list-group list-group-flush">
                {itemsToShow.map((item) => {
                  const ds = item.dataset_json || {};
                  const targetName = ds.target_name || "N/A";

                  const mjdNum = Number(String(ds.t_min).replace(",", "."));
                  const mjdKey = String(mjdNum);

                  const tminStr = Number.isFinite(mjdNum)
                    ? tminTTLabels[mjdKey] || "…"
                    : formatTminUtc(ds.t_min) || "…";

                  return (
                    <li
                      key={asId(item.id)}
                      className="list-group-item d-flex justify-content-between align-items-center flex-wrap gap-2"
                    >
                      <div>
                        Obs. id: <strong>{asId(item.obs_id)}</strong>{" "}
                        <small className="text-muted">| Target: {targetName} | T_min: {tminStr}</small>
                      </div>

                      <div className="d-flex gap-2">
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-primary"
                          onClick={() => openItemModal(item)}
                        >
                          View
                        </button>
                        <button
                          type="button"
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
              <div className="p-3">
                <p className="text-muted mb-0">No items in this basket.</p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="alert alert-info">You have no baskets. Create one below.</div>
      )}

      {/* Other baskets */}
      {otherGroups.length > 0 && (
        <div className="card mb-3">
          <div className="card-header d-flex align-items-center justify-content-between">
            <div>
              <div className="fw-semibold">Other baskets</div>
              <div className="text-muted small">Switch your active basket</div>
            </div>
            <span className="badge bg-secondary">{otherGroups.length}</span>
          </div>

          <div className="card-body p-0">
            <div className="list-group list-group-flush">
              {otherGroups.map((group) => (
                <button
                  key={asId(group.id)}
                  type="button"
                  className="list-group-item list-group-item-action d-flex justify-content-between align-items-center"
                  onClick={() => handleSetActiveGroup(group)}
                  title="Make this basket active"
                >
                  <span className="text-truncate" style={{ maxWidth: "70%" }}>
                    {group.name}
                  </span>
                  <span className="badge bg-secondary rounded-pill">{group.saved_datasets?.length || 0} items</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Create new basket */}
      <div className="card mb-3">
        <div className="card-header">
          <div className="fw-semibold">Create a new basket</div>
          <div className="text-muted small">Give it a short, descriptive name</div>
        </div>

        <div className="card-body">
          <div className="input-group">
            <input
              type="text"
              className="form-control"
              placeholder="New basket name"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  createNewGroup();
                }
              }}
            />
            <button
              className="btn btn-outline-primary"
              onClick={createNewGroup}
              disabled={!newGroupName.trim()}
              type="button"
            >
              Create
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}