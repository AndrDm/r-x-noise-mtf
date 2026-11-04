# AGENTS.md

Single-crate egui/eframe app: a test-pattern generator for ASTM E1695 with **known MTF and noise**. It creates a CT single-slice image of a circular object on a noisy background; the object edge is blurred by a Gaussian PSF derived from a user-requested **MTF10** and **resolution**. The image can be saved to TIFF or DICONDE (DICOM flavor used in NDT/industrial imaging). All app logic lives in `src/main.rs`; no tests, no CI, no task runner. `generator.py` is the Python reference for the MTF10 → PSF model and the PSF plot — keep `main.rs` consistent with it.

## Status

Implemented: `src/main.rs` realizes the spec below for both native and wasm targets, and `index.html` (the trunk host page) exists. See "Editing src/main.rs" for the per-target structure.

## MTF model (from `generator.py`)

- Inputs: **MTF10** in lp/mm (default 1.466) and **Resolution** in µm/pix (default 50) → σ ≈ 4.66 px, Nyquist 10 lp/mm.
- Conversion: `f [cycles/pixel] = f [lp/mm] · resolution_um / 1000`; Nyquist = 0.5 cycles/pixel.
- Gaussian PSF with σ (pixels) has `MTF(f) = exp(−2π²σ²f²)`, so
  - `σ = sqrt(ln 10) / (√2 · π · MTF10_cyc_per_px)`
  - `FWHM = σ · 2·sqrt(2 ln 2)`
  - `MTF50 = sqrt(ln 2) / (√2 · π · σ)` (forward check; MTF10 is recomputed the same way).
- `psf_from_mtf10(mtf10_lp_per_mm, resolution_um) -> Result<Psf, String>` (public) does this and returns `Psf { sigma, mtf10_lp_per_mm, mtf50_lp_per_mm }` (σ in px; widths and Nyquist are computed where they are shown). It rejects non-positive inputs and **MTF10 above Nyquist** (Generate then only sets the status message).
- Reference values: 50 lp/mm @ 1 µm → σ = 6.8308 px, FWHM = 16.085 px, MTF50 = 27.433 lp/mm, Nyquist = 500 lp/mm.

## Generated Image

- Square, side = pixels (default 3000, editable as **Image Size**, range 1–4096).
- Background noise: Mean (default 20000 grays) and StdDev (default 100, as `NOISE_STD` in `generator.py`).
- Center: filled circle of Diameter in pixels (default 2000), Mean (default 40000), StdDev (default 100). The center is offset by (+0.3, +0.5) px from the image center to break grid symmetry.
- Edge: ideal disk convolved with the Gaussian PSF (σ from the MTF model). Implemented analytically — blend weight = Gaussian CDF (`erf`) of the signed distance from the edge, sampled at the pixel center — rather than blurring a binary mask like `generator.py` (`gaussian_filter`), which avoids the mask's stair-steps. Noise is added after the blur, as in `generator.py`; its StdDev is blended between circle and background with the same weight.
- Cupping (%): dips the circle center darker by this percent of the mean difference between circle and background — e.g. circle 40000, background 10000, 10 % → center ≈ 37000 (dip 3000); the dip fades to 0 at the circle edge (`1 − (d/r)²` falloff, confirmed with the user); 0 % = flat circle. A small cupping tail outside the circle has width σ.
- Resolution is stored in Pixel Spacing for DICONDE (mm) and in the TIFF X/YResolution tags.
- There is no separate Transition Sigma input any more: σ always comes from MTF10 + resolution.

## GUI

```
+--------------------------------------------------------------------------------+
| Title bar                                                                      |
+--------------------------------------------------------------------------------+
| File Help                                                                      |
+--------+---------------------------+---------------------------+---------------+
| Tools  |                           |  Gaussian PSF             | = Parameters =|
| ZoomIn |                           |  sigma / widths caption   | MTF10, lp/mm  |
| ZoomOut|                           |  100 % ┌────────────────┐ | Resolution,µm |
| Fit    |          IMAGE            |        │   /\           │ | MTF50, Nyquist|
|        |          (50 %)           |   50 % │--/--\--       │ | ------------- |
|        |                           |   10 % │-/----\-       │ | Image Size    |
|        |                           |    0 % └────────────────┘ | Bkg Mean/Std  |
|        |                           |   -W10 -W50 0 W50 W10     | Circle M/Std  |
|        |                           |         (50 %)            | Diameter      |
|        |                           |                           | Cupping, %    |
|        |                           |                           | [Generate]    |
|        |                           |                           | Component Name|
+--------+---------------------------+---------------------------+---------------+
| Status bar: image size                          last action / errors           |
+--------------------------------------------------------------------------------+
```

Interface is panels: menu bar on top, then four panels in the middle (Tools | Image | Gaussian PSF | Parameters), status bar at the bottom. Image and PSF graph share the space between Tools and Parameters **50/50** (user request): the PSF panel is a `Panel::right("psf")` shown after the Parameters panel and the status bar, with `exact_size(ui.available_rect_before_wrap().width() / 2.0)`, and the `CentralPanel` (image) takes the rest. Keep that call order — showing the PSF panel before the status bar would make it run down the full height.

