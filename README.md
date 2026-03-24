# Multiversal Pictures

Repository: `https://github.com/yongjip/multiversal-pictures.git`

This repository is focused on a Python-based OpenAI workflow for:

- generating narration-first storybook shot lists from story prompts
- rendering stable visual clips that play under external voiceover
- exporting narration scripts for TTS and final edit
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
- `export-narration`: shotlist JSON -> narration script
- `synthesize-narration`: shotlist JSON -> narration audio track
- `export-subtitles`: shotlist or narration timing -> SRT/VTT/JSON subtitles
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
multiversal-pictures export-narration \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story/narration.md
```

```bash
multiversal-pictures synthesize-narration \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --output-dir /Users/yongjip/Projects/potato-king/runs/panda_story/narration
```

```bash
multiversal-pictures export-subtitles \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --narration-manifest /Users/yongjip/Projects/potato-king/runs/panda_story/narration/narration-manifest.json \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story/narration/captions.srt
```

```bash
multiversal-pictures render-shotlist \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story
```

```bash
multiversal-pictures render-shotlist \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story \
  --jobs 4 \
  --stitch-output /Users/yongjip/Projects/potato-king/runs/panda_story/story.mp4 \
  --stitch-overwrite
```

```bash
multiversal-pictures stitch-run \
  --run-dir /Users/yongjip/Projects/potato-king/runs/panda_story \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story/story.mp4 \
  --overwrite
```

```bash
multiversal-pictures stitch-run \
  --run-dir /Users/yongjip/Projects/potato-king/runs/panda_story \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story/story-with-narration.mp4 \
  --narration-audio /Users/yongjip/Projects/potato-king/runs/panda_story/narration/narration.wav \
  --background-music /absolute/path/to/music.wav \
  --subtitle-file /Users/yongjip/Projects/potato-king/runs/panda_story/narration/captions.srt \
  --mute-clip-audio \
  --overwrite
```

```bash
multiversal-pictures stitch-run \
  --run-dir /Users/yongjip/Projects/potato-king/runs/panda_story \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story/story-with-burned-subtitles.mp4 \
  --narration-audio /Users/yongjip/Projects/potato-king/runs/panda_story/narration/narration.wav \
  --background-music /absolute/path/to/music.wav \
  --subtitle-file /Users/yongjip/Projects/potato-king/runs/panda_story/narration/captions.srt \
  --burn-subtitles \
  --subtitle-preset large \
  --subtitle-layout auto \
  --mute-clip-audio \
  --overwrite
```

## Positioning

`Multiversal Pictures` is optimized for narration-led storybook videos.

- clips are generated as expressive visuals, not dialogue performances
- narration is planned per shot and exported for TTS or human voiceover
- shots can render concurrently and then be stitched into one master video
- stitched masters default to narration-first audio; clip audio can be added back only if needed
- background music can be looped and automatically ducked under narration
- subtitle sidecars can be exported from narration timing, embedded as soft tracks, or burned into frames
- burned subtitles support presets: `storybook`, `large`, `minimal`, `high-contrast`
- burned subtitle layouts support `widescreen`, `vertical`, and `auto`
- burned subtitle presets auto-scale font size, outline, and bottom margin to the output resolution
- this avoids unstable lip-sync and keeps children’s-story pacing under tighter control
