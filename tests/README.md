# joe tests

```sh
cd path/to/joe-repo
python3 -m pip install --user pytest
python3 -m pytest tests/ -v
```

The suite imports `bin/joe` as a module with `$HOME` redirected to a
pytest tmp dir, so nothing here touches your real `~/.joe-agent/`. All
tests are pure-Python and offline; no ollama or network calls required.

Coverage focuses on the parts that would silently corrupt state if they
broke:

- tool-call protocol parser (XML tag + legacy `RUN:` fallback)
- time-phrase extractor for `/recall yesterday morning`
- content-addressed blob store
- subagent seeder + loader
- lessons + provenance round-trip
- active-repo discovery
- small math helpers (cosine, vec pack/unpack, token estimate)
