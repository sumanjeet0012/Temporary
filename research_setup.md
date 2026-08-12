# Local Autonomous Research Agent Setup
## MacBook Air M4 (16GB RAM)

This guide describes how to build a fully local AI research stack capable of:

- Running open-weight models locally
- Performing web searches
- Reading and analyzing websites
- Following links across multiple pages
- Generating detailed research reports
- Maintaining privacy without relying on cloud AI services

---

# Final Architecture

```text
┌─────────────────────────┐
│        OpenHands        │
│   Autonomous Agent      │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│        Ollama           │
│    Local LLM Runtime    │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│      Qwen3 8B           │
│    Research Model       │
└─────────────────────────┘


┌─────────────────────────┐
│        SearXNG          │
│      Web Search         │
└─────────────────────────┘


┌─────────────────────────┐
│      Playwright         │
│ Browser Automation      │
└─────────────────────────┘
```

---

# Why This Stack?

## Ollama

Provides:

- Local LLM execution
- Easy model downloads
- OpenAI-compatible API
- Native Apple Silicon support

No cloud services required.

---

## Qwen3 8B

Recommended for MacBook Air M4 16GB.

Advantages:

- Strong reasoning
- Good research abilities
- Efficient memory usage
- Better tool usage than most similarly sized models

Expected memory:

```text
~5-6 GB RAM
```

---

## OpenHands

Provides:

- Autonomous task planning
- Web research
- Browser navigation
- Multi-step workflows
- File generation
- Report generation

Example:

```text
Research Tails OS

↓

Searches web

↓

Reads sources

↓

Follows links

↓

Compares information

↓

Generates report
```

Unlike a normal chatbot, OpenHands can actively perform tasks.

---

## Playwright

Provides browser control.

Capabilities:

- Open websites
- Click buttons
- Follow links
- Read page contents
- Extract information
- Take screenshots

The LLM decides *what* to do.
Playwright performs the browser actions.

---

## SearXNG

Provides:

- Web search
- Privacy-oriented searching
- Multiple search providers
- Self-hosted operation

Recommended providers:

```text
Google
Brave
Wikipedia
```

Avoid using Google only.

Having multiple providers improves reliability.

---

# Hardware Expectations

Machine:

```text
MacBook Air M4
16 GB RAM
```

Expected usage:

| Component | RAM |
|-----------|-----|
| macOS | 4 GB |
| Qwen3 8B | 5-6 GB |
| OpenHands | 0.5-1 GB |
| Playwright Browser | 1-2 GB |

Normal workload:

```text
10-12 GB RAM
```

Heavy research:

```text
12-15 GB RAM
```

This is acceptable on a 16 GB Air.

---

# Step 1 - Install Homebrew

Verify:

```bash
brew --version
```

If not installed:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

---

# Step 2 - Install Ollama

Install:

```bash
brew install ollama
```

Start Ollama:

```bash
ollama serve
```

Verify:

```bash
curl http://localhost:11434/api/tags
```

---

# Step 3 - Install Research Model

Download Qwen3:

```bash
ollama pull qwen3:8b
```

Test:

```bash
ollama run qwen3:8b
```

Basic prompt:

```text
Explain how Tails OS works.
```

---

# Step 4 - Install Docker Desktop

Install:

```bash
brew install --cask docker
```

Launch Docker Desktop.

Verify:

```bash
docker ps
```

Expected:

```text
CONTAINER ID   IMAGE   COMMAND
```

No errors should appear.

---

# Step 5 - Install OpenHands

Create workspace:

```bash
mkdir ~/openhands
cd ~/openhands
```

Start container:

```bash
docker run -it --rm \
  -p 3000:3000 \
  --add-host host.docker.internal:host-gateway \
  ghcr.io/all-hands-ai/openhands:latest
```

Open:

```text
http://localhost:3000
```

---

# Step 6 - Connect OpenHands to Ollama

Inside OpenHands:

Provider:

```text
OpenAI Compatible
```

Base URL:

```text
http://host.docker.internal:11434/v1
```

Model:

```text
qwen3:8b
```

Save settings.

Perform a test query:

```text
What is Tails OS?
```

---

# Step 7 - Install Node.js

Required for Playwright.

Install:

```bash
brew install node
```

Verify:

```bash
node -v
npm -v
```

---

# Step 8 - Install Playwright

Install:

```bash
npm install -g playwright
```

Install browser:

```bash
playwright install chromium
```

Verify:

```bash
playwright --version
```

---

# Step 9 - Use Headless Browser Mode

Recommended settings:

```text
Browser:
Chromium

Mode:
Headless

Screenshots:
Optional
```

Benefits:

- Lower RAM usage
- Faster execution
- No browser windows

---

# Step 10 - Install SearXNG

Create directory:

```bash
mkdir ~/searxng
cd ~/searxng
```

Create:

```yaml
version: "3"

services:
  searxng:
    image: searxng/searxng
    ports:
      - "8080:8080"
```

Save as:

```text
docker-compose.yml
```

Start:

```bash
docker compose up -d
```

Open:

```text
http://localhost:8080
```

---

# Step 11 - Configure Search Providers

Recommended:

```text
Google
Brave
Wikipedia
```

Do not limit yourself to:

```text
Google only
```

Benefits:

- Redundancy
- Better coverage
- Less rate limiting

---

# Step 12 - Research Workflow Examples

## Example 1

Prompt:

```text
Research Tails OS.

Requirements:
- Read at least 15 sources
- Compare official docs and community opinions
- Include pros and cons
- Generate markdown report
```

---

## Example 2

Prompt:

```text
Explain onion routing in depth.

Requirements:
- Include diagrams in markdown
- Cite sources
- Compare with VPNs
```

---

## Example 3

Prompt:

```text
Research anonymous operating systems.

Compare:

- Tails
- Whonix
- Qubes OS

Generate detailed comparison report.
```

---

# Recommended Models

## Primary

```bash
ollama pull qwen3:8b
```

---

## Secondary

```bash
ollama pull qwen3-coder
```

For:

- Programming
- Automation
- Scripts

---

## Optional

```bash
ollama pull dolphin3
```

Useful when you want a model with fewer refusals.

Keep Qwen3 as the primary research model and use Dolphin3 as an alternate model when desired.

---

# Future Upgrades

If you later upgrade to:

```text
24 GB RAM
```

You can move to:

```bash
ollama pull qwen3:14b
```

Expected improvement:

- Better reasoning
- Better planning
- Better autonomous research

---

# Final Recommended Setup

```text
MacBook Air M4 (16 GB)

✓ Ollama
✓ Qwen3 8B
✓ OpenHands
✓ Playwright (Headless Chromium)
✓ SearXNG

Result:

Local AI
+
Local Search
+
Autonomous Research Agent
+
Browser Automation
+
Private Workflow
```

This setup provides the best balance of performance, resource usage, and research capability on a 16GB M4 Air.
