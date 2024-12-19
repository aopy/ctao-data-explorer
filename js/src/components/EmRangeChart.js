import React, { useMemo, useEffect, useState } from 'react';
import Plot from 'react-plotly.js';

const EmRangeChart = ({ results, selectedIds }) => {
  const { columns, data } = results || {};

  // Conversion factor from wavelength in meters to energy in TeV
  const wavelengthToTeV = (wavelength) => {
    const planckConstant = 6.626e-34; // Planck constant in J.s
    const speedOfLight = 2.998e8;     // Speed of light in m/s
    const electronVoltToJoule = 1.602e-19; // Conversion factor
    const TeVToEV = 1e12; // 1 TeV = 10^12 eV

    const energyInJoules = (planckConstant * speedOfLight) / wavelength;
    const energyInEv = energyInJoules / electronVoltToJoule;
    const energyInTeV = energyInEv / TeVToEV;
    return energyInTeV;
  };


  // Convert the results data into a format suitable for plotting, converting to TeV
  const emData = useMemo(() => {
    if (!columns || !data) {
      console.log('No columns or data available.');
      return [];
    }

    const em_min_index = columns.indexOf('em_min');
    const em_max_index = columns.indexOf('em_max');
    const id_index = columns.indexOf('obs_id');

    if (em_min_index === -1 || em_max_index === -1 || id_index === -1) {
      console.error('Required columns not found in results');
      return [];
    }

    const result = data.map((row) => {
      const em_min_val = parseFloat(row[em_min_index]);
      const em_max_val = parseFloat(row[em_max_index]);

      const em_min_tev = wavelengthToTeV(em_max_val);
      const em_max_tev = wavelengthToTeV(em_min_val);
      console.log(
          `Observation ID: ${row[id_index]}, em_min: ${em_min_val}, em_max: ${em_max_val}, em_min_tev: ${em_min_tev}, em_max_tev: ${em_max_tev}`
        );
      return {
        id: row[id_index].toString(),
        em_min: em_min_tev,
        em_max: em_max_tev,
      };
    });

    console.log('emData:', result);
    return result;
  }, [columns, data, wavelengthToTeV]);


  // Determine the earliest and latest values on the EM axis
  const [earliest_em_min, latest_em_max] = useMemo(() => {
    if (emData.length === 0) {
      return [0, 1];
    }

    let minVal = emData[0].em_min;
    let maxVal = emData[0].em_max;

    emData.forEach((item) => {
      if (item.em_min < minVal) {
        minVal = item.em_min;
      }
      if (item.em_max > maxVal) {
        maxVal = item.em_max;
      }
    });

    return [minVal, maxVal];
  }, [emData]);

  // Create shapes for each observation
  const shapes = useMemo(() => {
    if (emData.length === 0) {
      return [];
    }

    return emData.map((item) => {
      const isSelected = selectedIds && selectedIds.includes(item.id);
      const color = isSelected ? 'rgba(255, 165, 0, 0.7)' : 'rgba(0, 0, 255, 0.4)'; // Orange for selected blue for others

      return {
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: item.em_min,
        x1: item.em_max,
        y0: 0,
        y1: 1,
        fillcolor: color,
        line: {
            width: isSelected ? 2 : 0, // Show line for selected
            color: isSelected ? 'red' : 'transparent',
        },
        layer: 'below',
      };
    });
  }, [emData, selectedIds]);

  // Layout configuration
  const layout = useMemo(() => {
    return {
      title: 'Electromagnetic Range (TeV)',
      xaxis: {
        type: 'log',
        autorange: true,
        title: 'Energy (TeV)',
          tickformat: '.1e',
      },
       xaxis2: {
          type: 'log',
            overlaying: 'x',
             side: 'top',
              title: 'Wavelength (m)',
             autorange: true,
             tickformat: '.1e',
            // Define a static range based on minimum and maximum values from original input
             tickvals: [1e-14, 1e-12, 1e-10, 1e-8, 1e-6, 1e-4, 1e-2, 1, 1e2, 1e4],
            ticktext: ['1e-14', '1e-12', '1e-10', '1e-8', '1e-6', '1e-4', '1e-2', '1', '1e2', '1e4'],
           showgrid: true, // Keep this for grid lines
            showline: true, // Keep this for axis line
          showticklabels: true, // Make sure axis tick labels are displayed

      },
      yaxis: {
        visible: false,
        range: [0, 1],
        fixedrange: true,
      },
      showlegend: false,
      height: 200,
      margin: { l: 50, r: 50, t: 50, b: 50 },
      hovermode: 'closest',
      shapes: shapes,
    };
  }, [earliest_em_min, latest_em_max, shapes]);


  const plotData = useMemo(() => {
    if (emData.length === 0) {
      return [];
    }
    // Static values for the top axis
     const wavelengthTickVals = [1e-14, 1e-12, 1e-10, 1e-8, 1e-6, 1e-4, 1e-2, 1, 1e2, 1e4];
     const emptyY =  Array(wavelengthTickVals.length).fill(0.95); // Constant y position to be on the top
    return [
      {
        type: 'scatter',
        mode: 'markers',
        x: emData.map((item) => (item.em_min + item.em_max) / 2),
        y: emData.map(() => 0.5),
        xaxis:'x',
        marker: { size: 30, opacity: 0.1 },
        hoverinfo: 'text',
        hovertext: emData.map(
          (item) =>
            `ID: ${item.id}<br>Energy Min: ${item.em_min.toExponential(2)} TeV<br>Energy Max: ${item.em_max.toExponential(2)} TeV`
        ),
      },
       {
            type: 'scatter',
             mode: 'markers',
            x:  wavelengthTickVals, // Use wavelength values as x points
             y: emptyY,       // constant Y position, same for all values
            xaxis:'x2',
            marker: { size: 0, opacity: 0 }, // invisible markers
             hoverinfo: 'none', // Remove hover
             },
        {
           type: 'scatter',
        mode: 'markers',
         x: emData.map((item) => (item.em_min + item.em_max) / 2),
        y: emData.map(() => 0.5),
            xaxis:'x2',
             marker: { size: 0, opacity: 0 },
             hoverinfo: 'text',
             hovertext: emData.map(
                  (item) => `ID: ${item.id}<br>Wavelength Min: ${1.24e-6 / (item.em_max *1e12)} m<br>Wavelength Max: ${1.24e-6 / (item.em_min *1e12)} m`
              ),

        }
    ];
  }, [emData]);

  console.log('Shapes:', shapes);
  console.log('Layout:', layout);
  console.log('Plot Data:', plotData);

  const [revision, setRevision] = useState(0);

  useEffect(() => {
    setRevision((prev) => prev + 1);
  }, [results, selectedIds]);

  if (emData.length === 0) {
    return <div>No data available for the EM range chart.</div>;
  }

  return (
    <div style={{ width: '100%', height: '200px' }}>
      <Plot
        data={plotData}
        layout={layout}
        revision={revision}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler={true}
           config={{
             responsive: true,
             displayModeBar: false,
           }}
      />
    </div>
  );
};

export default EmRangeChart;
