# Session artifact pointer (git-tracked)

Large session files are **not in git**. They live on disk at:

```
docs/research/session-artifacts/3863951f-0f13-4730-8c2c-4af7f3011b71/
```

Read `README.md` in that folder first. Resume: `claude --resume 3863951f-0f13-4730-8c2c-4af7f3011b71`

Key paths (replace `$ART` with the folder above):

- VLM inputs: `$ART/scratchpad/vlm_clean/*.png` (31 images)
- Subagent transcripts: `$ART/subagents/`
- N=31 VLM scores: `docs/research/experiments/vlm_clean_rerun_n31.json`
