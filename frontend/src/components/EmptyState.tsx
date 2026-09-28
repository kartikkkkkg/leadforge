export default function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-title">{title}</div>
      {hint ? <p className="empty-hint">{hint}</p> : null}
      {action}
    </div>
  );
}
