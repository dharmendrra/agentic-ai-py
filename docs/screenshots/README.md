# Showcase screenshots

These PNGs are referenced by `docs/index.html`. Generate them against the
running apps:

```bash
# from the repo root, with the three services running (./run.sh)
pip install playwright
python -m playwright install chromium
python docs/capture_screenshots.py
```

Expected files (the showcase shows a styled "pending" placeholder for any that
are missing, so the page stays presentable before capture):

| File | What it shows | Source URL |
|---|---|---|
| `chat-hero.png` | Chat landing: hero band + chat column + sidebar | http://localhost:8082 |
| `source-toggles.png` | Web + My Library toggles active | http://localhost:8082 |
| `answer-web-citations.png` | Answer with provenance chip + clickable web sources | http://localhost:8082 (needs live LLM + Tavily) |
| `sidebar-conversations.png` | Past-conversations sidebar with saved chats | http://localhost:8082 |
| `ingest-dropzone.png` | Drag-and-drop PDF upload page | http://localhost:8081 |
| `ingest-search-test.png` | Direct vector-search test panel | http://localhost:8081 |
