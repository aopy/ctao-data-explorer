import React, { useMemo, useEffect, useState, useRef, useCallback } from "react";
import { palette, rgba } from "./chartColours";
import Plot from "react-plotly.js";

const EmRangeChart = ({ results, selectedIds, onSelectIds = () => {} }) => {
  const { columns, data } = results || {};
  const infoTipRef = useRef(null);

  // Make stable so useMemo deps don't churn
  const wavelengthToTeV = useCallback((wavelength) => {
    const planckConstant = 6.626e-34; // J.s
    const speedOfLight = 2.998e8; // m/s
    const electronVoltToJoule = 1.602e-19;
    const TeVToEV = 1e12;

    const energyInJoules = (planckConstant * speedOfLight) / wavelength;
    const energyInEv = energyInJoules / electronVoltToJoule;
    return energyInEv / TeVToEV;
  }, []);

  // fit chart to the available height
  const wrapRef = useRef(null);
  const [plotH, setPlotH] = useState(220);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el || !("ResizeObserver" in window)) return;

    const ro = new ResizeObserver(() => {
      const h = Math.floor(el.getBoundingClientRect().height);

      setPlotH(Math.max(200, h - 6));
    });

    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Bootstrap tooltip init
  useEffect(() => {
    const el = infoTipRef.current;
    const bs = window.bootstrap;
    if (!el || !bs?.Tooltip) return;
    const t = new bs.Tooltip(el);
    return () => t.dispose();
  }, []);

  const emData = useMemo(() => {
    if (!columns || !data) return [];

    const em_min_index = columns.indexOf("em_min");
    const em_max_index = columns.indexOf("em_max");
    const id_index = columns.indexOf("obs_id");

    if (em_min_index === -1 || em_max_index === -1 || id_index === -1) return [];

    return data.map((row) => {
      const em_min_val = parseFloat(row[em_min_index]);
      const em_max_val = parseFloat(row[em_max_index]);

      return {
        id: row[id_index].toString(),
        em_min: wavelengthToTeV(em_min_val),
        em_max: wavelengthToTeV(em_max_val),
      };
    });
  }, [columns, data, wavelengthToTeV]);

  const shapes = useMemo(() => {
    if (!emData.length) return [];

    return emData.map((item) => {
      const isSelected = selectedIds && selectedIds.includes(item.id);
      const color = isSelected ? rgba(palette.orange, 0.75) : rgba(palette.blue, 0.35);

      return {
        type: "rect",
        xref: "x",
        yref: "paper",
        x0: item.em_min,
        x1: item.em_max,
        y0: 0,
        y1: 1,
        fillcolor: color,
        line: {
          width: isSelected ? 2 : 0,
          color: isSelected ? "red" : "transparent",
        },
        layer: "below",
      };
    });
  }, [emData, selectedIds]);

  const layout = useMemo(
    () => ({
      title: "Electromagnetic Range",
      xaxis: {
        type: "log",
        autorange: true,
        title: { text: "Energy (TeV)", standoff: 8 },
        tickformat: ".1e",
        nticks: 6,
        tickangle: -30,
        automargin: true,
      },
      yaxis: { visible: false, range: [0, 1], fixedrange: true },
      showlegend: false,
      autosize: true,
      height: plotH,
      margin: { l: 40, r: 34, t: 42, b: 65 },
      hovermode: "closest",
      shapes,
    }),
    [shapes, plotH]
  );

  const plotData = useMemo(() => {
    if (!emData.length) return [];
    return [
      {
        type: "scatter",
        mode: "markers",
        x: emData.map((item) => (item.em_min + item.em_max) / 2),
        y: emData.map(() => 0.5),
        marker: { size: 30, opacity: 0.1 },
        customdata: emData.map((it) => it.id),
        hoverinfo: "text",
        hovertext: emData.map(
          (item) =>
            `ID: ${item.id}<br>Energy Min: ${item.em_min.toExponential(
              2
            )} TeV<br>Energy Max: ${item.em_max.toExponential(2)} TeV`
        ),
      },
    ];
  }, [emData]);

  const [revision, setRevision] = useState(0);
  useEffect(() => {
    setRevision((prev) => prev + 1);
  }, [results, selectedIds, plotH]);

  if (!emData.length) return <div>No data available for the EM range chart.</div>;

  const handleClick = (e) => {
    if (!e?.points?.length) return;
    const id = e.points[0].customdata;
    const next = selectedIds.includes(id)
      ? selectedIds.filter((x) => x !== id)
      : [...selectedIds, id];
    onSelectIds(next);
  };

  const clearAll = () => onSelectIds([]);

  return (
    <div
      ref={wrapRef}
      style={{
        width: "100%",
        height: "100%",
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        position: "relative",
      }}
    >
    {/* info tooltip (top-right) */}
      <button
        ref={infoTipRef}
        type="button"
        className="btn btn-sm btn-link p-0"
        style={{ position: "absolute", top: 6, right: 8, zIndex: 5 }}
        data-bs-toggle="tooltip"
        data-bs-placement="left"
        title="The Energy (TeV) values were converted from wavelength (m) measurements."
        aria-label="EM Range conversion info"
      >
        <i className="bi bi-info-circle"></i>
      </button>
      <div style={{ flex: "1 1 auto", minHeight: 0 }}>
        <Plot
          data={plotData}
          layout={layout}
          revision={revision}
          style={{ width: "100%", height: "100%" }}
          useResizeHandler
          config={{ responsive: true }}
          onClick={handleClick}
          onDoubleClick={clearAll}
        />
      </div>
    </div>
  );
};

export default EmRangeChart;
