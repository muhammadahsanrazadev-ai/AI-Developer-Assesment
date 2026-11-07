from app import db
from app.models import isoformat, new_uuid, utcnow


class DiscoveredQuery(db.Model):
    __tablename__ = "discovered_queries"
    __table_args__ = (
        db.CheckConstraint(
            "opportunity_score IS NULL OR (opportunity_score >= 0 AND opportunity_score <= 1)",
            name="ck_discovered_queries_opportunity_score",
        ),
        db.CheckConstraint(
            "competitive_difficulty IS NULL OR "
            "(competitive_difficulty >= 0 AND competitive_difficulty <= 100)",
            name="ck_discovered_queries_competitive_difficulty",
        ),
        db.CheckConstraint(
            "estimated_search_volume IS NULL OR estimated_search_volume >= 0",
            name="ck_discovered_queries_search_volume",
        ),
        db.CheckConstraint(
            "visibility_position IS NULL OR visibility_position >= 1",
            name="ck_discovered_queries_visibility_position",
        ),
    )

    uuid = db.Column(db.String(36), primary_key=True, default=new_uuid)
    profile_uuid = db.Column(
        db.String(36),
        db.ForeignKey("business_profiles.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_uuid = db.Column(
        db.String(36),
        db.ForeignKey("pipeline_runs.uuid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query_text = db.Column(db.Text, nullable=False)
    # Google Ads keyword built from query_text. Null when the question cannot become
    # a phrase the search-volume API accepts.
    search_keyword = db.Column(db.String(80), nullable=True)
    # Scoring fields stay NULL when the Visibility Scoring Agent fails for this query;
    # domain_visible NULL is what the API exposes as status "unknown".
    estimated_search_volume = db.Column(db.Integer, nullable=True)
    competitive_difficulty = db.Column(db.Integer, nullable=True)
    opportunity_score = db.Column(db.Float, nullable=True, index=True)
    domain_visible = db.Column(db.Boolean, nullable=True)
    visibility_position = db.Column(db.Integer, nullable=True)
    discovered_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    profile = db.relationship("BusinessProfile", back_populates="queries")
    run = db.relationship("PipelineRun", back_populates="queries")
    recommendations = db.relationship(
        "ContentRecommendation",
        back_populates="target_query",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self) -> dict:
        return {
            "query_uuid": self.uuid,
            "profile_uuid": self.profile_uuid,
            "run_uuid": self.run_uuid,
            "query_text": self.query_text,
            "search_keyword": self.search_keyword,
            "estimated_search_volume": self.estimated_search_volume,
            "competitive_difficulty": self.competitive_difficulty,
            "opportunity_score": self.opportunity_score,
            "domain_visible": self.domain_visible,
            "visibility_position": self.visibility_position,
            "discovered_at": isoformat(self.discovered_at),
        }
