# Multiversal Pictures

Repository: `https://github.com/yongjip/multiversal-pictures.git`

This repository is focused on a Python-based OpenAI workflow for:

- generating shot lists from story prompts
- rendering stable video clips from those shot lists
- iterating with character continuity and shot-level control

## Start

```bash
cd /Users/yongjip/Projects/potato-king
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

## Configure

```bash
cp /Users/yongjip/Projects/potato-king/.env.example /Users/yongjip/Projects/potato-king/.env
```

Set `OPENAI_API_KEY` in `/Users/yongjip/Projects/potato-king/.env`.

## Agent Workflow

- `generate-shotlist`: story prompt -> story brief -> shotlist JSON
- `render-shotlist`: shotlist JSON -> rendered video clips
- `create-character`: reference video -> reusable character ID

Architecture notes: `/Users/yongjip/Projects/potato-king/docs/agent-workflow.md:1`

## Run

```bash
multiversal-pictures generate-shotlist \
  --prompt-file /Users/yongjip/Projects/potato-king/examples/panda_story_prompt.txt \
  --output /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json
```

```bash
multiversal-pictures render-shotlist \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story
```
