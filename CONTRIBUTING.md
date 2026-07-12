# Contributing to Moonlight Voice

Keep changes local-first, dependency-light, and compatible with Home Assistant Ingress. Use English for code, UI text, metadata, and documentation.

Before opening a pull request, run:

```bash
python3 -m unittest discover -s tests
PYTHONPATH=moonlight-voice python3 -m pytest moonlight-voice/tests
```

Do not add credentials, cloud dependencies, outbound network calls, or generated media without confirming redistribution rights. Describe API or storage changes in the pull request and include regression coverage.
