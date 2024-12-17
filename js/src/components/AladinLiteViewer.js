import React, { useEffect, useRef } from 'react';

const AladinLiteViewer = ({ overlays = [], selectedIds = [] }) => {
  const aladinRef = useRef(null);
  const aladinInstance = useRef(null);
  const allCatalogRef = useRef(null);
  const selectedCatalogRef = useRef(null);
  const circleOverlayRef = useRef(null);

  useEffect(() => {
    if (!window.A || !window.A.init) {
      console.error('Aladin Lite v3 not loaded.');
      return;
    }

    window.A.init.then(() => {
      aladinInstance.current = window.A.aladin(aladinRef.current, {
        // survey: 'P/DSS2/color', // Might cause IRSA CORS logs
        survey: 'CDS/P/Fermi/color',
        fov: 30,
        projection: 'AIT'
      });

      // Two catalogs, both shaped like 'triangle'
      allCatalogRef.current = window.A.catalog({
        name: 'allCatalog',
        shape: 'triangle', // unselected markers
        color: 'yellow',
        sourceSize: 16
      });
      selectedCatalogRef.current = window.A.catalog({
        name: 'selectedCatalog',
        shape: 'triangle', // selected markers
        color: 'red',
        sourceSize: 16
      });

      aladinInstance.current.addCatalog(allCatalogRef.current);
      aladinInstance.current.addCatalog(selectedCatalogRef.current);

      // Overlay for circles based on s_fov
      circleOverlayRef.current = window.A.graphicOverlay({ name: 'circlesOverlay' });
      aladinInstance.current.addOverlay(circleOverlayRef.current);

      updateMarkers();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    updateMarkers();
  }, [overlays, selectedIds]);

  const updateMarkers = () => {
    if (!aladinInstance.current ||
        !allCatalogRef.current ||
        !selectedCatalogRef.current ||
        !circleOverlayRef.current) {
      return;
    }

    const allCatalog = allCatalogRef.current;
    const selectedCatalog = selectedCatalogRef.current;
    const circleOverlay = circleOverlayRef.current;

    // Clear old markers & circles
    allCatalog.removeAll();
    selectedCatalog.removeAll();
    circleOverlay.removeAll();

    const raValues = [];
    const decValues = [];

    overlays.forEach((coord) => {
      const { ra, dec, id, s_fov } = coord;

      if (isNaN(ra) || isNaN(dec)) {
        console.error('Invalid RA/Dec for overlay:', coord);
        return;
      }

      // Create one marker (triangle shape as set by catalog default)
      const isSelected = selectedIds.includes(id);
      const source = window.A.source(ra, dec, {
        popupTitle: `Obs ID: ${id}`,
        popupDesc: `RA: ${ra}, DEC: ${dec}`
      });

      // Put marker in the correct catalog so no duplicates
      if (isSelected) {
        selectedCatalog.addSources([source]);
      } else {
        allCatalog.addSources([source]);
      }

      raValues.push(ra);
      decValues.push(dec);

      // If s_fov numeric, draw a circle of radius s_fov degrees
      if (!isNaN(s_fov)) {
        console.log(`Drawing circle for ID=${id}, s_fov=${s_fov} deg`);
        // A.circle(ra, dec, radiusDeg, style)
        const circle = window.A.circle(ra, dec, parseFloat(s_fov), {
          color: 'blue',
          lineWidth: 2,
          popupTitle: `FOV Circle (ID: ${id})`,
          popupDesc: `Radius: ${s_fov} deg`
        });
        circleOverlay.add(circle);
      } else {
        console.log(`No valid s_fov for ID=${id}`);
      }
    });

    // Auto-zoom if we have any markers
    if (raValues.length > 0) {
      autoZoom(raValues, decValues);
    }
  };

  const autoZoom = (raValues, decValues) => {
    const minRa = Math.min(...raValues);
    const maxRa = Math.max(...raValues);
    const minDec = Math.min(...decValues);
    const maxDec = Math.max(...decValues);

    let centerRa = (minRa + maxRa) / 2;
    let centerDec = (minDec + maxDec) / 2;
    let maxDiff = Math.max(maxRa - minRa, maxDec - minDec);

    // RA wrap-around
    if (maxRa - minRa > 180) {
      const adjustedRa = raValues.map(r => (r < 180 ? r + 360 : r));
      const adjustedMinRa = Math.min(...adjustedRa);
      const adjustedMaxRa = Math.max(...adjustedRa);
      maxDiff = Math.max(adjustedMaxRa - adjustedMinRa, maxDec - minDec);

      const adjustedCenterRa = (adjustedMinRa + adjustedMaxRa) / 2;
      centerRa = adjustedCenterRa > 360 ? adjustedCenterRa - 360 : adjustedCenterRa;
    }

    // Original bounding logic
    const baseFov = Math.min(Math.max(maxDiff * 1.2, 0.1), 180);

    // Apply an extra multiplier to zoom out more
    const finalFov = Math.min(baseFov * 6, 180);

    aladinInstance.current.gotoRaDec(centerRa, centerDec);
    aladinInstance.current.setFov(finalFov);
  };

  return (
    <div style={{ width: '100%', height: '100%' }} ref={aladinRef} />
  );
};

export default AladinLiteViewer;
