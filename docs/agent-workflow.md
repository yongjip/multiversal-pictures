# Agent Workflow

`Multiversal Pictures` uses a staged agent workflow instead of one giant prompt.

```mermaid
flowchart LR
    U["User Prompt"] --> S["Story Agent"]
    S --> B["Story Brief JSON"]
    B --> P["Shot Planner Agent"]
    P --> L["Shotlist JSON"]
    L --> H["Human Review"]
    H --> R["Render Agent"]
    R --> V["OpenAI Videos API"]
    V --> O["Downloaded Clips"]
    O --> Q["Review / Edit / Extend Loop"]
```

## Roles

- `Story Agent`
  - turns a rough premise into a visual story brief
  - defines audience, tone, character bible, story beats, and continuity notes
- `Shot Planner Agent`
  - converts the brief into a renderable `shotlist.json`
  - ensures every shot has concrete camera, setting, lighting, and action fields
- `Render Agent`
  - executes the shot list with the OpenAI Videos API
  - polls job status and downloads result assets
- `Review Agent`
  - checks finished clips and decides whether to keep, edit, or extend

## Why this is more stable

- one prompt rarely preserves character continuity across multiple clips
- a story brief gives the planner a stable source of truth
- a shot list makes the render layer deterministic and retryable
- failed clips can be rerun without rebuilding the whole story

## Recommended operating loop

1. write or paste a short story prompt
2. run `generate-shotlist`
3. inspect the generated brief and shot list
4. render one shot first
5. fix prompt or shot fields if needed
6. render the full sequence
7. use `edit` or `extend` for problem shots

## Commands

Generate a shot list from a story prompt:

```bash
multiversal-pictures generate-shotlist \
  --prompt-file examples/panda_story_prompt.txt \
  --output examples/panda_story_generated.json
```

Preview the agent request without calling the API:

```bash
multiversal-pictures generate-shotlist \
  --prompt-file examples/panda_story_prompt.txt \
  --output examples/panda_story_generated.json \
  --dry-run
```

Render the generated shot list:

```bash
multiversal-pictures render-shotlist \
  --shotlist examples/panda_story_generated.json \
  --output runs/panda_story
```

## OpenAI APIs used

- Planning: [Responses API](https://developers.openai.com/api/docs/guides/text)
- Structured planning output: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- Rendering: [Video generation with Sora](https://developers.openai.com/api/docs/guides/video-generation)
- Video job endpoints: [Videos API Reference](https://developers.openai.com/api/reference/resources/videos)
