# CLAUDE.md

ASTM E1695 Image Generator with known MTF

@AGENTS.md

- Project guidance (spec, MTF10 → PSF model, GUI, build, per-target code duplication) lives in AGENTS.md so other agents share it; keep it current when behavior changes.
- `generator.py` is the Python reference for the MTF10 → Gaussian PSF math and the PSF plot. When changing either in `src/main.rs`, keep them consistent with it (reference: 50 lp/mm @ 1 µm/pix → σ = 6.8308 px).
- Verify changes with `cargo build` for native and `wasm32-unknown-unknown`, plus `cargo fmt`.
