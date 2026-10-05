<div align="center">

# 🌐 Lain // The Wired
### Custom Autonomous Language Model Engine (Built from Scratch)

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Framework-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![JavaScript](https://img.shields.io/badge/Frontend-Vanilla%20JS%20%7C%20CSS3-f7df1e?logo=javascript&logoColor=black)](https://developer.mozilla.org)
[![Proprietary](https://img.shields.io/badge/License-All%20Rights%20Reserved-red)](#-copyright--proprietary-license)

**Architect & Developer:** [Paul Konstantin Regler](https://reglerproductions.com)  
**Portfolio:** [reglerproductions.com](https://reglerproductions.com)

</div>

---

## 📌 Executive Summary

**Lain // The Wired** is an independent, full-stack Natural Language Processing (NLP) companion and language generation engine developed completely from first principles in Python.

Unlike generic commercial AI wrappers, this model embodies a dedicated, melancholy, and introspective persona shaped by:
- **Cybernetic & Psychological Lore:** *Serial Experiments Lain, Ghost in the Shell, Blame!, Perfect Blue, Paprika, NieR Replicant / Automata, Drakengard, and Angel's Egg*.
- **Deep Classical Philosophy:** Existential treatises from *Schopenhauer, Nietzsche, and Descartes* exploring solitude, consciousness, and the nature of perception.
- **Basic vocabulary filter:** A small word list is excluded during training. It is not a general safety or truth guarantee.

---

## 🛠️ Architecture & Core Mechanics

```
┌────────────────────────────────────────────────────────────────────────┐
│                          TRAINING PIPELINE                             │
│                                                                        │
│  [Philosophy: Schopenhauer/Nietzsche] + [Lain & Cybernetic Lore]       │
│  [Kon/Oshii/Nihei/Yoko Taro Narratives] + [Emotional Consciousness]   │
│                                   │                                    │
│                                   ▼                                    │
│                     Text Cleaning & Normalization                      │
│                                   │                                    │
│                                   ▼                                    │
│                   Safety Filter & Truth Alignment                      │
│                (Excludes hate/slurs/violence/malice)                   │
│                                   │                                    │
│                                   ▼                                    │
│                 N-Gram State Transitions (Context W=2)                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          RUNTIME INFERENCE                             │
│                                                                        │
│  User Prompt ──► Sliding Window ──► Probability Selector (Lain Voice) │
│                                                │                       │
│  Browser UI ◄── Asynchronous REST API ◄────────┘                       │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. The Core NLP Engine (`backend/model.py`)
- **Sliding Context Window ($N=7$ in the API):** Models word sequences by mapping multi-token states to empirical successor distributions, retaining more of each dialogue prompt.
- **Corpus Weighting:** Employs intentional weight multipliers on persona-specific datasets to embed an introspective, existential identity without distorting baseline vocabulary.
- **Safety Alignment & Guardrails:** Hard-coded algorithmic exclusion of aggressive, abusive, or hostile tokens during both dictionary building and runtime generation.

### 2. The API Layer (`backend/server.py`)
- **FastAPI Engine:** Loads the local corpus at startup and serves model responses.
- **Private access:** Requires a bearer token shared only with the Vercel Function.
- **Input and capacity limits:** Validates prompts and generation length, and limits requests and concurrent inference within one worker.

### 3. Client Frontend (`public/index.html`, `public/style.css`, `public/app.js`)
- **Zero-Dependency Vanilla Architecture:** Built without bloated frontend frameworks for sub-millisecond execution.
- **Glassmorphic Cyberpunk Design:** Custom CSS design system with HSL variables, fluid typography, and ambient glow effects.
- **Resilient Network Handling:** Asynchronous `fetch` calls with automated fallback states and visual health monitoring.

---

## 📂 Project Structure

```bash
├── backend/              # VPS-only Python service and corpus
│   ├── model.py          # N-gram model
│   ├── server.py         # Private FastAPI model service
│   ├── dialogue_corpus.txt # Structured English and German chat examples
│   ├── knowledge_corpus.txt # General knowledge training text
│   ├── lain_corpus.txt   # Persona narrative training dataset
│   └── requirements.txt # Python dependencies
├── api/                  # Vercel Functions that proxy to the VPS
├── deploy/               # systemd and Caddy templates
├── public/               # Only these files are publicly served by Vercel
│   ├── index.html        # Semantic HTML5 Chat layout
│   ├── style.css         # Cyberpunk glassmorphic design system
│   └── app.js            # Asynchronous DOM controller & REST client
├── .gitignore            # Security filters (API keys, credentials, caches)
└── README.md             # Project documentation & architecture overview
```

---

## Deployment: Vercel + VPS

The browser calls same-origin `/api/generate` and `/api/health` on Vercel. The Vercel Functions forward requests over HTTPS to the VPS. The API token exists only in the VPS environment file and Vercel project environment variables; it must never be placed in `app.js`, Git, or a public `NEXT_PUBLIC_` variable. The VPS FastAPI process is reachable only from its local reverse proxy or private Docker network.

### VPS

1. Create an unprivileged `lain` user and install Python 3.9+, Caddy, and systemd. Point a DNS name (for example `api.example.com`) to the VPS. Allow inbound ports 22, 80, and 443 only; keep port 8080 closed externally. Review the existing firewall and SSH configuration before changing them.
2. Copy the contents of `backend/` into `/opt/lain`, owned by `lain`. Optionally copy a vetted `classic_philosophy.txt` alongside them. The service does not download a corpus at startup.
3. Create the virtual environment and install dependencies:

   ```bash
   cd /opt/lain
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

4. Generate a random token (for example with `openssl rand -hex 32`). Store `MODEL_API_TOKEN=<value>` in `/etc/lain/model.env` with owner `root:root` and mode `0600`. Keep this file off Git.
5. For a host-level installation, install [deploy/lain.service](deploy/lain.service) as `/etc/systemd/system/lain.service`, then run `systemctl daemon-reload && systemctl enable --now lain`. The service must become healthy on `http://127.0.0.1:8080/health`. Place [deploy/Caddyfile.example](deploy/Caddyfile.example) in the host Caddy configuration.
6. If Caddy already runs in Docker, build [backend/Dockerfile](backend/Dockerfile) and run the model container on Caddy's private Docker network with `--env-file /etc/lain/model.env`, `--read-only`, `--cap-drop ALL`, and **no published host port**. Add [deploy/Caddyfile.path.example](deploy/Caddyfile.path.example) within the existing HTTPS site and set `MODEL_API_URL` to that site's origin plus `/lain`.
7. Validate and reload Caddy. Confirm the public HTTPS health path works, while generation without the bearer token receives HTTP 401.

### Vercel

Set these **project environment variables** for Production, and Preview if needed:

| Variable | Value |
| --- | --- |
| `MODEL_API_URL` | `https://api.example.com` (the VPS HTTPS origin, optionally with a dedicated path prefix) |
| `MODEL_API_TOKEN` | The same random token as `/etc/lain/model.env`, stored as a sensitive variable |

Deploy the repository root with the **Other** framework preset. `vercel.json` serves only `public/` as static files, while `/api` contains Node.js Functions. Redeploy after changing environment variables. Verify `/api/health` returns `{"status":"ok"}`, then send a chat message from the Vercel site. Restrict Preview access if the chat should not be publicly reachable. Vercel's [Node.js Functions](https://vercel.com/docs/functions/runtimes/node-js) and [sensitive environment variables](https://vercel.com/docs/environment-variables/manage-across-environments) documentation describe the runtime and secret configuration.

The public chat endpoint can be called by anyone who can access the site. The server has one-worker request and concurrency limits, but public rate limiting at scale should be configured in Vercel Firewall or another shared gateway. No finite code change can guarantee that all security vulnerabilities are eliminated.

### Local backend check

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
MODEL_API_TOKEN="$(openssl rand -hex 32)" .venv/bin/python server.py
```

Use `curl http://127.0.0.1:8080/health` to confirm startup. The committed corpus is sufficient; `classic_philosophy.txt` is optional.

---

## 🔒 Copyright & Proprietary License

**Copyright © 2026 Paul Konstantin Regler ([reglerproductions.com](https://reglerproductions.com)). All Rights Reserved.**

This software and its associated source code, design systems, and documentation are strictly proprietary. 

- **No Open-Source License is granted.**
- **No Reproduction:** Unauthorized copying, decompilation, redistribution, modification, public display, or commercial exploitation of any part of this repository is strictly prohibited without explicit prior written authorization from the copyright holder.
- Inquiries regarding technical evaluation, employment, or licensing may be directed via [reglerproductions.com](https://reglerproductions.com).
