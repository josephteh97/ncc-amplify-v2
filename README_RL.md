# OpenClaw-RL — MCC Amplify v2

Agentic RL-powered PDF → RVT pipeline based on the OpenClaw-RL framework (arXiv:2603.10165).

## Architecture

```
PDF upload
    │
    ▼
FastAPI server_rl.py (port 8001)
    │  POST /run
    ▼
PipelineOrchestrator
    ├── Stage 1: PDFExtractionAgent
    ├── Stage 2: ElementDetectionAgent
    ├── Stage 3: GridDetectionAgent
    ├── Stage 4: SemanticAnalysisAgent
    └── Stage 5: RevitBuildAgent
              │
              └── (concurrent) RL Update Loop
                    ├── prm_judge()        — majority-vote reward
                    ├── opd_extract_hint() — hindsight hint extraction
                    ├── compute_advantage()
                    └── update_policy()    — append learned rules to system prompt
```

## Key components

| Component | File | Purpose |
|---|---|---|
| RL Core | `backend/rl_engine/rl_core.py` | PRM judge, OPD extractor, policy update |
| Replay Buffer | `backend/rl_engine/replay_buffer.py` | Thread-safe deque + JSONL log |
| Policy Registry | `backend/rl_engine/policy_registry.py` | JSON-persisted agent policies |
| MCP Registry | `backend/mcp_servers/mcp_registry.py` | 5 MCP servers wired to existing services |
| Skill Library | `backend/skills/skill_library.py` | 4 built-in skills, learnable via hints |
| Base Agent | `backend/agents/base_agent.py` | TOOL_CALL loop + RL wiring |
| Pipeline Agents | `backend/agents/pipeline_agents.py` | 5 specialised agents |
| Orchestrator | `backend/orchestrator/orchestrator.py` | Sequential stages + concurrent RL |
| RL Server | `backend/server_rl.py` | FastAPI on port 8001 |
| Dashboard | `frontend/dashboard_rl.html` | SSE live view + policy cards + feedback |

## Agents

| Agent | Stage | MCP Servers | Skills |
|---|---|---|---|
| `pdf_extraction_agent` | 1 | filesystem, pdf_processor | pdf_scale_detection |
| `element_detection_agent` | 2 | vision, filesystem | wall_classification, element_validation |
| `grid_detection_agent` | 3 | filesystem, llm | pdf_scale_detection |
| `semantic_analysis_agent` | 4 | llm | wall_classification, element_validation |
| `revit_build_agent` | 5 | revit, filesystem | revit_command_format, element_validation |

## MCP Servers

| Server | Tools | Wired to |
|---|---|---|
| `filesystem` | read_file, write_file, list_dir, run_shell | stdlib Path + subprocess |
| `pdf_processor` | convert_pdf | VectorProcessor + StreamingProcessor |
| `vision` | yolo_detect | YoloDetector (falls back to stub) |
| `revit` | build_revit_model | RevitClient HTTP |
| `llm` | generate | Ollama /api/chat |

## Skills

| Skill | Purpose |
|---|---|
| `pdf_scale_detection` | Scale bar / ratio / door / grid inference |
| `wall_classification` | Thickness → external / load-bearing / partition |
| `revit_command_format` | Complete JSON schema for Revit transaction |
| `element_validation` | Plausibility rules for walls, doors, windows, columns |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/run` | Upload PDF, start pipeline, returns `job_id` |
| GET | `/run/stream/{job_id}` | SSE stream of pipeline events |
| GET | `/status/{job_id}` | Current job status + stage outputs |
| POST | `/feedback` | Inject human reward + hint for an agent |
| GET | `/policies` | Summary of all agent policies |
| POST | `/policies/{agent}/reset` | Reset a specific agent's learned guidance |
| GET | `/replay-buffer/stats` | Replay buffer counts and reward sums |
| GET | `/skills` | Skill library summary |
| GET | `/health` | Health check |

## Start

```bash
# 1. Install deps
pip install -r requirements_rl.txt

# 2. Ensure Ollama is running with the model
ollama serve
ollama pull qwen2.5:latest   # or set OLLAMA_MODEL env var

# 3. Start the RL server
cd backend
python server_rl.py          # listens on :8001

# 4. Open the dashboard
open frontend/dashboard_rl.html
```

## Configuration (backend/.env)

```
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:latest
RL_PORT=8001
RL_UPDATE_EVERY=3            # interactions before policy update
AGENT_MAX_TURNS=12           # max tool-call turns per agent
WINDOWS_REVIT_SERVER=http://localhost:5000
```

## Run Tests

```bash
pip install pytest pytest-asyncio
pytest tests/test_rl_pipeline.py -v
```

All Ollama / HTTP calls are mocked — tests run fully offline.
