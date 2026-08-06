# Generation Runner

This runner executes the 120-row internal evaluation plan against Qwen/DashScope through its OpenAI-compatible API.

## Configure

Fill the API key in the project-root file:

```text
D:\AI_talk\personal_writing_agent_saas\.env.local
```

Required value:

```env
DASHSCOPE_API_KEY=your_key_here
```

Defaults are already set for:

```env
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-plus
```

## Dry Run

```powershell
& 'C:\Users\songw\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\tools\evaluation\run_generation_plan.py --dry-run --limit 5
```

## Smoke Test

Run one task through all variants:

```powershell
& 'C:\Users\songw\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\tools\evaluation\run_generation_plan.py --task-id ART-001_moyan
```

Run only one generation:

```powershell
& 'C:\Users\songw\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\tools\evaluation\run_generation_plan.py --limit 1
```

## Full Run

```powershell
& 'C:\Users\songw\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\tools\evaluation\run_generation_plan.py
```

Outputs are written under:

```text
eval_sets\mvp_style_eval_v1\outputs\
```

The runner also updates:

```text
eval_sets\mvp_style_eval_v1\generation_manifest.csv
eval_sets\mvp_style_eval_v1\retrieval_events.jsonl
```
