import React, { useEffect, useRef } from 'react';

const AladinLiteViewer = ({ overlays = [], selectedIds = [] }) => {
  const aladinRef = useRef(null);
  const aladinInstance = useRef(null);
  const allCatalogRef = useRef(null);
  const selectedCatalogRef = useRef(null);

  useEffect(() => {
    if (!window.A || !window.A.init) {
      console.error('Aladin Lite v3 is not loaded.');
      return;
    }

    // Wait for Aladin Lite to initialize
    window.A.init.then(() => {
      aladinInstance.current = window.A.aladin(aladinRef.current, {
        survey: 'P/DSS2/color',
        fov: 60,
        projection: 'AIT',
      });

      // Create two catalogs, letting Aladin defaults apply
      allCatalogRef.current = window.A.catalog({ name: 'allCatalog' });
      selectedCatalogRef.current = window.A.catalog({ name: 'selectedCatalog' });

      // Add them so that 'selectedCatalog' is on top
      aladinInstance.current.addCatalog(allCatalogRef.current);
      aladinInstance.current.addCatalog(selectedCatalogRef.current);

      updateMarkers();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    updateMarkers();
  }, [overlays, selectedIds]);

  const updateMarkers = () => {
    if (
      !aladinInstance.current ||
      !allCatalogRef.current ||
      !selectedCatalogRef.current
    ) {
      return;
    }

    const allCatalog = allCatalogRef.current;
    const selectedCatalog = selectedCatalogRef.current;

    // Clear out old markers
    allCatalog.removeAll();
    selectedCatalog.removeAll();

    const raValues = [];
    const decValues = [];

    // Add each coordinate to exactly ONE catalog
    overlays.forEach((coord) => {
      const { ra, dec, id } = coord;
      if (isNaN(ra) || isNaN(dec)) {
        console.error('Invalid RA/Dec:', coord);
        return;
      }

      const isSelected = selectedIds.includes(id);

      // Create a basic source with default styling (no color/shape/size)
      // Only attach popup info once so there's no duplicate info
      const source = window.A.source(ra, dec, {
        popupTitle: `Obs ID: ${id}`,
        popupDesc: `RA: ${ra}, DEC: ${dec}`,
      });

      // If it's in selectedIds, put it only in 'selectedCatalog'
      // Else, put it only in 'allCatalog'
      if (isSelected) {
        selectedCatalog.addSources([source]);
      } else {
        allCatalog.addSources([source]);
      }

      raValues.push(ra);
      decValues.push(dec);
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

    const fov = Math.min(Math.max(maxDiff * 1.2, 0.1), 180);
    aladinInstance.current.gotoRaDec(centerRa, centerDec);
    aladinInstance.current.setFov(fov);
  };

  return (
    <div
      style={{ width: '100%', height: '100%' }}
      ref={aladinRef}
    />
  );
};

export default AladinLiteViewer;
