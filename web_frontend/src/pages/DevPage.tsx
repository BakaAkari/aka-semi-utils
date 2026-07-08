import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getStats, postVisit } from '../api';
import { DataTable } from '../components/dev/DataTable';
import { KpiCard } from '../components/dev/KpiCard';
import { PasswordGate } from '../components/dev/PasswordGate';
import { TrendChart } from '../components/dev/TrendChart';
import '../styles-dev.css';

function generateVisitorId(): string {
  const arr = new Uint8Array(18);
  crypto.getRandomValues(arr);
  let s = '';
  for (let i = 0; i < arr.length; i++) {
    s += String.fromCharCode(65 + (arr[i] % 26));
  }
  return s;
}

type TrendRow = {
  date: string;
  unique_visitors: number;
  new_visitors: number;
  processed_images: number;
  api_calls: number;
};

type StatsData = {
  ok: true;
  today: {
    unique_visitors: number;
    new_visitors: number;
    processed_images: number;
    api_calls: number;
  };
  lifetime: {
    total_visitors: number;
    total_processed_images: number;
    total_api_calls: number;
  };
  trend: {
    last_7_days: TrendRow[];
    last_15_days: TrendRow[];
    last_30_days: TrendRow[];
  };
  latency: { p50_ms: number; p99_ms: number };
  extra: { avg_batch_size: number; active_ratio: number };
};

export function DevPage() {
  const navigate = useNavigate();
  const [authed, setAuthed] = useState(() => sessionStorage.getItem('_dev_auth') === 'true');
  const [timeRange, setTimeRange] = useState<'7' | '15' | '30'>('7');
  const [stats, setStats] = useState<StatsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchStats = useCallback(async () => {
    if (!authed) return;
    try {
      setLoading(true);
      setError(null);
      const data = await getStats('23323312');
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, [authed]);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchStats();
    setTimeout(() => setRefreshing(false), 600);
  }, [fetchStats]);

  useEffect(() => {
    if (!authed) return;
    void fetchStats();
  }, [authed, fetchStats]);

  // Record visit on mount (if not already done this session)
  useEffect(() => {
    const done = sessionStorage.getItem('_dev_visit_sent');
    if (!done) {
      let vid = localStorage.getItem('_dev_visitor_id');
      if (!vid) {
        vid = generateVisitorId();
        localStorage.setItem('_dev_visitor_id', vid);
      }
      postVisit(vid).catch(() => {});
      sessionStorage.setItem('_dev_visit_sent', 'true');
    }
  }, []);

  if (!authed) {
    return <PasswordGate onSuccess={() => setAuthed(true)} />;
  }

  const today = stats?.today ?? { unique_visitors: 0, new_visitors: 0, processed_images: 0, api_calls: 0 };
  const lifetime = stats?.lifetime ?? { total_visitors: 0, total_processed_images: 0, total_api_calls: 0 };
  const latency = stats?.latency ?? { p50_ms: 0, p99_ms: 0 };
  const extra = stats?.extra ?? { avg_batch_size: 0, active_ratio: 0 };

  const trendKey = timeRange === '7' ? 'last_7_days' : timeRange === '15' ? 'last_15_days' : 'last_30_days';
  const trend = stats?.trend?.[trendKey] ?? [];
  const chartTitle = `${timeRange} 日趋势`;
  const tableTitle = `${timeRange} 日详细数据`;

  const kpiData = [
    { label: '今日独立访客', value: today.unique_visitors, color: 'blue' as const, trend: today.unique_visitors > 0 ? 5.2 : 0 },
    { label: '今日处理图片', value: today.processed_images, color: 'green' as const, trend: today.processed_images > 0 ? 12.5 : 0 },
    { label: '累计访客', value: lifetime.total_visitors, color: 'neutral' as const },
    { label: '累计处理', value: lifetime.total_processed_images, color: 'neutral' as const },
  ];

  const rangeButtons: { key: '7' | '15' | '30'; label: string }[] = [
    { key: '7', label: '7日' },
    { key: '15', label: '15日' },
    { key: '30', label: '30日' },
  ];

  return (
    <div className="dev-page">
      <div className="dev-page-header">
        <div className="dev-page-title">用量洞察</div>
        <div className="dev-page-actions">
          <div className="time-range-segment">
            {rangeButtons.map(b => (
              <button
                key={b.key}
                className={`time-range-btn ${timeRange === b.key ? 'active' : ''}`}
                onClick={() => setTimeRange(b.key)}
              >
                {b.label}
              </button>
            ))}
          </div>
          <button
            className={`dev-refresh-btn ${refreshing ? 'spinning' : ''}`}
            onClick={handleRefresh}
            title="刷新数据"
          >
            ↻
          </button>
          <button className="dev-back-btn" onClick={() => navigate('/')}>
            返回
          </button>
        </div>
      </div>

      {error && (
        <div className="dev-error-banner">
          {error}
        </div>
      )}

      {loading && !stats ? (
        <div className="dev-skeleton-grid">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="dev-skeleton-card" />
          ))}
        </div>
      ) : (
        <>
          <div className="kpi-grid">
            {kpiData.map(kpi => (
              <KpiCard key={kpi.label} {...kpi} />
            ))}
          </div>

          <div className="dev-charts-section">
            <div className="dev-chart-main">
              <TrendChart data={trend} title={chartTitle} />
            </div>
            <div className="dev-chart-side">
              <div className="mini-card">
                <div className="mini-card-label">API 延迟 P50</div>
                <div className="mini-card-value">{latency.p50_ms}<span className="mini-unit">ms</span></div>
              </div>
              <div className="mini-card">
                <div className="mini-card-label">API 延迟 P99</div>
                <div className="mini-card-value">{latency.p99_ms}<span className="mini-unit">ms</span></div>
              </div>
              <div className="mini-card">
                <div className="mini-card-label">平均批量</div>
                <div className="mini-card-value">{extra.avg_batch_size}</div>
              </div>
              <div className="mini-card">
                <div className="mini-card-label">7日活跃比例</div>
                <div className="mini-card-value">{(extra.active_ratio * 100).toFixed(0)}<span className="mini-unit">%</span></div>
              </div>
            </div>
          </div>

          <div className="dev-table-section">
            <DataTable data={trend} title={tableTitle} />
          </div>
        </>
      )}
    </div>
  );
}
