interface DataTableProps {
  data: Array<{
    date: string;
    unique_visitors: number;
    new_visitors: number;
    processed_images: number;
    api_calls: number;
  }>;
}

export function DataTable({ data }: DataTableProps) {
  if (data.length === 0) return (
    <div className="data-table-empty">暂无数据</div>
  );

  return (
    <div className="data-table-wrapper">
      <div className="data-table-header">
        <div className="data-table-title">7 日详细数据</div>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>日期</th>
            <th>独立访客</th>
            <th>新访客</th>
            <th>处理图片</th>
            <th>API 调用</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={row.date} style={{ animationDelay: `${i * 60}ms` }} className="data-table-row">
              <td>{row.date}</td>
              <td>{row.unique_visitors.toLocaleString()}</td>
              <td>{row.new_visitors.toLocaleString()}</td>
              <td>{row.processed_images.toLocaleString()}</td>
              <td>{row.api_calls.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
