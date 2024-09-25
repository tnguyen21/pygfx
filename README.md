# pygfx

some implementations of image processing algorithms with only numpy and opencv2 -- for fun!

![birb.jpg](birb.jpg)

![kuwahara_birb.png](kuwahara_birb.png)

## video

https://nullprogram.com/blog/2017/07/02/

visually edit videos frame-by-frame

1. compile one of the scripts in `/video` e.g. `clang identity.c -o identity`
1. `ffmpeg -i input.mp4 -f image2pipe -vcodec ppm pipe:1 | ./identity | ppmtoy4m | x264 -o output.mp4 /dev/stdin`

the command:

- Decodes the input video file to a series of PPM images
- Converts these PPM images to Y4M format
- Encodes the Y4M stream to H.264 format, saving it as output.mp4

and uses pipes to direct frame data between stdin and stdout
