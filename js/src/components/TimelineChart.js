import React, { useMemo, useEffect, useState, useRef } from "react";
import axios from "axios";
import { palette, rgba } from "./chartColours";
import Plot from "react-plotly.js";

const fixZ = (s) => (s && !/[zZ]$/.test(s) ? s + "Z" : s);

const formatTtLabel = (tt_isot) => {
  if (!tt_isot) return "";
  const [d, t] = tt_isot.split("T"); // "YYYY-MM-DD" , "hh:mm:ss.sss"
  const [y, m, day] = d.split("-");
  return `${day}/${m}/${y} ${t.slice(0, 8)} TT`;
};

// Small conversion cache to avoid repeated calls
const convCache = new Map(); // key: `${mjd}` -> { utc_isot, tt_isot }

async function convertMjdTT(mjdVal) {
  const key = String(mjdVal);
  if (convCache.has(key)) return convCache.get(key);

  const resp = await axios.post("/api/convert_time", {
    value: key,
    input_format: "mjd",
    input_scale: "tt", // t_min/t_max are TT in ObsCore
  });

  const out = { utc_isot: resp.data.utc_isot, tt_isot: resp.data.tt_isot };
  convCache.set(key, out);
  return out;
}

const TimelineChart = ({ results, selectedIds = [], onSelectIds = () => {} }) => {
  const { columns, data } = results || {};
  const [rows, setRows] = useState([]); // [{id, x0UtcISO, x1UtcISO, ttStart, ttEnd}]
  const cancelRef = useRef(false);

  // measure available container height and drive Plotly layout.height with it
  const containerRef = useRef(null);
  const [plotH, setPlotH] = useState(240);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !("ResizeObserver" in window)) return;

    const ro = new ResizeObserver(() => {
      const h = Math.floor(el.getBoundingClientRect().height);
      setPlotH(Math.max(220, h));
    });

    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    cancelRef.current = false;

    (async () => {
      if (!columns || !data) {
        setRows([]);
        return;
      }

      const tminIdx = columns.indexOf("t_min");
      const tmaxIdx = columns.indexOf("t_max");
      const idIdx = columns.indexOf("obs_id");
      if (tminIdx === -1 || tmaxIdx === -1 || idIdx === -1) {
        setRows([]);
        return;
      }

      try {
        // Collect unique MJDs to reduce duplicate calls
        const mjds = new Set();
        for (const row of data) {
          const a = Number(row[tminIdx]);
          if (Number.isFinite(a)) mjds.add(a);
          const b = Number(row[tmaxIdx]);
          if (Number.isFinite(b)) mjds.add(b);
        }

        // Convert all unique MJDs (TT → {utc_isot, tt_isot})
        const uniq = Array.from(mjds);
        const all = await Promise.all(uniq.map(async (m) => [m, await convertMjdTT(m)]));
        if (cancelRef.current) return;

        const map = new Map(all); // mjd -> {utc_isot, tt_isot}

        const out = data.map((row) => {
          const id = String(row[idIdx]);
          const mjd0 = Number(row[tminIdx]);
          const mjd1 = Number(row[tmaxIdx]);
          const c0 = map.get(mjd0);
          const c1 = map.get(mjd1);

          return {
            id,
            x0UtcISO: c0 ? c0.utc_isot : null,
            x1UtcISO: c1 ? c1.utc_isot : null,
            ttStart: c0 ? c0.tt_isot : null,
            ttEnd: c1 ? c1.tt_isot : null,
          };
        });

        if (!cancelRef.current) setRows(out);
      } catch (e) {
        if (!cancelRef.current) setRows([]);
      }
    })();

    return () => {
      cancelRef.current = true;
    };
  }, [columns, data]);

  const shapes = useMemo(() => {
    return rows
      .filter((r) => r.x0UtcISO && r.x1UtcISO)
      .map((r) => {
        const isSelected = selectedIds.includes(r.id);
        return {
          type: "rect",
          xref: "x",
          yref: "paper",
          x0: fixZ(r.ttStart),
          x1: fixZ(r.ttEnd),
          y0: 0,
          y1: 1,
          fillcolor: isSelected ? rgba(palette.green, 0.75) : rgba(palette.grey, 0.35),
          line: {
            width: isSelected ? 2 : 0.5,
            color: rgba(palette.green, 0.95),
          },
          layer: "above",
        };
      });
  }, [rows, selectedIds]);

  const layout = useMemo(
    () => ({
      title: "Observation Timeline",
      xaxis: {
        type: "date",
        autorange: true,
        title: { text: "Time (TT)", standoff: 8 },
        tickformat: "%Y-%m-%d\n%H:%M:%S",
        tickangle: -45,
        automargin: true,
      },
      yaxis: { visible: false, range: [0, 1], fixedrange: true },
      showlegend: false,
      autosize: true,
      height: plotH,
      margin: { l: 40, r: 10, t: 42, b: 75 },
      hovermode: "closest",
      shapes,
    }),
    [shapes, plotH]
  );

  const plotData = useMemo(() => {
    if (!rows.length) return [];
    return [
      {
        type: "scatter",
        mode: "markers",
        x: rows.map((r) => {
          const t0 = new Date(fixZ(r.ttStart)).getTime();
          const t1 = new Date(fixZ(r.ttEnd)).getTime();
          return new Date((t0 + t1) / 2).toISOString();
        }),
        y: rows.map(() => 0.5),
        marker: { size: 20, opacity: 0 },
        customdata: rows.map((r) => r.id),
        hoverinfo: "text",
        hovertext: rows.map((r) => {
          const s = formatTtLabel(r.ttStart);
          const e = formatTtLabel(r.ttEnd);
          return `ID: ${r.id}<br>Start: ${s}<br>End: ${e}`;
        }),
      },
    ];
  }, [rows]);

  const [revision, setRevision] = useState(0);
  useEffect(() => {
    setRevision((v) => v + 1);
  }, [results, selectedIds, plotH]);

  if (!rows.length) return <div>No data available for the timeline.</div>;

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
    <div ref={containerRef} style={{ width: "100%", height: "100%", minHeight: 0 }}>
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
  );
};

export default TimelineChart;
