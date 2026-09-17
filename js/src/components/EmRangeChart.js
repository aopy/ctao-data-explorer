import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import PropTypes from "prop-types";
import Plot from "react-plotly.js";

import { palette, rgba } from "./chartColours";

const MAX_INDIVIDUAL_RANGES = 80;
const ENERGY_BIN_PRECISION = 3;

const formatGroupedIds = (ids, limit = 3) => {
  const visibleIds = ids.slice(0, limit);
  const remainingCount = ids.length - visibleIds.length;

  if (remainingCount <= 0) {
    return visibleIds.join(", ");
  }

  return `${visibleIds.join(", ")} and ${remainingCount} more`;
};

const EmRangeChart = ({
  results = {columns: [], data: []},
  selectedIds = [],
  onSelectIds = () => {},
}) => {
  const { columns, data } = results || {};
  const infoTipRef = useRef(null);

  const wavelengthToTeV = useCallback((wavelength) => {
    const planckConstant = 6.626e-34;
    const speedOfLight = 2.998e8;
    const electronVoltToJoule = 1.602e-19;
    const TeVToEV = 1e12;

    const energyInJoules =
      (planckConstant * speedOfLight) / wavelength;
    const energyInEv =
      energyInJoules / electronVoltToJoule;

    return energyInEv / TeVToEV;
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

    if (
      em_min_index === -1 ||
      em_max_index === -1 ||
      id_index === -1
    ) {
      return [];
    }

    return data
      .map((row) => {
        const wavelengthMin = Number(row[em_min_index]);
        const wavelengthMax = Number(row[em_max_index]);
        const id = String(row[id_index] ?? "").trim();

        if (
          !Number.isFinite(wavelengthMin) ||
          !Number.isFinite(wavelengthMax) ||
          wavelengthMin <= 0 ||
          wavelengthMax <= 0 ||
          !id
        ) {
          return null;
        }

        const energyFromMinWavelength = wavelengthToTeV(wavelengthMin);
        const energyFromMaxWavelength = wavelengthToTeV(wavelengthMax);

        return {
          id,
          energyMin: Math.min(
            energyFromMinWavelength,
            energyFromMaxWavelength
          ),
          energyMax: Math.max(
            energyFromMinWavelength,
            energyFromMaxWavelength
          ),
        };
      })
      .filter(Boolean);
  }, [columns, data, wavelengthToTeV]);

  const isAggregated = emData.length > MAX_INDIVIDUAL_RANGES;

  const chartRanges = useMemo(() => {
    if (!emData.length) {
      return [];
    }

    if (!isAggregated) {
      return emData.map((item) => ({
        key: item.id,
        ids: [item.id],
        energyMin: item.energyMin,
        energyMax: item.energyMax,
        count: 1,
      }));
    }

    const groups = new Map();

    emData.forEach((item) => {
      const logMin = Math.log10(item.energyMin);
      const logMax = Math.log10(item.energyMax);

      const roundedLogMin = Number(logMin.toFixed(ENERGY_BIN_PRECISION));
      const roundedLogMax = Number(logMax.toFixed(ENERGY_BIN_PRECISION));

      const key = `${roundedLogMin}:${roundedLogMax}`;
      const existing = groups.get(key);

      if (existing) {
        existing.ids.push(item.id);
        existing.count += 1;

        // Retain the complete range represented by the group
        existing.energyMin = Math.min(existing.energyMin, item.energyMin);
        existing.energyMax = Math.max(existing.energyMax, item.energyMax);
      } else {
        groups.set(key, {
          key,
          ids: [item.id],
          energyMin: item.energyMin,
          energyMax: item.energyMax,
          count: 1,
        });
      }
    });

    return Array.from(groups.values()).sort(
      (a, b) =>
        a.energyMin - b.energyMin ||
        a.energyMax - b.energyMax
    );
  }, [emData, isAggregated]);

  const shapes = useMemo(() => {
    if (!chartRanges.length) {
      return [];
    }

    const currentSelectedIds = selectedIds || [];

    return chartRanges.map((item, index) => {
      const selectedCount = item.ids.filter((id) =>
        currentSelectedIds.includes(id)
      ).length;

      const allSelected =
        item.ids.length > 0 && selectedCount === item.ids.length;

      const partiallySelected =
        selectedCount > 0 && selectedCount < item.ids.length;

      let fillColor = rgba(palette.blue, 0.35);
      let lineColor = "transparent";
      let lineWidth = 0;

      if (allSelected) {
        fillColor = rgba(palette.orange, 0.75);
        lineColor = "red";
        lineWidth = 2;
      } else if (partiallySelected) {
        fillColor = rgba(palette.orange, 0.45);
        lineColor = rgba(palette.orange, 0.9);
        lineWidth = 1;
      }

      return {
        type: "rect",
        xref: "x",
        yref: "y",
        x0: item.energyMin,
        x1: item.energyMax,
        y0: index - 0.35,
        y1: index + 0.35,
        fillcolor: fillColor,
        line: {
          width: lineWidth,
          color: lineColor,
        },
        layer: "below",
      };
    });
  }, [chartRanges, selectedIds]);

  const layout = useMemo(
    () => ({
      title: {
        text: "Electromagnetic Range",
        x: 0.5,
        xanchor: "center",
      },
      xaxis: {
        type: "log",
        autorange: true,
        title: {
          text: "Energy (TeV)",
          standoff: 8,
        },
        tickformat: ".1e",
        nticks: 6,
        tickangle: -30,
        automargin: true,
      },
      yaxis: {
        visible: false,
        range: [
          -0.5,
          Math.max(chartRanges.length - 0.5, 0.5),
        ],
        fixedrange: true,
      },
      showlegend: false,
      autosize: true,
      margin: {
        l: 40,
        r: 34,
        t: 48,
        b: 65,
      },
      hovermode: "closest",
      shapes,
    }),
    [shapes, chartRanges.length]
  );

  const plotData = useMemo(() => {
    if (!chartRanges.length) {
      return [];
    }

    return [
      {
        type: "scatter",
        mode: "markers",
        x: chartRanges.map((item) =>
          Math.sqrt(item.energyMin * item.energyMax)
        ),
        y: chartRanges.map((_, index) => index),
        marker: {
          size: isAggregated ? 18 : 12,
          opacity: 0.01,
        },
        customdata: chartRanges.map((item) => ({
          ids: item.ids,
          count: item.count,
        })),
        hoverinfo: "text",
        hovertext: chartRanges.map((item) => {
          const energyText =
            `<br>Energy Min: ${item.energyMin.toExponential(2)} TeV` +
            `<br>Energy Max: ${item.energyMax.toExponential(2)} TeV`;

          if (item.count === 1) {
            return `Observation ID: ${item.ids[0]}${energyText}`;
          }

          return (
            `${item.count} observations` +
            `<br>Example IDs: ${formatGroupedIds(item.ids)}` +
            energyText +
            `<br><i>Click to select the entire group</i>`
          );
        }),
        cliponaxis: false,
      },
    ];
  }, [chartRanges, isAggregated]);

  const [revision, setRevision] = useState(0);

  useEffect(() => {
    setRevision((prev) => prev + 1);
  }, [chartRanges, selectedIds]);

  if (!emData.length) return <div>No data available for the EM range chart.</div>;

  const handleClick = (event) => {
    if (!event?.points?.length) {
      return;
    }

    const clickedIds = event.points[0].customdata?.ids || [];

    if (!clickedIds.length) {
      return;
    }

    const currentIds = selectedIds || [];

    const allClickedIdsSelected = clickedIds.every((id) =>
      currentIds.includes(id)
    );

    const next = allClickedIdsSelected
      ? currentIds.filter((id) => !clickedIds.includes(id))
      : Array.from(new Set([...currentIds, ...clickedIds]));

    onSelectIds(next);
  };

  const clearAll = () => onSelectIds([]);

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        className="d-flex align-items-center justify-content-between gap-2 px-2 py-1"
        style={{
          flex: "0 0 auto",
          minHeight: "32px",
          borderBottom: "1px solid var(--bs-border-color, #dee2e6)",
        }}
      >
        <div className="small text-muted text-truncate">
          {isAggregated
            ? `${emData.length} observations grouped into ${chartRanges.length} energy ranges`
            : `${emData.length} observation${emData.length === 1 ? "" : "s"}`}
        </div>

        <button
          ref={infoTipRef}
          type="button"
          className="btn btn-sm btn-link p-0 flex-shrink-0"
          data-bs-toggle="tooltip"
          data-bs-placement="left"
          title={
            isAggregated
              ? "Energy values were converted from wavelength measurements. Similar energy ranges are grouped, and each displayed number is the number of observations in that group."
              : "Energy values were converted from wavelength measurements."
          }
          aria-label="EM Range conversion information"
        >
          <i className="bi bi-info-circle" />
        </button>
      </div>

    <div
      style={{
        flex: "1 1 auto",
        minHeight: 0,
        position: "relative",
      }}
    >
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

EmRangeChart.propTypes = {
  results: PropTypes.shape({
    columns: PropTypes.arrayOf(PropTypes.string),
    data: PropTypes.arrayOf(
      PropTypes.arrayOf(PropTypes.any)
    ),
  }),
  selectedIds: PropTypes.arrayOf(
    PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.number,
    ])
  ),
  onSelectIds: PropTypes.func,
};

export default EmRangeChart;
