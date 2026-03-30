/**
 * StatCard — Wiederverwendbare KPI-Statistik-Karte
 * ==================================================
 * Zeigt eine einzelne Kennzahl mit Icon, Trend und Farbe an.
 *
 * Usage:
 *   <StatCard
 *     title="Offene Reklamationen"
 *     value={42}
 *     icon={AlertCircle}
 *     trend={+5}
 *     trendLabel="vs. Vormonat"
 *     color="blue"
 *     invertTrend={true}
 *   />
 *
 * Props:
 *   - title: string — Beschriftung der Kennzahl
 *   - value: number|string — Anzuzeigender Wert
 *   - icon: LucideIcon — Icon-Komponente aus lucide-react
 *   - trend: number — Veraenderung (positiv/negativ)
 *   - trendLabel: string — Zusaetzlicher Text zum Trend
 *   - color: string — Farbschema (blue, green, red, purple, amber, orange)
 *   - invertTrend: boolean — Wenn true, ist positiver Trend schlecht (rot)
 *   - loading: boolean — Zeigt Skeleton-Platzhalter
 */

import React from 'react';
import { Card, CardContent } from '../ui/card';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const COLOR_MAP = {
  blue: {
    iconBg: 'bg-blue-100',
    iconText: 'text-blue-600',
    cardBg: 'bg-gradient-to-br from-blue-50 to-white',
  },
  green: {
    iconBg: 'bg-green-100',
    iconText: 'text-green-600',
    cardBg: 'bg-gradient-to-br from-green-50 to-white',
  },
  red: {
    iconBg: 'bg-red-100',
    iconText: 'text-red-600',
    cardBg: 'bg-gradient-to-br from-red-50 to-white',
  },
  purple: {
    iconBg: 'bg-purple-100',
    iconText: 'text-purple-600',
    cardBg: 'bg-gradient-to-br from-purple-50 to-white',
  },
  amber: {
    iconBg: 'bg-amber-100',
    iconText: 'text-amber-600',
    cardBg: 'bg-gradient-to-br from-amber-50 to-white',
  },
  orange: {
    iconBg: 'bg-orange-100',
    iconText: 'text-orange-600',
    cardBg: 'bg-gradient-to-br from-orange-50 to-white',
  },
};

function SkeletonCard() {
  return (
    <Card className="animate-pulse">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-3 flex-1">
            <div className="h-3 w-24 bg-gray-200 rounded" />
            <div className="h-8 w-16 bg-gray-200 rounded" />
            <div className="h-3 w-20 bg-gray-100 rounded" />
          </div>
          <div className="w-10 h-10 bg-gray-200 rounded-lg" />
        </div>
      </CardContent>
    </Card>
  );
}

export default function StatCard({
  title,
  value,
  icon: Icon,
  trend,
  trendLabel,
  color = 'blue',
  invertTrend = false,
  loading = false,
}) {
  if (loading) return <SkeletonCard />;

  const colors = COLOR_MAP[color] || COLOR_MAP.blue;

  // Determine trend direction and color
  let trendIcon = null;
  let trendColor = 'text-gray-500';

  if (trend != null && trend !== 0) {
    const isPositive = trend > 0;
    // invertTrend: positive trend is bad (e.g. more open complaints)
    if (invertTrend) {
      trendColor = isPositive ? 'text-red-600' : 'text-green-600';
    } else {
      trendColor = isPositive ? 'text-green-600' : 'text-red-600';
    }
    trendIcon = isPositive ? TrendingUp : TrendingDown;
  } else if (trend === 0) {
    trendIcon = Minus;
    trendColor = 'text-gray-400';
  }

  const TrendIcon = trendIcon;

  return (
    <Card className={`${colors.cardBg} border hover:shadow-md transition-shadow`}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">
              {title}
            </p>
            <p className="text-2xl font-bold text-gray-900">
              {typeof value === 'number' ? value.toLocaleString('de-DE') : value}
            </p>
            {trend != null && (
              <div className={`flex items-center gap-1 text-xs font-medium ${trendColor}`}>
                {TrendIcon && <TrendIcon className="w-3.5 h-3.5" />}
                <span>
                  {trend > 0 ? '+' : ''}{typeof trend === 'number' ? trend.toLocaleString('de-DE') : trend}
                </span>
                {trendLabel && (
                  <span className="text-gray-400 font-normal ml-0.5">{trendLabel}</span>
                )}
              </div>
            )}
          </div>

          {Icon && (
            <div className={`p-2.5 rounded-lg ${colors.iconBg}`}>
              <Icon className={`w-5 h-5 ${colors.iconText}`} />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
