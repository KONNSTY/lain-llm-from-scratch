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

**Lain // The Wired** is a full-stack portfolio chatbot built around the open-weight `Qwen/Qwen2.5-0.5B-Instruct` model, with an original philosophical persona prompt and an optional LoRA adapter. The old from-scratch N-gram implementation could only replay local word patterns; it was not GPT-2-level language modeling. The current runtime uses pretrained instruction-following weights for coherent answers and multi-turn chat.

Unlike generic commercial AI wrappers, this model embodies a dedicated, melancholy, and introspective persona shaped by:
- **Philosophical role-play:** an original system prompt evokes a quiet, introspective digital persona interested in identity, memory, consciousness, and connection. It does not use anime dialogue as training material.
- **Base model:** Qwen2.5-0.5B-Instruct, Apache-2.0, with a model context limit of 32,768 tokens. This deployment defaults to an 8,192-token input budget to manage memory and latency.
- **Fine-tuning:** optional LoRA supervised fine-tuning uses MIT-licensed UltraChat 200k plus the project's original examples in `backend/persona_sft.jsonl`. Training is a separate opt-in command; no downloaded dataset or fine-tuned adapter is committed.

---

## 🛠️ Architecture & Core Mechanics

```
┌────────────────────────────────────────────────────────────────────────┐
│                          TRAINING PIPELINE                             │
│                                                                        │
│  Qwen2.5-0.5B-Instruct + original persona prompt                       │
│                                   │                                    │
│           Optional LoRA SFT: MIT UltraChat + original examples          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          RUNTIME INFERENCE                             │
│                                                                        │
│  Conversation history ──► Chat template ──► Transformers generation    │
│                                                 │                       │
│  Browser UI ◄────────── FastAPI response ◄──────┘                       │
└────────────────────────────────────────────────────────────────────────┘
```

### 1. The Chat Model (`backend/model.py`)
- Uses the pretrained model's native chat template and supports conversation history.
- Configurable context budget (`MODEL_MAX_INPUT_TOKENS`, default 8192) and output length up to 512 new tokens.
- The role-play instruction guides tone and subject; it is not a factuality or safety guarantee.

### 2. The API Layer (`backend/server.py`)
- **FastAPI Engine:** Loads the configured Hugging Face model and optional LoRA adapter at startup.
- **Private access:** Requires a bearer token shared only with the Vercel Function.
- **Input and capacity limits:** Validates prompts and generation length, and limits requests and concurrent inference within one worker.

### 3. Client Frontend (`public/index.html`, `public/style.css`, `public/app.js`)
- **Zero-Dependency Vanilla Architecture:** Built without bloated frontend frameworks for sub-millisecond execution.
- **Glassmorphic Cyberpunk Design:** Custom CSS design system with HSL variables, fluid typography, and ambient glow effects.
- **Resilient Network Handling:** Asynchronous `fetch` calls with automated fallback states and visual health monitoring.

---

## 📂 Project Structure

```bash
├── backend/              # VPS-only Python service and training pipeline
│   ├── model.py          # Transformers chat inference
│   ├── train_lora.py     # Optional LoRA fine-tuning
│   ├── persona_sft.jsonl # Original persona examples
│   ├── server.py         # Private FastAPI model service
│   ├── dialogue_corpus.txt # Legacy N-gram corpus; not used by current inference
│   ├── knowledge_corpus.txt # Legacy corpus; not used by current inference
│   ├── lain_corpus.txt   # Legacy corpus; not used for current training
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
2. Copy the contents of `backend/` into `/opt/lain`, owned by `lain`. At first start, Transformers downloads the model weights from Hugging Face unless they are already cached. Pin a reviewed model revision for production deployments.
3. Create the virtual environment and install dependencies:

   ```bash
   cd /opt/lain
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

4. Generate a random token (for example with `openssl rand -hex 32`). Store `MODEL_API_TOKEN=<value>` in `/etc/lain/model.env` with owner `root:root` and mode `0600`. Keep this file off Git.
5. For a host-level installation, install [deploy/lain.service](deploy/lain.service) as `/etc/systemd/system/lain.service`, then run `systemctl daemon-reload && systemctl enable --now lain`. Systemd creates a writable persistent model cache at `/var/lib/lain/huggingface`. The first startup downloads model weights and may take several minutes. The service must become healthy on `http://127.0.0.1:8080/health`. Place [deploy/Caddyfile.example](deploy/Caddyfile.example) in the host Caddy configuration.
6. If Caddy already runs in Docker, build [backend/Dockerfile](backend/Dockerfile) and run the model container on Caddy's private Docker network with `--env-file /etc/lain/model.env`, `--read-only`, `--cap-drop ALL`, a persistent writable volume mounted at `/var/cache/lain`, and **no published host port**. Add [deploy/Caddyfile.path.example](deploy/Caddyfile.path.example) within the existing HTTPS site and set `MODEL_API_URL` to that site's origin plus `/lain`. Give the model several minutes for its initial download before checking the health endpoint.
7. Validate and reload Caddy. The Caddy request size limit is 64 KB to support conversation history. Confirm the public HTTPS health path works, while generation without the bearer token receives HTTP 401.

