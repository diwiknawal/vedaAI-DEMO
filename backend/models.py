"""
Veda AI — SQLAlchemy Models
Tables: Job, Scene, Clip
"""
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, Enum, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# ─── Enums ────────────────────────────────────────────────────────────────────

JOB_STATUS = Enum(
    "queued",
    "transcoding",
    "transcribing",
    "scene_detecting",
    "virality_scoring",
    "reframing",
    "ai_suggestions",
    "captioning",
    "completed",
    "failed",
    name="job_status",
)

PLATFORM = Enum("tiktok", "reels", "shorts", name="platform")


# ─── Models ───────────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    original_filename: Mapped[str] = mapped_column(String)
    upload_path: Mapped[str] = mapped_column(String)
    processed_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(JOB_STATUS, default="queued")
    progress: Mapped[int] = mapped_column(default=0)       # 0-100 percentage
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scenes: Mapped[list["Scene"]] = relationship("Scene", back_populates="job", cascade="all, delete")
    clips: Mapped[list["Clip"]] = relationship("Clip", back_populates="job", cascade="all, delete")

    def to_dict(self):
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "status": self.status,
            "progress": self.progress,
            "error_message": self.error_message,
            "duration_sec": self.duration_sec,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "scenes_count": len(self.scenes),
            "clips_count": len(self.clips),
        }


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id", ondelete="CASCADE"))
    scene_index: Mapped[int] = mapped_column(default=0)
    start_sec: Mapped[float] = mapped_column(Float)
    end_sec: Mapped[float] = mapped_column(Float)
    duration_sec: Mapped[float] = mapped_column(Float)
    virality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    transcript_segment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    motion_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    selected_for_clip: Mapped[bool] = mapped_column(default=False)

    job: Mapped["Job"] = relationship("Job", back_populates="scenes")
    clips: Mapped[list["Clip"]] = relationship("Clip", back_populates="scene", cascade="all, delete")

    def to_dict(self):
        return {
            "id": self.id,
            "scene_index": self.scene_index,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "duration_sec": self.duration_sec,
            "virality_score": self.virality_score,
            "transcript_segment": self.transcript_segment,
            "thumbnail_path": self.thumbnail_path,
            "motion_score": self.motion_score,
            "selected_for_clip": self.selected_for_clip,
        }


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id", ondelete="CASCADE"))
    scene_id: Mapped[str] = mapped_column(String, ForeignKey("scenes.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(PLATFORM, default="tiktok")
    file_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    duration_sec: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    virality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_suggestions: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    caption_file: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["Job"] = relationship("Job", back_populates="clips")
    scene: Mapped["Scene"] = relationship("Scene", back_populates="clips")

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "scene_id": self.scene_id,
            "platform": self.platform,
            "file_path": self.file_path,
            "duration_sec": self.duration_sec,
            "virality_score": self.virality_score,
            "ai_suggestions": self.ai_suggestions,
            "caption_file": self.caption_file,
            "created_at": self.created_at.isoformat(),
        }
