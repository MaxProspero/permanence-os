#!/usr/bin/env python3
"""Tests for telegram_control helpers."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import scripts.telegram_control as telegram_mod  # noqa: E402


def test_extract_update_message_prefers_message_payload() -> None:
    update = {
        "update_id": 10,
        "message": {"message_id": 2, "text": "hello", "chat": {"id": -1001}},
        "channel_post": {"message_id": 3, "text": "ignored", "chat": {"id": -1001}},
    }
    msg = telegram_mod._extract_update_message(update)
    assert isinstance(msg, dict)
    assert msg.get("message_id") == 2


def test_media_specs_selects_largest_photo_and_document() -> None:
    msg = {
        "photo": [
            {"file_id": "small", "file_size": 100, "file_unique_id": "u1"},
            {"file_id": "large", "file_size": 500, "file_unique_id": "u2"},
        ],
        "document": {
            "file_id": "doc1",
            "file_name": "notes.pdf",
            "file_unique_id": "d1",
        },
    }
    specs = telegram_mod._media_specs(msg)
    assert len(specs) == 2
    assert specs[0]["file_id"] == "large"
    assert specs[1]["file_id"] == "doc1"
    assert specs[1]["name"] == "notes.pdf"


def test_build_event_extracts_sender_message_and_urls() -> None:
    update = {"update_id": 42}
    msg = {
        "message_id": 12,
        "date": 1760000000,
        "text": "check this https://example.com/path",
        "from": {"username": "payton"},
        "chat": {"id": -1003837160764, "title": "Permanence"},
    }
    event = telegram_mod._build_event(
        update=update,
        msg=msg,
        source="telegram-control",
        channel="telegram",
        media_paths=["/tmp/file.jpg"],
    )
    assert event["source"] == "telegram-control"
    assert event["sender"] == "payton"
    assert event["channel"] == "telegram"
    assert "example.com/path" in " ".join(event.get("urls") or [])
    assert event["telegram_update_id"] == 42
    assert event["telegram_chat_id"] == -1003837160764
    assert event["media_paths"] == ["/tmp/file.jpg"]
    assert event["voice_note"] is False
    assert event["priority"] == "normal"


def test_extract_command_normalizes_and_strips_bot_suffix() -> None:
    cmd = telegram_mod._extract_command("/comms_status@Teleophtxnbot run")
    assert cmd == "comms-status"
    assert telegram_mod._extract_command("no command") == ""


def test_extract_command_args_reads_tail() -> None:
    args = telegram_mod._extract_command_args("/remember focus on high leverage work")
    assert args == "focus on high leverage work"
    assert telegram_mod._extract_command_args("hello") == ""


def test_execute_control_command_unknown_is_unhandled() -> None:
    result = telegram_mod._execute_control_command("not-a-real-command", timeout=3, prefix="/")
    assert result["handled"] is False


def test_command_argv_maps_known_command() -> None:
    argv = telegram_mod._command_argv("comms-status")
    assert "cli.py" in " ".join(argv)
    assert "comms-status" in argv
    esc = telegram_mod._command_argv("comms-escalations")
    assert "comms-escalation-digest" in esc
    esc_send = telegram_mod._command_argv("comms-escalations-send")
    assert "comms-escalation-digest" in esc_send
    assert "--send" in esc_send
    esc_status = telegram_mod._command_argv("comms-escalation-status")
    assert "comms-automation" in esc_status
    assert "escalation-status" in esc_status
    improve = telegram_mod._command_argv("improve-approve", "IMP-XYZ123456 246810")
    assert "self-improvement" in improve
    assert "--proposal-id" in improve
    assert "IMP-XYZ123456" in improve
    assert "--decision-code" in improve
    assert "246810" in improve
    x_add = telegram_mod._command_argv("x-watch", "@ophtxn")
    assert "x-account-watch" in x_add
    assert "--action" in x_add
    assert "add" in x_add
    assert "--handle" in x_add
    assert "@ophtxn" in x_add
    x_list = telegram_mod._command_argv("x-watch-list")
    assert "x-account-watch" in x_list
    assert "list" in x_list
    platform_watch = telegram_mod._command_argv("platform-watch", "strict no-queue")
    assert "platform-change-watch" in platform_watch
    assert "--strict" in platform_watch
    assert "--no-queue" in platform_watch
    brain_recall = telegram_mod._command_argv("brain-recall", "market focus and ophtxn")
    assert "ophtxn-brain" in brain_recall
    assert "recall" in brain_recall
    assert "--query" in brain_recall


def test_command_help_text_includes_escalation_controls() -> None:
    text = telegram_mod._command_help_text(prefix="/")
    assert "/comms-mode" in text
    assert "/comms-whoami" in text
    assert "/remember <note>" in text
    assert "/recall" in text
    assert "/profile-set <field> <value>" in text
    assert "/personality [mode]" in text
    assert "/habit-add <name>" in text
    assert "/comms-escalations-send" in text
    assert "/comms-escalation-status" in text
    assert "/comms-escalation-enable" in text
    assert "/comms-escalation-disable" in text
    assert "/learn-status" in text
    assert "/learn-run" in text
    assert "/improve-pitch" in text
    assert "/improve-list" in text
    assert "/improve-approve" in text
    assert "/platform-watch [strict] [no-queue]" in text
    assert "/brain-sync" in text
    assert "/brain-recall <query>" in text
    assert "/terminal <task>" in text
    assert "/terminal-list" in text


def test_parse_allowlist_and_command_user_gate() -> None:
    allowlist = telegram_mod._parse_id_allowlist("123, 456 789 not-an-id")
    assert allowlist == {"123", "456", "789"}
    assert telegram_mod._is_command_user_allowed("123", allowlist) is True
    assert telegram_mod._is_command_user_allowed("999", allowlist) is False
    assert telegram_mod._is_command_user_allowed("any", set()) is True
    assert telegram_mod._is_command_chat_allowed("-1001", {"-1001"}) is True
    assert telegram_mod._is_command_chat_allowed("-1002", {"-1001"}) is False
    assert telegram_mod._is_command_chat_allowed("-1002", set()) is True
    assert telegram_mod._is_public_command("comms-whoami") is True
    assert telegram_mod._is_public_command("remember") is True
    assert telegram_mod._is_public_command("share") is True
    assert telegram_mod._is_public_command("terminal") is True
    assert telegram_mod._is_public_command("terminal-list") is True
    assert telegram_mod._is_public_command("improve-pitch") is True
    assert telegram_mod._is_public_command("platform-watch") is True
    assert telegram_mod._is_public_command("comms-status") is False


def test_redact_sensitive_text_masks_card_and_payment_link() -> None:
    raw = "card 4242 4242 4242 4242 and https://checkout.stripe.com/c/pay/cs_test_123"
    scrubbed, reasons = telegram_mod._redact_sensitive_text(raw)
    assert "4242 4242 4242 4242" not in scrubbed
    assert "checkout.stripe.com" not in scrubbed
    assert "[REDACTED_CARD_NUMBER]" in scrubbed
    assert "[REDACTED_PAYMENT_LINK]" in scrubbed
    assert "card_number" in reasons
    assert "payment_link" in reasons


def test_send_imessage_reports_platform_requirement() -> None:
    original_platform = telegram_mod.sys.platform
    try:
        telegram_mod.sys.platform = "linux"
        ok, detail = telegram_mod._send_imessage(target="+15551230000", text="hello")
    finally:
        telegram_mod.sys.platform = original_platform
    assert ok is False
    assert "requires macOS" in detail


def test_send_ack_mirrors_to_imessage_when_enabled() -> None:
    original_env = dict(os.environ)
    original_api = telegram_mod._api
    original_send_imessage = telegram_mod._send_imessage
    calls: dict[str, str] = {}

    def _fake_api(*, token: str, method: str, params: dict[str, object] | None = None, timeout: int = 20) -> dict[str, object]:
        calls["api_method"] = method
        calls["api_text"] = str((params or {}).get("text") or "")
        return {"ok": True}

    def _fake_send_imessage(*, target: str, text: str, service: str = "iMessage", timeout: int = 20) -> tuple[bool, str]:
        calls["imessage_target"] = target
        calls["imessage_text"] = text
        calls["imessage_service"] = service
        return True, "sent"

    try:
        os.environ["PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_MIRROR"] = "1"
        os.environ["PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_TARGET"] = "+15551230000"
        os.environ["PERMANENCE_TELEGRAM_CONTROL_IMESSAGE_PREFIX"] = "[Ophtxn]"
        telegram_mod._api = _fake_api  # type: ignore[assignment]
        telegram_mod._send_imessage = _fake_send_imessage  # type: ignore[assignment]
        telegram_mod._send_ack(token="abc", chat_id="-1001", text="mirror this", timeout=3)
    finally:
        os.environ.clear()
        os.environ.update(original_env)
        telegram_mod._api = original_api  # type: ignore[assignment]
        telegram_mod._send_imessage = original_send_imessage  # type: ignore[assignment]
    assert calls.get("api_method") == "sendMessage"
    assert calls.get("api_text") == "mirror this"
    assert calls.get("imessage_target") == "+15551230000"
    assert "[Ophtxn] mirror this" == calls.get("imessage_text")


def test_memory_command_terminal_queue_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        queue_path = Path(tmp) / "terminal_tasks.jsonl"
        store: dict[str, object] = {"profiles": {}, "updated_at": ""}
        key = "user:123"

        queued = telegram_mod._execute_memory_command(
            command="terminal",
            command_args="harden telegram queue parser 4242 4242 4242 4242 https://checkout.stripe.com/c/pay/test_1",
            store=store,  # type: ignore[arg-type]
            memory_key=key,
            chat_id="-1001",
            sender_user_id="123",
            sender_name="payton",
            max_notes=200,
            terminal_queue_path=queue_path,
            prefix="/",
        )
        assert queued["handled"] is True
        assert queued["ok"] is True
        assert "Queued terminal task" in str(queued.get("summary") or "")
        assert queue_path.exists()
        queue_text = queue_path.read_text(encoding="utf-8")
        assert "4242 4242 4242 4242" not in queue_text
        assert "checkout.stripe.com" not in queue_text
        assert "[REDACTED_CARD_NUMBER]" in queue_text
        assert "[REDACTED_PAYMENT_LINK]" in queue_text

        listing = telegram_mod._execute_memory_command(
            command="terminal-list",
            command_args="",
            store=store,  # type: ignore[arg-type]
            memory_key=key,
            chat_id="-1001",
            sender_user_id="123",
            sender_name="payton",
            max_notes=200,
            terminal_queue_path=queue_path,
            prefix="/",
        )
        assert listing["handled"] is True
        assert listing["ok"] is True
        assert "Recent terminal tasks" in str(listing.get("summary") or "")


def test_configured_target_chat_ids_combines_env_and_cli() -> None:
    old_env = dict(os.environ)
    try:
        os.environ.pop("PERMANENCE_TELEGRAM_CONTROL_TARGET_CHAT_IDS", None)
        os.environ["PERMANENCE_TELEGRAM_CHAT_ID"] = "-1001"
        os.environ["PERMANENCE_TELEGRAM_CHAT_IDS"] = "-1002, -1003"
        rows = telegram_mod._configured_target_chat_ids("-1004,invalid")
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    assert rows == {"-1001", "-1002", "-1003", "-1004"}


def test_configured_target_chat_ids_control_scope_blank_means_all() -> None:
    old_env = dict(os.environ)
    try:
        os.environ["PERMANENCE_TELEGRAM_CHAT_ID"] = "-1001"
        os.environ["PERMANENCE_TELEGRAM_CHAT_IDS"] = "-1002"
        os.environ["PERMANENCE_TELEGRAM_CONTROL_TARGET_CHAT_IDS"] = ""
        rows = telegram_mod._configured_target_chat_ids("")
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    assert rows == set()


def test_execute_control_command_mode_is_handled() -> None:
    result = telegram_mod._execute_control_command("comms-mode", timeout=3, prefix="/")
    assert result["handled"] is True
    assert result["ok"] is True
    assert "routing mode" in str(result.get("summary") or "").lower()


def test_chat_prompt_and_trim_reply() -> None:
    history = [
        telegram_mod._chat_history_entry("user", "first"),
        telegram_mod._chat_history_entry("assistant", "second"),
        telegram_mod._chat_history_entry("user", "third"),
    ]
    prompt = telegram_mod._compose_chat_prompt(
        user_text="latest ask",
        sender="payton",
        chat_id="-1001",
        history_rows=history,
        memory_rows=[{"text": "avoid context switching"}],
        profile_lines=["- Goals: build permanence"],
        habit_lines=["- Daily review (streak=4, last_done=2026-03-04)"],
        max_history_messages=2,
        brain_rows=[{"source": "docs/ophtxn_personal_agent_roadmap.md", "text": "Mission: build a personal intelligence system."}],
    )
    assert "Chat ID: -1001" in prompt
    assert "latest ask" in prompt
    assert "first" not in prompt
    assert "avoid context switching" in prompt
    assert "Goals: build permanence" in prompt
    assert "Daily review" in prompt
    assert "System brain context" in prompt
    assert "personal intelligence system" in prompt
    clipped = telegram_mod._trim_reply_text("x" * 1000, max_chars=160)
    assert len(clipped) <= 160


def test_brain_context_notes_matches_query_tokens() -> None:
    rows = [
        {"source": "docs/a.md", "text": "Ophtxn should run finance and AI research daily.", "tokens": ["ophtxn", "finance", "research"]},
        {"source": "docs/b.md", "text": "Workout routine planning and recovery.", "tokens": ["workout", "routine"]},
    ]
    selected = telegram_mod._brain_context_notes(rows, query="ophtxn finance", limit=2)
    assert selected
    assert "finance" in str(selected[0].get("text") or "").lower()


def test_generate_chat_reply_handles_missing_router() -> None:
    text, err = telegram_mod._generate_chat_reply(prompt="hello", task_type="execution", model_router=None)
    assert text == ""
    assert "unavailable" in err


def test_chat_history_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "chat_history.json"
        payload = {"-1001": [telegram_mod._chat_history_entry("user", "hello")]}
        telegram_mod._save_chat_history(path, payload)
        loaded = telegram_mod._load_chat_history(path)
        assert "-1001" in loaded
        assert loaded["-1001"][0]["text"] == "hello"


def test_memory_store_roundtrip_and_commands() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "memory.json"
        intake_path = Path(tmp) / "telegram_share_intake.jsonl"
        store = telegram_mod._load_memory_store(path)
        key = telegram_mod._memory_key(chat_id="-1001", sender_user_id="42", sender_name="payton")
        changed = telegram_mod._memory_add_note(
            store=store,
            key=key,
            chat_id="-1001",
            sender_user_id="42",
            sender_name="payton",
            text="Prioritize deep work blocks each morning.",
            source="manual",
            max_notes=50,
        )
        assert changed is True
        recall = telegram_mod._memory_recall_text(store, key, limit=5, prefix="/")
        assert "deep work blocks" in recall
        recall_query = telegram_mod._memory_recall_text(store, key, query="deep work", limit=5, prefix="/")
        assert "Matching memory notes" in recall_query
        profile = telegram_mod._memory_profile_text(store, key, prefix="/")
        assert "Notes stored: 1" in profile
        profile_set = telegram_mod._execute_memory_command(
            command="profile-set",
            command_args="goals ship ophtxn weekly",
            store=store,
            memory_key=key,
            chat_id="-1001",
            sender_user_id="42",
            sender_name="payton",
            max_notes=50,
            prefix="/",
        )
        assert profile_set["handled"] is True
        assert profile_set["ok"] is True
        personality_set = telegram_mod._execute_memory_command(
            command="personality",
            command_args="operator",
            store=store,
            memory_key=key,
            chat_id="-1001",
            sender_user_id="42",
            sender_name="payton",
            max_notes=50,
            prefix="/",
        )
        assert personality_set["ok"] is True
        habit_add = telegram_mod._execute_memory_command(
            command="habit-add",
            command_args="daily planning",
            store=store,
            memory_key=key,
            chat_id="-1001",
            sender_user_id="42",
            sender_name="payton",
            max_notes=50,
            prefix="/",
        )
        assert habit_add["ok"] is True
        habit_done = telegram_mod._execute_memory_command(
            command="habit-done",
            command_args="daily planning",
            store=store,
            memory_key=key,
            chat_id="-1001",
            sender_user_id="42",
            sender_name="payton",
            max_notes=50,
            prefix="/",
        )
        assert habit_done["ok"] is True
        share_run = telegram_mod._execute_memory_command(
            command="share",
            command_args="Vision: build Ophtxn into a personal operating system with strict governance.",
            store=store,
            memory_key=key,
            chat_id="-1001",
            sender_user_id="42",
            sender_name="payton",
            max_notes=50,
            intake_path=intake_path,
            prefix="/",
        )
        assert share_run["ok"] is True
        assert intake_path.exists()
        intake_rows = [row for row in intake_path.read_text(encoding="utf-8").splitlines() if row.strip()]
        assert intake_rows
        assert "Ophtxn" in intake_rows[-1]
        habit_list = telegram_mod._execute_memory_command(
            command="habit-list",
            command_args="",
            store=store,
            memory_key=key,
            chat_id="-1001",
            sender_user_id="42",
            sender_name="payton",
            max_notes=50,
            prefix="/",
        )
        assert "daily planning" in str(habit_list.get("summary") or "").lower()
        run = telegram_mod._execute_memory_command(
            command="forget-last",
            command_args="",
            store=store,
            memory_key=key,
            chat_id="-1001",
            sender_user_id="42",
            sender_name="payton",
            max_notes=50,
            prefix="/",
        )
        assert run["handled"] is True
        assert run["ok"] is True
        telegram_mod._save_memory_store(path, store)
        loaded = telegram_mod._load_memory_store(path)
        notes = telegram_mod._memory_recent_notes(loaded, key, limit=5)
        assert len(notes) == 1
        assert "deep work blocks" in str(notes[0].get("text") or "").lower()


def test_memory_select_notes_uses_semantic_synonyms() -> None:
    notes = [
        {"text": "Prioritize deep work blocks from 8am to 11am.", "source": "manual"},
        {"text": "Keep outreach concise and respectful.", "source": "manual"},
    ]
    selected = telegram_mod._select_memory_notes(notes, query="need better focus at work", limit=1)
    assert selected
    assert "deep work blocks" in str(selected[0].get("text") or "").lower()


def test_profile_history_and_conflicts_are_logged() -> None:
    store = {"profiles": {}, "updated_at": ""}
    key = telegram_mod._memory_key(chat_id="-1001", sender_user_id="42", sender_name="payton")
    profile = telegram_mod._memory_profile(store, key)

    changed1, _summary1 = telegram_mod._profile_set_field(profile, field_alias="goals", value="Ship daily")
    changed2, _summary2 = telegram_mod._profile_set_field(profile, field_alias="goals", value="Ship weekly")
    assert changed1 is True
    assert changed2 is True

    history = telegram_mod._profile_history_rows(profile)
    conflicts = telegram_mod._profile_conflict_rows(profile)
    assert len(history) >= 2
    assert len(conflicts) >= 1

    history_text = telegram_mod._profile_history_text(profile, field_alias="goals", prefix="/")
    conflicts_text = telegram_mod._profile_conflicts_text(profile, prefix="/")
    assert "Goals" in history_text
    assert "Open profile conflicts" in conflicts_text


def test_habit_plan_and_nudge_commands() -> None:
    store = {"profiles": {}, "updated_at": ""}
    key = telegram_mod._memory_key(chat_id="-1001", sender_user_id="42", sender_name="payton")

    add = telegram_mod._execute_memory_command(
        command="habit-add",
        command_args="daily planning | cue: after coffee | plan: If it is 8am, open plan board.",
        store=store,
        memory_key=key,
        chat_id="-1001",
        sender_user_id="42",
        sender_name="payton",
        max_notes=50,
        prefix="/",
    )
    assert add["ok"] is True

    update = telegram_mod._execute_memory_command(
        command="habit-plan",
        command_args="daily planning | cue: after workout | plan: If it is 8:30am, set top 3 tasks.",
        store=store,
        memory_key=key,
        chat_id="-1001",
        sender_user_id="42",
        sender_name="payton",
        max_notes=50,
        prefix="/",
    )
    assert update["ok"] is True

    nudge = telegram_mod._execute_memory_command(
        command="habit-nudge",
        command_args="",
        store=store,
        memory_key=key,
        chat_id="-1001",
        sender_user_id="42",
        sender_name="payton",
        max_notes=50,
        prefix="/",
    )
    assert nudge["ok"] is True
    assert "after workout" in str(nudge.get("summary") or "").lower()


def test_chat_system_prompt_uses_personality_mode() -> None:
    prompt = telegram_mod._chat_system_prompt(personality_mode="coach", profile_lines=["- Goals: consistency"])
    assert "Personality mode: coach" in prompt
    assert "- Goals: consistency" not in prompt  # profile details are not injected verbatim


def test_voice_note_detection_and_media_types() -> None:
    msg = {
        "voice": {"file_id": "v1"},
        "document": {"mime_type": "audio/mpeg", "file_name": "memo.mp3"},
    }
    assert telegram_mod._is_voice_note_message(msg) is True
    types = telegram_mod._message_media_types(msg)
    assert "voice" in types
    assert "audio" in types


def test_enqueue_transcription_items_dedupes_existing_paths() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        queue_path = Path(tmp) / "transcription_queue.json"
        queued1 = telegram_mod._enqueue_transcription_items(
            queue_path=queue_path,
            media_paths=["/tmp/a.m4a", "/tmp/a.m4a", "/tmp/b.mp4", "/tmp/c.jpg"],
            source="telegram-control",
            channel="telegram-voice",
            sender="payton",
            message="voice",
            event_time="2026-03-03T00:00:00+00:00",
        )
        assert queued1 == 2
        queued2 = telegram_mod._enqueue_transcription_items(
            queue_path=queue_path,
            media_paths=["/tmp/a.m4a"],
            source="telegram-control",
            channel="telegram-voice",
            sender="payton",
            message="voice",
            event_time="2026-03-03T00:00:00+00:00",
        )
        assert queued2 == 0


if __name__ == "__main__":
    test_extract_update_message_prefers_message_payload()
    test_media_specs_selects_largest_photo_and_document()
    test_build_event_extracts_sender_message_and_urls()
    test_extract_command_normalizes_and_strips_bot_suffix()
    test_extract_command_args_reads_tail()
    test_execute_control_command_unknown_is_unhandled()
    test_command_argv_maps_known_command()
    test_command_help_text_includes_escalation_controls()
    test_parse_allowlist_and_command_user_gate()
    test_send_imessage_reports_platform_requirement()
    test_send_ack_mirrors_to_imessage_when_enabled()
    test_configured_target_chat_ids_combines_env_and_cli()
    test_configured_target_chat_ids_control_scope_blank_means_all()
    test_execute_control_command_mode_is_handled()
    test_chat_prompt_and_trim_reply()
    test_brain_context_notes_matches_query_tokens()
    test_generate_chat_reply_handles_missing_router()
    test_chat_history_roundtrip()
    test_memory_store_roundtrip_and_commands()
    test_memory_select_notes_uses_semantic_synonyms()
    test_profile_history_and_conflicts_are_logged()
    test_habit_plan_and_nudge_commands()
    test_chat_system_prompt_uses_personality_mode()
    test_voice_note_detection_and_media_types()
    test_enqueue_transcription_items_dedupes_existing_paths()
    print("✓ Telegram control tests passed")