### Vercel

Set these **project environment variables** for Production, and Preview if needed:

| Variable | Value |
| --- | --- |
| `MODEL_API_URL` | `https://api.example.com` (the VPS HTTPS origin, optionally with a dedicated path prefix) |
| `MODEL_API_TOKEN` | The same random token as `/etc/lain/model.env`, stored as a sensitive variable |

Deploy the repository root with the **Other** framework preset. `vercel.json` serves only `public/` as static files, while `/api` contains Node.js Functions. Redeploy after changing environment variables. Verify `/api/health` returns `{"status":"ok"}`, then send a chat message from the Vercel site. Restrict Preview access if the chat should not be publicly reachable. Vercel's [Node.js Functions](https://vercel.com/docs/functions/runtimes/node-js) and [sensitive environment variables](https://vercel.com/docs/environment-variables/manage-across-environments) documentation describe the runtime and secret configuration.

The public chat endpoint can be called by anyone who can access the site. The server has one-worker request and concurrency limits, but public rate limiting at scale should be configured in Vercel Firewall or another shared gateway. No finite code change can guarantee that all security vulnerabilities are eliminated.

### Troubleshooting an offline chat

The production Vercel project uses `MODEL_API_URL=https://api.reglerproductions.com/lain`. An HTTP 404 from `/api/health`'s upstream means the public HTTPS host is reachable but its `/lain/*` reverse-proxy route is missing or points to the wrong service. Check both the local model and the public route on the VPS:

```bash
systemctl status lain --no-pager
journalctl -u lain -n 80 --no-pager
curl -i http://127.0.0.1:8080/health
curl -i https://api.reglerproductions.com/lain/health
```

If the model runs in Docker, inspect `docker ps` and `docker logs lain-model --tail 80` instead of the systemd commands. Add [deploy/Caddyfile.path.example](deploy/Caddyfile.path.example) inside the existing HTTPS site block and ensure Caddy and `lain-model` share a Docker network; or use [deploy/Caddyfile.example](deploy/Caddyfile.example) for a host-level systemd service. Validate and reload the active Caddy instance, then check the two health URLs again. Do not change Vercel's `MODEL_API_URL` until the public upstream health route returns 200.

### Optional LoRA fine-tuning

Run this explicitly from `backend/` on a machine with enough memory/storage. It downloads the MIT-licensed `HuggingFaceH4/ultrachat_200k` SFT split and saves only a LoRA adapter; the default is 5,000 general dialogue examples plus repeated original persona examples. Reduce `--max-examples` for a quick smoke run. Training speed depends heavily on GPU/MPS support and is not guaranteed to be practical on CPU.

```bash
cd backend
python train_lora.py --max-examples 5000 --output ./artifacts/lain-qwen-lora
```

To serve the resulting adapter, set `MODEL_ADAPTER_PATH=/opt/lain/artifacts/lain-qwen-lora`. Set `MODEL_ID` to the same base model used for fine-tuning. `MODEL_MAX_INPUT_TOKENS` controls the API's context budget; 8192 is the default, while the base model supports up to 32768 tokens. Longer contexts need substantially more memory and increase latency.

The dataset card identifies UltraChat 200k as MIT-licensed and describes it as filtered conversations generated from ChatGPT. The adapter inherits the base model's and training data's relevant terms; review those terms and the dataset card before redistributing a trained artifact.

### Local backend check

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
MODEL_API_TOKEN="$(openssl rand -hex 32)" .venv/bin/python server.py
```

Use `curl http://127.0.0.1:8080/health` to confirm startup. The first model load downloads the base weights if they are not cached.

---

## 🔒 Copyright & Proprietary License

**Copyright © 2026 Paul Konstantin Regler ([reglerproductions.com](https://reglerproductions.com)). All Rights Reserved.**

This software and its associated source code, design systems, and documentation are strictly proprietary. 

- **No Open-Source License is granted.**
- **No Reproduction:** Unauthorized copying, decompilation, redistribution, modification, public display, or commercial exploitation of any part of this repository is strictly prohibited without explicit prior written authorization from the copyright holder.
- Inquiries regarding technical evaluation, employment, or licensing may be directed via [reglerproductions.com](https://reglerproductions.com).
