#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct frame {
  size_t width;
  size_t height;
  unsigned char data[];
};

static struct frame * frame_create(size_t width, size_t height) {
  struct frame *f = malloc(sizeof(*f) + width * height * 3);
  f->width = width;
  f->height = height;
  return f;
}

static void frame_write(struct frame *f) {
  printf("P6\n%zu %zu\n255\n", f->width, f->height);
  fwrite(f->data, f->width*f->height, 3, stdout);
}

static struct frame * frame_read(struct frame *f) {
  size_t width, height;
  if (scanf("P6 %zu%zu%*d%*c", &width, &height) < 2) {
    free(f);
    return 0;
  }

  if (!f || f->width != width || f->height != height) {
    free(f);
    f = frame_create(width, height);
  }
  fread(f->data, width * height, 3, stdin);
  return f;
}

void blur(unsigned char data[], int width, int height) {
  unsigned char* tmp = (unsigned char*)malloc(height * width * 3 * sizeof(unsigned char));

  for (int x = 0; x < height; x++) {
    for (int y = 0; y < width; y++) {
      int nPixels, avgR, avgG, avgB;
      nPixels = avgR = avgG = avgB = 0;
      
      for (int i = -2; i < 3; i++) {
        for (int j =-2; j < 3; j++) {
          if ((x+i) >= 0 && (x+i) < height && (y+j) >= 0 && (y+j) < width) {
            int idx = ((x+i) * width + (y+j)) * 3;
            avgR += data[idx];
            avgG += data[idx+1];
            avgB += data[idx+2];
            nPixels++;
          }
        }
      }

      int idx = (x * width + y) * 3;
      tmp[idx]   = (unsigned char)(avgR / nPixels);
      tmp[idx+1] = (unsigned char)(avgG / nPixels);
      tmp[idx+2] = (unsigned char)(avgB / nPixels);
    }
  }

  memcpy(data, tmp, height * width * 3 * sizeof(unsigned char));
  free(tmp);
}

int main(int argc, char *argv[])
{
  struct frame *f = frame_read(0);

  while ((f = frame_read(f))) {
    blur(f->data, f->width, f->height);
    frame_write(f);
  }

  free(f);
}


