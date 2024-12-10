import React, { useMemo, useEffect, useState } from 'react';
import Plot from 'react-plotly.js';

const TimelineChart = ({ results, selectedIds }) => {
  const { columns, data } = results || {};

  // Convert the results data into a format suitable for plotting
  const timelineData = useMemo(() => {
    if (!columns || !data) {
      console.log('No columns or data available.');
      return [];
    }

    const t_min_index = columns.indexOf('t_min');
    const t_max_index = columns.indexOf('t_max');
    const id_index = columns.indexOf('obs_id');

    if (t_min_index === -1 || t_max_index === -1 || id_index === -1) {
      console.error('Required columns not found in results');
      return [];
    }

    // Function to convert Modified Julian Date (MJD) to JavaScript Date
    const mjdToDate = (mjd) => {
      if (isNaN(mjd)) {
        console.error('Invalid MJD:', mjd);
        return new Date(NaN);
      }
      const MJD_UNIX_EPOCH = 40587; // MJD at Unix Epoch (1970-01-01)
      const millisecondsPerDay = 86400000; // Number of milliseconds in a day
      const unixTime = (mjd - MJD_UNIX_EPOCH) * millisecondsPerDay;
      return new Date(unixTime); // Date in UTC
    };

    const result = data.map((row) => {
      const t_min_mjd = parseFloat(row[t_min_index]);
      const t_max_mjd = parseFloat(row[t_max_index]);
      const t_min_date = mjdToDate(t_min_mjd);
      const t_max_date = mjdToDate(t_max_mjd);
      console.log(
        `Observation ID: ${row[id_index]}, t_min: ${t_min_mjd} -> ${t_min_date}, t_max: ${t_max_mjd} -> ${t_max_date}`
      );
      return {
        id: row[id_index].toString(),
        t_min: t_min_date,
        t_max: t_max_date,
      };
    });

    console.log('timelineData:', result);
    return result;
  }, [columns, data]);

  // Determine the earliest and latest times
  const [earliest_t_min, latest_t_max] = useMemo(() => {
    if (timelineData.length === 0) {
      const now = new Date();
      return [now, now];
    }

    let minDate = timelineData[0].t_min;
    let maxDate = timelineData[0].t_max;

    timelineData.forEach((item) => {
      if (item.t_min < minDate) {
        minDate = item.t_min;
      }
      if (item.t_max > maxDate) {
        maxDate = item.t_max;
      }
    });

    return [minDate, maxDate];
  }, [timelineData]);

    // Create shapes for each observation
    const shapes = timelineData.map((item) => {
      const isSelected = selectedIds && selectedIds.includes(item.id);

      return {
        type: 'rect',
        xref: 'x',
        yref: 'paper',
        x0: item.t_min.toISOString(),
        x1: item.t_max.toISOString(),
        y0: 0,
        y1: 1,
        fillcolor: isSelected ? 'blue' : 'lightblue',
        line: {
          width: isSelected ? 2 : 1,         // Thicker border for selected
          color: isSelected ? 'red' : 'blue' // Red border for selected, blue for unselected
        },
        layer: 'above'
      };
    });


  // Layout configuration
  const layout = useMemo(() => {
    return {
      title: 'Observation Timeline',
      xaxis: {
        type: 'date',
        // Let Plotly automatically determine the range
        autorange: true,
        // Ror fixed range:
        // range: [
        //   earliest_t_min.toISOString(),
        //   latest_t_max.toISOString()
        // ],
        title: 'Time',
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
  }, [earliest_t_min, latest_t_max, shapes]);

  // Create an invisible scatter trace for hover interactions
  const plotData = useMemo(() => {
    if (timelineData.length === 0) {
      return [];
    }

    return [
      {
        type: 'scatter',
        mode: 'markers',
        x: timelineData.map((item) =>
          new Date(
            (item.t_min.getTime() + item.t_max.getTime()) / 2
          ).toISOString()
        ),
        y: timelineData.map(() => 0.5),
        marker: { size: 20, opacity: 0 },
        hoverinfo: 'text',
        hovertext: timelineData.map(
          (item) =>
            `ID: ${item.id}<br>Start: ${item.t_min.toUTCString()}<br>End: ${item.t_max.toUTCString()}`
        ),
      },
    ];
  }, [timelineData]);

  console.log('Shapes:', shapes);
  console.log('Layout:', layout);
  console.log('xaxis.range:', layout.xaxis.range);
  console.log('Plot Data:', plotData);

  const [revision, setRevision] = useState(0);

  useEffect(() => {
    setRevision((prev) => prev + 1);
  }, [layout]);

  if (timelineData.length === 0) {
    return <div>No data available for the timeline.</div>;
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

export default TimelineChart;