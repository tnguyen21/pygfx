import numpy as np
import cv2

def box_blur(img: np.ndarray, kernel_sz: int = 3) -> np.ndarray:
    kernel = np.ones((kernel_sz, kernel_sz), np.float32) / kernel_sz**2
    return cv2.filter2D(img, -1, kernel)

def to_websafe(img: np.ndarray) -> np.ndarray:
    levels = [0, 51, 102, 153, 204, 255]
    lut = np.zeros(256, np.uint8)
    for i in range(256):
        lut[i] = min(levels, key=lambda x: abs(x - i))
    
    return cv2.LUT(img, lut)

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
                img[y, x+1] += error * 7 / 16
            if y < h - 1:
                if x > 0:
                    img[y+1, x-1] += error * 3 / 16
                img[y+1, x] += error * 5 / 16
                if x < w - 1:
                    img[y+1, x+1] += error * 1 / 16
    return new_img