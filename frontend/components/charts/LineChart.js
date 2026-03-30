/**
 * LineChart — Recharts-basiertes interaktives Liniendiagramm
 * =============================================================
 * Fuer Trenddaten mit mehreren Linien, Tooltips, Brush und Referenzlinien.
 *
 * Usage:
 *   <LineChart
 *     data={[{label: "Jan", value1: 12, value2: 8}, ...]}
 *     lines={[
 *       {key: "value1", color: "#3b82f6", label: "Neu"},
 *       {key: "value2", color: "#10b981", label: "Geschlossen"},
 *     ]}
 *     xKey="label"
 *     height={300}
 *     showGrid={true}
 *     showBrush={false}
 *     referenceLine={{ y: 10, label: "Ziel", color: "#ef4444" }}
 *     onPointClick={(data, lineKey, index) => {}}
 *   />
 */

import React, { useCallback } from 'react';
import {
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Brush,
  ReferenceLine,
} from 'recharts';

function GermanTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="bg-gray-900 text-white text-xs px-3 py-2 rounded-lg shadow-xl border border-gray-700">
      <p className="font-semibold mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="flex items-center gap-1.5">
          <span
            className="w-2 h-2 rounded-full inline-block"
            style={{ backgroundColor: entry.color }}
          />
          <span>{entry.name}: {Number(entry.value).toLocaleString('de-DE')}</span>
        </p>
      ))}
    </div>
  );
}

export default function LineChart({
  data = [],
  lines = [],
  xKey = 'label',
  height = 300,
  showGrid = true,
  showBrush = false,
  referenceLine,
  onPointClick,
}) {
  const handleClick = useCallback(
    (lineKey) => (point, index) => {
      if (onPointClick) {
        onPointClick(point, lineKey, index);
      }
    },
    [onPointClick]
  );

  if (data.length === 0 || lines.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm text-gray-400" style={{ height }}>
        Keine Daten vorhanden
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsLineChart
        data={data}
        margin={{ top: 10, right: 20, left: 10, bottom: showBrush ? 30 : 5 }}
      >
        {showGrid && (
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        )}
        <XAxis
          dataKey={xKey}
          tick={{ fontSize: 11, fill: '#6b7280' }}
          axisLine={{ stroke: '#e5e7eb' }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#6b7280' }}
          axisLine={{ stroke: '#e5e7eb' }}
          tickFormatter={(v) => v.toLocaleString('de-DE')}
        />
        <Tooltip content={<GermanTooltip />} />
        <Legend
          iconType="circle"
          iconSize={8}
          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
        />
        {referenceLine && (
          <ReferenceLine
            y={referenceLine.y}
            label={{
              value: referenceLine.label || '',
              position: 'right',
              fill: referenceLine.color || '#ef4444',
              fontSize: 11,
            }}
            stroke={referenceLine.color || '#ef4444'}
            strokeDasharray="6 3"
            strokeWidth={1.5}
          />
        )}
        {showBrush && (
          <Brush
            dataKey={xKey}
            height={20}
            stroke="#6b7280"
            travellerWidth={8}
          />
        )}
        {lines.map((line) => (
          <Line
            key={line.key}
            type="monotone"
            dataKey={line.key}
            name={line.label || line.key}
            stroke={line.color || '#3b82f6'}
            strokeWidth={2}
            dot={{ r: 4, fill: line.color || '#3b82f6', strokeWidth: 0 }}
            activeDot={{
              r: 6,
              fill: line.color || '#3b82f6',
              stroke: '#fff',
              strokeWidth: 2,
              onClick: handleClick(line.key),
              cursor: onPointClick ? 'pointer' : 'default',
            }}
            animationDuration={500}
          />
        ))}
      </RechartsLineChart>
    </ResponsiveContainer>
  );
}
