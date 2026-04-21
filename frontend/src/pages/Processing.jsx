import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import axios from "axios";
import PipelineStatus from "../components/PipelineStatus";

const POLL_INTERVAL_MS = 3000;

const STAGE_ORDER = [
  "queued",
  "transcoding",
  "transcribing",
  "scene_detecting",
  "virality_scoring",
  "reframing",
  "ai_suggestions",
  "captioning",
  "completed",
];

export default function Processing() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let timer;
    const poll = async () => {
      try {
        const { data } = await axios.get(`/api/jobs/${jobId}/status`);
        setJob(data);

        if (data.status === "completed") {
          navigate(`/results/${jobId}`);
          return;
        }
        if (data.status === "failed") {
          setError(data.error_message || "Pipeline failed");
          return;
        }
        timer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        setError("Lost connection to server. Retrying…");
        timer = setTimeout(poll, 5000);
      }
    };

    poll();
    return () => clearTimeout(timer);
  }, [jobId, navigate]);

  return (
    <div className="page" style={{ maxWidth: "640px" }}>
      <div style={{ marginBottom: "2rem" }}>
        <h1 style={{ fontSize: "1.8rem", fontWeight: 800, letterSpacing: "-0.03em", marginBottom: "0.4rem" }}>
          Processing your video
        </h1>
        <p className="text-muted text-sm">
          Job ID: <span style={{ fontFamily: "monospace", color: "var(--purple-400)" }}>{jobId}</span>
        </p>
      </div>

      {error ? (
        <div className="card" style={{ borderColor: "var(--red-400)", background: "rgba(248,113,113,0.08)" }}>
          <p style={{ color: "var(--red-400)", fontWeight: 600 }}>❌ {error}</p>
        </div>
      ) : (
        <div className="card">
          <div className="flex justify-between items-center mb-4">
            <span className="font-semibold">Pipeline Progress</span>
            <span style={{ fontSize: "1.1rem", fontWeight: 800, color: "var(--purple-400)" }}>
              {job?.progress ?? 0}%
            </span>
          </div>

          <div className="progress-bar-track mb-6">
            <div className="progress-bar-fill" style={{ width: `${job?.progress ?? 0}%` }} />
          </div>

          <PipelineStatus currentStatus={job?.status || "queued"} stageOrder={STAGE_ORDER} />
        </div>
      )}

      <p className="text-muted text-xs mt-4" style={{ textAlign: "center" }}>
        This page auto-refreshes every 3 seconds. You can close this tab and come back later.
      </p>
    </div>
  );
}
