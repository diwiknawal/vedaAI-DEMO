import { Flame, TrendingUp, Minus } from "lucide-react";

export default function ViralityBadge({ score }) {
  if (score == null) return null;

  const s = Math.round(score);
  const tier = s >= 75 ? "high" : s >= 50 ? "mid" : "low";

  const Icon = tier === "high" ? Flame : tier === "mid" ? TrendingUp : Minus;
  const label = tier === "high" ? "Viral" : tier === "mid" ? "Good" : "Low";

  return (
    <span className={`virality-badge ${tier}`}>
      <Icon size={11} />
      {label} {s}
    </span>
  );
}
