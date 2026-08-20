import argparse
from shaders import *

# ponytail: presets are just lambdas; promote to configs if/when they need CLI knobs
PRESETS = {
    # 1-bit stochastic grain, black ink on cyan paper (colors are BGR)
    "monk": lambda img: duotone(
        noise_dither(tone_curve(img, strength=10)), ink=(16, 8, 4), paper=(235, 200, 140)
    ),
    # angled halftone, deep-purple ink on lavender paper, misregistered plate
    "astro": lambda img: plate_shift(
        grain(duotone(halftone(tone_curve(img, strength=6), cell=5), ink=(90, 20, 60), paper=(230, 175, 195)), amount=8)
    ),
    # fine gray dot screen on warm paper
    "fog": lambda img: duotone(halftone(tone_curve(img, strength=4), cell=4, angle=45), ink=(40, 40, 45), paper=(235, 240, 240)),
    "bayer": lambda img: duotone(ordered_dither(tone_curve(img))),
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Path to the image.")
    parser.add_argument("--preset", default="monk", choices=PRESETS, help="Named look to apply.")
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

    new_img = PRESETS[args.preset](img)

    if args.save:
        out_img_path = args.image.rsplit(".", 1)[0] + f"_{args.preset}.png"
        print(f"Saving image to {out_img_path}")
        cv2.imwrite(out_img_path, new_img)

    if args.show:
        cv2.imshow("Original", img)
        cv2.imshow("Filter", new_img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
