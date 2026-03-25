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

To upload to YouTube, also enable the YouTube Data API v3 in Google Cloud, create an OAuth desktop client, and point `YOUTUBE_CLIENT_SECRETS_FILE` at the downloaded JSON file. The CLI stores the reusable OAuth token in `YOUTUBE_TOKEN_FILE` or defaults to `~/.multiversal-pictures/youtube-token.json`.

Recommended quality-first defaults:

```bash
OPENAI_AGENT_MODEL=gpt-5.4
OPENAI_AGENT_REASONING_EFFORT=medium
OPENAI_VIDEO_MODEL=sora-2-pro
OPENAI_IMAGE_MODEL=gpt-image-1.5
OPENAI_IMAGE_QUALITY=high
OPENAI_TTS_MODEL=tts-1-hd
STORYBOOK_QA_MODEL=gpt-5.4
STORYBOOK_QA_THRESHOLD=0.78
STORYBOOK_QA_BEST_OF=2
STORYBOOK_PRODUCTION_MODE=balanced
STORYBOOK_REVIEW_MODE=score_only
STORYBOOK_SUBTITLE_POSITION=bottom_raised
```

Weekly flagship Shorts overrides:

```bash
STORYBOOK_REVIEW_MODE=repair
STORYBOOK_QA_THRESHOLD=0.84
STORYBOOK_QA_BEST_OF=2
```

## Agent Workflow

- `generate-shotlist`: story prompt -> story brief -> shotlist JSON
- `export-narration`: shotlist JSON -> narration script
- `synthesize-narration`: shotlist JSON -> narration audio track
- `export-subtitles`: shotlist or narration timing -> SRT/VTT/JSON subtitles
- `generate-anchors`: shotlist JSON -> anchor images + derived shotlist with `input_reference`
- `render-shotlist`: shotlist JSON -> rendered video clips
- `review-shots`: render run -> score-only review or repair review + selected winner
- `produce`: prompt file or shotlist -> narration-led storybook master video
- `upload-youtube`: stitched video or run directory -> YouTube upload manifest
- `create-character`: reference video -> reusable character ID

Output presets: `storybook-landscape`, `storybook-vertical`, `storybook-short`, `storybook-short-vertical`, `storybook-pro-landscape`, `storybook-pro-vertical`
When a preset is selected, it overrides the project-level default `size`, `seconds`, framing guidance, and subtitle defaults. Vertical presets now default to raised-bottom subtitles.

Architecture notes: `/Users/yongjip/Projects/potato-king/docs/agent-workflow.md:1`
Topic research playbook: `/Users/yongjip/Projects/potato-king/docs/topic-research-playbook.md:1`
High-quality Shorts workflow: `/Users/yongjip/Projects/potato-king/docs/high-quality-short-form-workflow.md:1`
Short-form review checklist: `/Users/yongjip/Projects/potato-king/docs/short-form-review-checklist.md:1`
Engineer + AI production guide: `/Users/yongjip/Projects/potato-king/docs/engineer-with-ai-best-practices.md:1`
Shorts package template: `/Users/yongjip/Projects/potato-king/examples/high_quality_shorts_package_template.md:1`
Shorts prompt template: `/Users/yongjip/Projects/potato-king/examples/high_quality_shorts_prompt_template.txt:1`
Hybrid proof shotlist example: `/Users/yongjip/Projects/potato-king/examples/hybrid_proof_short_shotlist.json:1`

## Weekly Flagship Shorts

Recommended operating loop:

1. fill out `/Users/yongjip/Projects/potato-king/examples/high_quality_shorts_package_template.md`
2. write the approved production prompt using `/Users/yongjip/Projects/potato-king/examples/high_quality_shorts_prompt_template.txt`
3. generate anchors for human/workspace shots
4. pilot the riskiest shot with `render-shotlist --only`
5. compare `alloy` and `nova` narration before the final master pass

Hybrid note: real proof clips and exact UI overlays are still assembled after the selected run. Use the pipeline for AI plates, narration, subtitles, and review, then finish precision proof beats in the final edit.

Example pilot render:

```bash
multiversal-pictures render-shotlist \
  --shotlist /Users/yongjip/Projects/potato-king/examples/hybrid_proof_short_shotlist.json \
  --output /Users/yongjip/Projects/potato-king/runs/hybrid_short_pilot \
  --output-preset storybook-pro-vertical \
  --only proof-overlay-plate
```

Example master-quality pass:

