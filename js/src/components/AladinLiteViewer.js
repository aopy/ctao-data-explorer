import React, { useEffect, useRef } from 'react';

const AladinLiteViewer = ({ target, overlays }) => {
  const aladinRef = useRef(null);
  const aladinInstance = useRef(null);

  // Initialize Aladin Lite when the component mounts
  useEffect(() => {
    const loadAladinLite = async () => {
      if (window.A && typeof window.A.aladin === 'function') {
        initializeAladin();
      } else {
        try {
          // Load jQuery if not already loaded
          if (!window.jQuery) {
            await loadScript('https://code.jquery.com/jquery-3.6.0.min.js');
            console.log('jQuery loaded');
          }

          // Load Aladin Lite CSS
          loadCSS('https://aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.css');

          // Load Aladin Lite JavaScript
          await loadScript('https://aladin.u-strasbg.fr/AladinLite/api/v2/latest/aladin.min.js');
          console.log('Aladin Lite script loaded');

          initializeAladin();
        } catch (error) {
          console.error('Error loading Aladin Lite:', error);
        }
      }
    };

    const loadScript = (url) => {
      return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = url;
        script.onload = resolve;
        script.onerror = () => reject(new Error(`Failed to load script: ${url}`));
        document.body.appendChild(script);
      });
    };

    const loadCSS = (url) => {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = url;
      document.head.appendChild(link);
    };

    const initializeAladin = () => {
      console.log('Initializing Aladin Lite...');
      aladinInstance.current = window.A.aladin(aladinRef.current, {
        survey: 'P/DSS2/color',
        fov: 60, // Field of view in degrees
        target: target || '',
      });
    };

    loadAladinLite();

    // Clean up when the component unmounts
    return () => {
      if (aladinInstance.current) {
        // Remove the Aladin Lite content
        aladinRef.current.innerHTML = '';
        aladinInstance.current = null;
      }
    };
  }, [target]);

  // Update overlays when the 'overlays' prop changes
  useEffect(() => {
  if (aladinInstance.current && overlays) {
    console.log('Updating Aladin Lite overlays:', overlays);

    // Find the existing 'selectedObjects' catalog or create it
    const catalogs = aladinInstance.current.view.catalogs;
    let catalog = catalogs.find(
      (catalog) => catalog.name === 'selectedObjects'
    );

    if (!catalog) {
      // If the catalog doesn't exist, create it
      catalog = window.A.catalog({
        name: 'selectedObjects',
        sourceSize: 32,
        color: 'yellow',
      });
      aladinInstance.current.addCatalog(catalog);
    }

    // Remove existing sources from the catalog
    catalog.removeAll();

    // Add new sources
    overlays.forEach((coord) => {
      try {
        const ra = parseFloat(coord.ra);
        const dec = parseFloat(coord.dec);
    
        if (!isNaN(ra) && !isNaN(dec)) {
          const source = window.A.marker(ra, dec, {
            popupTitle: `Object ID: ${coord.id}`,
            popupDesc: `RA: ${ra}, Dec: ${dec}`,
            data: { id: coord.id },
          });
          catalog.addSources([source]);
          console.log(`Added marker at RA: ${ra}, Dec: ${dec}`);
        } else {
          throw new Error(
            `Invalid coordinates for object ID ${coord.id}: RA=${coord.ra}, Dec=${coord.dec}`
          );
        }
      } catch (error) {
        console.error('Error adding marker:', error);
      }
    });

    // Center the sky map on the first overlay coordinate
    if (overlays.length > 0) {
      const firstCoord = overlays[0];
      const ra = parseFloat(firstCoord.ra);
      const dec = parseFloat(firstCoord.dec);

      if (!isNaN(ra) && !isNaN(dec)) {
        aladinInstance.current.gotoRaDec(ra, dec);
        aladinInstance.current.setFov(0.5); // Adjust the field of view for zoom level
        console.log(`Sky map centered at RA: ${ra}, Dec: ${dec}`);
      }
    }
  }
}, [overlays]);

  return (
    <div
      style={{ width: '100%', height: '500px' }}
      ref={aladinRef}
    ></div>
  );
};

export default AladinLiteViewer;
