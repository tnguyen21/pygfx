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


def ordered_dither(img: np.ndarray) -> np.ndarray:
    M = np.array([[0, 2], [3, 1]]) / 4
    h, w = img.shape[:2]
    new_img = np.zeros((h, w, 3), np.uint8)
    for y in range(h):
        for x in range(w):
            old_pixel = img[y, x]
            new_pixel = [min(255, p + M[y % 2, x % 2] * 255) for p in old_pixel]
            new_img[y, x] = new_pixel
    return new_img


def ordered_dither_2(img: np.ndarray) -> np.ndarray:
    M = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16
    h, w = img.shape[:2]
    new_img = np.zeros((h, w, 3), np.uint8)
    for y in range(h):
        for x in range(w):
            old_pixel = img[y, x]
            new_pixel = [min(255, p + M[y % 4, x % 4] * 255) for p in old_pixel]
            new_img[y, x] = new_pixel
    return new_img


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