- The image area supports wheel zoom (anchored at the mouse pointer — `zoom_step` keeps the anchor's texel fraction fixed) and drag-to-pan; zoom = 1.0 is fit-to-screen. A green circle overlay marks the ideal edge on screen only (never written to files).
- Tools panel holds only three 36×36 icon buttons (zoom_in, zoom_out, fit_to_screen SVGs in `assets/icons`, embedded via `egui::include_image!` — paths relative to `src/`), no caption; the panel is `exact_size(52.0)` so the gaps left/right of each button match.
- Parameters panel: MTF10 and Resolution first, followed by exactly two read-only rows (user request): **MTF50** (from `psf_from_mtf10`) and **Nyquist** (`0.5 · 1000 / resolution_um` lp/mm, computed separately so it stays visible when MTF10 is invalid). If MTF10 is above Nyquist (or ≤ 0) the MTF50 value is replaced by a red "invalid" whose tooltip gives the reason; Nyquist is only replaced when the resolution itself is invalid. Sigma/FWHM/% of Nyquist rows were removed on purpose — sigma and widths are shown in the PSF panel, a separator row, then Image Size, Background/Circle Mean/StdDev, Circle Diameter, Cupping, and **Component Name** below the grid.
- The numeric rows live in a 2-column `egui::Grid` (`id "parameters"`) so labels stay left-aligned and all editor boxes start on one vertical line (user request); the separator row is two `ui.separator()` cells. A full-width **Generate** button sits directly under the grid; `Component Name` remains below a separator outside the grid. The grid row is the only GUI access to Generate — there are no quick buttons in the menu bar (removed on purpose: Generate under the controls, Save TIFF only in the File menu).
- **Generate highlight** (user request): `GenParams` snapshots every image-affecting parameter (size, background/circle mean+stddev, diameter, cupping, MTF10, resolution — not Component Name). `generate()` stores it in `App.generated_params` after a successful generation; while `image_is_stale()` (current params ≠ snapshot, or nothing generated yet) the Generate button gets a light-yellow fill (`#FFF3B0`) with an amber stroke and a hover hint, otherwise it is the default gray button. A failed generation leaves the highlight on. When adding a new generator parameter, add it to `GenParams` and `gen_params()` too.
- Shortcuts (constants near the top of `main.rs`): Generate = Ctrl+G, Save TIFF = Ctrl+S, Save DICONDE = Ctrl+Shift+S (`Modifiers::COMMAND.plus(Modifiers::SHIFT)` — the `|` operator is not `const fn`, so it can't be used in the constant), Quit = Ctrl+Q (native only).
- **Gaussian PSF plot** (replaces the former histogram) lives in its own panel (`show_psf`) between the image and the Parameters panel: bold title + three weak caption lines: sigma in px only (user request — σ is a pixel quantity), then width @50 % (FWHM) and width @10 %, each in px and as a physical length via `format_length` — mm with 3 decimals when ≥ 0.1 mm, otherwise µm with 2 decimals (user request) + a plot of `ui.available_height().max(80.0)` that fills the panel. It follows the current MTF10/Resolution live (no image needed). Details (user requests):
  - y is **peak-normalized to 0…100 %** (not unit area); fixed bounds via `include_x/include_y`, zoom/drag/scroll disabled so the scale never changes.
  - x = pixel offset over **±3σ** (not ±5σ like `generator.py`) so the widths are well separated; 401 samples, `egui_plot::Line`.
  - `HLine`s at 50 % and 10 % plus matching `VLine`s at ±half width (`σ·sqrt(2 ln 2)` and `σ·sqrt(2 ln 10)`); a `Legend` names them with the full widths as physical lengths only (`format_length`, no px — user request), e.g. "50 %: 16.09 µm".
  - Two x axes via `custom_x_axes(vec![AxisHints::new_x()…placement(VPlacement::Bottom), …placement(VPlacement::Top)])` (user request): **bottom = physical offset** in mm (3 decimals) or µm (2 decimals), **top = offset in px** — one unit for the whole axis, mm when the 10 % half width is ≥ 0.1 mm (same rule as `format_length`). Both axes share the x grid marks, so the px labels sit exactly above the physical labels. `custom_x_axes` replaces `x_axis_label`/`x_axis_formatter`, so don't add those back.
  - Custom grid spacers: x marks only at 0, ±half width @50 %, ±half width @10 % (2 decimals); y marks at 0, 10, 50, 100 %. egui_plot hides a tick label when the mark's `step_size` spans fewer screen points than the axis `label_spacing` (default 60 pt for x, 20 pt for y) — that is why the default x axis usually showed only "0". Each custom mark therefore gets the whole range as `step_size`, which keeps all labels visible.
  - API (egui_plot 0.37, name is arg #1): `Line::new(name, PlotPoints)`, `HLine::new(name, y)`, `VLine::new(name, x)`; `HLine/VLine::width` takes `impl Into<f32>`, so pass `1.0_f32` (a bare `1.0` infers f64 and fails). `egui_plot = "0.37"` (depends on egui ^0.36 — compatible with eframe 0.36).
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
