import cv2
import numpy as np


def box_blur(img: np.ndarray, kernel_sz: int = 3) -> np.ndarray:
    kernel = np.ones((kernel_sz, kernel_sz), np.float32) / kernel_sz**2
    return cv2.filter2D(img, -1, kernel)


def to_websafe(img: np.ndarray) -> np.ndarray:
    levels = [0, 51, 102, 153, 204, 255]
    lut = np.zeros(256, np.uint8)
    for i in range(256):
        lut[i] = min(levels, key=lambda x: abs(x - i))

    return cv2.LUT(img, lut)


BAYER2 = np.array([[0, 2], [3, 1]]) / 4
BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16


def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def ordered_dither(img: np.ndarray, M: np.ndarray = BAYER4) -> np.ndarray:
    """Threshold against a tiled Bayer matrix. Returns a 1-bit (0/255) mask."""
    g = _gray(img).astype(np.float32) / 255
    h, w = g.shape
    n = M.shape[0]
    thresh = np.tile(M, (h // n + 1, w // n + 1))[:h, :w]
    return np.where(g > thresh, 255, 0).astype(np.uint8)


def noise_dither(img: np.ndarray, seed: int = 0) -> np.ndarray:
    """Stochastic threshold — grainy 1-bit, like a photocopied photo."""
    g = _gray(img).astype(np.float32) / 255
    thresh = np.random.default_rng(seed).random(g.shape, dtype=np.float32)
    return np.where(g > thresh, 255, 0).astype(np.uint8)


def halftone(img: np.ndarray, cell: int = 6, angle: float = 15.0) -> np.ndarray:
    """Angled dot screen — dot radius grows with darkness. Returns 1-bit."""
    g = _gray(img).astype(np.float32) / 255
    h, w = g.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = np.deg2rad(angle)
    u = (xx * np.cos(a) + yy * np.sin(a)) / cell
    v = (-xx * np.sin(a) + yy * np.cos(a)) / cell
    r = np.sqrt((u - np.round(u)) ** 2 + (v - np.round(v)) ** 2)
    return np.where(r >= (1 - g) * 0.75, 255, 0).astype(np.uint8)


def tone_curve(img: np.ndarray, strength: float = 8.0, mid: float = 0.5) -> np.ndarray:
    """Sigmoid contrast crush. Higher strength = harder shadows/highlights."""
    x = img.astype(np.float32) / 255
    y = 1 / (1 + np.exp(-strength * (x - mid)))
    lo = 1 / (1 + np.exp(strength * mid))
    hi = 1 / (1 + np.exp(-strength * (1 - mid)))
    return np.clip(np.rint((y - lo) / (hi - lo) * 255), 0, 255).astype(np.uint8)


def duotone(mask: np.ndarray, ink=(0, 0, 0), paper=(255, 255, 255)) -> np.ndarray:
    """Map a 1-bit mask to two BGR colors: 0 -> ink, 255 -> paper."""
    out = np.empty((*mask.shape[:2], 3), np.uint8)
    out[mask == 0] = ink
    out[mask != 0] = paper
    return out


def grain(img: np.ndarray, amount: float = 12.0, seed: int = 0) -> np.ndarray:
    noise = np.random.default_rng(seed).normal(0, amount, img.shape[:2]).astype(np.float32)
    if img.ndim == 3:
        noise = noise[..., None]
    return np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)


def plate_shift(img: np.ndarray, dx: int = 3, dy: int = 1, channel: int = 2) -> np.ndarray:
    """Misregistration: roll one BGR channel to fake an offset print plate."""
    out = img.copy()
    out[..., channel] = np.roll(img[..., channel], (dy, dx), axis=(0, 1))
    return out


def tommy_dither(img: np.ndarray) -> np.ndarray:
    """
    This isn't really dithering. I'm doing a bunch of messed up math.
    But it creates a cool effect, so I'm keeping it
    """

    img = img.astype(np.float32)
    levels = [0, 51, 102, 153, 204, 255]
    lut = np.zeros(256, np.uint8)
    for i in range(256):
        lut[i] = min(levels, key=lambda x: abs(x - i))

    h, w = img.shape[:2]
    new_img = np.zeros((h, w), np.uint8)
    for y in range(h):
        for x in range(w):
            old_pixel = img[y, x]
            new_pixel = min(levels, key=lambda x: abs(x - old_pixel).sum())
            new_img[y, x] = new_pixel
            error = old_pixel - new_pixel
            if x < w - 1:
                img[y, x + 1] += error * 7 / 16
            if y < h - 1:
                if x > 0:
                    img[y + 1, x - 1] += error * 3 / 16
                img[y + 1, x] += error * 5 / 16
                if x < w - 1:
                    img[y + 1, x + 1] += error * 1 / 16
    return new_img

def kuwahara(img: np.ndarray, ksize: int = 3) -> np.ndarray:
    """
    Apply Kuwahara filter to an image.
    
    :param src: Input image
    :param ksize: Size of the kernel. Must be odd and greater than 1.
    :return: Filtered image
    """
    h, w = img.shape[:2]
    new_img = np.zeros((h, w, 3), dtype=img.dtype)

    pad = np.ceil(ksize / 2).astype(int)
    img_pad = cv2.copyMakeBorder(img, *[pad]*4, cv2.BORDER_DEFAULT)

    for y in range(h):
        for x in range(w):
            regions = [
                ((y, x), (y+ksize, x+ksize)), # top left
                ((y, x+ksize-1), (y+ksize, x+2*ksize-1)), # top right
                ((y+ksize-1, x), (y+2*ksize-1, x+ksize)), # bottom left
                ((y+ksize-1, x+ksize-1), (y+2*ksize-1, x+2*ksize-1)) # bottom right
            ]

            min_var = float('inf')
            for r1, r2 in regions:
                y1, x1 = r1
                y2, x2 = r2
                mean, var = cv2.meanStdDev(img_pad[y1:y2, x1:x2])
                avg_var = var.mean()
                if avg_var < min_var:
                    min_var = avg_var
                    new_img[y, x] = mean.astype(np.uint8).reshape(3,)
    
    return new_img