```bash
multiversal-pictures produce \
  --shotlist /Users/yongjip/Projects/potato-king/examples/hybrid_proof_short_shotlist.json \
  --output-preset storybook-pro-vertical \
  --production-mode master \
  --with-anchors \
  --with-review \
  --review-mode repair \
  --review-threshold 0.84 \
  --review-best-of 2 \
  --burn-subtitles \
  --narration-voice alloy \
  --output /Users/yongjip/Projects/potato-king/runs/hybrid_short_master
```

## Run

```bash
multiversal-pictures generate-shotlist \
  --prompt-file /Users/yongjip/Projects/potato-king/examples/panda_story_prompt.txt \
  --output-preset storybook-vertical \
  --output /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json
```

```bash
multiversal-pictures produce \
  --prompt-file /Users/yongjip/Projects/potato-king/examples/panda_story_prompt.txt \
  --output-preset storybook-vertical \
  --production-mode balanced \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story_vertical
```

```bash
multiversal-pictures generate-anchors \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --output-dir /Users/yongjip/Projects/potato-king/runs/panda_story_vertical/anchors \
  --output-shotlist /Users/yongjip/Projects/potato-king/runs/panda_story_vertical/anchored-shotlist.json
```

```bash
multiversal-pictures produce \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --output-preset storybook-vertical \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story_vertical
```

```bash
multiversal-pictures produce \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --output-preset storybook-pro-vertical \
  --production-mode master \
  --with-review \
  --review-mode repair \
  --review-best-of 2 \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story_pro_vertical
```

```bash
multiversal-pictures review-shots \
  --run-dir /Users/yongjip/Projects/potato-king/runs/panda_story_pro_vertical \
  --mode repair \
  --best-of 2 \
  --threshold 0.78
```

```bash
multiversal-pictures produce \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --output-preset storybook-vertical \
  --production-mode balanced \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story_vertical \
  --stop-after render
```

```bash
multiversal-pictures produce \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --output-preset storybook-vertical \
  --production-mode balanced \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story_vertical \
  --resume
```

```bash
multiversal-pictures produce \
  --shotlist /Users/yongjip/Projects/potato-king/examples/panda_story_generated.json \
  --output-preset storybook-vertical \
  --output /Users/yongjip/Projects/potato-king/runs/panda_story_vertical \
  --upload-youtube \
  --youtube-title "Pobi Bamboo Breakfast" \
  --youtube-description "A short storybook video made with Multiversal Pictures." \
  --youtube-tags panda,storybook,kids \
  --youtube-privacy-status private
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
  --output-preset storybook-vertical \
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

```bash
multiversal-pictures upload-youtube \
  --run-dir /Users/yongjip/Projects/potato-king/runs/panda_story_vertical \
  --title "Pobi Bamboo Breakfast" \
  --description "A short storybook video made with Multiversal Pictures." \
  --tags panda,storybook,kids \
  --privacy-status private
```

## Positioning

`Multiversal Pictures` is optimized for narration-led storybook videos.

- clips are generated as expressive visuals, not dialogue performances
- narration is planned per shot and exported for TTS or human voiceover
- shots can render concurrently and then be stitched into one master video
- the production wrapper can overlap narration synthesis with shot rendering and stitch the master automatically
- stitched masters default to narration-first audio; clip audio can be added back only if needed
- background music can be looped and automatically ducked under narration
- subtitle sidecars can be exported from narration timing, embedded as soft tracks, or burned into frames
- burned subtitles support presets: `storybook`, `large`, `minimal`, `high-contrast`
- burned subtitle layouts support `widescreen`, `vertical`, and `auto`
- burned subtitle presets auto-scale font size, outline, side margins, and bottom margin to the output resolution
- output presets bundle render size, clip duration, framing guidance, and subtitle defaults for landscape vs 9:16 delivery
- vertical-first production defaults now favor `balanced` runs with concurrency `2`, anchor reuse on resume, score-only review by default, and a raised-bottom subtitle band
- quality-first runs can create anchor frames first, feed them into Sora as `input_reference`, then review thumbnail/spritesheet assets before stitching
- review manifests now keep `candidates[]`, `selected_candidate`, `review`, and `recommended_action` so stitching only uses the selected winner
- final stitched videos can be uploaded to YouTube with stored OAuth credentials and a reusable upload manifest
- this avoids unstable lip-sync and keeps children’s-story pacing under tighter control

source .venv/bin/activate

multiversal-pictures upload-youtube \
  --video /Users/yongjip/Projects/potato-king/runs/engineer_with_ai_1min_final/story.mp4 \
  --title "Test Upload" \
  --description "Test upload from multiversal-pictures" \
  --privacy-status private
