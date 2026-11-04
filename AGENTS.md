# AGENTS.md

Single-crate egui/eframe app: a test-pattern generator for ASTM E1695 with **known MTF and noise**. It creates a CT single-slice image of a circular object on a noisy background; the object edge is blurred by a Gaussian PSF derived from a user-requested **MTF10** and **resolution**. The image can be saved to TIFF or DICONDE (DICOM flavor used in NDT/industrial imaging). All app logic lives in `src/main.rs`; no tests, no CI, no task runner. `generator.py` is the Python reference for the MTF10 → PSF model and the PSF plot — keep `main.rs` consistent with it.

## Status

Implemented: `src/main.rs` realizes the spec below for both native and wasm targets, and `index.html` (the trunk host page) exists. See "Editing src/main.rs" for the per-target structure.

## MTF model (from `generator.py`)

- Inputs: **MTF10** in lp/mm (default 50) and **Resolution** in µm/pix (default 1.0).
- Conversion: `f [cycles/pixel] = f [lp/mm] · resolution_um / 1000`; Nyquist = 0.5 cycles/pixel.
- Gaussian PSF with σ (pixels) has `MTF(f) = exp(−2π²σ²f²)`, so
  - `σ = sqrt(ln 10) / (√2 · π · MTF10_cyc_per_px)`
  - `FWHM = σ · 2·sqrt(2 ln 2)`
  - `MTF50 = sqrt(ln 2) / (√2 · π · σ)` (forward check; MTF10 is recomputed the same way).
- `psf_from_mtf10(mtf10_lp_per_mm, resolution_um) -> Result<Psf, String>` (public) does this and returns σ, FWHM, MTF10/MTF50/Nyquist in lp/mm and MTF10/MTF50 as % of Nyquist. It rejects non-positive inputs and **MTF10 above Nyquist** (Generate then only sets the status message).
- Reference values: 50 lp/mm @ 1 µm → σ = 6.8308 px, FWHM = 16.085 px, MTF50 = 27.433 lp/mm, Nyquist = 500 lp/mm.

## Generated Image

- Square, side = pixels (default 1000, editable as **Image Size**, range 1–4096).
- Background noise: Mean (default 20000 grays) and StdDev (default 500).
- Center: filled circle of Diameter in pixels (default 700), Mean (default 40000), StdDev (default 1000). The center is offset by (+0.3, +0.5) px from the image center to break grid symmetry.
- Edge: ideal disk convolved with the Gaussian PSF (σ from the MTF model). Implemented analytically — blend weight = Gaussian CDF (`erf`) of the signed distance from the edge, sampled at the pixel center — rather than blurring a binary mask like `generator.py` (`gaussian_filter`), which avoids the mask's stair-steps. Noise is added after the blur, as in `generator.py`; its StdDev is blended between circle and background with the same weight.
- Cupping (%): dips the circle center darker by this percent of the mean difference between circle and background — e.g. circle 40000, background 10000, 10 % → center ≈ 37000 (dip 3000); the dip fades to 0 at the circle edge (`1 − (d/r)²` falloff, confirmed with the user); 0 % = flat circle. A small cupping tail outside the circle has width σ.
- Resolution is stored in Pixel Spacing for DICONDE (mm) and in the TIFF X/YResolution tags.
- There is no separate Transition Sigma input any more: σ always comes from MTF10 + resolution.

## GUI

```
+-----------------------------------------------------------+
| Title bar                                                 |
+-----------------------------------------------------------+
| File Help                                                 |
+-----------------+--------------------+--------------------+
|  = Tools =      |                    |  = Parameters =    |
| Zoom In         |                    | MTF10, lp/mm       |
| Zoom Out        |                    | Resolution, µm/pix |
| Fit to Screen   |                    | (PSF sigma / FWHM) |
|                 |                    | (MTF50)            |
|                 |                    | (Nyquist)          |
|                 |                    | (MTF10/MTF50 %Nyq) |
|                 |                    | ------------------ |
|                 |                    | Image Size         |
|                 |       IMAGE        | Background Mean    |
|                 |                    | Background StdDev  |
|                 |                    | Circle Mean        |
|                 |                    | Circle StdDev      |
|                 |                    | Circle Diameter    |
|                 |                    | Cupping, %         |
|                 |                    | [Generate]         |
|                 |                    | Component Name     |
|                 |                    +--------------------+
|                 |                    | Gaussian PSF plot  |
+-----------------+--------------------+--------------------+
| Status bar: image size            last action / errors    |
+-----------------------------------------------------------+
```

