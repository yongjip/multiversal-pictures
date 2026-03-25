# High-Quality Short-Form Workflow

This guide defines the default operating loop for **one flagship Short per week**.

Use it when the goal is:

- broad English-language reach
- strong packaging before production
- hybrid proof-based storytelling
- higher consistency than a pure one-pass AI workflow

Pair this guide with:

- `/Users/yongjip/Projects/potato-king/docs/topic-research-playbook.md:1`
- `/Users/yongjip/Projects/potato-king/examples/high_quality_shorts_package_template.md:1`
- `/Users/yongjip/Projects/potato-king/examples/high_quality_shorts_prompt_template.txt:1`
- `/Users/yongjip/Projects/potato-king/examples/hybrid_proof_short_shotlist.json:1`
- `/Users/yongjip/Projects/potato-king/docs/short-form-review-checklist.md:1`

## Defaults

- runtime: 25 to 35 seconds
- format: 9:16 vertical
- audience: broad English-speaking viewers
- structure: one core claim, one early proof point, 5 to 7 beats
- production style: hybrid proof-based
- publication cadence: one flagship Short per week

## Core Rule

Do not ask one system to do everything.

Use:

- topic research and packaging for the argument
- AI video for atmosphere, metaphor, and stylized plates
- real screen captures or designed overlays when exact proof is required
- review loops before final stitch

Avoid building a Short that depends on more than one of these:

- readable generated UI
- lip-synced dialogue
- close-up typing or hand precision
- dense technical explanation
- multi-character realism

## Workflow

### 1. Lock the package before production

Fill out `/Users/yongjip/Projects/potato-king/examples/high_quality_shorts_package_template.md:1`.

Do not proceed until you have:

- 3 candidate angles scored across the standard rubric
- one chosen title direction
- one chosen hook
- a claim/evidence map
- a 25 to 35 second script with 5 to 7 lines

### 2. Mark proof beats early

Before shot planning, label each beat as one of:

- `AI plate`: fully generated
- `overlay plate`: generated background with space reserved for a real overlay
- `manual proof`: real screen capture or external edit element

Important:

- `multiversal-pictures` v1 does **not** ingest real proof clips directly into the shot pipeline
- real proof clips and exact UI overlays are assembled after the selected run, in the final edit

### 3. Generate the production prompt

Start from `/Users/yongjip/Projects/potato-king/examples/high_quality_shorts_prompt_template.txt:1`.

The prompt should already include:

- the chosen core claim
- the exact source/date for any timely proof
- the narration structure
- visual constraints
- proof-beat notes

### 4. Generate the shot list

Recommended command:

```bash
multiversal-pictures generate-shotlist \
  --prompt-file /Users/yongjip/Projects/potato-king/examples/high_quality_shorts_prompt_template.txt \
  --output-preset storybook-pro-vertical \
  --audience "broad English-speaking audience" \
  --language en \
  --style "premium vertical short-form explainer, cinematic but restrained, no readable generated UI text" \
  --shots 6 \
  --output /Users/yongjip/Projects/potato-king/runs/high_quality_short/shotlist.json
```

### 5. Generate anchors for human/workspace shots

Use anchors for any shot with:

- a person
- a workspace
- a monitor
- a recurring outfit or environment

Recommended command:

```bash
multiversal-pictures generate-anchors \
  --shotlist /Users/yongjip/Projects/potato-king/examples/hybrid_proof_short_shotlist.json \
  --output-dir /Users/yongjip/Projects/potato-king/runs/hybrid_short/anchors \
  --output-shotlist /Users/yongjip/Projects/potato-king/runs/hybrid_short/anchored-shotlist.json
```

### 6. Pilot the riskiest shot first

Use `render-shotlist --only` for the shot most likely to fail:

- proof plate composition
- human continuity
- complex camera movement
- anatomy-heavy action

Example:

```bash
multiversal-pictures render-shotlist \
  --shotlist /Users/yongjip/Projects/potato-king/examples/hybrid_proof_short_shotlist.json \
  --output /Users/yongjip/Projects/potato-king/runs/hybrid_short_pilot \
  --output-preset storybook-pro-vertical \
  --only proof-overlay-plate \
  --jobs 1
```

Do not run the full batch until the pilot shot is compositionally correct.

### 7. Compare narration voices before the final pass

Generate narration for both `alloy` and `nova`, then keep the clearer take.

```bash
multiversal-pictures synthesize-narration \
  --shotlist /Users/yongjip/Projects/potato-king/examples/hybrid_proof_short_shotlist.json \
  --output-dir /Users/yongjip/Projects/potato-king/runs/hybrid_short_alloy/narration \
  --voice alloy
```

```bash
multiversal-pictures synthesize-narration \
  --shotlist /Users/yongjip/Projects/potato-king/examples/hybrid_proof_short_shotlist.json \
  --output-dir /Users/yongjip/Projects/potato-king/runs/hybrid_short_nova/narration \
  --voice nova
```

Choose the take that is:

- clearer on first listen
- less ad-like
- more controlled in emphasis
- better matched to the hook

### 8. Run the final master pass

Use `balanced` while iterating. Use `master` only for the approved final run.

Recommended final command:

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

### 9. Assemble hybrid proof beats in the final edit

After the selected run is approved:

- replace designated proof beats with real screen captures when needed
- add designed overlays where the shot list reserved clean space
- keep the final subtitle-safe band clear

### 10. Upload privately first

Use `private` uploads as the default.

Example:

```bash
multiversal-pictures upload-youtube \
  --run-dir /Users/yongjip/Projects/potato-king/runs/hybrid_short_master \
  --title "Your Final Short Title" \
  --description "Short-form explainer created with Multiversal Pictures." \
  --privacy-status private
```

Review the result in YouTube Studio before switching to `public`.

## Acceptance Bar

A Short is ready only if:

- the hook reads clearly in 1 to 2 seconds
- every shot supports the same claim
- there is no readable generated UI, code, or metric text
- narration is understandable on first listen
- review scores meet or exceed `0.84`
- subtitles are burned cleanly and remain mobile-readable
- the final export still works with sound off
