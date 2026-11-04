from app import db
from app.models import isoformat, new_uuid, utcnow

CONTENT_TYPES = ("blog_post", "landing_page", "faq")
PRIORITIES = ("high", "medium", "low")


class ContentRecommendation(db.Model):
    __tablename__ = "content_recommendations"
    __table_args__ = (
        db.CheckConstraint(
            "content_type IN ('blog_post', 'landing_page', 'faq')",
            name="ck_content_recommendations_content_type",
        ),
        db.CheckConstraint(
            "priority IN ('high', 'medium', 'low')",
            name="ck_content_recommendations_priority",
        ),
    )

    uuid = db.Column(db.String(36), primary_key=True, default=new_uuid)
    profile_uuid = db.Column(
        db.String(36),
        db.ForeignKey("business_profiles.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_uuid = db.Column(
        db.String(36),
        db.ForeignKey("discovered_queries.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content_type = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    rationale = db.Column(db.Text, nullable=False)
    target_keywords = db.Column(db.JSON, nullable=False, default=list)
    priority = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    profile = db.relationship("BusinessProfile", back_populates="recommendations")
    target_query = db.relationship("DiscoveredQuery", back_populates="recommendations")

    def to_dict(self) -> dict:
        return {
            "recommendation_uuid": self.uuid,
            "target_query_uuid": self.query_uuid,
            "profile_uuid": self.profile_uuid,
            "content_type": self.content_type,
            "title": self.title,
            "rationale": self.rationale,
            "target_keywords": list(self.target_keywords or []),
            "priority": self.priority,
            "created_at": isoformat(self.created_at),
        }