Interface is panels: menu bar on top, then three panels in the middle (Tools | Image | Parameters), status bar at the bottom.

- The image area supports wheel zoom (anchored at the mouse pointer — `zoom_step` keeps the anchor's texel fraction fixed) and drag-to-pan; zoom = 1.0 is fit-to-screen. A green circle overlay marks the ideal edge on screen only (never written to files).
- Tools panel holds only three 36×36 icon buttons (zoom_in, zoom_out, fit_to_screen SVGs in `assets/icons`, embedded via `egui::include_image!` — paths relative to `src/`), no caption; the panel is `exact_size(52.0)` so the gaps left/right of each button match.
- Parameters panel: MTF10 and Resolution first, followed by read-only derived rows (weak text, recomputed live from `psf_from_mtf10`; an invalid combination shows a red "invalid" with the reason as tooltip), a separator row, then Image Size, Background/Circle Mean/StdDev, Circle Diameter, Cupping, and **Component Name** below the grid.
- The numeric rows live in a 2-column `egui::Grid` (`id "parameters"`) so labels stay left-aligned and all editor boxes start on one vertical line (user request); the separator row is two `ui.separator()` cells. A full-width **Generate** button sits directly under the grid; `Component Name` remains below a separator outside the grid. The grid row is the only GUI access to Generate — there are no quick buttons in the menu bar (removed on purpose: Generate under the controls, Save TIFF only in the File menu).
- Shortcuts (constants near the top of `main.rs`): Generate = Ctrl+G, Save TIFF = Ctrl+S, Save DICONDE = Ctrl+Shift+S (`Modifiers::COMMAND.plus(Modifiers::SHIFT)` — the `|` operator is not `const fn`, so it can't be used in the constant), Quit = Ctrl+Q (native only).
- **Gaussian PSF plot** (replaces the former histogram) starts right below the parameter content (bold title + weak "FWHM = …, sigma = …" caption + `ui.available_height().max(80.0)`-tall plot), filling the whole bottom area of the Parameters panel — it is NOT a bottom sub-panel (a `Panel::bottom` pins to the panel bottom and leaves a gap after short parameter content). It ports the 1D PSF plot of `generator.py`: x = pixel offset over ±⌈5σ⌉, y = unit-area Gaussian amplitude, 401 samples, drawn as an `egui_plot::Line` (`Line::new(name, PlotPoints)` — name is arg #1 in egui_plot 0.37). It follows the current MTF10/Resolution live (no image needed). `egui_plot = "0.37"` (depends on egui ^0.36 — compatible with eframe 0.36).
- Open TIFF was removed on purpose — the app builds its own image; don't reintroduce it without a request.

## Build & run

- Desktop (Windows MSVC): `cargo run`.
- Web: `cargo build --target wasm32-unknown-unknown` (target installed via rustup). The web entry panics unless `index.html` contains `<canvas id="the_canvas_id">` (renaming it breaks the wasm build), plus `<div id="loading_text">` which the bootstrap removes on startup.
- Web build check: `trunk build --release --public-url . --no-default-features`.
- `rand` pulls getrandom 0.3, which refuses bare wasm32 unless the `wasm_js` feature is enabled (`[target.'cfg(target_arch = "wasm32")'.dependencies]` in `Cargo.toml`) **and** `--cfg getrandom_backend="wasm_js"` is set (`.cargo/config.toml`); remove neither or the wasm build fails to compile.
- TIFF resolution tags are written with the `tiff` crate directly (`write_tiff` in `main.rs`) because `image`'s `TiffEncoder` cannot write X/YResolution; there is no millimeter ResolutionUnit, so the spacing is stored as pixels per centimeter, `Rational { n: 10_000_000, d: spacing_nm }` (1 nm precision — µm voxels need it).
- No clippy config; effective verification is `cargo build` on **both** targets + `cargo fmt` (wasm build needs the getrandom config above).

## Formatting

- `rustfmt.toml` is non-default: **hard tabs** (not 4 spaces), `max_width = 100`, `use_small_heuristics = "Max"`. Run `cargo fmt` instead of hand-formatting.

## Editing src/main.rs

Layout is **duplicated per target**; each copy only compiles on its own target:

- `save_tiff`, `save_dicom`, and `main` each exist in two versions guarded by `#[cfg(not(target_arch = "wasm32"))]` / `#[cfg(target_arch = "wasm32")]`. The dialogs, the DICOM element construction in `save_dicom`, and the download/write plumbing are duplicated in both copies — change both (`write_tiff` tag encoding and `pixel_spacing_ds` are shared).
- Save functions take the spacing in **mm** (`resolution_um / 1000.0` at the call site); the App stores µm.
- Any tag/VR/metadata change hits two output paths: wasm serializes to bytes and triggers a browser download; native writes the file with `write_to_file`.
- There are no cfg-gated `App` fields at the moment (the old wasm-only `pending_image` open-queue was removed with Open TIFF); if target-specific fields reappear, don't "clean up" the cfg attributes.

eframe/egui 0.36 gotchas (verified against docs.rs 0.36.2):

- `eframe::App` has no `update` method in 0.36 — the required method is `fn ui(&mut self, ui: &mut Ui, frame: &mut Frame)`, and that `Ui` is the bare root (no margin/background). Layout = `egui::Panel`s (top/bottom, shown in call order) + `egui::CentralPanel::default()` for the image; painting widgets directly on the root `Ui` leaves the rest of the window the default dark viewport background.
- The app forces a light look regardless of OS theme: both `main()`s call `set_theme(Light)` + `set_visuals_of` (both themes, `Visuals::light()`), and panels use an explicit white `light_panel_frame()` helper — menu bars drawn straight on the root `Ui` have no background at all.
- `egui::include_image!` embeds assets, but its paths are relative to **`src/`** (e.g. `"../assets/icons/zoom_in.svg"`).
- SVG assets require the `svg` feature on `egui_extras` (already enabled in `Cargo.toml`) **and** `egui_extras::install_image_loaders(&cc.egui_ctx)` in both `main()`s (native and wasm) — without the install call the texture never loads and buttons render empty.

## DICOM output

- Image → 16-bit grayscale (`to_luma16`), single frame, 1 sample, `MONOCHROME2`, uncompressed Explicit VR Little Endian (`transfer_syntax "1.2.840.10008.1.2.1"`), pixel data in VR `OW`.
- Pixel Spacing (0028,0030) is written in mm as one value repeated for both row/column components, formatted by `pixel_spacing_ds` (rounded to 1e-9 mm, trailing zeros trimmed, so it fits the 16-char DS limit; 1 µm → `0.001\0.001`).
- UI label "Component Name (0010,0010)" is the DICOM *Patient Name* tag; the code uses standard DICOM tags, not separate DICONDE tags.
- Errors are surfaced in the bottom status bar (`App.status`), set by the results of generate/save calls; a successful Generate reports the σ and MTF10 used.
- Noise generator: `gen_noise` (public in `main.rs`) samples per-pixel Gaussian noise with `rand_distr::StandardNormal`; the circle→background blend weight is a Gaussian CDF (`erf` approximation) of the distance from the circle edge, driven by `psf_sigma` (from `psf_from_mtf10`); `psf_sigma == 0` still yields an exact pixel-area-coverage sharp edge, but the GUI never passes 0. `cupping` (percent) applies a `1 − (d/r)²` mean dip inside the circle, zero at the edge.
