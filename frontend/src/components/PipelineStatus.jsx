import { CheckCircle, Circle, Loader } from "lucide-react";

const STAGE_LABELS = {
  queued:           { label: "Queued",                  emoji: "📋" },
  transcoding:      { label: "Transcoding",             emoji: "🎥" },
  transcribing:     { label: "Transcribing Speech",     emoji: "🎙️" },
  scene_detecting:  { label: "Detecting Scenes",        emoji: "🔍" },
  virality_scoring: { label: "Scoring Virality",        emoji: "⚡" },
  reframing:        { label: "Reframing to 9:16",       emoji: "📱" },
  ai_suggestions:   { label: "AI Scene Suggestions",    emoji: "🤖" },
  captioning:       { label: "Burning Captions",        emoji: "💬" },
  completed:        { label: "Completed!",              emoji: "✅" },
};

export default function PipelineStatus({ currentStatus, stageOrder }) {
  const currentIndex = stageOrder.indexOf(currentStatus);

  return (
    <div className="pipeline-steps">
      {stageOrder.map((stage, i) => {
        const isDone    = i < currentIndex;
        const isActive  = i === currentIndex;
        const isWaiting = i > currentIndex;
        const info = STAGE_LABELS[stage] || { label: stage, emoji: "⚙️" };

        return (
          <div key={stage}>
            <div
              className={`pipeline-step ${isActive ? "active" : ""} ${isDone ? "completed" : ""} ${isWaiting ? "waiting" : ""}`}
            >
              <div className="step-icon">
                {isDone    ? <CheckCircle size={18} color="var(--green-400)" /> :
                 isActive  ? <Loader size={18} color="var(--purple-400)" className="spin" /> :
                             <Circle size={18} color="var(--text-muted)" />}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ fontSize: "1rem" }}>{info.emoji}</span>
                  <span className={`text-sm ${isActive ? "font-semibold" : ""}`}
                        style={{ color: isDone ? "var(--text-muted)" : isActive ? "var(--text-primary)" : "var(--text-muted)" }}>
                    {info.label}
                  </span>
                </div>
              </div>
              {isDone && (
                <span style={{ fontSize: "0.7rem", color: "var(--green-400)", fontWeight: 600 }}>Done</span>
              )}
              {isActive && (
                <span style={{ fontSize: "0.7rem", color: "var(--purple-400)", fontWeight: 600 }}>Running…</span>
              )}
            </div>
            {i < stageOrder.length - 1 && (
              <div className={`step-connector ${isDone ? "filled" : ""}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}
