import React, { useEffect, useRef, useCallback } from 'react';

const UNSELECTED_COLOR = 'yellow';
const SELECTED_COLOR = 'red';
const CIRCLE_COLOR_UNSELECTED = 'cyan';
const CIRCLE_COLOR_SELECTED = 'red';
const MARKER_SIZE = 8;
const CIRCLE_LINE_WIDTH = 1;

const AladinLiteViewer = ({ overlays = [], selectedIds = [] }) => {
  const aladinRef = useRef(null);
  const aladinInstance = useRef(null);
  const resultsCatalogRef = useRef(null);

  const customDrawFunction = useCallback((source, canvasCtx, viewParams) => {
    const data = source.data || {};
    const isSelected = data.isSelected;
    const fovDeg = parseFloat(data.s_fov);

    canvasCtx.beginPath();
    const baseSize = isSelected ? MARKER_SIZE + 2 : MARKER_SIZE;
    canvasCtx.moveTo(source.x, source.y - baseSize * 0.7);
    canvasCtx.lineTo(source.x - baseSize * 0.6, source.y + baseSize * 0.4);
    canvasCtx.lineTo(source.x + baseSize * 0.6, source.y + baseSize * 0.4);
    canvasCtx.closePath();
    canvasCtx.fillStyle = isSelected ? SELECTED_COLOR : UNSELECTED_COLOR;
    canvasCtx.fill();

    if (!isNaN(fovDeg) && fovDeg > 0) {
            if (viewParams?.fov?.[0] && viewParams?.width > 0 && viewParams.fov[0] !== 0) {
                 const degPerPixel = viewParams.fov[0] / viewParams.width;
                 if (degPerPixel > 0) {
                    const radiusPixels = fovDeg / degPerPixel;
                    if (radiusPixels > 1) {
                        canvasCtx.beginPath();
                        canvasCtx.arc(source.x, source.y, radiusPixels, 0, 2 * Math.PI, false);
                        canvasCtx.closePath();
                        canvasCtx.strokeStyle = isSelected ? CIRCLE_COLOR_SELECTED : CIRCLE_COLOR_UNSELECTED;
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
                name: 'SearchResults',
                sourceSize: 10,
                shape: customDrawFunction,
                color: UNSELECTED_COLOR,
                onClick: 'showPopup'
            });

            aladinInstance.current.addCatalog(resultsCatalogRef.current);

            console.log("Aladin Instance and Catalog created.");

            updateMarkers(); // Update markers after init

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
    };
  }, [customDrawFunction]);

  // effect to update markers when data changes
  useEffect(() => {
    updateMarkers();
  }, [overlays, selectedIds, customDrawFunction]);


  // update markers logic
  const updateMarkers = () => {
    if (!aladinInstance.current || !resultsCatalogRef.current) {
        // console.log("Skipping updateMarkers: Aladin not ready.");
        return;
    }
    console.log("Updating markers...");

    const resultsCatalog = resultsCatalogRef.current;
    resultsCatalog.removeAll();

    const sources = [];
    const validCoords = []; // For autoZoom

    overlays.forEach((coord) => {
      const { ra, dec, id, s_fov } = coord;

      // Ensure coordinates are valid numbers
      const raNum = parseFloat(ra);
      const decNum = parseFloat(dec);
      if (isNaN(raNum) || isNaN(decNum)) {
        console.warn('Invalid RA/Dec for overlay, skipping:', coord);
        return;
      }

      const isSelected = selectedIds.includes(id?.toString()); // Ensure comparison with string ID
      console.log(`ID: ${id?.toString()}, IsSelected: ${isSelected}, Selected IDs:`, selectedIds);

      // create the source object with data for the draw function
      const source = window.A.source(raNum, decNum, {
        id: id?.toString() || 'N/A',
        ra: raNum,
        dec: decNum,
        s_fov: parseFloat(s_fov), // Ensure s_fov is a number or NaN
        isSelected: isSelected,
        // Popup content:
        popupTitle: `Obs ID: ${id?.toString() || 'N/A'}`,
        popupDesc: `RA: ${raNum.toFixed(6)}, Dec: ${decNum.toFixed(6)}<br/>FOV: ${!isNaN(parseFloat(s_fov)) ? parseFloat(s_fov) + ' deg' : 'N/A'}`
      });
      sources.push(source);

      validCoords.push({ ra: raNum, dec: decNum }); // Add to list for zooming
    });

    resultsCatalog.addSources(sources); // Add all sources at once
    console.log(`Added ${sources.length} sources to catalog.`);

    // Auto-zoom if we have valid coordinates
    if (validCoords.length > 0) {
        autoZoom(validCoords);
    } else {
        // Reset zoom/position if no data?
        // aladinInstance.current.gotoRaDec(0, 0);
        // aladinInstance.current.setFov(60);
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
    let minRaRaw = Math.min(...raValues);
    let maxRaRaw = Math.max(...raValues);
    let minDecRaw = Math.min(...decValues);
    let maxDecRaw = Math.max(...decValues);

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
    <div className="aladin-lite-container" style={{ width: '100%', height: '100%', overflow: 'hidden' }} ref={aladinRef}>
    </div>
  );
};

export default AladinLiteViewer;
