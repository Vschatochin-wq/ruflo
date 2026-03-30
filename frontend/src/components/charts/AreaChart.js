/**
 * AreaChart — Recharts-basiertes Flaechendiagramm
 * ==================================================
 * Fuer kumulative/gestapelte Daten mit Verlaufsfuellungen.
 *
 * Usage:
 *   <AreaChart
 *     data={[{label: "Jan", value: 12}, ...]}
 *     areas={[{key: "value", color: "#3b82f6", label: "Reklamationen"}]}
 *     xKey="label"
 *     height={300}
 *     stacked={false}
 *     gradient={true}
 *   />
 */

import React from 'react';
import {
  AreaChart as RechartsAreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
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

export default function AreaChart({
  data = [],
  areas = [],
  xKey = 'label',
  height = 300,
  stacked = false,
  gradient = true,
}) {
  if (data.length === 0 || areas.length === 0) {
    return (
      <div className="flex items-center justify-center text-sm text-gray-400" style={{ height }}>
        Keine Daten vorhanden
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <RechartsAreaChart
        data={data}
        margin={{ top: 10, right: 20, left: 10, bottom: 5 }}
      >
        <defs>
          {gradient &&
            areas.map((area) => (
              <linearGradient
                key={`gradient-${area.key}`}
                id={`gradient-${area.key}`}
                x1="0"
                y1="0"
                x2="0"
                y2="1"
              >
                <stop offset="0%" stopColor={area.color || '#3b82f6'} stopOpacity={0.3} />
                <stop offset="95%" stopColor={area.color || '#3b82f6'} stopOpacity={0.02} />
              </linearGradient>
            ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
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
        {areas.map((area) => (
          <Area
            key={area.key}
            type="monotone"
            dataKey={area.key}
            name={area.label || area.key}
            stroke={area.color || '#3b82f6'}
            strokeWidth={2}
            fill={gradient ? `url(#gradient-${area.key})` : (area.color || '#3b82f6')}
            fillOpacity={gradient ? 1 : 0.15}
            stackId={stacked ? 'stack' : undefined}
            animationDuration={500}
            dot={{ r: 3, fill: area.color || '#3b82f6', strokeWidth: 0 }}
            activeDot={{ r: 5, stroke: '#fff', strokeWidth: 2 }}
          />
        ))}
      </RechartsAreaChart>
    </ResponsiveContainer>
  );
}
