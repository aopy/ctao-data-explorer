import React, { useMemo, useEffect, useState } from 'react';
import Plot from 'react-plotly.js';

const EmRangeChart = ({ results, selectedIds }) => {
  const { columns, data } = results || {};

  // Convert the results data into a format suitable for plotting
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

      console.log(
        `Observation ID: ${row[id_index]}, em_min: ${em_min_val}, em_max: ${em_max_val}`
      );
      return {
        id: row[id_index].toString(),
        em_min: em_min_val,
        em_max: em_max_val,
      };
    });

    console.log('emData:', result);
    return result;
  }, [columns, data]);

  // Determine the earliest and latest values on the EM axis
  const [earliest_em_min, latest_em_max] = useMemo(() => {
    if (emData.length === 0) {
      // Provide a default range
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
      return {
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: item.em_min,
        x1: item.em_max,
        y0: 0,
        y1: 1,
        fillcolor: isSelected ? 'rgba(255, 165, 0, 0.5)' : 'rgba(255, 255, 0, 0.5)',
        line: {
          width: isSelected ? 2 : 1,   // Thicker line for selected
          color: isSelected ? 'red' : 'blue',
        },
        layer: 'below', // Draw shapes behind data traces
      };
    });
  }, [emData, selectedIds]);

  // Layout configuration
  const layout = useMemo(() => {
    return {
      title: 'Electromagnetic Range',
      xaxis: {
        type: 'linear',
        autorange: true,
        title: 'EM Values',
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

  // Create an invisible scatter trace for hover interactions
  const plotData = useMemo(() => {
    if (emData.length === 0) {
      return [];
    }

    return [
      {
        type: 'scatter',
        mode: 'markers',
        x: emData.map((item) => (item.em_min + item.em_max) / 2),
        y: emData.map(() => 0.5),
        marker: { size: 30, opacity: 0.1 },
        hoverinfo: 'text',
        hovertext: emData.map(
          (item) =>
            `ID: ${item.id}<br>EM Min: ${item.em_min}<br>EM Max: ${item.em_max}`
        ),
      },
    ];
  }, [emData]);

  console.log('Shapes:', shapes);
  console.log('Layout:', layout);
  console.log('Plot Data:', plotData);

  const [revision, setRevision] = useState(0);

  useEffect(() => {
    setRevision((prev) => prev + 1);
  }, [layout]);

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
        config={{ responsive: true }}
      />
    </div>
  );
};

export default EmRangeChart;
