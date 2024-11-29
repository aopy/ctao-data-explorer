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
        fov: 60, // Initial field of view in degrees
        target: target || '',
      });
    };

    loadAladinLite();

    // Clean up when the component unmounts
    return () => {
      if (aladinInstance.current) {
        // Remove the Aladin Lite content
        if (aladinRef.current) {
          aladinRef.current.innerHTML = '';
        }
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
          color: 'yellow', // Make markers yellow for visibility
        });
        aladinInstance.current.addCatalog(catalog);
      }

      // Remove existing sources from the catalog
      catalog.removeAll();

      // Add new sources
      const raValues = [];
      const decValues = [];

      overlays.forEach((coord) => {
        const ra = parseFloat(coord.ra);
        const dec = parseFloat(coord.dec);

        if (!isNaN(ra) && !isNaN(dec)) {
          const source = window.A.marker(ra, dec, {
            popupTitle: `Observation ID: ${coord.id}`,
            popupDesc: `RA: ${ra}, Dec: ${dec}`,
            data: { id: coord.id },
          });
          catalog.addSources([source]);
          raValues.push(ra);
          decValues.push(dec);
          console.log(`Added marker at RA: ${ra}, Dec: ${dec}`);
        } else {
          console.error(
            `Invalid coordinates for object ID ${coord.id}: RA=${coord.ra}, Dec=${coord.dec}`
          );
        }
      });

      // Adjust the sky map view to include all markers
      if (raValues.length > 0 && decValues.length > 0) {
        // Calculate the min and max RA and Dec
        const minRa = Math.min(...raValues);
        const maxRa = Math.max(...raValues);
        const minDec = Math.min(...decValues);
        const maxDec = Math.max(...decValues);

        // Calculate the center RA and Dec
        let centerRa = (minRa + maxRa) / 2;
        let centerDec = (minDec + maxDec) / 2;

        // Calculate the required field of view
        const raDiff = maxRa - minRa;
        const decDiff = maxDec - minDec;
        let maxDiff = Math.max(raDiff, decDiff);

        // Handle edge cases where RA crosses 0/360 degrees
        if (raDiff > 180) {
          // Adjust RA values for wrap-around
          const adjustedRaValues = raValues.map((ra) => (ra < 180 ? ra + 360 : ra));
          const adjustedMinRa = Math.min(...adjustedRaValues);
          const adjustedMaxRa = Math.max(...adjustedRaValues);
          maxDiff = Math.max(adjustedMaxRa - adjustedMinRa, decDiff);
          const adjustedCenterRa = (adjustedMinRa + adjustedMaxRa) / 2;
          centerRa = adjustedCenterRa > 360 ? adjustedCenterRa - 360 : adjustedCenterRa;
        }

        // Add some padding to the field of view
        const fov = maxDiff * 1.2; // Increase by 20% for padding

        // Set minimum and maximum FOV limits
        const minFov = 0.1; // Minimum FOV in degrees
        const maxFov = 180; // Maximum FOV in degrees

        const adjustedFov = Math.min(Math.max(fov, minFov), maxFov);

        // Center the sky map and set the field of view
        aladinInstance.current.gotoRaDec(centerRa, centerDec);
        aladinInstance.current.setFov(adjustedFov);
        console.log(`Sky map centered at RA: ${centerRa}, Dec: ${centerDec}, FOV: ${adjustedFov}`);
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
