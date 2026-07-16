import React from 'react';

/**
 * Mini SVG sparkline for risk score history.
 * `points` — array of numbers (e.g. score_delta values or risk scores)
 * `color`  — stroke color
 * `width`, `height` — SVG dimensions
 */
export const RiskSparkline = ({
  points = [],
  color = '#38a0ff',
  width = 120,
  height = 36,
  strokeWidth = 2,
  fill = true,
}) => {
  if (points.length < 2) {
    return (
      <svg width={width} height={height} role="img" aria-label="No data">
        <line x1="0" y1={height / 2} x2={width} y2={height / 2} stroke="var(--app-border)" strokeWidth="1" strokeDasharray="4 2" />
      </svg>
    );
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const pad = strokeWidth + 1;
  const w = width - pad * 2;
  const h = height - pad * 2;

  const toX = (i) => pad + (i / (points.length - 1)) * w;
  const toY = (v) => pad + h - ((v - min) / range) * h;

  const linePath = points
    .map((v, i) => `${i === 0 ? 'M' : 'L'} ${toX(i).toFixed(1)} ${toY(v).toFixed(1)}`)
    .join(' ');

  const fillPath = fill
    ? `${linePath} L ${toX(points.length - 1).toFixed(1)} ${height} L ${pad} ${height} Z`
    : null;

  return (
    <svg width={width} height={height} role="img" aria-label="Risk sparkline">
      {fill && (
        <defs>
          <linearGradient id={`sg-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.3" />
            <stop offset="100%" stopColor={color} stopOpacity="0.02" />
          </linearGradient>
        </defs>
      )}
      {fill && (
        <path
          d={fillPath}
          fill={`url(#sg-${color.replace('#', '')})`}
        />
      )}
      <path
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* End dot */}
      <circle
        cx={toX(points.length - 1)}
        cy={toY(points[points.length - 1])}
        r={3}
        fill={color}
        style={{ filter: `drop-shadow(0 0 4px ${color})` }}
      />
    </svg>
  );
};

export default RiskSparkline;
