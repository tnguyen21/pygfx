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

void convert_to_grayscale(unsigned char* data, int width, int height) {
  for (int i=0; i<width*height; i++) {
    unsigned char grey = (unsigned char)(0.299*data[i*3] + 0.587*data[i*3+1] + 0.114*data[i*3+2]);

    data[i*3]   = grey; 
    data[i*3+1] = grey;
    data[i*3+2] = grey;
  }
}

int main(int argc, char *argv[])
{
  struct frame *f = frame_read(0);

  while ((f = frame_read(f))) {
    convert_to_grayscale(f->data, f->width, f->height);
    frame_write(f);
  }

  free(f);
}


