import { useEffect, useRef, useState } from 'react';

interface KpiCardProps {
  label: string;
  value: number;
  unit?: string;
  trend?: number;
  trendLabel?: string;
  color?: 'blue' | 'green' | 'red' | 'neutral';
}

export function KpiCard({ label, value, unit = '', trend, trendLabel, color = 'neutral' }: KpiCardProps) {
  const [display, setDisplay] = useState(0);
  const rafRef = useRef<number>(0);
  const startRef = useRef<number>(0);

  useEffect(() => {
    const startValue = 0;
    const duration = 1200;
    const startTime = performance.now();
    startRef.current = startTime;

    const animate = (now: number) => {
      const elapsed = now - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      const current = Math.round(startValue + (value - startValue) * eased);
      setDisplay(current);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [value]);

  const colorClass = color === 'blue' ? 'kpi-blue' : color === 'green' ? 'kpi-green' : color === 'red' ? 'kpi-red' : 'kpi-neutral';

  return (
    <div className={`kpi-card ${colorClass}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">
        {display.toLocaleString()}
        {unit && <span className="kpi-unit">{unit}</span>}
      </div>
      {typeof trend === 'number' && (
        <div className={`kpi-trend ${trend >= 0 ? 'up' : 'down'}`}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend).toFixed(1)}%
          {trendLabel && <span className="kpi-trend-label"> {trendLabel}</span>}
        </div>
      )}
    </div>
  );
}
