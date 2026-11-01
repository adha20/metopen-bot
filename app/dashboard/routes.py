from __future__ import annotations

from flask import Flask, Response, jsonify, render_template, request

from app.bot.actions import DISCORD_ACTIONS, ActionError, run_discord_action, run_restore_message
from app.database.db import (
    apply_user_action,
    count_dataset_contributions,
    delete_analysis_log,
    execute_dashboard_review_action,
    export_dataset_contributions_csv,
    fetch_audit_logs,
    fetch_dashboard_stats,
    fetch_flagged_queue,
    fetch_label_distribution,
    fetch_log_by_id,
    fetch_log_context,
    fetch_user_context,
    fetch_users_summary,
    init_db,
    save_dataset_contribution,
    update_analysis_log,
)


VALID_ACTIONS = DISCORD_ACTIONS | {"pardon"}


def _parse_duration(value) -> int | None:
    """Menit untuk ban sementara; kosong/0 berarti permanen."""
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return None
    return minutes if minutes > 0 else None


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
        cleaned_id = str(payload.get("message_id", "")).replace("msg_", "")
        raw_id = int(cleaned_id) if cleaned_id.isdigit() else 0
        if not raw_id:
            return jsonify({"error": "Invalid message ID"}), 400

        action = payload.get("action", "")
        if action not in VALID_ACTIONS:
            return jsonify({"error": f"Aksi tidak dikenal: {action}"}), 400

        ctx = fetch_log_context(raw_id)
        if not ctx:
            return jsonify({"error": "Message not found"}), 404

        notes = payload.get("notes")
        duration = _parse_duration(payload.get("duration_minutes"))

        discord_message = ""
        if action in DISCORD_ACTIONS:
            try:
                discord_message = run_discord_action(
                    action=action,
                    user_id=ctx["user_id"],
                    guild_id=ctx["guild_id"],
                    channel_id=ctx["channel_id"],
                    duration_minutes=duration,
                    audit_reason=notes,
                )
            except ActionError as err:
                return jsonify({"error": str(err)}), err.status_code
        elif action == "pardon":
            # Discord tidak bisa meng-undelete pesan; bot mengirim ulang isinya. Best-effort: gagal tidak menghalangi pardon.
            msg = fetch_log_by_id(raw_id)
            if msg and msg["automated_action"] == "Pesan Dihapus Otomatis (Sanitasi)":
                try:
                    discord_message = run_restore_message(
                        guild_id=ctx["guild_id"],
                        channel_id=ctx["channel_id"],
                        author=msg["author"],
                        content=msg["content"],
                    )
                except ActionError as err:
                    discord_message = f"Status dipulihkan, tapi pesan tidak bisa dikirim ulang: {err}"

        result = execute_dashboard_review_action(raw_id, action, notes, duration)
        if not result:
            return jsonify({"error": "Message not found"}), 404
        result["discord_message"] = discord_message
        return jsonify(result)

    @app.route("/api/actions/user", methods=["POST"])
    def api_user_action():
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "")).strip()
        action = payload.get("action", "")
        if not user_id.isdigit():
            return jsonify({"error": "ID pengguna tidak valid"}), 400
        if action not in VALID_ACTIONS:
            return jsonify({"error": f"Aksi tidak dikenal: {action}"}), 400

        reason = (payload.get("reason") or "").strip() or None
        duration = _parse_duration(payload.get("duration_minutes"))

        discord_message = ""
        if action in DISCORD_ACTIONS:
            ctx = fetch_user_context(user_id)
            try:
                discord_message = run_discord_action(
                    action=action,
                    user_id=user_id,
                    guild_id=ctx["guild_id"],
                    channel_id=ctx["channel_id"],
                    duration_minutes=duration,
                    audit_reason=reason or "Sanksi manual oleh Administrator dashboard",
                    dm_note=reason,
                )
            except ActionError as err:
                return jsonify({"error": str(err)}), err.status_code

        resolved = apply_user_action(user_id, action, reason, duration)
        return jsonify({"success": True, "resolved_messages": resolved, "discord_message": discord_message})

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

    return app
