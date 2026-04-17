# The Gemma 4 Good Hackathon

> Harness the power of Gemma 4 to drive positive change and global impact.

**Host:** Google DeepMind x Kaggle
**Prize Pool:** $200,000 USD (+ $10,000 Unsloth special prize)
**Deadline:** May 18, 2026 (11:59 PM UTC)
**Teams Entered:** ~67
**Max Team Size:** 5
**Max Daily Submissions:** 5
**Status:** YOU ARE ENROLLED

---

## Table of Contents

1. [Competition Overview](#competition-overview)
2. [Timeline](#timeline)
3. [Competition Tracks](#competition-tracks)
4. [Prize Breakdown](#prize-breakdown)
5. [Submission Requirements](#submission-requirements)
6. [Evaluation Criteria](#evaluation-criteria)
7. [Gemma 4 Models Available](#gemma-4-models-available)
8. [Technical Constraints](#technical-constraints)
9. [What Judges Are Looking For](#what-judges-are-looking-for)
10. [What to Avoid](#what-to-avoid)
11. [Resources & Links](#resources--links)
12. [Source Attribution](#source-attribution)

---

## Competition Overview

This is a **hackathon-style competition** (not a traditional ML leaderboard). Participants build real-world applications powered by Google's Gemma 4 open-source models that address urgent social challenges. There is **no provided dataset** — you bring your own data, problem, and solution.

The competition emphasizes:
- **Social impact** over pure model performance
- **Working prototypes** over theoretical proposals
- **Accessibility** — solutions should work in low-resource environments
- **Multimodal capabilities** — leveraging Gemma 4's text + vision + audio support

---

## Timeline

| Milestone | Date |
|---|---|
| Competition Created | March 18, 2026 |
| Competition Opened | April 2, 2026 |
| **Final Submission Deadline** | **May 18, 2026 (11:59 PM UTC)** |
| Team Merger Deadline | May 18, 2026 |

**Time Remaining:** ~34 days from April 14, 2026

---

## Competition Tracks

Submissions should target one or more of these **5 primary impact areas**:

### 1. Future of Education
- Personalized learning experiences
- Educator support tools
- Adaptive tutoring systems
- Curriculum generation

### 2. Health and Sciences
- Medical research assistance
- Patient care improvement
- Health literacy tools
- Diagnostic support

### 3. Digital Equity
- Technology access for underserved communities
- Language accessibility (Gemma 4 supports 140+ languages)
- Bridging the digital divide
- Inclusive design

### 4. Global Resilience
- Climate action and sustainability
- Disaster response and preparedness
- Environmental monitoring
- Resource management

### 5. Safety
- AI security and transparency
- Content reliability
- Trustworthy AI systems
- Misinformation detection

**Additional domains mentioned:** Agriculture & food security, assistive technology, and other high-impact areas.

---

## Prize Breakdown

**Total Pool: $200,000 USD**

| Prize | Amount | Details |
|---|---|---|
| Main competition prizes | $200,000 | Distributed across track categories |
| **Unsloth Special Prize** | **$10,000** | Best fine-tuned Gemma 4 model built with Unsloth |

> **Note:** The exact per-category prize breakdown is managed on the Kaggle competition page (JS-rendered, not extractable via API). The total $200K is distributed across the 5 tracks and potentially overall winner categories. Check the [Kaggle prizes page](https://www.kaggle.com/competitions/gemma-4-good-hackathon/overview/prizes) for the latest breakdown.

---

## Submission Requirements

Every submission **must include all four components**:

### 1. Working Demo / Prototype
- A functional application demonstrating your solution
- Must be interactive and testable
- Should showcase real-world usage

### 2. Public Code Repository
- Open-source codebase (e.g., GitHub)
- Clean, documented code
- Reproducible setup instructions

### 3. Technical Write-up
- How Gemma 4 features were specifically implemented
- Architecture decisions and trade-offs
- Data sources and preprocessing (if applicable)
- Performance metrics and results

### 4. Short Video Demo
- Demonstrates real-world use case scenario
- Shows the application solving an actual problem
- Judges need to quickly understand the pain point and the solution

---

## Evaluation Criteria

Submissions are judged by a panel (not automated scoring). **There is no evaluation metric** — this is purely human-judged.

| Criterion | Weight | Description |
|---|---|---|
| **Innovation** | 30% | Novelty of approach, creative use of Gemma 4 capabilities |
| **Impact Potential** | 30% | Real-world value, scale of the problem being solved |
| **Technical Execution** | 25% | Quality of implementation, effective use of Gemma 4 features |
| **Accessibility** | 15% | Works in low-bandwidth, limited-compute, offline environments |

### Judging Emphasis
- **Problem clarity** — judges should immediately understand the pain point
- **Practical deployment** — solutions that could actually be deployed win over theoretical ones
- **Meaningful use of Gemma 4** — not just wrapping a chatbot, but leveraging multimodal, function calling, on-device, or fine-tuning capabilities

---

## Gemma 4 Models Available

### Model Variants

| Model | Parameters | Active Params | Context | Best For |
|---|---|---|---|---|
| **Gemma 4 E2B** | ~2B | ~2B | 128K tokens | Mobile, IoT, edge deployment |
| **Gemma 4 E4B** | ~4B | ~4B | 128K tokens | Enhanced edge, multimodal on-device |
| **Gemma 4 26B MoE** | 26B | 3.8B (MoE) | 256K tokens | Low-latency inference, efficiency |
| **Gemma 4 31B Dense** | 31B | 31B | 256K tokens | Maximum quality, fine-tuning |

### Key Capabilities

- **Multimodal:** All variants natively process text + images + video at variable resolutions
- **Audio:** E2B and E4B support native audio input (speech recognition & understanding)
- **Function Calling:** Native support for tool use and structured JSON output
- **Agentic Workflows:** Multi-step planning and deep reasoning
- **Code Generation:** High-quality offline code synthesis
- **Visual Tasks:** OCR, chart analysis, document understanding
- **Languages:** Trained on 140+ languages natively
- **License:** Apache 2.0 (fully open source)
- **Quantization:** Supports 4-bit and 8-bit quantization for resource-constrained deployment

### Benchmark Highlights
- 31B model ranks **#3 on Arena AI text leaderboard**
- 26B MoE ranks **#6 on Arena AI text leaderboard**
- Outcompetes models 20x its size on key benchmarks

### Where to Access
- [Kaggle Models](https://www.kaggle.com/models/google/gemma-4)
- [Hugging Face](https://huggingface.co/google/gemma-4)
- [Ollama](https://ollama.com/library/gemma4)
- Google AI Studio
- Vertex AI

---

## Technical Constraints

Solutions should demonstrate capability in **resource-constrained environments**:

- **Low bandwidth** — works with limited internet connectivity
- **Limited compute** — runs on consumer hardware or mobile devices
- **Offline capability** — core functionality available without internet
- **Privacy-sensitive** — on-device processing where possible

This aligns with the 15% **Accessibility** judging weight and the competition's emphasis on serving underserved communities.

---

## What Judges Are Looking For

Based on multiple sources analyzing the competition:

### DO
- Solve a **concrete, specific problem** for a real audience
- Show a **working prototype** (not mockups)
- Leverage Gemma 4's **unique strengths** (multimodal, function calling, on-device)
- Demonstrate **fine-tuning** or domain adaptation (especially for Unsloth prize)
- Target **underserved populations** or **high-impact domains**
- Make the **pain point and payoff** immediately clear in your video
- Show deployment readiness — how could this actually reach users?

### DON'T
- Build a generic chatbot wrapper
- Submit a vague, theoretical proposal
- Create a fake UI or mocked-up demo
- Rely solely on basic prompting without technical depth
- Ignore accessibility and offline requirements
- Submit without all 4 required components (demo, code, writeup, video)

---

## Resources & Links

| Resource | URL |
|---|---|
| Competition Page | https://www.kaggle.com/competitions/gemma-4-good-hackathon |
| Gemma 4 on Kaggle Models | https://www.kaggle.com/models/google/gemma-4 |
| Kaggle Benchmarks (26B & 31B) | https://www.kaggle.com/models/google/gemma-4/competitions |
| Google Gemma 4 Blog Post | https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/ |
| Google DeepMind Gemma Page | https://deepmind.google/models/gemma/gemma-4/ |
| Unsloth Gemma 4 Notebook | https://www.kaggle.com/code/danielhanchen/gemma4-31b-unsloth |
| Unsloth Gemma 4 Docs | https://unsloth.ai/docs/models/gemma-4 |
| Hugging Face Gemma 4 Blog | https://huggingface.co/blog/gemma4 |
| Ollama Gemma 4 | https://ollama.com/library/gemma4 |

---

## Source Attribution

This document was compiled from the following sources, cross-referenced for accuracy:

| Source | Type | What It Provided |
|---|---|---|
| [Kaggle API](https://www.kaggle.com/competitions/gemma-4-good-hackathon) | **Primary (Official)** | Competition metadata: host, prize, deadline, team size, max submissions, tags, enrollment status |
| [Kaggle Official Tweet](https://x.com/kaggle/status/2039740198259462370) | **Primary (Official)** | Confirmed tracks: health, education, climate. $200K pool. May 18 deadline |
| [Kaggle Benchmarks Tweet](https://x.com/kaggle/status/2039763598768066774) | **Primary (Official)** | Confirmed Gemma 4 26B and 31B on Kaggle Benchmarks |
| [Google Blog - Gemma 4](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/) | **Primary (Official)** | Model specs: E2B, E4B, 26B MoE, 31B Dense. Context windows, capabilities, benchmarks |
| [Unsloth AI Tweet](https://x.com/UnslothAI/status/2042599142560796991) | **Primary (Partner)** | $10,000 Unsloth special prize for best fine-tuned Gemma 4 model |
| [EvoArt.ai Blog](https://www.evoart.ai/blog/gemma-4-good-hackathon-kaggle-2026) | Secondary | Evaluation weights (Innovation 30%, Impact 30%, Technical 25%, Accessibility 15%), focus areas |
| [The Inner Detail](https://theinnerdetail.com/google-announces-hackathon-on-ai-skills-using-gemma-4-with-200k-prize/) | Secondary | 5 tracks confirmed, submission requirements (demo, code, writeup, video) |
| [EdTech Innovation Hub](https://www.edtechinnovationhub.com/news/kaggle-and-google-deepmind-open-gemma-4-hackathon-focused-on-ai-skills-and-real-world-impact) | Secondary | Focus areas, judging emphasis on technical execution + real-world problem solving |
| [GitHub (johnsonhk88)](https://github.com/johnsonhk88/Kaggle-The-Gemma-4-Good-Hackathon) | Community | Additional domains (agriculture, assistive tech), model variants, evaluation dimensions |
| [Kaggle Competition Files](https://www.kaggle.com/competitions/gemma-4-good-hackathon/data) | **Primary (Official)** | Confirmed: "This is a Hackathon with no provided dataset" (NOTE.md) |
| [Hugging Face Blog](https://huggingface.co/blog/gemma4) | Secondary | Model technical details and deployment options |

### Reliability Notes
- **Evaluation weights** (30/30/25/15) come from the EvoArt.ai blog, not directly from Kaggle's JS-rendered page. These are widely cited but should be verified against the official competition page.
- **Prize per-category breakdown** is not publicly extractable via API — only the total $200K is confirmed officially.
- All model specifications are from Google's official blog post.

---

*Last updated: April 14, 2026*
*Competition URL: https://www.kaggle.com/competitions/gemma-4-good-hackathon*
