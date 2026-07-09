from __future__ import annotations

import importlib.resources

from mcp.server.fastmcp import FastMCP

from codex_advisor import config as cfg_mod
from codex_advisor import providers, rollout

mcp = FastMCP("codex-advisor")

_consult_count = 0


def _system_prompt() -> str:
    return (
        importlib.resources.files("codex_advisor") / "advisor_prompt.md"
    ).read_text(encoding="utf-8")


def _build_user_content(transcript: str, question: str, context_hint: str) -> str:
    sections = [
        "# Current session transcript",
        transcript or "(no transcript found)",
        "# Question from the coding agent",
        question,
    ]
    if context_hint:
        sections += ["# Additional context from the agent", context_hint]
    return "\n\n".join(sections)


@mcp.tool()
def consult_advisor(question: str, context_hint: str = "") -> str:
    """Consult the configured advisor model for strategic guidance.

    Call this at decision points: before committing to a non-trivial plan,
    when the same error persists after two fix attempts, or before declaring
    a complex task complete. The current session transcript is attached
    automatically; put the specific decision to evaluate in `question`.
    """
    global _consult_count
    cfg = cfg_mod.load_config()
    prefix = "".join(f"[advisor warning] {w}\n" for w in cfg.warnings)
    if not cfg.enabled:
        return prefix + (
            "advisor is disabled. Use advisor_config(action='set', model=...) "
            "only if the user asks to re-enable it."
        )
    if _consult_count >= cfg.max_consults_per_session:
        return prefix + (
            f"consult limit reached ({cfg.max_consults_per_session} per session). "
            "Proceed with your own judgment."
        )
    try:
        provider_name, model_name = cfg_mod.split_model(cfg.model)
    except ValueError as e:
        return prefix + f"advisor unavailable: {e}"
    provider = cfg.providers.get(provider_name)
    if provider is None:
        return prefix + (
            f"advisor unavailable: unknown provider {provider_name!r}. "
            f"Add [providers.{provider_name}] to advisor.toml."
        )
    try:
        system_prompt = _system_prompt()
    except Exception as e:
        return prefix + f"advisor unavailable: failed to load advisor_prompt.md ({e})"
    transcript = ""
    transcript_note = ""
    rollout_path = rollout.find_latest_rollout(cfg_mod.sessions_root())
    if rollout_path is not None:
        try:
            transcript = rollout.build_transcript(rollout_path, cfg.max_context_chars)
        except Exception:
            rollout_path = None
    if rollout_path is None:
        transcript_note = (
            "\n\n(note: no session transcript was found; advice is based on the question only)"
        )
    _consult_count += 1
    try:
        advice = providers.call_advisor(
            provider,
            model_name,
            system_prompt,
            _build_user_content(transcript, question, context_hint),
        )
    except providers.AdvisorError as e:
        return prefix + f"advisor unavailable: {e}. Proceed with your own judgment."
    return prefix + f"[advice from {cfg.model}]\n{advice}{transcript_note}"


def main() -> None:
    cfg_mod.load_env_file()
    mcp.run()
