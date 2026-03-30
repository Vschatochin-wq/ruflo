/**
 * CompletenessMeter — Visual 8D Completeness Indicator
 * =====================================================
 * Displays a circular progress ring with overall completion
 * percentage and individual D1-D8 step indicators.
 *
 * Usage:
 *   <CompletenessMeter summary={summaryData} />
 *
 * Props:
 *   summary - Object with d_step_status (D1-D8 completion info)
 *             and overall_completeness (0-100)
 */

import React, { useState, useEffect } from 'react';

const D_STEPS = [
  { key: 'D1', label: 'Team', fullLabel: 'D1 — Teamzusammenstellung' },
  { key: 'D2', label: 'Problem', fullLabel: 'D2 — Problembeschreibung' },
  { key: 'D3', label: 'Sofort', fullLabel: 'D3 — Sofortmassnahmen' },
  { key: 'D4', label: 'Ursache', fullLabel: 'D4 — Ursachenanalyse' },
  { key: 'D5', label: 'Abstell', fullLabel: 'D5 — Abstellmassnahmen' },
  { key: 'D6', label: 'Verif.', fullLabel: 'D6 — Verifizierung' },
  { key: 'D7', label: 'Vorbeu.', fullLabel: 'D7 — Vorbeugungsmassnahmen' },
  { key: 'D8', label: 'Abschl.', fullLabel: 'D8 — Abschluss' },
];

function getStepStatus(summary, stepKey) {
  if (!summary?.d_step_status) return 'empty';
  const step = summary.d_step_status[stepKey] || summary.d_step_status[stepKey.toLowerCase()];
  if (!step) return 'empty';
  if (step.complete || step.status === 'complete') return 'complete';
  if (step.partial || step.status === 'partial' || step.filled > 0) return 'partial';
  return 'empty';
}

function getStepColor(status) {
  if (status === 'complete') return { bg: '#22c55e', ring: '#16a34a' };
  if (status === 'partial') return { bg: '#eab308', ring: '#ca8a04' };
  return { bg: '#d1d5db', ring: '#9ca3af' };
}

export default function CompletenessMeter({ summary }) {
  const [animatedProgress, setAnimatedProgress] = useState(0);
  const overallPercent = summary?.overall_completeness ?? summary?.completeness_percent ?? 0;

  useEffect(() => {
    const timer = setTimeout(() => setAnimatedProgress(overallPercent), 100);
    return () => clearTimeout(timer);
  }, [overallPercent]);

  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (animatedProgress / 100) * circumference;

  const progressColor = animatedProgress >= 80
    ? '#22c55e'
    : animatedProgress >= 50
    ? '#eab308'
    : animatedProgress >= 25
    ? '#f97316'
    : '#ef4444';

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Circular Progress Ring */}
      <div
        className="relative"
        style={{ width: 140, height: 140 }}
        role="meter"
        aria-valuenow={animatedProgress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Gesamtfortschritt: ${animatedProgress}%`}
      >
        <svg className="transform -rotate-90" width="140" height="140" viewBox="0 0 120 120">
          <circle
            cx="60" cy="60" r={radius}
            fill="none" stroke="#e5e7eb" strokeWidth="8"
          />
          <circle
            cx="60" cy="60" r={radius}
            fill="none" stroke={progressColor} strokeWidth="8"
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 1s ease-in-out, stroke 0.5s ease' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold text-gray-800">
            {Math.round(animatedProgress)}%
          </span>
          <span className="text-xs text-gray-500">Komplett</span>
        </div>
      </div>

      {/* D1-D8 Step Indicators */}
      <div className="grid grid-cols-4 gap-2 w-full max-w-[240px]">
        {D_STEPS.map((step) => {
          const status = getStepStatus(summary, step.key);
          const colors = getStepColor(status);

          return (
            <div
              key={step.key}
              className="flex flex-col items-center group relative"
              title={step.fullLabel}
            >
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-transform group-hover:scale-110"
                style={{
                  backgroundColor: colors.bg + '20',
                  border: `2px solid ${colors.ring}`,
                  color: colors.ring,
                }}
              >
                {status === 'complete' ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  step.key.replace('D', '')
                )}
              </div>
              <span className="text-[10px] text-gray-500 mt-1 text-center leading-tight">
                {step.label}
              </span>

              {/* Tooltip */}
              <div className="absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-[10px] px-2 py-1 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                {step.fullLabel}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
