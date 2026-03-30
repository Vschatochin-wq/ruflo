/**
 * BarChart — Recharts-basiertes interaktives Balkendiagramm
 * ===========================================================
 * Enterprise-Qualitaet mit Tooltips, Zoom (Brush) und Klick-Handler.
 *
 * Usage:
 *   <BarChart
 *     data={[{ label: "Jan", value: 12 }, { label: "Feb", value: 8 }]}
 *     color="blue"
 *     maxHeight={200}
 *     showValues={true}
 *     orientation="vertical"
 *     onBarClick={(item, index) => console.log(item)}
 *   />
 *
 * Props:
 *   - data: Array<{ label: string, value: number, color?: string }>
 *   - color: string — Standardfarbe (blue, green, red, purple, amber, orange)
 *   - maxHeight: number — Hoehe des Charts in px
 *   - showValues: boolean — Werte an den Balken anzeigen
 *   - orientation: "vertical" | "horizontal"
 *   - onBarClick: (item, index) => void — Optionaler Klick-Handler
 *   - barWidth: number — (ignoriert, fuer Abwaertskompatibilitaet)
 *   - animate: boolean — Animation aktivieren (Standard true)
 */

import React, { useState, useCallback } from 'react';
import {
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Brush,
  Cell,
  LabelList,
} from 'recharts';

const COLOR_MAP = {
  blue: '#3b82f6',
  green: '#22c55e',
  red: '#ef4444',
  purple: '#a855f7',
  amber: '#f59e0b',
  orange: '#f97316',
  indigo: '#6366f1',
};

const COLOR_HOVER_MAP = {
  blue: '#2563eb',
  green: '#16a34a',
  red: '#dc2626',
  purple: '#9333ea',
  amber: '#d97706',
  orange: '#ea580c',
  indigo: '#4f46e5',
};

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
          <span>Wert: {Number(entry.value).toLocaleString('de-DE')}</span>
        </p>
      ))}
    </div>
  );
}

export default function BarChart({
  data = [],
  color = 'blue',
  maxHeight = 200,
  showValues = true,
  orientation = 'vertical',
  onBarClick,
  barWidth,
  animate = true,
}) {
  const [activeIndex, setActiveIndex] = useState(null);

  const fillColor = COLOR_MAP[color] || COLOR_MAP.blue;
  const hoverColor = COLOR_HOVER_MAP[color] || COLOR_HOVER_MAP.blue;

  const chartData = data.map((item, i) => ({
    name: item.label,
    value: item.value || 0,
    _color: item.color || null,
    _index: i,
  }));

  const handleClick = useCallback(
    (entry, index) => {
      if (onBarClick) {
        onBarClick(data[index], index);
      }
    },
    [onBarClick, data]
  );

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-sm text-gray-400">
        Keine Daten vorhanden
      </div>
    );
  }

  const showBrush = data.length > 8;
  const isHorizontal = orientation === 'horizontal';
  const chartHeight = isHorizontal
    ? Math.max(maxHeight, data.length * 40 + 40)
    : maxHeight;

  if (isHorizontal) {
    return (
      <ResponsiveContainer width="100%" height={chartHeight}>
        <RechartsBarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 40, left: 10, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            tickFormatter={(v) => v.toLocaleString('de-DE')}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={100}
            tick={{ fontSize: 11, fill: '#6b7280' }}
            axisLine={{ stroke: '#e5e7eb' }}
          />
          <Tooltip content={<GermanTooltip />} cursor={{ fill: 'rgba(0,0,0,0.04)' }} />
          <Bar
            dataKey="value"
            radius={[0, 4, 4, 0]}
            animationDuration={animate ? 500 : 0}
            onClick={handleClick}
            cursor={onBarClick ? 'pointer' : 'default'}
          >
            {showValues && (
              <LabelList
                dataKey="value"
                position="right"
                formatter={(v) => v.toLocaleString('de-DE')}
                style={{ fontSize: 10, fontWeight: 600, fill: '#374151' }}
              />
            )}
            {chartData.map((entry, i) => (
              <Cell
                key={i}
                fill={entry._color || (activeIndex === i ? hoverColor : fillColor)}
                onMouseEnter={() => setActiveIndex(i)}
                onMouseLeave={() => setActiveIndex(null)}
              />
            ))}
          </Bar>
        </RechartsBarChart>
      </ResponsiveContainer>
    );
  }

  // Vertical bars (default)
  return (
    <ResponsiveContainer width="100%" height={chartHeight}>
      <RechartsBarChart
        data={chartData}
        margin={{ top: showValues ? 20 : 5, right: 10, left: 10, bottom: showBrush ? 30 : 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
        <XAxis
          dataKey="name"
          tick={{ fontSize: 11, fill: '#6b7280' }}
          axisLine={{ stroke: '#e5e7eb' }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#6b7280' }}
          axisLine={{ stroke: '#e5e7eb' }}
          tickFormatter={(v) => v.toLocaleString('de-DE')}
        />
        <Tooltip content={<GermanTooltip />} cursor={{ fill: 'rgba(0,0,0,0.04)' }} />
        {showBrush && (
          <Brush
            dataKey="name"
            height={20}
            stroke={fillColor}
            travellerWidth={8}
            startIndex={0}
            endIndex={Math.min(7, data.length - 1)}
          />
        )}
        <Bar
          dataKey="value"
          radius={[4, 4, 0, 0]}
          animationDuration={animate ? 500 : 0}
          onClick={handleClick}
          cursor={onBarClick ? 'pointer' : 'default'}
        >
          {showValues && (
            <LabelList
              dataKey="value"
              position="top"
              formatter={(v) => v.toLocaleString('de-DE')}
              style={{ fontSize: 10, fontWeight: 600, fill: '#374151' }}
            />
          )}
          {chartData.map((entry, i) => (
            <Cell
              key={i}
              fill={entry._color || (activeIndex === i ? hoverColor : fillColor)}
              onMouseEnter={() => setActiveIndex(i)}
              onMouseLeave={() => setActiveIndex(null)}
            />
          ))}
        </Bar>
      </RechartsBarChart>
    </ResponsiveContainer>
  );
}
