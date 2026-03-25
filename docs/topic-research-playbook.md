# Topic Research Playbook

This document is a reusable instruction set for future agents that need to go from **topic selection -> packaging -> production handoff -> publishing handoff**.

For topic-specific production guidance after the angle is chosen, use the companion guide at `/Users/yongjip/Projects/potato-king/docs/engineer-with-ai-best-practices.md:1` when the topic is developers, coding workflows, or engineers using AI.

The target outcome is not just a correct topic. The target outcome is a topic that:

- has a strong reason to be clicked
- can be defended with current evidence
- can be explained clearly in English to a broad audience
- can be turned into a short video without visual confusion

## Core Principle

Do not optimize for "what is interesting to insiders."

Optimize for **what creates instant tension for a broad audience**:

- status loss
- job risk
- performance gap
- leverage asymmetry
- hidden rule change
- future advantage

Use the public figure or company name as **supporting proof**, not automatically as the main hook.

Example:

- weaker: `Jensen Huang says engineers need AI`
- stronger: `A mediocre engineer with AI can beat a genius without it`

The name `Jensen Huang` can still appear in the first 3-10 seconds, the subtitle, the description, and the evidence section.

## Hard Rules

1. **Verify recency with exact dates**
   - When the topic depends on a recent interview, keynote, earnings call, or podcast, verify the latest relevant source and record the exact date.
   - Do not say "recently" when the date matters. Write the date.

2. **Prefer primary sources first**
   - Best: full interview video, transcript, official keynote, official blog, official event page.
   - Acceptable: reputable coverage that clearly links to the underlying interview.
   - Weak: reposts, social fragments, unsourced summaries.

3. **Separate quote, paraphrase, and inference**
   - Mark direct quote vs paraphrase vs your own conclusion.
   - Never scale a number proportionally unless you explicitly label it as an inference.
   - Example: if a speaker says `$500K engineer -> $250K tokens`, do not present `$800K -> $400K` as a quote.

4. **Avoid niche terminology in the title if a broader phrasing exists**
   - Prefer `AI leverage`, `job risk`, `100 AI agents`, `falling behind`.
   - Avoid leading with terms like `token budget` unless the audience is already specialized.

5. **One video = one core claim**
   - Pick one dominant idea.
   - Supporting facts should strengthen the same argument, not open three different threads.

6. **The hook must survive without the speaker's name**
   - If the title only works because a celebrity said it, the angle is weak.
   - The claim itself should create curiosity or tension.

7. **Broad audience first means English-first packaging**
   - Draft titles, thumbnail text, hooks, and script in English unless the target audience is explicitly local-language.

## Topic Selection Workflow

### Step 1: Collect raw material

Build a source set from the last 30-90 days:

- interviews
- podcasts
- keynotes
- earnings calls
- conference appearances
- official blog summaries

For each source, record:

- speaker
- source title
- source URL
- event date
- publication date
- strongest provocative claim

### Step 2: Extract provocative claims

Look for claims with built-in tension:

- "If you do not do X, you fall behind"
- "The old way is dead"
- "One person will control much more leverage than before"
- "A weaker actor using AI beats a stronger actor without AI"
- "The unit of competition has changed"

Ignore claims that are merely descriptive unless they can be reframed into consequence.

### Step 3: Convert insider claims into mass-audience claims

Translate from:

- insider wording
- company framing
- technical metrics

Into:

- career consequence
- power shift
- winner vs loser framing
- fear of replacement
- fear of irrelevance
- asymmetry in output

Examples:

- insider: `engineers should use more AI tokens`
- broad: `high-paid engineers who barely use AI are already behind`

- insider: `every engineer will have 100 agents`
- broad: `the next engineer will not work alone`

### Step 4: Score each angle

Score 1-5 on each dimension:

- **Click tension**: does it trigger curiosity, fear, rivalry, or surprise?
- **Broad clarity**: does a non-specialist understand the point immediately?
- **Source strength**: is it backed by a direct or highly reliable source?
- **Visualizability**: can this be shown in 4-6 short shots?
- **Defensibility**: can the script survive scrutiny without exaggeration?
- **Novelty**: does it feel timely or newly urgent?

Pick the angle with the highest total, but reject it if source strength or defensibility is weak.

### Step 5: Decide whether to use the person's name

Use the person's name in the title only if at least one is true:

