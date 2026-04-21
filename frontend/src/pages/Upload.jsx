import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Upload as UploadIcon, Film, Zap, Clock, Scissors } from "lucide-react";

const FEATURES = [
  { icon: <Film size={20} />, label: "Scene Detection", desc: "Auto-identify scene boundaries" },
  { icon: <Zap size={20} />, label: "Virality Scoring", desc: "AI ranks your best moments" },
  { icon: <Scissors size={20} />, label: "Smart Reframe", desc: "Auto 9:16 vertical crop" },
  { icon: <Clock size={20} />, label: "20–30s Clips", desc: "TikTok, Reels & Shorts ready" },
];

export default function Upload() {
  const navigate = useNavigate();
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");

  const handleFile = useCallback(async (file) => {
    if (!file) return;
    setError("");
    setUploading(true);
    setUploadProgress(0);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const { data } = await axios.post("/api/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => {
          if (e.total) setUploadProgress(Math.round((e.loaded / e.total) * 100));
        },
      });
      navigate(`/processing/${data.job_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || "Upload failed. Please try again.");
      setUploading(false);
    }
  }, [navigate]);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const onFileInput = (e) => {
    const file = e.target.files[0];
    if (file) handleFile(file);
  };

  return (
    <div className="page">
      {/* Hero */}
      <div className="hero">
        <h1>Turn Long Videos into<br />Viral Clips Instantly</h1>
        <p>
          Upload a 20–50 minute video. Our AI pipeline detects scenes,
          scores virality, reframes for vertical, and adds captions — automatically.
        </p>
        <div className="hero-stats">
          <div className="stat"><div className="stat-value">7</div><div className="stat-label">AI Pipeline Stages</div></div>
          <div className="stat"><div className="stat-value">30s</div><div className="stat-label">Avg Clip Length</div></div>
          <div className="stat"><div className="stat-value">3x</div><div className="stat-label">Platforms at Once</div></div>
        </div>
      </div>

      {/* Upload Zone */}
      <div
        id="upload-dropzone"
        className={`upload-zone ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !uploading && document.getElementById("file-input").click()}
        style={{ cursor: uploading ? "default" : "pointer", marginBottom: "2rem" }}
      >
        <input
          id="file-input"
          type="file"
          accept="video/mp4,video/quicktime,video/x-msvideo,video/x-matroska,video/webm"
          style={{ display: "none" }}
          onChange={onFileInput}
          disabled={uploading}
        />

        <div className="upload-icon">
          {uploading ? "⚙️" : "🎬"}
        </div>

        {uploading ? (
          <>
            <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: "0.5rem" }}>
              Uploading to storage…
            </h2>
            <p className="text-muted text-sm mb-4">{uploadProgress}% complete</p>
            <div className="progress-bar-track" style={{ maxWidth: "360px", margin: "0 auto" }}>
              <div className="progress-bar-fill" style={{ width: `${uploadProgress}%` }} />
            </div>
          </>
        ) : (
          <>
            <h2 style={{ fontSize: "1.4rem", fontWeight: 700, marginBottom: "0.5rem" }}>
              Drop your video here
            </h2>
            <p className="text-muted text-sm mb-4">
              MP4, MOV, AVI, MKV, WebM · Up to 2 GB · 20–50 minutes recommended
            </p>
            <button id="upload-btn" className="btn btn-primary btn-lg" onClick={(e) => e.stopPropagation()}>
              <UploadIcon size={18} />
              Choose Video
            </button>
          </>
        )}

        {error && (
          <p style={{ color: "var(--red-400)", marginTop: "1rem", fontSize: "0.9rem" }}>{error}</p>
        )}
      </div>

      {/* Feature Cards */}
      <div className="two-col" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))" }}>
        {FEATURES.map((f) => (
          <div key={f.label} className="card" style={{ display: "flex", gap: "1rem", alignItems: "flex-start" }}>
            <div style={{
              padding: "0.65rem", borderRadius: "10px",
              background: "rgba(139,92,246,0.15)", color: "var(--purple-400)", flexShrink: 0
            }}>
              {f.icon}
            </div>
            <div>
              <div className="font-semibold mb-1">{f.label}</div>
              <div className="text-muted text-sm">{f.desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
