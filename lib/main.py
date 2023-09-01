import argparse
from shaders import *

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to the image.")
    parser.add_argument(
        "--save",
        default=False,
        help="Save the image to the current directory.",
        action=argparse.BooleanOptionalAction,
    )
    parser.add_argument(
        "--show",
        default=False,
        help="Show the image in a window.",
        action=argparse.BooleanOptionalAction,
    )
    args = parser.parse_args()

    img = cv2.imread(args.image)

    if img is None:
        print("Error: Could not open or find the image.")
        exit()

    new_img = ordered_dither(img)

    if args.save:
        out_img_path = args.image.split(".")[0] + "_out.png"
        print(f"Saving image to {out_img_path}")
        cv2.imwrite(out_img_path, new_img)

    if args.show:
        cv2.imshow("Original", img)
        cv2.imshow("Filter", new_img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
