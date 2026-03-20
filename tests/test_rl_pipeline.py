"""
Tests for the OpenClaw-RL pipeline components.
All Ollama / HTTP calls are mocked so tests run fully offline.

Run:
    pip install pytest pytest-asyncio
    pytest tests/test_rl_pipeline.py -v
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

pytest_plugins = ("pytest_asyncio",)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fake_ollama_response(content: str) -> dict:
    return {"message": {"content": content}}


# ── 1. Interaction dataclass ───────────────────────────────────────────────────

def test_interaction_to_dict():
    from rl_engine.rl_core import Interaction
    i = Interaction(
        session_id="s1", turn_idx=0, agent_name="test_agent",
        state="state", action="action",
    )
    d = i.to_dict()
    assert d["session_id"] == "s1"
    assert d["agent_name"] == "test_agent"
    assert d["reward"] == 0.0
    assert "timestamp" in d


# ── 2. AgentPolicy effective_system_prompt ────────────────────────────────────

def test_agent_policy_prompt_with_addendum():
    from rl_engine.rl_core import AgentPolicy
    p = AgentPolicy(agent_name="a", base_system_prompt="BASE")
    assert p.effective_system_prompt == "BASE"

    p.apply_hint("Always check units.")
    assert "LEARNED GUIDANCE" in p.effective_system_prompt
    assert "Always check units" in p.effective_system_prompt

    # Duplicate hints not added twice
    p.apply_hint("Always check units.")
    assert p.learned_addendum.count("Always check units") == 1


# ── 3. PRM Judge ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_prm_judge_positive():
    from rl_engine.rl_core import prm_judge
    with patch("rl_engine.rl_core._ollama_chat", new=AsyncMock(return_value="SCORE: 1")):
        score = await prm_judge("good action", "positive next state", "agent", num_votes=3)
    assert score == 1.0


@pytest.mark.asyncio
async def test_prm_judge_negative():
    from rl_engine.rl_core import prm_judge
    with patch("rl_engine.rl_core._ollama_chat", new=AsyncMock(return_value="SCORE: -1")):
        score = await prm_judge("bad action", "error next state", "agent", num_votes=3)
    assert score == -1.0


# ── 4. OPD Hint Extraction ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_opd_extracts_hint():
    from rl_engine.rl_core import opd_extract_hint
    hint_response = "SCORE: -1\nHINT: You should have validated the wall thickness first."
    with patch("rl_engine.rl_core._ollama_chat", new=AsyncMock(return_value=hint_response)):
        score, hint = await opd_extract_hint("action", "next_state", "agent")
    assert score == -1.0
    assert "wall thickness" in hint


@pytest.mark.asyncio
async def test_opd_no_hint_when_perfect():
    from rl_engine.rl_core import opd_extract_hint
    with patch("rl_engine.rl_core._ollama_chat", new=AsyncMock(return_value="SCORE: 1\nHINT: none")):
        score, hint = await opd_extract_hint("action", "next_state", "agent")
    assert score == 1.0
    assert hint == ""


# ── 5. Replay Buffer ──────────────────────────────────────────────────────────

def test_replay_buffer_add_and_stats(tmp_path):
    from rl_engine.replay_buffer import ReplayBuffer
    from rl_engine.rl_core import Interaction

    buf = ReplayBuffer(maxlen=10, log_dir=str(tmp_path))
    for i in range(3):
        interaction = Interaction(
            session_id="s", turn_idx=i,
            agent_name="agent_a", state="s", action="a",
            reward=1.0,
        )
        buf.add(interaction)

    stats = buf.stats()
    assert stats["total"] == 3
    assert stats["by_agent"]["agent_a"]["count"] == 3
    assert stats["by_agent"]["agent_a"]["reward"] == 3.0


# ── 6. Policy Registry persist / reload ───────────────────────────────────────

def test_policy_registry_persist_reload(tmp_path):
    from rl_engine.policy_registry import PolicyRegistry
    from rl_engine.rl_core import AgentPolicy

    path = str(tmp_path / "policies.json")
    reg  = PolicyRegistry(persist_path=path)
    p    = AgentPolicy(agent_name="my_agent", base_system_prompt="BASE")
    p.apply_hint("Check scale first.")
    reg.register(p)

    # Reload from disk
    reg2 = PolicyRegistry(persist_path=path)
    loaded = reg2.get("my_agent")
    assert loaded is not None
    assert "Check scale first" in loaded.learned_addendum


# ── 7. MCP Registry and skill library ─────────────────────────────────────────

def test_mcp_registry_default():
    from mcp_servers.mcp_registry import MCPRegistry
    reg = MCPRegistry.default()
    names = reg.all_names()
    assert "filesystem" in names
    assert "pdf_processor" in names
    assert "vision" in names
    assert "revit" in names
    assert "llm" in names


def test_skill_library_defaults(tmp_path):
    from skills.skill_library import SkillLibrary
    sl = SkillLibrary(persist_path=str(tmp_path / "skills.json"))
    names = sl.all_names()
    assert "pdf_scale_detection"  in names
    assert "wall_classification"  in names
    assert "revit_command_format" in names
    assert "element_validation"   in names

    # Learn a hint
    sl.learn_from_hint("wall_classification", "Thin glass curtain walls are < 50 mm.")
    text = sl.get_text(["wall_classification"])
    assert "curtain walls" in text
