# Kaggle "Gemma 4 Good" Submission Research

**Date:** 2026-05-01 — **Deadline:** 2026-05-18 23:59 UTC (T-17 days)
**Sources:** `HACKATHON.md`, Kaggle competition page (JS-rendered, partial), Gemma 3n Impact Challenge winners blog (Google), Google Tunix Hackathon submission template (current Kaggle/Google hackathon, same template family).

## 1. Required Artifacts Checklist

Confirmed from `HACKATHON.md` (4 mandatory components) and Tunix-template parallels. Every submission ships **all** of:

- [ ] **Public Kaggle Writeup** — title + subtitle + body, **≤1,500 words** (Tunix template). Markdown on Kaggle, not a PDF. Sections: Problem, Users, Gemma 4 usage (which features, why), Architecture, Demo, Results, Limitations, Future work.
- [ ] **Public Kaggle Notebook** — runnable, links to data/models. Embedded inline in writeup or linked.
- [ ] **Public code repository** — GitHub, MIT/Apache-2.0, README with one-command setup, demo GIF.
- [ ] **Video demo** — **≤3 minutes**, hosted on **YouTube** (public/unlisted), embedded in writeup. Show pain point in first 30s.
- [ ] **Cover image** — Kaggle Media Gallery, ~1200×800, brand-clean (no coaching watermarks per our source-hygiene rule).
- [ ] **Hosted demo URL** — not strictly required but every Gemma 3n top-3 had one (mobile/web). Strongly recommended.

## 2. Judging Rubric (from HACKATHON.md, cross-cited from EvoArt blog)

| Criterion | Weight | What it means for Gemma Tutor |
|---|---|---|
| Innovation | 30% | Novel use of Gemma 4 — multimodal, function calling, on-device. NOT a chatbot wrapper. |
| Impact Potential | 30% | Concrete user (Rajasthan RAS aspirant), measurable scale, deployable today. |
| Technical Execution | 25% | Working PageIndex retrieval, FSRS spaced repetition, glossary-injected Hindi. |
| Accessibility | 15% | Offline Ollama, Hindi-first, low-bandwidth. This is our home turf — over-index on it. |

Human-judged panel. **No leaderboard, no auto-scoring.** Tiebreaker is the video.

## 3. Patterns from Gemma 3n Impact Challenge Top-3 (closest analog, 600+ submissions)

1. **Gemma Vision (1st):** Accessibility for visually impaired. Wearable + voice. Won **Google AI Edge tech prize** too.
2. **Vite Vere Offline (2nd):** Cognitive disability support. Cloud → fully offline port via Gemma 3n.
3. **3VA (3rd):** Pictogram→speech AAC for non-verbal users. **Fine-tuned** Gemma 3n.

**Common winning DNA:**
- Underserved population, named not theoretical.
- **Offline-first** is the moat (matches our 15% Accessibility lever).
- Fine-tuning or domain adaptation appears in most top finishers (also unlocks $10K Unsloth prize).
- Sub-3-min video opens with the user's pain, not the architecture.
- Hosted/installable demo, not just a notebook.

## 4. DECISION — what we ship

Given Gemma Tutor (RAS aspirants, English-canonical KB + Hindi output, PageIndex + FSRS):

- **Writeup (1,400 words):** lead with one named aspirant persona ("Pooja, BA-Hindi, Sikar district, no coaching budget"). Then Gemma 4 features used (E4B + E2B retrieval traversal, function calling for MCQs, multimodal for diagram pages). Architecture diagram. Results: retrieval recall@5, glossary-injection eval, FSRS retention curve.
- **Kaggle Notebook:** end-to-end demo — load NCERT JSON → PageIndex query → Gemma E4B answer in Hindi → MCQ tool-call → FSRS schedule. Must run on Kaggle GPU.
- **GitHub:** public, Apache-2.0, README quickstart runs the whole stack (Ollama for offline / OpenRouter for hosted).
- **Video (2:45):** 0–30s Pooja's day, 30–90s tutor in action (Hindi answer, MCQ, spaced review), 90–150s offline toggle + low-bandwidth claim, 150–165s tech stack flash.
- **Hosted demo:** Vercel preview of frontend pointing to a Cloudflare-tunneled Ollama box for judge testing window only.
- **Stretch (Unsloth $10K):** thin LoRA on Hindi-glossary outputs — was deferred per `CLAUDE.md §3`, **reconsider on Day 14** if time permits.

## 5. Submission-Day Timeline (May 18, deadline 23:59 UTC = May 19 05:29 IST)

| T-minus | What |
|---|---|
| T-7 (May 11) | Freeze features. Writeup draft v1. Record video v1. |
| T-3 (May 15) | Writeup v2, video v2, hosted demo URL live, GitHub README final. |
| T-1 (May 17) | Dry-run submit on Kaggle (writeups can be edited). Verify notebook runs from clean Kaggle env. Cover image uploaded. |
| **May 18 12:00 UTC** | **Submit final.** ~12hr buffer before deadline. |
| May 18 20:00 UTC | Last edit window — fix typos, swap video if reshot. |

Never submit in the last 2 hours — Kaggle uploads queue under load.

---
**Open verifications** (do before Day 14): confirm 1,500-word cap and 3-min video cap on the actual Gemma 4 Good rules tab (JS-rendered, needs browser/playwright). Tunix template is our best proxy until then.
