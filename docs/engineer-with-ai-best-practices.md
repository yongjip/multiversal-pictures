# Engineer With AI Best Practices

This document is a focused production guide for one specific content category:

- engineer + AI
- coding with AI
- AI workflow for developers
- "AI will/won't replace engineers" style Shorts and explainers

The goal is not to make the most technically accurate possible video.

The goal is to make a video that:

- looks coherent under current text-to-video constraints
- sounds credible with AI narration
- preserves one strong idea
- can be produced reliably with the `multiversal-pictures` pipeline

Use this guide when the topic is software engineering, coding workflows, AI tools for developers, or career claims about engineers and AI.

## Core Finding

The weakest version of this category is:

- one fully AI-generated realistic engineer
- readable code on screen
- typing close-ups
- dense paragraph narration
- a generic "AI changes everything" thesis

That combination fails because it stacks the current failure modes of both video generation and TTS:

- unreadable or unstable UI text
- weak finger and keyboard interaction
- unrealistic screen behavior
- flat or overlong narration
- too many ideas in one short video

The strongest version of this category is:

- one clear thesis
- short shots
- narration-led structure
- abstract or cinematic supporting visuals
- real screen capture for precise UI if needed
- references and anchors for any generated human scene

## Best-Practice Rules

### 1. Do not ask the video model to fake readable code

If the viewer needs to read code, terminal output, logs, or UI labels, use:

- real screen recording
- static screenshots
- designed overlays added in post

Do not rely on generated video for:

- code editors
- terminal sessions
- commit diffs
- dashboards with small text
- browser UIs with multiple panes

Generated video should carry mood, movement, and metaphor, not exact interface detail.

### 2. Use AI video for atmosphere, not proof

In this topic, AI video works best for:

- a reflective engineer in a workspace
- abstract system diagrams in space
- modular blocks assembling into a structure
- flowing cables, windows, or luminous graphs
- a "problem becoming simpler" visual metaphor

It works poorly for:

- tight keyboard close-ups
- mouse cursor precision
- rapid screen interaction
- realistic spoken dialogue on camera
- multi-character office scenes

### 3. Keep one video to one claim

Good examples:

- engineers who use AI well move faster on the blank page
- AI does not replace engineering judgment
- "vibe coding" is not the same as engineering with AI

Bad examples:

- AI changes jobs
- AI changes coding
- AI changes startups
- AI changes product design
- AI changes education

Choose one claim and make every shot support it.

### 4. Write for speech, not for reading

Most weak narration comes from scripts written like essays.

Narration should be:

- short
- concrete
- spoken in one breath
- one idea per line

Recommended constraints:

- 6 to 14 words per line
- 1 sentence per beat
- 5 to 7 lines for a 25 to 40 second Short

Weak:

`Software engineering is undergoing a profound transformation because developers are increasingly incorporating AI systems into their daily workflow.`

Better:

`AI does not remove engineering.`  
`It removes waiting.`  
`The blank page disappears first.`  
`Then the busywork.`  
`Judgment still matters.`  
`Maybe more than ever.`

### 5. Prefer English for OpenAI TTS unless there is a strong reason not to

Current OpenAI TTS voices are optimized for English.

If the content is aimed at a broad audience and the voice quality matters more than local-language nuance:

- write the script in English
- test `cedar`
- test `marin`
- keep the tone controlled and direct

If the content must be in Korean:

- shorten lines even further
- avoid slang
- avoid dense technical phrasing
- expect more manual iteration on pronunciation and pacing

### 6. Direction matters more than voice choice

Do not change the voice first.

Change the instructions first.

Use instructions that control:

- pace
- confidence
- warmth
- emphasis
- restraint

Recommended narration direction for this topic:

- calm
- intelligent
- understated
- not salesy
- not overly excited
- slight tension in the first line

Example instruction:

`Speak like a thoughtful senior engineer explaining a hard truth. Keep the pace measured, the tone calm, and the emphasis subtle. Avoid sounding like an ad.`

### 7. Keep human shots medium or wide

For generated human scenes:

- prefer medium shot
- prefer wide shot
- prefer profile or over-shoulder

Avoid:

- close-up hands
- close-up typing
- talking-head lip-sync
- intricate hand-object interaction

If the character must touch something, keep it broad and slow:

- placing a notebook on a desk
- looking up at a diagram
- sliding one large panel

