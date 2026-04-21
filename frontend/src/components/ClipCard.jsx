import { useState } from "react";
import { Play, Download, Lightbulb } from "lucide-react";
import ViralityBadge from "./ViralityBadge";

export default function ClipCard({ clip }) {
  const [playing, setPlaying] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const suggestions = clip.ai_suggestions || {};

  const handleDownload = () => {
    if (clip.download_url) {
      const a = document.createElement("a");
      a.href = clip.download_url;
      a.download = `veda_clip_${clip.id}_${clip.platform}.mp4`;
      a.click();
    }
  };

  return (
    <div className="clip-card">
      {/* Thumbnail / Video */}
      <div className="clip-thumbnail">
        {playing && clip.download_url ? (
          <video
            src={clip.download_url}
            controls
            autoPlay
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <>
            <div style={{
              width: "100%", height: "100%",
              background: "linear-gradient(135deg, var(--bg-2) 0%, var(--bg-card) 100%)",
              display: "flex", alignItems: "center", justifyContent: "center",
              flexDirection: "column", gap: "0.5rem",
            }}>
              <span style={{ fontSize: "2.5rem" }}>🎬</span>
              <span className="text-muted text-xs">{clip.duration_sec?.toFixed(1)}s clip</span>
            </div>
            <div className="play-overlay">
              <button
                className="play-btn"
                id={`play-clip-${clip.id}`}
                onClick={() => setPlaying(true)}
                title="Play clip"
              >
                <Play size={22} fill="black" color="black" />
              </button>
            </div>
          </>
        )}
      </div>

      {/* Meta */}
      <div className="clip-meta">
        <div className="flex justify-between items-center mb-2">
          <span className={`platform-tag ${clip.platform}`}>
            {clip.platform === "tiktok" ? "🎵" : clip.platform === "reels" ? "📸" : "▶️"}
            {" "}{clip.platform}
          </span>
          <ViralityBadge score={clip.virality_score} />
        </div>

        {suggestions.hook_text && (
          <p className="text-sm mb-2" style={{ color: "var(--text-primary)", fontWeight: 600, lineHeight: 1.3 }}>
            "{suggestions.hook_text}"
          </p>
        )}

        {suggestions.suggested_title && (
          <p className="text-xs text-muted mb-3" style={{ lineHeight: 1.4 }}>
            {suggestions.suggested_title}
          </p>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <button
            id={`download-clip-${clip.id}`}
            onClick={handleDownload}
            className="btn btn-primary btn-sm"
            style={{ flex: 1 }}
            disabled={!clip.download_url}
          >
            <Download size={13} />
            Download
          </button>
          {Object.keys(suggestions).length > 0 && (
            <button
              id={`suggestions-clip-${clip.id}`}
              onClick={() => setShowSuggestions(!showSuggestions)}
              className="btn btn-ghost btn-sm"
              title="View AI suggestions"
            >
              <Lightbulb size={13} />
            </button>
          )}
        </div>

        {/* AI Suggestions Panel */}
        {showSuggestions && (
          <div style={{
            marginTop: "0.75rem", padding: "0.75rem", borderRadius: "var(--radius-sm)",
            background: "rgba(139,92,246,0.08)", border: "1px solid var(--border-accent)",
          }}>
            {suggestions.broll_prompts?.length > 0 && (
              <div className="mb-2">
                <div className="text-xs font-semibold accent mb-1">B-Roll Ideas</div>
                {suggestions.broll_prompts.map((p, i) => (
                  <div key={i} className="text-xs text-muted" style={{ lineHeight: 1.5 }}>• {p}</div>
                ))}
              </div>
            )}
            {suggestions.music_mood && (
              <div className="text-xs text-muted mb-1">
                🎵 Music mood: <span style={{ color: "var(--text-primary)" }}>{suggestions.music_mood}</span>
              </div>
            )}
            {suggestions.cta && (
              <div className="text-xs text-muted">
                📢 CTA: <span style={{ color: "var(--text-primary)" }}>{suggestions.cta}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
