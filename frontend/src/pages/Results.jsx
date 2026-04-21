import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import ClipCard from "../components/ClipCard";
import { ArrowLeft, Download } from "lucide-react";

export default function Results() {
  const { jobId } = useParams();
  const [clips, setClips] = useState([]);
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");  // all | tiktok | reels | shorts

  useEffect(() => {
    const load = async () => {
      const [jobRes, clipsRes] = await Promise.all([
        axios.get(`/api/jobs/${jobId}`),
        axios.get(`/api/clips/${jobId}`),
      ]);
      setJob(jobRes.data);
      setClips(clipsRes.data.clips);
      setLoading(false);
    };
    load().catch(console.error);
  }, [jobId]);

  const PLATFORMS = ["all", "tiktok", "reels", "shorts"];
  const filtered = filter === "all" ? clips : clips.filter((c) => c.platform === filter);

  // Sort by virality score descending
  const sorted = [...filtered].sort((a, b) => (b.virality_score || 0) - (a.virality_score || 0));

  if (loading) {
    return (
      <div className="page" style={{ textAlign: "center", paddingTop: "4rem" }}>
        <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>⚡</div>
        <p className="text-muted">Loading results…</p>
      </div>
    );
  }

  return (
    <div className="page">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <Link to="/" className="btn btn-ghost btn-sm mb-3" style={{ display: "inline-flex" }}>
            <ArrowLeft size={14} /> New Video
          </Link>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 800, letterSpacing: "-0.03em" }}>
            Your Viral Clips
          </h1>
          <p className="text-muted text-sm mt-1">
            {clips.length} clips generated from{" "}
            <span style={{ color: "var(--purple-400)" }}>{job?.original_filename}</span>
          </p>
        </div>
      </div>

      {/* Platform Filter */}
      <div className="flex gap-2 mb-6" style={{ flexWrap: "wrap" }}>
        {PLATFORMS.map((p) => (
          <button
            key={p}
            id={`filter-${p}`}
            onClick={() => setFilter(p)}
            className={`btn btn-sm ${filter === p ? "btn-primary" : "btn-ghost"}`}
            style={{ textTransform: p === "all" ? "none" : "capitalize" }}
          >
            {p === "all" ? "All Clips" : p === "tiktok" ? "🎵 TikTok" : p === "reels" ? "📸 Reels" : "▶️ Shorts"}
          </button>
        ))}
        <span className="text-muted text-sm" style={{ lineHeight: "2rem", marginLeft: "auto" }}>
          {sorted.length} clip{sorted.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Clips Grid */}
      {sorted.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "3rem" }}>
          <p style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>🎬</p>
          <p className="text-muted">No clips found for this filter.</p>
        </div>
      ) : (
        <div className="clips-grid">
          {sorted.map((clip) => (
            <ClipCard key={clip.id} clip={clip} />
          ))}
        </div>
      )}
    </div>
  );
}
