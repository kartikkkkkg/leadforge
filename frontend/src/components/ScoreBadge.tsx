/** Mirrors backend `completeness_band`: High >= 90, Medium >= 70, Low < 70. */
export function completenessBand(score: number): "High" | "Medium" | "Low" {
  if (score >= 90) return "High";
  if (score >= 70) return "Medium";
  return "Low";
}

export default function ScoreBadge({ score }: { score: number }) {
  const band = completenessBand(score);
  const tone =
    band === "High" ? "tone-ok" : band === "Medium" ? "tone-warn" : "tone-bad";
  return (
    <span className={`badge ${tone}`} title={`Completeness score ${score}/100 (${band})`}>
      {score} · {band}
    </span>
  );
}
