import argparse
from shaders import *

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to the image.")
    args = parser.parse_args()

    img = cv2.imread(args.image)
    
    if img is None:
        print("Error: Could not open or find the image.")
        exit()
    
    new_img = to_websafe(img)

    cv2.imshow('Original', img)
    # cv2.imshow('Filter', box_blur(img, 5))
    # cv2.imshow('Filter', to_websafe(img))
    cv2.imshow('Filter', bw_floyd_steinberg_dither(img))
    cv2.waitKey(0)
    cv2.destroyAllWindows()