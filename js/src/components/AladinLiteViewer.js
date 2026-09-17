import React, {
  useEffect,
  useRef,
  useCallback,
  useState,
} from "react";

// Okabe–Ito colour-blind-safe palette
const UNSELECTED_COLOR = "#56B4E9";
const SELECTED_COLOR = "#F0E442";
const CIRCLE_COLOR_UNSELECTED = "#999999";
const CIRCLE_COLOR_SELECTED = "#F0E442";
const MARKER_SIZE = 8;
const CIRCLE_LINE_WIDTH = 1;

const COORDINATE_PRECISION = 6;

const positionKey = (ra, dec) =>
  `${ra.toFixed(COORDINATE_PRECISION)}:${dec.toFixed(
    COORDINATE_PRECISION
  )}`;

const AladinLiteViewer = ({ overlays = [], selectedIds = [], onSelectIds = () => {} }) => {
  const aladinRef = useRef(null);
  const aladinInstance = useRef(null);
  const resultsCatalogRef = useRef(null);
  const clickHandlerRef = useRef(null);
  const mapClickHandlerRef = useRef(null);
  const ignoreNextMapClickRef = useRef(false);
  const isRefreshingRef = useRef(false);
  const selectedIdsRef = useRef([]);
  const selectedIdsSetRef = useRef(new Set());

  const [lastClickedPosition, setLastClickedPosition] =
    useState(null);

  const [activePosition, setActivePosition] =
    useState(null);

  const onSelectIdsRef = useRef(onSelectIds);

  useEffect(() => {
    onSelectIdsRef.current = onSelectIds;
  }, [onSelectIds]);

  const customDrawFunction = useCallback((source, canvasCtx, viewParams) => {
    const data = source.data || {};
    const ids = Array.isArray(data.ids)
      ? data.ids.map(String)
      : data.id
        ? [String(data.id)]
        : [];

    const selectedIdsSet = selectedIdsSetRef.current;

    const selectedCount = ids.filter((id) =>
      selectedIdsSet.has(id)
    ).length;

    const isSelected =
      ids.length > 0 && selectedCount === ids.length;

    const isPartiallySelected =
      selectedCount > 0 && selectedCount < ids.length;

    const count = Number(data.count) || 1;
    const fovDeg = Number(data.s_fov);

    canvasCtx.beginPath();

    const groupSizeIncrease = count > 1
      ? Math.min(5, Math.log2(count) * 1.5)
      : 0;

    const baseSize =
      MARKER_SIZE + groupSizeIncrease;

    canvasCtx.moveTo(
      source.x,
      source.y - baseSize * 0.7
    );
    canvasCtx.lineTo(
      source.x - baseSize * 0.6,
      source.y + baseSize * 0.4
    );
    canvasCtx.lineTo(
      source.x + baseSize * 0.6,
      source.y + baseSize * 0.4
    );
    canvasCtx.closePath();

    canvasCtx.fillStyle = isSelected
      ? SELECTED_COLOR
      : UNSELECTED_COLOR;

    canvasCtx.lineWidth =
      isSelected || isPartiallySelected ? 2 : 0.5;

    canvasCtx.strokeStyle = isPartiallySelected
      ? SELECTED_COLOR
      : "#00000099";

    canvasCtx.stroke();
    canvasCtx.fill();

    if (Number.isFinite(fovDeg) && fovDeg > 0) {
            if (viewParams?.fov?.[0] && viewParams?.width > 0 && viewParams.fov[0] !== 0) {
                 const degPerPixel = viewParams.fov[0] / viewParams.width;
                 if (degPerPixel > 0) {
                    const radiusPixels = fovDeg / degPerPixel;
                    if (radiusPixels > 1) {
                        canvasCtx.beginPath();
                        canvasCtx.arc(source.x, source.y, radiusPixels, 0, 2 * Math.PI, false);
                        canvasCtx.closePath();
                        canvasCtx.strokeStyle =
                          isSelected || isPartiallySelected
                            ? CIRCLE_COLOR_SELECTED
                            : CIRCLE_COLOR_UNSELECTED;
                        canvasCtx.lineWidth = CIRCLE_LINE_WIDTH;
                        canvasCtx.globalAlpha = 0.7;
                        canvasCtx.stroke();
                        canvasCtx.globalAlpha = 1.0;
                    }
                 }
            } else {
                console.warn("Cannot draw circle: Invalid viewParams for calculation", viewParams);
            }
        }

    }, []);

  useEffect(() => {
    let isMounted = true;

    if (!window.A || !window.A.init) {
      console.error('Aladin Lite v3 not loaded.');
      return;
    }


    if (aladinInstance.current) {
        console.log("Aladin instance already exists, skipping init.");
        updateMarkers(); // Update markers if already initialized
        return;
    }

    console.log("Initializing Aladin Lite...");
    window.A.init.then(() => {
      if (!isMounted || !aladinRef.current) return; // Check if component is still mounted

      console.log("Aladin Core Ready, creating instance...");
      try {
            aladinInstance.current = window.A.aladin(aladinRef.current, {
                survey: 'CDS/P/Fermi/color',
                fov: 60,
                projection: 'AIT',
                showFullscreenControl: false,
                showFrame: true,
                showCoordinates: true,
                showGotoControl: true,
                showZoomControl: true,
                showLayersControl: true,
            });

            resultsCatalogRef.current = window.A.catalog({
              name: "SearchResults",
              sourceSize: 10,
              shape: customDrawFunction,
              color: UNSELECTED_COLOR,
              selectionColor: "rgba(0, 0, 0, 0)",
              selectionLineWidth: 0,
            });

            resultsCatalogRef.current.setSelectionColor?.(
              "rgba(0, 0, 0, 0)"
            );

            resultsCatalogRef.current.setSelectionLineWidth?.(0);

            aladinInstance.current.addCatalog(
              resultsCatalogRef.current
            );

            console.log("Aladin Instance and Catalog created.");
            clickHandlerRef.current = (obj) => {
              if (isRefreshingRef.current) {
                return;
              }

              const clickedIds = Array.isArray(obj?.data?.ids)
                ? obj.data.ids.map(String)
                : obj?.data?.id
                  ? [String(obj.data.id)]
                  : [];
              if (!clickedIds.length) {
                return;
              }

              ignoreNextMapClickRef.current = true;

              window.setTimeout(() => {
                ignoreNextMapClickRef.current = false;
              }, 0);

              setLastClickedPosition({
                ids: clickedIds,
                count: clickedIds.length,
                ra: Number(obj.data.ra),
                dec: Number(obj.data.dec),
                sFov: Number(obj.data.s_fov),
              });

              setActivePosition(null);

              const currentIds = selectedIdsRef.current.map(String);

              const allSelected = clickedIds.every((id) =>
                currentIds.includes(id)
              );

              const next = allSelected
                ? currentIds.filter((id) => !clickedIds.includes(id))
                : Array.from(new Set([...currentIds, ...clickedIds]));

              onSelectIdsRef.current(next);
            };

            aladinInstance.current.on(
              "objectClicked",
              clickHandlerRef.current
            );

            mapClickHandlerRef.current = () => {
              if (ignoreNextMapClickRef.current) {
                return;
              }

              onSelectIdsRef.current([]);
              setLastClickedPosition(null);
              setActivePosition(null);

              resultsCatalogRef.current?.deselectAll?.();
            };

            aladinInstance.current.on(
              "mapClicked",
              mapClickHandlerRef.current
            );

            updateMarkers();

      } catch (error) {
          console.error("Error initializing Aladin:", error);
      }

    }).catch(err => {
        console.error("Aladin Lite init promise failed:", err);
    });

    // Cleanup function
    return () => {
      isMounted = false;
      console.log("AladinLiteViewer unmounting...");

      if (aladinInstance.current && clickHandlerRef.current) {
        aladinInstance.current.off?.(
          'objectClicked',
          clickHandlerRef.current
        );
      }

      if (aladinInstance.current && mapClickHandlerRef.current) {
        aladinInstance.current.off?.(
          'mapClicked',
          mapClickHandlerRef.current
        );
      }
    };
    }, [customDrawFunction]);

  useEffect(() => {
    setLastClickedPosition(null);
    setActivePosition(null);
  }, [overlays]);

  useEffect(() => {
    updateMarkers({
      shouldAutoZoom: true,
    });
  }, [overlays, customDrawFunction]);

  useEffect(() => {
    selectedIdsRef.current = selectedIds;
    selectedIdsSetRef.current = new Set(
      selectedIds.map(String)
    );

    resultsCatalogRef.current?.setShape?.(
      customDrawFunction
    );
  }, [selectedIds, customDrawFunction]);




  // update markers logic
  const updateMarkers = ({ shouldAutoZoom = true } = {}) => {
    if (!aladinInstance.current || !resultsCatalogRef.current) {
        // console.log("Skipping updateMarkers: Aladin not ready.");
        return;
    }
    console.log("Updating markers...");

    isRefreshingRef.current = true;

    try {
      const resultsCatalog = resultsCatalogRef.current;
      resultsCatalog.removeAll();

      const groupedPositions = new Map();

      overlays.forEach((coord) => {
        const raNum = Number(coord.ra);
        const decNum = Number(coord.dec);
        const id = String(coord.id ?? "").trim();
        const fov = Number(coord.s_fov);

        if (
          !Number.isFinite(raNum) ||
          !Number.isFinite(decNum) ||
          !id
        ) {
          console.warn("Invalid sky-map overlay, skipping:", coord);
          return;
        }

        const key = positionKey(raNum, decNum);
        const existing = groupedPositions.get(key);

        if (existing) {
          existing.ids.push(id);

          if (Number.isFinite(fov)) {
            existing.fovValues.push(fov);
          }
        } else {
          groupedPositions.set(key, {
            ra: raNum,
            dec: decNum,
            ids: [id],
            fovValues: Number.isFinite(fov) ? [fov] : [],
          });
        }
      });

      const sources = [];
      const validCoords = [];

      groupedPositions.forEach((group) => {

        const representativeFov = group.fovValues.length
          ? Math.max(...group.fovValues)
          : Number.NaN;

        const source = window.A.source(group.ra, group.dec, {
          id: group.ids[0],
          ids: group.ids,
          count: group.ids.length,
          ra: group.ra,
          dec: group.dec,
          s_fov: representativeFov,
        });

        sources.push(source);
        validCoords.push({
          ra: group.ra,
          dec: group.dec,
        });
      });

      resultsCatalog.addSources(sources); // Add all sources at once
      console.log(
        `Added ${sources.length} sky positions representing ` +
        `${overlays.length} observations.`
      );


      // Auto-zoom if we have valid coordinates
      if (shouldAutoZoom && validCoords.length > 0) {
        autoZoom(validCoords);
      }
    } finally {
      isRefreshingRef.current = false;
    }
  };

  // AutoZoom Logic
  const autoZoom = (coords) => { // Receives array of {ra: number, dec: number}
    if (!aladinInstance.current || coords.length === 0) return;

    console.log("Auto-zooming (previous logic) based on coordinates:", coords);

    // Extract RA and Dec values into separate arrays
    const raValues = coords.map(c => c.ra);
    const decValues = coords.map(c => c.dec);

    const margin = 15; // Margin in degrees

    // Compute bounding box of the COORDINATES themselves
    const minRaRaw = Math.min(...raValues);
    const maxRaRaw = Math.max(...raValues);
    const minDecRaw = Math.min(...decValues);
    const maxDecRaw = Math.max(...decValues);

    // Apply the margin to the raw coordinate bounds
    let minRa = minRaRaw - margin;
    let maxRa = maxRaRaw + margin;
    let minDec = minDecRaw - margin;
    let maxDec = maxDecRaw + margin;

    // Clamp Dec values to valid range [-90, 90] AFTER adding margin
    minDec = Math.max(-90, minDec);
    maxDec = Math.min(90, maxDec);

    // RA wrap-around handling
    let needsRaWrapCheck = false;
    if (maxRa - minRa > 180) {
       needsRaWrapCheck = true;
      // Use original values for wrap calculation, then apply margin
      const adjustedRa = raValues.map(r => (r < 180 ? r + 360 : r));
      const adjustedMinRaRaw = Math.min(...adjustedRa);
      const adjustedMaxRaRaw = Math.max(...adjustedRa);
      // Apply margin to adjusted values
      minRa = adjustedMinRaRaw - margin;
      maxRa = adjustedMaxRaRaw + margin;
    }

    // Calculate center
    let centerRa = (minRa + maxRa) / 2; // Center of the MARGIN-ADJUSTED box
    if (needsRaWrapCheck && centerRa >= 360) {
        centerRa -= 360; // Bring back to 0-360 range
    }
    // Ensure RA is within [0, 360)
    centerRa = ((centerRa % 360) + 360) % 360;

    const centerDec = (minDec + maxDec) / 2; // Center of the MARGIN-ADJUSTED box

    // Determine the FOV needed to cover the MARGIN-ADJUSTED bounding box
    const raSpan = maxRa - minRa;
    const decSpan = maxDec - minDec;
    let fovCandidate = Math.max(raSpan, decSpan);

    // Ensure a minimum reasonable FOV and cap at 180
    const minFov = 0.5;
    const maxFov = 180;
    fovCandidate = Math.max(fovCandidate, minFov);
    const finalFov = Math.min(fovCandidate, maxFov);

    console.log(`AutoZoom: Center=(${centerRa.toFixed(4)}, ${centerDec.toFixed(4)}), FOV=${finalFov.toFixed(4)}`);

    try {
        aladinInstance.current.gotoRaDec(centerRa, centerDec);
        aladinInstance.current.setFov(finalFov);
    } catch(err) {
        console.error("Error during Aladin goto/setFov:", err);
    }
  };

  return (
      <div
        style={{
          width: "100%",
          height: "100%",
          minHeight: 0,
          position: "relative",
        }}
      >
        <div
          className="aladin-lite-container"
          style={{
            width: "100%",
            height: "100%",
            overflow: "hidden",
          }}
          ref={aladinRef}
        />

        {lastClickedPosition && (
          <button
            type="button"
            className="btn btn-sm btn-light border"
            style={{
              position: "absolute",
              top: 48,
              right: 8,
              zIndex: 10,
            }}
            onClick={() => setActivePosition(lastClickedPosition)}
          >
            <i className="bi bi-info-circle me-1" />
            {" "}
            Details
          </button>
        )}

        {activePosition && (
          <div
            className="card shadow-sm"
            style={{
              position: "absolute",
              top: 84,
              right: 8,
              zIndex: 10,
              width: "min(300px, calc(100% - 16px))",
            }}
          >
            <div className="card-header d-flex justify-content-between align-items-center py-1">
              <strong className="small">Position details</strong>

              <button
                type="button"
                className="btn-close"
                aria-label="Close"
                onClick={() => setActivePosition(null)}
              />
            </div>

            <div className="card-body small py-2">
              <div>
                <strong>
                  {activePosition.count === 1
                    ? "Observation ID:"
                    : "Observations:"}
                </strong>{" "}
                {activePosition.count === 1
                  ? activePosition.ids[0]
                  : activePosition.count}
              </div>

              {activePosition.count > 1 && (
                <div className="text-muted text-truncate">
                  {activePosition.ids.slice(0, 3).join(", ")}
                  {activePosition.count > 3
                    ? ` and ${activePosition.count - 3} more`
                    : ""}
                </div>
              )}

              <div className="mt-1">
                <strong>RA:</strong>{" "}
                {Number.isFinite(activePosition.ra)
                  ? activePosition.ra.toFixed(6)
                  : "N/A"}
              </div>

              <div>
                <strong>Dec:</strong>{" "}
                {Number.isFinite(activePosition.dec)
                  ? activePosition.dec.toFixed(6)
                  : "N/A"}
              </div>

              {Number.isFinite(activePosition.sFov) && (
                <div>
                  <strong>FoV:</strong>{" "}
                  {activePosition.sFov.toFixed(3)}°
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
};

export default AladinLiteViewer;
