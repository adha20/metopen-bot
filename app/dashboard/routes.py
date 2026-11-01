from __future__ import annotations

from flask import Flask, Response, jsonify, render_template, request

from app.database.db import (
    count_dataset_contributions,
    delete_analysis_log,
    execute_dashboard_review_action,
    export_dataset_contributions_csv,
    fetch_audit_logs,
    fetch_dashboard_stats,
    fetch_flagged_queue,
    fetch_label_distribution,
    fetch_log_by_id,
    fetch_users_summary,
    init_db,
    save_dataset_contribution,
    update_analysis_log,
)


def create_dashboard_app() -> Flask:
    init_db()

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    @app.route("/")
    def index() -> str:
        stats = fetch_dashboard_stats()
        flagged = fetch_flagged_queue()
        audit_logs = fetch_audit_logs()
        label_dist = fetch_label_distribution()
        users_summary = fetch_users_summary()
        dataset_count = count_dataset_contributions()
        return render_template(
            "dashboard.html",
            stats=stats,
            flagged=flagged,
            audit_logs=audit_logs,
            label_dist=label_dist,
            users_summary=users_summary,
            dataset_count=dataset_count,
        )

    @app.route("/api/stats")
    def api_stats():
        return jsonify(fetch_dashboard_stats())

    @app.route("/api/flagged-queue")
    def api_flagged_queue():
        return jsonify(fetch_flagged_queue())

    @app.route("/api/audit-logs")
    def api_audit_logs():
        search = request.args.get("search")
        label_filter = request.args.get("label_filter")
        status_filter = request.args.get("status_filter")
        return jsonify(
            fetch_audit_logs(
                search=search,
                label_filter=label_filter,
                status_filter=status_filter,
            )
        )

    @app.route("/api/label-distribution")
    def api_label_distribution():
        return jsonify(fetch_label_distribution())

    @app.route("/api/users-summary")
    def api_users_summary():
        return jsonify(fetch_users_summary())

    @app.route("/api/messages/<message_id>", methods=["GET", "PUT", "DELETE"])
    def api_message(message_id: str):
        cleaned_id = message_id.replace("msg_", "")
        raw_id = int(cleaned_id) if cleaned_id.isdigit() else 0
        if not raw_id:
            return jsonify({"error": "Invalid message ID"}), 400

        if request.method == "GET":
            msg = fetch_log_by_id(raw_id)
            if not msg:
                return jsonify({"error": "Message not found"}), 404
            return jsonify(msg)

        if request.method == "PUT":
            payload = request.get_json(silent=True) or {}
            updated = update_analysis_log(
                log_id=raw_id,
                status=payload.get("status", ""),
                admin_notes=payload.get("admin_notes"),
            )
            if not updated:
                return jsonify({"error": "Message not found"}), 404
            return jsonify(updated)

        if request.method == "DELETE":
            deleted = delete_analysis_log(raw_id)
            if not deleted:
                return jsonify({"error": "Message not found"}), 404
            return jsonify({"success": True, "message_id": message_id})

    @app.route("/api/actions/review", methods=["POST"])
    def api_review_action():
        payload = request.get_json(silent=True) or {}
        message_id = payload.get("message_id", "")
        cleaned_id = str(message_id).replace("msg_", "")
        raw_id = int(cleaned_id) if cleaned_id.isdigit() else 0
        if not raw_id:
            return jsonify({"error": "Invalid message ID"}), 400

        action = payload.get("action", "")
        notes = payload.get("notes")
        result = execute_dashboard_review_action(raw_id, action, notes)
        if not result:
            return jsonify({"error": "Failed to execute review action"}), 404
        return jsonify(result)

    @app.route("/api/dataset/add", methods=["POST"])
    def api_dataset_add():
        payload = request.get_json(silent=True) or {}
        text = payload.get("text", "").strip()
        if not text:
            return jsonify({"error": "Teks kalimat tidak boleh kosong"}), 400
        labels = payload.get("labels", {})
        source_id = payload.get("source_log_id")
        if isinstance(source_id, str):
            digits = "".join(ch for ch in source_id if ch.isdigit())
            source_id = int(digits) if digits else None

        try:
            row_id = save_dataset_contribution(text, labels, source_id)
        except ValueError as err:
            return jsonify({"error": str(err), "already_added": True}), 409

        total = count_dataset_contributions()
        return jsonify({"success": True, "id": row_id, "total": total, "source_log_id": source_id})

    @app.route("/api/dataset/export", methods=["GET"])
    def api_dataset_export():
        csv_data = export_dataset_contributions_csv()
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=re_dataset_contributions.csv"},
        )

    @app.route("/api/dataset/stats", methods=["GET"])
    def api_dataset_stats():
        return jsonify({"total": count_dataset_contributions()})

    return app
