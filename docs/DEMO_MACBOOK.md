# Demo setup on a MacBook with 8 GB RAM

The defense demo fits in 8 GB because the heavy model (mistral 7B, ~5 GB RAM)
is not needed: Task 1 and Task 2 run entirely on RapidFuzz with the LLM
checkbox off (default). The only LLM feature in the demo is manufacturer
search, which uses qwen2.5:1.5b (~1.5 GB).

Memory budget: macOS ~3 GB + containers <0.5 GB + qwen ~1.5 GB ≈ 5 GB of 8.

## One-time setup (do this at least a day before the defense)

1. Install Docker Desktop for Mac. In **Settings → Resources** set
   Memory limit to **3 GB** (leaves room for macOS and the browser).

2. Clone and build (images are multi-arch, ARM build works out of the box):

   ```bash
   git clone <repo-url> && cd gazprom-diplom
   docker compose up -d --build
   ```

3. Pull ONLY the small model — do NOT pull mistral on this machine:

   ```bash
   docker exec -it gazprom-ollama ollama pull qwen2.5:1.5b
   ```

4. Open http://localhost:3000, log in `admin` / `admin`, upload the demo
   files from `examples/` (per `examples/README.md`): leader_smi, veneta,
   dlux pairs and `Task2/synthetic/` registries.

5. Dry-run the whole demo once: Task 1 (dlux), Task 2 wizard, one
   manufacturer search ("Труба стальная бесшовная" finds results).
   The first search loads the model into RAM (~30 s); subsequent ones are
   faster.

## Optional: faster search on Apple Silicon (M1/M2/M3)

Ollama inside Docker on macOS is CPU-only. The native Ollama.app uses the
Metal GPU and runs qwen several times faster:

1. Install https://ollama.com/download/mac, then `ollama pull qwen2.5:1.5b`.
2. Create `docker-compose.override.yml` in the repo root (gitignored):

   ```yaml
   services:
     backend:
       environment:
         OLLAMA_BASE_URL: http://host.docker.internal:11434
   ```

3. `docker compose up -d backend` to apply. The gazprom-ollama container
   stays up but idle (~120 MB) — harmless.

On an Intel MacBook skip this section and skip live LLM search entirely —
show screenshots instead (CPU generation takes minutes there).

## Day of the defense

- Start Docker Desktop, then `docker compose up -d` — wait until
  http://localhost:3000 responds.
- Warm up the search once before the talk (first request loads the model).
- Keep the "LLM-верификация спорных позиций" checkbox OFF in Task 1 —
  processing takes seconds and the result is identical on the demo data.
- No internet required; only Google Fonts degrade to system fonts offline.

## Honest answer for the commission about hardware requirements

| Mode | CPU | RAM | Disk |
|---|---|---|---|
| Tasks 1 & 2 (no LLM) | 2 cores | 4 GB | 20 GB |
| Full functionality (CPU inference) | 4–8 cores | 16 GB | 30 GB |
| Full functionality (GPU) | 4 cores | 8 GB + NVIDIA ≥6 GB VRAM | 30 GB |

The 16 GB figure: mistral 7B q4 holds ~5 GB resident plus qwen ~1.5 GB plus
OS/Docker overhead. CPU cores translate directly into tokens/second.
