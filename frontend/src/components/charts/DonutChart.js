/**
 * DonutChart — Recharts-basiertes interaktives Kreisdiagramm
 * =============================================================
 * Enterprise-Qualitaet mit aktiver Segment-Hervorhebung, Tooltips und Legende.
 *
 * Usage:
 *   <DonutChart
 *     data={[
 *       { label: "Offen", value: 12, color: "#3b82f6" },
 *       { label: "Geschlossen", value: 25, color: "#22c55e" },
 *     ]}
 *     size={200}
 *     thickness={30}
 *     showLegend={true}
 *     centerLabel="37 Gesamt"
 *     onSegmentClick={(item, index) => console.log(item)}
 *   />
 */

import React, { useState, useMemo, useCallback } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Sector,
} from 'recharts';

// Active shape renderer — expanded segment with label, value, and percentage
function renderActiveShape(props) {
  const {
    cx, cy, innerRadius, outerRadius, startAngle, endAngle,
    fill, payload, value, percent,
  } = props;

  return (
    <g>
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius - 2}
        outerRadius={outerRadius + 6}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={1}
      />
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={outerRadius + 8}
        outerRadius={outerRadius + 12}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        opacity={0.4}
      />
    </g>
  );
}

function GermanTooltip({ active, payload }) {
  if (!active || !payload || payload.length === 0) return null;
  const item = payload[0];
  const total = item.payload._total || 1;
  const pct = Math.round((item.value / total) * 100);
  return (
    <div className="bg-gray-900 text-white text-xs px-3 py-2 rounded-lg shadow-xl border border-gray-700">
      <div className="flex items-center gap-1.5 mb-0.5">
        <span
          className="w-2 h-2 rounded-full inline-block"
          style={{ backgroundColor: item.payload.fill || item.color }}
        />
        <span className="font-semibold">{item.name}</span>
      </div>
      <p>
        {Number(item.value).toLocaleString('de-DE')} ({pct}%)
      </p>
    </div>
  );
}

function CustomLegend({ payload, hoveredIndex, onHover, onLeave }) {
  return (
    <div className="flex flex-wrap justify-center gap-x-4 gap-y-1.5 mt-2">
      {payload.map((entry, i) => (
        <button
          key={i}
          className={`flex items-center gap-1.5 text-xs transition-opacity ${
            hoveredIndex != null && hoveredIndex !== i ? 'opacity-40' : 'opacity-100'
          }`}
          onMouseEnter={() => onHover(i)}
          onMouseLeave={onLeave}
        >
          <span
            className="w-2.5 h-2.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-gray-600">{entry.value}</span>
          <span className="text-gray-400 font-medium">
            ({Number(entry.payload?.value || 0).toLocaleString('de-DE')})
          </span>
        </button>
      ))}
    </div>
  );
}

// Center label rendered as custom SVG text inside the PieChart
function CenterLabel({ cx, cy, label }) {
  if (!label) return null;
  const lines = String(label).split('\n');
  return (
    <g>
      {lines.map((line, i) => (
        <text
          key={i}
          x={cx}
          y={cy + (i - (lines.length - 1) / 2) * 18}
          textAnchor="middle"
          dominantBaseline="central"
          className="fill-gray-700"
          style={{ fontSize: lines.length > 1 ? 12 : 14, fontWeight: 600 }}
        >
          {line}
        </text>
      ))}
    </g>
  );
}

export default function DonutChart({
  data = [],
  size = 200,
  thickness = 30,
  showLegend = true,
  centerLabel,
  onSegmentClick,
}) {
  const [activeIndex, setActiveIndex] = useState(null);

  const total = useMemo(
    () => data.reduce((sum, d) => sum + (d.value || 0), 0),
    [data]
  );

  const chartData = useMemo(
    () =>
      data.map((item, i) => ({
        name: item.label,
        value: item.value || 0,
        fill: item.color || '#9ca3af',
        _total: total,
        _index: i,
      })),
    [data, total]
  );

  const outerRadius = (size - 20) / 2;
  const innerRadius = outerRadius - thickness;

  const handleMouseEnter = useCallback((_, index) => {
    setActiveIndex(index);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setActiveIndex(null);
  }, []);

  const handleClick = useCallback(
    (entry, index) => {
      if (onSegmentClick) {
        onSegmentClick(data[index], index);
      }
    },
    [onSegmentClick, data]
  );

  if (data.length === 0 || total === 0) {
    return (
      <div className="flex flex-col items-center">
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={outerRadius - thickness / 2}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth={thickness}
          />
          <text
            x={size / 2}
            y={size / 2}
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-gray-400"
            style={{ fontSize: 14 }}
          >
            Keine Daten
          </text>
        </svg>
      </div>
    );
  }

  // Derive center display when hovering
  const centerDisplay = activeIndex != null
    ? `${chartData[activeIndex].value.toLocaleString('de-DE')}\n${chartData[activeIndex].name}\n${Math.round((chartData[activeIndex].value / total) * 100)}%`
    : centerLabel || `${total.toLocaleString('de-DE')}\nGesamt`;

  return (
    <div className="flex flex-col items-center gap-2">
      <ResponsiveContainer width={size} height={size}>
        <PieChart>
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={innerRadius}
            outerRadius={outerRadius}
            paddingAngle={1}
            dataKey="value"
            nameKey="name"
            activeIndex={activeIndex}
            activeShape={renderActiveShape}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            onClick={handleClick}
            cursor={onSegmentClick ? 'pointer' : 'default'}
            animationDuration={500}
          >
            {chartData.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.fill}
                opacity={activeIndex != null && activeIndex !== i ? 0.5 : 1}
                className="transition-opacity duration-200"
              />
            ))}
          </Pie>
          <Tooltip content={<GermanTooltip />} />
          {/* Center label */}
          <CenterLabel
            cx={size / 2}
            cy={size / 2}
            label={centerDisplay}
          />
        </PieChart>
      </ResponsiveContainer>

      {showLegend && (
        <CustomLegend
          payload={chartData.map((d) => ({
            value: d.name,
            color: d.fill,
            payload: d,
          }))}
          hoveredIndex={activeIndex}
          onHover={setActiveIndex}
          onLeave={() => setActiveIndex(null)}
        />
      )}
    </div>
  );
}
