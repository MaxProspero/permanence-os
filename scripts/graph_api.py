"""
PERMANENCE OS -- Entity Graph API

Flask Blueprint for the Entity Graph engine. Provides REST endpoints
for creating, querying, and traversing the entity graph.

Usage in dashboard_api.py:
    from scripts.graph_api import graph_bp
    app.register_blueprint(graph_bp, url_prefix="/api/graph")

Endpoints:
    GET    /api/graph/stats            -- graph statistics
    POST   /api/graph/entity           -- create entity
    GET    /api/graph/entity/<id>      -- get entity
    PUT    /api/graph/entity/<id>      -- update entity
    DELETE /api/graph/entity/<id>      -- delete entity
    POST   /api/graph/link             -- create relationship
    GET    /api/graph/linked/<id>      -- get linked entities
    GET    /api/graph/search           -- search entities
    GET    /api/graph/around/<id>      -- get subgraph
"""

import json
import os
import sys
from datetime import datetime, timezone
from typing import Optional

try:
    from flask import Blueprint, jsonify, request
except ImportError:
    Blueprint = None

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOG_DIR = os.path.join(BASE_DIR, "logs")
API_LOG = os.path.join(LOG_DIR, "graph_api.log")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_api_call(
    method: str,
    endpoint: str,
    payload: Optional[dict] = None,
    result: str = "OK",
) -> None:
    """Append-only audit log for graph API calls."""
    try:
        os.makedirs(os.path.dirname(API_LOG), exist_ok=True)
        entry = {
            "timestamp": _utc_iso(),
            "method": method,
            "endpoint": endpoint,
            "payload": payload,
            "result": result,
        }
        with open(API_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # Logging should never break the API


def _get_graph():
    """Lazy import and singleton for EntityGraph."""
    sys.path.insert(0, BASE_DIR)
    from core.entity_graph import EntityGraph

    db_path = os.path.join(BASE_DIR, "permanence_storage", "entity_graph.db")
    return EntityGraph(db_path=db_path)


# ---------------------------------------------------------------------------
# Blueprint
# ---------------------------------------------------------------------------

graph_bp = Blueprint("graph", __name__) if Blueprint else None

if graph_bp is not None:

    @graph_bp.route("/stats", methods=["GET"])
    def graph_stats():
        """GET /api/graph/stats -- graph statistics."""
        try:
            g = _get_graph()
            stats = g.stats()
            log_api_call("GET", "/api/graph/stats")
            return jsonify(stats)
        except Exception as e:
            log_api_call("GET", "/api/graph/stats", result=str(e))
            return jsonify({"error": str(e)}), 500

    @graph_bp.route("/entity", methods=["POST"])
    def create_entity():
        """POST /api/graph/entity -- create entity."""
        try:
            data = request.get_json(force=True)
            if not data:
                return jsonify({"error": "Request body required"}), 400

            entity_type = data.get("entity_type")
            title = data.get("title")

            if not entity_type or not title:
                return jsonify({"error": "entity_type and title are required"}), 400

            g = _get_graph()
            entity = g.create_entity(
                entity_type=entity_type,
                title=title,
                properties=data.get("properties"),
                created_by=data.get("created_by", "api"),
            )
            log_api_call("POST", "/api/graph/entity", {"title": title, "type": entity_type})
            return jsonify(entity), 201
        except ValueError as e:
            log_api_call("POST", "/api/graph/entity", result=str(e))
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            log_api_call("POST", "/api/graph/entity", result=str(e))
            return jsonify({"error": str(e)}), 500

    @graph_bp.route("/entity/<entity_id>", methods=["GET"])
    def get_entity(entity_id):
        """GET /api/graph/entity/<id> -- get entity."""
        try:
            g = _get_graph()
            entity = g.get_entity(entity_id)
            log_api_call("GET", f"/api/graph/entity/{entity_id}")
            if entity is None:
                return jsonify({"error": "Entity not found"}), 404
            return jsonify(entity)
        except Exception as e:
            log_api_call("GET", f"/api/graph/entity/{entity_id}", result=str(e))
            return jsonify({"error": str(e)}), 500

    @graph_bp.route("/entity/<entity_id>", methods=["PUT"])
    def update_entity(entity_id):
        """PUT /api/graph/entity/<id> -- update entity."""
        try:
            data = request.get_json(force=True)
            if not data:
                return jsonify({"error": "Request body required"}), 400

            g = _get_graph()
            updated = g.update_entity(entity_id, data)
            log_api_call("PUT", f"/api/graph/entity/{entity_id}", data)
            if updated is None:
                return jsonify({"error": "Entity not found"}), 404
            return jsonify(updated)
        except ValueError as e:
            log_api_call("PUT", f"/api/graph/entity/{entity_id}", result=str(e))
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            log_api_call("PUT", f"/api/graph/entity/{entity_id}", result=str(e))
            return jsonify({"error": str(e)}), 500

    @graph_bp.route("/entity/<entity_id>", methods=["DELETE"])
    def delete_entity(entity_id):
        """DELETE /api/graph/entity/<id> -- delete entity."""
        try:
            g = _get_graph()
            deleted = g.delete_entity(entity_id)
            log_api_call("DELETE", f"/api/graph/entity/{entity_id}")
            if not deleted:
                return jsonify({"error": "Entity not found"}), 404
            return jsonify({"deleted": True, "id": entity_id})
        except Exception as e:
            log_api_call("DELETE", f"/api/graph/entity/{entity_id}", result=str(e))
            return jsonify({"error": str(e)}), 500

    @graph_bp.route("/link", methods=["POST"])
    def create_link():
        """POST /api/graph/link -- create relationship."""
        try:
            data = request.get_json(force=True)
            if not data:
                return jsonify({"error": "Request body required"}), 400

            source_id = data.get("source_id")
            target_id = data.get("target_id")
            relationship = data.get("relationship")

            if not all([source_id, target_id, relationship]):
                return jsonify({"error": "source_id, target_id, and relationship are required"}), 400

            g = _get_graph()
            rel = g.link(
                source_id=source_id,
                target_id=target_id,
                relationship=relationship,
                properties=data.get("properties"),
            )
            log_api_call("POST", "/api/graph/link", {
                "source": source_id, "target": target_id, "rel": relationship
            })
            return jsonify(rel), 201
        except ValueError as e:
            log_api_call("POST", "/api/graph/link", result=str(e))
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            log_api_call("POST", "/api/graph/link", result=str(e))
            return jsonify({"error": str(e)}), 500

    @graph_bp.route("/linked/<entity_id>", methods=["GET"])
    def get_linked(entity_id):
        """GET /api/graph/linked/<id> -- get linked entities."""
        try:
            relationship = request.args.get("relationship")
            entity_type = request.args.get("type")

            g = _get_graph()
            linked = g.get_linked(
                entity_id,
                relationship=relationship,
                entity_type=entity_type,
            )
            log_api_call("GET", f"/api/graph/linked/{entity_id}")
            return jsonify(linked)
        except ValueError as e:
            log_api_call("GET", f"/api/graph/linked/{entity_id}", result=str(e))
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            log_api_call("GET", f"/api/graph/linked/{entity_id}", result=str(e))
            return jsonify({"error": str(e)}), 500

    @graph_bp.route("/search", methods=["GET"])
    def search_entities():
        """GET /api/graph/search?q=<query>&type=<type> -- search entities."""
        try:
            query = request.args.get("q", "")
            entity_type = request.args.get("type")
            limit = request.args.get("limit", 20, type=int)

            g = _get_graph()
            results = g.search(query, entity_type=entity_type, limit=limit)
            log_api_call("GET", "/api/graph/search", {"q": query, "type": entity_type})
            return jsonify(results)
        except ValueError as e:
            log_api_call("GET", "/api/graph/search", result=str(e))
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            log_api_call("GET", "/api/graph/search", result=str(e))
            return jsonify({"error": str(e)}), 500

    @graph_bp.route("/around/<entity_id>", methods=["GET"])
    def get_graph_around(entity_id):
        """GET /api/graph/around/<id>?depth=1 -- get subgraph."""
        try:
            depth = request.args.get("depth", 1, type=int)
            depth = min(depth, 5)  # Cap depth to prevent expensive queries

            g = _get_graph()
            result = g.get_graph_around(entity_id, depth=depth)
            log_api_call("GET", f"/api/graph/around/{entity_id}", {"depth": depth})
            if result is None:
                return jsonify({"error": "Entity not found"}), 404
            return jsonify(result)
        except Exception as e:
            log_api_call("GET", f"/api/graph/around/{entity_id}", result=str(e))
            return jsonify({"error": str(e)}), 500