### 8. Use 4 to 5 second shots as the default

For this category, shorter is safer.

Recommended timing:

- 4 to 5 seconds per shot
- 5 to 7 shots total
- 25 to 35 seconds total runtime for Shorts

Use extension only if a shot already works.

Do not start with long shots.

### 9. Use anchors or storyboards for every generated shot with a human

When a generated shot includes:

- a person
- a monitor
- a workspace
- a repeated outfit or environment

use anchor images or storyboard references first.

This is not optional if you want consistency.

Recommended process:

1. generate storyboard keyframes
2. review composition and wardrobe
3. inject `input_reference`
4. render the shot

### 10. Build a hybrid workflow by default

The most reliable format for "engineer with AI" is hybrid:

- real screen capture for proof
- AI video for cinematic support
- TTS or human narration for the throughline
- subtitles and timing done after narration is locked

Do not force fully synthetic production unless the video is deliberately abstract.

## Reference Pack

These references are useful because they show structures and angles that can be adapted without copying scripts or visuals directly.

### Long-form references

- [How I Actually Code with AI as a Senior Software Engineer](https://www.youtube.com/watch?v=Qe64DwfiRBY)
  - practical workflow framing
  - useful for realism and credibility
- [Stop "Vibe Coding": An Engineering Approach to AI](https://www.youtube.com/watch?v=sGscFMQDGSg)
  - strong thesis
  - useful for contrast-driven messaging
- [How AI will change software engineering – with Martin Fowler](https://www.youtube.com/watch?v=CQmI4XKTa0U)
  - serious authority framing
  - useful for long-term positioning
- [Everything You Need to Know About Coding with AI // NOT vibe coding](https://www.youtube.com/watch?v=5fhcklZe-qE)
  - broad packaging
  - useful for title and audience fit
- [How I use Claude Code (Meta Staff Engineer Tips)](https://www.youtube.com/watch?v=mZzhfPle9QU)
  - concrete workflow language
  - useful for tool-era vocabulary

### Short-form references

- [탑티어 대기업 AI개발자가 일하는 법 #shorts](https://www.youtube.com/shorts/RLgBZGNc-gc)
  - authority and compression
- [I asked Cursor to fix a "small bug" | Coding with AI #shorts](https://www.youtube.com/shorts/riflxxpE-Cg)
  - relatable hook and fast setup
- [Will AI REPLACE Software Engineers?? #shorts](https://www.youtube.com/shorts/7FkF2_1BipY)
  - broad audience hook pattern
- [Will AI Replace Software Engineers? The Future Awaits!](https://www.youtube.com/shorts/LV-Uu7GvpUo)
  - simple clickable framing
- [AI User vs AI Engineer: The BIGGEST Difference Revealed! #shorts](https://www.youtube.com/shorts/gNV_bsQQmSk)
  - contrast hook structure

## Patterns Worth Reusing

Across the reference set, the strongest repeatable patterns are:

- a tension hook in the first second
- one claim, not a panel discussion compressed into 30 seconds
- strong contrast framing
- workflow specificity over vague futurism
- a calm, credible tone instead of hype

The best reusable formulas are:

- `X with AI beats Y without it`
- `This is not AI replacing engineers`
- `This is what engineers actually use AI for`
- `The mistake is not using AI like a system`

## Recommended Angles for This Pipeline

These are the best-fit original angles for `multiversal-pictures`.

### Angle 1: Engineers do not use AI to type faster

Core claim:

`The biggest gain from AI is not typing speed. It is getting past the blank page and removing low-value friction.`

Why it fits:

- easy to visualize abstractly
- does not require fake UI detail
- works with calm narration

### Angle 2: Vibe coding is not engineering with AI

Core claim:

`Real engineering with AI is not random prompting. It is structured judgment with faster iteration.`

Why it fits:

- strong tension
- easy contrast structure
- credible with developer audience

### Angle 3: The best engineers with AI think bigger, not less

Core claim:

`AI removes the busywork, so the real differentiator becomes system judgment, taste, and decision quality.`

Why it fits:

- more timeless
- less tool-dependent
- easier to make cinematic

## Recommended Production Formula for Shorts

Use this structure for most 25 to 35 second videos in this category.

### Shot formula

1. Hook shot
   - visual tension
   - one sharp first line
2. Clarifying shot
   - what people usually think
3. Reframe shot
   - what is actually true
4. Support shot
   - one concrete example or metaphor
5. Conclusion shot
   - stronger version of the claim
6. Final beat
   - memorable closing line

### Visual formula

- 2 to 3 generated cinematic shots
- 1 to 2 abstract diagram/metaphor shots
- optional real screen capture insert
- no more than one realistic monitor-focused shot unless it is real footage

### Narration formula

- line 1: tension
- line 2: misconception
- line 3: reframe
- line 4: consequence
- line 5: stronger conclusion

## Shot Review Checklist

Reject or rerender a shot if any of these happen:

- code or UI text becomes important but unreadable
- fingers or typing draw attention
- the face drifts between shots
- the workspace layout changes too much
- there are multiple focal points
- the motion is too busy for narration to land
- the shot says nothing new

Keep or refine a shot when:

- the composition is simple
- the movement is slow and legible
- the human figure is believable at medium distance
- the mood supports the line cleanly
- the shot communicates one idea in under two seconds

## Narration Review Checklist

Reject or rewrite narration if:

- a sentence has two ideas
- it sounds like blog prose
- it depends on jargon
- it needs on-screen text to make sense
- the energy sounds like an ad

Keep narration when:

- the meaning is obvious on first listen
- the sentence can be spoken cleanly in one breath
- one stressed phrase carries the beat
- it sounds like a person talking, not a LinkedIn post

## House Style for This Topic

Use this default style unless a specific campaign says otherwise.

- language: English-first
- tone: calm, sharp, credible
- visual style: cinematic, clean, minimal, intelligent
- character count: one engineer
- environment count: one workspace, one abstract system space
- subtitle burden: low
- screen text burden: near zero
- audio energy: moderate, not trailer-like

## Starter Prompt Guidance

When writing prompts for this topic:

- describe environment, posture, composition, and mood
- avoid asking for exact code on screen
- avoid "typing furiously"
- avoid "talking directly to camera"
- prefer "studying a floating architecture diagram"
- prefer "watching modular blocks assemble into a system"

Weak prompt direction:

`A genius software engineer rapidly typing code into a complex terminal while AI writes perfect code on multiple monitors.`

Better prompt direction:

`A thoughtful software engineer in a quiet workspace, viewed from a medium over-shoulder angle, watching a clean luminous system diagram assemble in the air above the desk. Minimal monitor detail, calm movement, cinematic lighting, intelligent atmosphere.`

## Recommended Next Move

For the next attempt, do not remake the previous concept with minor edits.

Pick one of these two paths:

1. **Hybrid proof video**
   - real screen recording
   - AI b-roll
   - practical narration

2. **Abstract cinematic explainer**
   - no readable UI
   - no typing close-ups
   - one engineer, one thesis, one metaphor chain

If quality is the priority, path 1 is safer.

If brand tone is the priority, path 2 is cleaner.

## External Signals Behind These Rules

These rules are not arbitrary. They are aligned with a mix of:

- official OpenAI guidance
- official YouTube guidance
- current creator patterns in the reference pack above

Useful references:

- OpenAI TTS guide: voices, instructions, and the note that voices are currently optimized for English  
  [https://platform.openai.com/docs/guides/text-to-speech](https://platform.openai.com/docs/guides/text-to-speech)
- OpenAI Sora app help: shorter, simpler shots and iterative prompting when outputs break  
  [https://help.openai.com/en/articles/12456897-getting-started-with-the-sora-app](https://help.openai.com/en/articles/12456897-getting-started-with-the-sora-app)
- OpenAI Sora limitations: character and realism imperfections still exist  
  [https://help.openai.com/en/articles/12460853](https://help.openai.com/en/articles/12460853)
- OpenAI Sora 2 prompting guide: reference-first prompting and tighter shot control  
  [https://cookbook.openai.com/examples/sora/sora2_prompting_guide/](https://cookbook.openai.com/examples/sora/sora2_prompting_guide/)
- YouTube Shorts deep dive: the hook matters immediately, and Shorts work as compact "bits" rather than overloaded mini-essays  
  [https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/](https://blog.youtube/creator-and-artist-stories/youtube-shorts-deep-dive/)
- YouTube AI disclosure policy: synthetic media that could be mistaken for reality may require disclosure  
  [https://blog.youtube/news-and-events/disclosing-ai-generated-content/](https://blog.youtube/news-and-events/disclosing-ai-generated-content/)
