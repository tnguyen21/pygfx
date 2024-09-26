#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MIN(a,b) (((a)<(b))?(a):(b))

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

  double M[2][2] = {
    {0.0/4, 2.0/4},
    {3.0/4, 1.0/4}
  };

  for (int x = 0; x < width; x++) {
    for (int y = 0; y < height; y++) {
      for (int c = 0; c < 3; c++) {
        int idx = (y * width + x) * 3 + c;
        int old = data[idx];
        int new = MIN(255, old + (int)(M[y%2][x%2]*255));
        tmp[idx] = (unsigned char)new;
      }
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


