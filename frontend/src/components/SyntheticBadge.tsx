/** Marks synthetic demo data — never presented as real. */
export default function SyntheticBadge() {
  return (
    <span
      className="badge tone-warn"
      title="Synthetic demo data generated offline — not a real company."
    >
      Synthetic
    </span>
  );
}
