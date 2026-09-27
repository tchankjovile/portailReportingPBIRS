import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    pbirs_id = Column(String(255), unique=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    path = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, index=True)
    department = Column(String(100), nullable=False, index=True)
    tags = Column(String(255), nullable=True)
    embed_url = Column(String(500), nullable=True)
    view_count = Column(Integer, default=0)
    is_featured = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    favorites = relationship("Favorite", back_populates="report", cascade="all, delete-orphan")
    history_entries = relationship("ReportHistory", back_populates="report", cascade="all, delete-orphan")
    anomalies = relationship("AnomalyReport", back_populates="report", cascade="all, delete-orphan")


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    user_upn = Column(String(255), nullable=False, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)

    report = relationship("Report", back_populates="favorites")


class ReportHistory(Base):
    __tablename__ = "report_history"

    id = Column(Integer, primary_key=True, index=True)
    user_upn = Column(String(255), nullable=False, index=True)
    report_id = Column(Integer, ForeignKey("reports.id"), nullable=False)
    viewed_at = Column(DateTime, default=datetime.datetime.utcnow)

    report = relationship("Report", back_populates="history_entries")


class AnomalyReport(Base):
    """Signalement d'anomalie soumis par un utilisateur sur un rapport."""
    __tablename__ = "anomaly_reports"

    id            = Column(Integer, primary_key=True, index=True)
    report_id     = Column(Integer, ForeignKey("reports.id", ondelete="SET NULL"), nullable=True, index=True)
    report_name   = Column(String(255), nullable=False)   # Nom du rapport au moment du signalement
    report_path   = Column(String(500), nullable=True)
    user_upn      = Column(String(255), nullable=False, index=True)  # Qui a signalé
    user_name     = Column(String(255), nullable=False)
    user_dept     = Column(String(100), nullable=True)
    description   = Column(Text, nullable=False)           # Description de l'anomalie
    # Statuts : nouveau / en_traitement / résolu
    status        = Column(String(20), default="nouveau", index=True)
    created_at    = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    resolved_at   = Column(DateTime, nullable=True)
    resolved_by   = Column(String(255), nullable=True)
    admin_comment = Column(Text, nullable=True)

    report = relationship("Report", back_populates="anomalies")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_upn = Column(String(255), nullable=False, index=True)
    action = Column(String(100), nullable=False)
    report_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
