import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  className?: string;
}

/** Presentational table. Filtering/sorting/pagination are server-driven by the caller. */
export default function DataTable<T extends { id: string }>({
  columns,
  rows,
  emptyTitle = "No rows",
  emptyHint,
}: {
  columns: Column<T>[];
  rows: T[];
  emptyTitle?: string;
  emptyHint?: string;
}) {
  if (rows.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-title">{emptyTitle}</div>
        {emptyHint ? <p className="empty-hint">{emptyHint}</p> : null}
      </div>
    );
  }
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.className}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              {columns.map((c) => (
                <td key={c.key} className={c.className}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
