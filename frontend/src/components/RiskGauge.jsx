import React, { useEffect, useRef } from 'react';

/**
 * Animated SVG radial gauge for risk scores 0–100.
 * No external dependencies — pure SVG + CSS animation.
 */
const BAND_COLOR = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#eab308',
  low:      '#22c55e',
};

function getBand(score) {
  if (score >= 80) return 'critical';
  if (score >= 60) return 'high';
  if (score >= 40) return 'medium';
  return 'low';
}

export const RiskGauge = ({ score = 0, size = 140, label = 'Risk Score', animated = true }) => {
  const band  = getBand(score);
  const color = BAND_COLOR[band];

  // Arc: radius=54, circumference ≈ 339.3 (full), we use 270° arc (3/4 circle)
  const R   = 54;
  const C   = 2 * Math.PI * R;         // full circle circumference
  const arc = C * 0.75;                // 270° arc we show
  const gap = C - arc;                 // remaining 90°
  const pct = Math.min(Math.max(score / 100, 0), 1);
  const filled = arc * pct;

  // Rotate so the gap sits at the bottom-center (-135° from 12 o'clock → top-left)
  const rotate = -225;

  const circleRef = useRef(null);
  useEffect(() => {
    if (!animated || !circleRef.current) return;
    const el = circleRef.current;
    el.style.transition = 'none';
    el.style.strokeDashoffset = arc;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.style.transition = 'stroke-dashoffset 1.2s cubic-bezier(0.4, 0, 0.2, 1)';
        el.style.strokeDashoffset = arc - filled;
      });
    });
  }, [score, arc, filled, animated]);

  return (
    <div className="flex flex-col items-center gap-1" style={{ width: size }}>
      <svg width={size} height={size * 0.85} viewBox="0 0 120 100" role="img" aria-label={`${label}: ${score}`}>
        {/* Track */}
        <circle
          cx="60" cy="65" r={R}
          fill="none"
          stroke="var(--app-border)"
          strokeWidth="10"
          strokeDasharray={`${arc} ${gap}`}
          strokeDashoffset={0}
          strokeLinecap="round"
          transform={`rotate(${rotate} 60 65)`}
        />
        {/* Value arc */}
        <circle
          ref={circleRef}
          cx="60" cy="65" r={R}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={`${arc} ${gap}`}
          strokeDashoffset={animated ? arc : arc - filled}
          strokeLinecap="round"
          transform={`rotate(${rotate} 60 65)`}
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
        {/* Score text */}
        <text x="60" y="68" textAnchor="middle" fill="white" fontSize="22" fontWeight="700" fontFamily="Inter, sans-serif">
          {score}
        </text>
        {/* Label */}
        <text x="60" y="82" textAnchor="middle" fill="#64748b" fontSize="8" fontFamily="Inter, sans-serif">
          {band.toUpperCase()}
        </text>
      </svg>
      <p className="text-xs text-slate-400 font-medium tracking-wide">{label}</p>
    </div>
  );
};

export default RiskGauge;
