"""HTTP status and paginated receipts for accepted local bulk commands."""
from flask import Blueprint, jsonify, request

from core.operations.bulk_mutation_service import DEFAULT_PAGE_SIZE, read_receipt


def submission_error(exc):
    reason_code = str(exc)
    status = 409 if reason_code == "idempotency_key_conflict" else 400
    return jsonify(ok=False, reason_code=reason_code, error=reason_code), status


def create_bulk_mutations_blueprint(_context):
    blueprint = Blueprint("bulk_mutations", __name__)

    @blueprint.get("/api/bulk-mutations/<int:command_id>")
    def get_receipt(command_id):
        try:
            offset = int(request.args.get("offset", 0))
            limit = int(request.args.get("limit", DEFAULT_PAGE_SIZE))
            receipt = read_receipt(command_id, offset=offset, limit=limit)
        except ValueError:
            return jsonify(ok=False, reason_code="invalid_bulk_pagination", error="批量回执分页参数无效"), 400
        except LookupError:
            return jsonify(ok=False, reason_code="bulk_command_not_found", error="批量命令不存在"), 404
        return jsonify(ok=True, **receipt)

    return blueprint
