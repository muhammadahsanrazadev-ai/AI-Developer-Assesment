from flask import Blueprint, jsonify

from app import APIError, db
from app.models import DiscoveredQuery
from app.services import pipeline

queries_bp = Blueprint("queries", __name__)


@queries_bp.post("/queries/<query_uuid>/recheck")
def recheck_query(query_uuid: str):
    query = db.session.get(DiscoveredQuery, query_uuid)
    if query is None:
        raise APIError(404, "not_found", "Query not found.", {"query_uuid": query_uuid})
    return jsonify(pipeline.recheck_query(query).to_dict())
