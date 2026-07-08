import { useEffect, useRef, useState } from 'react';

interface TrendChartProps {
  data: Array<{ date: string; unique_visitors: number; processed_images: number }>;
}

export function TrendChart({ data }: TrendChartProps) {
  const [animated, setAnimated] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setAnimated(true), 50);
    return () => clearTimeout(timer);
  }, [data]);

  if (data.length === 0) return null;

  const width = 600;
  const height = 240;
  const padding = { top: 20, right: 20, bottom: 30, left: 40 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const maxVisitors = Math.max(...data.map(d => d.unique_visitors), 1);
  const maxProcessed = Math.max(...data.map(d => d.processed_images), 1);
  const maxY = Math.max(maxVisitors, maxProcessed);

  const xScale = (i: number) => padding.left + (i / (data.length - 1 || 1)) * chartWidth;
  const yScale = (v: number) => padding.top + chartHeight - (v / maxY) * chartHeight;

  const visitorsPoints = data.map((d, i) => `${xScale(i)},${yScale(d.unique_visitors)}`).join(' ');
  const processedPoints = data.map((d, i) => `${xScale(i)},${yScale(d.processed_images)}`).join(' ');

  const visitorsPath = `M ${data.map((d, i) => `${xScale(i)} ${yScale(d.unique_visitors)}`).join(' L ')}`;
  const processedPath = `M ${data.map((d, i) => `${xScale(i)} ${yScale(d.processed_images)}`).join(' L ')}`;

  const visitorsArea = `${visitorsPath} L ${xScale(data.length - 1)} ${padding.top + chartHeight} L ${xScale(0)} ${padding.top + chartHeight} Z`;
  const processedArea = `${processedPath} L ${xScale(data.length - 1)} ${padding.top + chartHeight} L ${xScale(0)} ${padding.top + chartHeight} Z`;

  const totalLength = 1000;

  return (
    <div className="trend-chart-card">
      <div className="trend-chart-header">
        <div className="trend-chart-title">7 日趋势</div>
        <div className="trend-chart-legend">
          <span className="legend-dot blue" /> 访客
          <span className="legend-dot green" /> 处理
        </div>
      </div>
      <svg ref={svgRef} viewBox={`0 0 ${width} ${height}`} className="trend-chart-svg">
        <defs>
          <linearGradient id="vgrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#007AFF" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#007AFF" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="pgrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#30D158" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#30D158" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Y axis grid */}
        {[0, 0.25, 0.5, 0.75, 1].map(r => (
          <line
            key={r}
            x1={padding.left}
            x2={width - padding.right}
            y1={padding.top + chartHeight - r * chartHeight}
            y2={padding.top + chartHeight - r * chartHeight}
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={1}
          />
        ))}

        {/* X axis labels */}
        {data.map((d, i) => (
          <text
            key={d.date}
            x={xScale(i)}
            y={height - 6}
            textAnchor="middle"
            fill="#8a8a8e"
            fontSize={10}
          >
            {d.date.slice(5)}
          </text>
        ))}

        {/* Y axis labels */}
        {[0, 0.25, 0.5, 0.75, 1].map(r => (
          <text
            key={r}
            x={padding.left - 8}
            y={padding.top + chartHeight - r * chartHeight + 3}
            textAnchor="end"
            fill="#8a8a8e"
            fontSize={10}
          >
            {Math.round(r * maxY)}
          </text>
        ))}

        {/* Areas */}
        <path d={visitorsArea} fill="url(#vgrad)" opacity={animated ? 0.15 : 0} className="chart-area" />
        <path d={processedArea} fill="url(#pgrad)" opacity={animated ? 0.15 : 0} className="chart-area" />

        {/* Lines */}
        <path
          d={visitorsPath}
          fill="none"
          stroke="#007AFF"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className={animated ? 'chart-line animated' : 'chart-line'}
          style={{
            strokeDasharray: totalLength,
            strokeDashoffset: animated ? 0 : totalLength,
          }}
        />
        <path
          d={processedPath}
          fill="none"
          stroke="#30D158"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className={animated ? 'chart-line animated' : 'chart-line'}
          style={{
            strokeDasharray: totalLength,
            strokeDashoffset: animated ? 0 : totalLength,
          }}
        />

        {/* Points */}
        {data.map((d, i) => (
          <g key={`v-${d.date}`}>
            <circle
              cx={xScale(i)}
              cy={yScale(d.unique_visitors)}
              r={4}
              fill="#007AFF"
              className={animated ? 'chart-point animated' : 'chart-point'}
              style={{ transformOrigin: `${xScale(i)}px ${yScale(d.unique_visitors)}px` }}
            />
          </g>
        ))}
        {data.map((d, i) => (
          <g key={`p-${d.date}`}>
            <circle
              cx={xScale(i)}
              cy={yScale(d.processed_images)}
              r={4}
              fill="#30D158"
              className={animated ? 'chart-point animated' : 'chart-point'}
              style={{ transformOrigin: `${xScale(i)}px ${yScale(d.processed_images)}px` }}
            />
          </g>
        ))}
      </svg>
    </div>
  );
}
