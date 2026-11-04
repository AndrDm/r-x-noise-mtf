import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
import tifffile

# =================================================
# Parameters (Square Image)
# =================================================

SIZE = 4000

BACKGROUND = 20000.0
OBJECT_INTENSITY = 40000.0

# Noise sigma (gray levels)
NOISE_STD = 100.0

# Circle center shifted from (2000, 2000)
CENTER_X = 2000.0 - 0.3  # 0.3 px left
CENTER_Y = 2000.0 - 0.5  # 0.5 px up

RADIUS = 1500.0

# =================================================
# User input
# =================================================

VOXEL_SIZE_UM = 1.0
EXPECTED_MTF10_LP_PER_MM = 50.0

# =================================================
# Derive Gaussian PSF from MTF10
# =================================================

MTF10 = EXPECTED_MTF10_LP_PER_MM * VOXEL_SIZE_UM / 1000.0

PSF_SIGMA = (
    np.sqrt(np.log(10.0))
    / (np.sqrt(2.0) * np.pi * MTF10)
)

FWHM_TO_SIGMA = 2.0 * np.sqrt(2.0 * np.log(2.0))

PSF_FWHM = PSF_SIGMA * FWHM_TO_SIGMA

# =================================================
# Forward-compute expected MTF values
# =================================================

MTF50 = (
    np.sqrt(np.log(2.0))
    / (np.sqrt(2.0) * np.pi * PSF_SIGMA)
)

MTF10_CHECK = (
    np.sqrt(np.log(10.0))
    / (np.sqrt(2.0) * np.pi * PSF_SIGMA)
)

NYQUIST = 0.5

# lp/mm
MTF50_LP_PER_MM = MTF50 * 1000.0 / VOXEL_SIZE_UM
MTF10_LP_PER_MM = MTF10_CHECK * 1000.0 / VOXEL_SIZE_UM
NYQUIST_LP_PER_MM = NYQUIST * 1000.0 / VOXEL_SIZE_UM

print()
print("Gaussian PSF derived from requested MTF10")
print("-----------------------------------------")
print(f"Voxel size            = {VOXEL_SIZE_UM:.3f} µm")
print(f"Requested MTF10       = {EXPECTED_MTF10_LP_PER_MM:.3f} lp/mm")
print()

print(f"PSF sigma             = {PSF_SIGMA:.6f} px")
print(f"PSF FWHM              = {PSF_FWHM:.6f} px")
print()

print(f"Expected MTF50        = {MTF50_LP_PER_MM:.3f} lp/mm")
print(f"Expected MTF10        = {MTF10_LP_PER_MM:.3f} lp/mm")
print(f"Nyquist               = {NYQUIST_LP_PER_MM:.3f} lp/mm")
print()

print(f"MTF50/Nyquist         = {100.0*MTF50/NYQUIST:.2f}%")
print(f"MTF10/Nyquist         = {100.0*MTF10_CHECK/NYQUIST:.2f}%")
print()

OUTPUT_FILE = "synthetic_psf_image.tif"

# =================================================
# Create ideal image
# =================================================

img = np.full(
    (SIZE, SIZE),
    BACKGROUND,
    dtype=np.float64
)

# Coordinate grid
y, x = np.indices((SIZE, SIZE), dtype=np.float64)

# Filled circle
r2 = (x - CENTER_X) ** 2 + (y - CENTER_Y) ** 2

mask = r2 <= RADIUS ** 2

img[mask] = OBJECT_INTENSITY

# =================================================
# Apply Gaussian PSF
# =================================================

img_blurred = gaussian_filter(
    img,
    sigma=PSF_SIGMA,
    mode="reflect"
)

# =================================================
# Add Gaussian (Normal) noise AFTER PSF
# =================================================

noise = np.random.normal(
    loc=0.0,
    scale=NOISE_STD,
    size=(SIZE, SIZE)
)

img_noisy = img_blurred + noise

# =================================================
# Statistics
# =================================================

background_roi = img_noisy[100:1000, 100:1000]

print(f"ROI mean = {background_roi.mean():.2f}")
print(f"ROI std  = {background_roi.std():.2f}")

# =================================================
# Convert to uint16 TIFF
# =================================================

img_out = np.clip(
    np.round(img_noisy),
    0,
    65535
).astype(np.uint16)

# =================================================
# Save TIFF
# =================================================

tifffile.imwrite(
    OUTPUT_FILE,
    img_out,
    photometric="minisblack"
)

print(f"Saved: {OUTPUT_FILE}")

# =================================================
# Plot 1D Gaussian PSF
# =================================================

extent = int(np.ceil(5 * PSF_SIGMA))
x_psf = np.arange(-extent, extent + 1)

psf = np.exp(
    -(x_psf ** 2) / (2 * PSF_SIGMA ** 2)
)

psf /= psf.sum()

plt.figure(figsize=(8, 4))
plt.plot(x_psf, psf, linewidth=2)
plt.grid(True)
plt.title(
    f"Gaussian PSF (FWHM={PSF_FWHM:.2f}px, sigma={PSF_SIGMA:.3f}px)"
)
plt.xlabel("Pixel offset")
plt.ylabel("Amplitude")
plt.tight_layout()

plt.show()
