from app import db
from app.models import isoformat, new_uuid, utcnow

PROFILE_STATUSES = ("created", "running", "completed", "failed")


class BusinessProfile(db.Model):
    __tablename__ = "business_profiles"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('created', 'running', 'completed', 'failed')",
            name="ck_business_profiles_status",
        ),
    )

    uuid = db.Column(db.String(36), primary_key=True, default=new_uuid)
    name = db.Column(db.String(255), nullable=False)
    domain = db.Column(db.String(255), nullable=False, index=True)
    industry = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    competitors = db.Column(db.JSON, nullable=False, default=list)
    status = db.Column(db.String(20), nullable=False, default="created")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    runs = db.relationship(
        "PipelineRun",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PipelineRun.started_at.desc()",
    )
    queries = db.relationship(
        "DiscoveredQuery",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    recommendations = db.relationship(
        "ContentRecommendation",
        back_populates="profile",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self) -> dict:
        return {
            "profile_uuid": self.uuid,
            "name": self.name,
            "domain": self.domain,
            "industry": self.industry,
            "description": self.description,
            "competitors": list(self.competitors or []),
            "status": self.status,
            "created_at": isoformat(self.created_at),
            "updated_at": isoformat(self.updated_at),
        }
