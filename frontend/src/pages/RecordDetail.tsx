import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type ResultDetail } from "../api/client";
import DetailDrawer from "../components/DetailDrawer";
import { ErrorBox, Loading } from "../components/Feedback";

export default function RecordDetail() {
  const { id, resultId } = useParams<{ id: string; resultId: string }>();
  const [result, setResult] = useState<ResultDetail | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!id || !resultId) return;
    let cancelled = false;
    api
      .getResult(id, resultId)
      .then((r) => {
        if (!cancelled) setResult(r);
      })
      .catch((e) => {
        if (!cancelled) setError(e);
      });
    return () => {
      cancelled = true;
    };
  }, [id, resultId]);

  return (
    <div className="page">
      <div className="page-head">
        <h1>Record detail</h1>
      </div>
      {error ? (
        <ErrorBox error={error} onRetry={() => window.location.reload()} />
      ) : !result ? (
        <Loading label="Loading record…" />
      ) : (
        <div className="card">
          <DetailDrawer result={result} />
        </div>
      )}
    </div>
  );
}