- the name itself materially increases click-through
- the claim is unusually tied to that person's authority
- search demand is an important part of discovery

Otherwise:

- make the title about the claim
- use the name in the subtitle, opening line, description, and source card

## Packaging Rules

### Title Rules

Titles should usually be built from:

- conflict
- consequence
- status reversal
- hidden rule change

Strong patterns:

- `X with AI beats Y without it`
- `If you are not doing X, you are already behind`
- `The next [profession] will not work alone`
- `The old [status advantage] no longer matters`

Avoid:

- bland authority-led titles
- overly technical nouns in the first 5 words
- titles that require prior knowledge of a conference or interview

### Thumbnail Rules

Thumbnail text should be 2-4 words and emotionally sharper than the title.

Good examples:

- `GENIUS LOSES`
- `100 AI AGENTS`
- `YOU'RE BEHIND`
- `MEDIOCRE WINS`

### Hook Rules

The first line should make the viewer feel the rule changed against them.

Good patterns:

- `The smartest engineer in the room may no longer win.`
- `A mediocre engineer with AI can now outperform a genius without it.`
- `The next top performer may just be the person using AI best.`

### Evidence Rules

The first proof point should arrive early:

- name the person
- give the date
- state the claim
- distinguish quote vs paraphrase

Example structure:

- `In a March 2026 interview, NVIDIA CEO Jensen Huang argued that engineers who barely use AI are already at a disadvantage.`

## Required Output Contract for Future Agents

Every topic-selection pass should return these sections:

### 1. Research Brief

- chosen topic
- core claim
- why it is clickable
- why it is defensible
- target audience
- target language

### 2. Source Table

For each source:

- speaker
- title
- URL
- event date
- publication date
- direct quote or paraphrase
- relevance to chosen topic

### 3. Shortlist

At least 3 candidate angles with:

- title
- hook
- audience fit
- risk of overclaiming
- score

### 4. Chosen Packaging

- final title options
- thumbnail text options
- one-sentence hook
- 30-60 second script
- claim/evidence map

### 5. Production Handoff

- English story prompt
- shot structure
- key visuals
- safe-area guidance
- narration tone

### 6. Distribution Handoff

- YouTube title
- short description
- tags
- pinned comment angle
- optional A/B title variants

## Reusable Agent Instruction

Copy this block into future research agents:

> You are the Topic Research and Packaging Agent for a short-form video pipeline.  
> Your job is to find a topic that is both clickable and defensible, then package it for production in English.  
> Prefer current interviews, keynotes, transcripts, and official sources.  
> Record exact dates. Distinguish direct quotes, paraphrases, and inferences.  
> Do not optimize for insider interest; optimize for broad-audience tension such as job risk, status loss, leverage asymmetry, or hidden rule changes.  
> The title should usually be about the claim, not just the speaker's name.  
> Pick one dominant claim per video.  
> Return: source table, 3+ angle options, chosen angle, title options, thumbnail text, short script, and production handoff.  
> Reject weak topics even if the speaker is famous.

## Worked Example: Jensen Huang / AI-First Engineering

### Raw findings

- Jensen Huang argued that engineers who barely use AI are in a dangerous position.
- He described a future where each engineer may work with many AI agents.
- He framed non-use of AI as operating with a severe performance disadvantage.

### Weak angle

- `Jensen Huang says engineers should use AI`

Why it is weak:

- too generic
- too authority-dependent
- low tension

### Stronger angle

- `A mediocre engineer with AI can beat a genius without it`

Why it is stronger:

- immediate conflict
- broad audience understands it
- emotionally provocative
- the public figure can still validate the claim inside the video

### Safe evidence handling

- State the exact direct example if it exists.
- Do not invent a larger numeric example unless labeled as inference.
- If a line is a paraphrase, mark it as a paraphrase in notes.

## Handoff Into This Repository

Once the topic is chosen:

1. write an English story prompt built around one core claim
2. generate the shotlist
3. prefer `--with-anchors` for composition lock
4. prefer `--with-review` for best-of selection
5. stitch and review the final cut
6. prepare YouTube metadata from the chosen packaging

Suggested production path:

```bash
multiversal-pictures generate-shotlist --prompt-file <prompt.txt> --output <shotlist.json>
multiversal-pictures produce --shotlist <shotlist.json> --output <run_dir> --with-anchors --with-review
multiversal-pictures upload-youtube --run-dir <run_dir> --title "<title>"
```
