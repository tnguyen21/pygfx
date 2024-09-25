#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <float.h>

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

void kuwahara(unsigned char img[], int width, int height, int ksize) {
    unsigned char* tmp = (unsigned char*)malloc(height * width * 3 * sizeof(unsigned char));
    
    int pad = ksize / 2;
    int stride = width * 3;

    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            double min_var = DBL_MAX;
            int best_mean[3] = {0, 0, 0};

            int regions[4][4] = {
                {-pad, -pad, 0, 0},           // top left
                {-pad, 0, 0, pad},            // top right
                {0, -pad, pad, 0},            // bottom left
                {0, 0, pad, pad}              // bottom right
            };

            for (int r = 0; r < 4; r++) {
                int sum[3] = {0, 0, 0};
                int sum_sq[3] = {0, 0, 0};
                int count = 0;

                for (int i = regions[r][0]; i <= regions[r][2]; i++) {
                    for (int j = regions[r][1]; j <= regions[r][3]; j++) {
                        int yi = y + i;
                        int xj = x + j;
                        if (yi >= 0 && yi < height && xj >= 0 && xj < width) {
                            int idx = (yi * width + xj) * 3;
                            for (int c = 0; c < 3; c++) {
                                int val = img[idx + c];
                                sum[c] += val;
                                sum_sq[c] += val * val;
                            }
                            count++;
                        }
                    }
                }

                if (count > 0) {
                    double var = 0;
                    for (int c = 0; c < 3; c++) {
                        double mean = (double)sum[c] / count;
                        var += (sum_sq[c] - 2 * mean * sum[c] + count * mean * mean) / count;
                    }
                    var /= 3;

                    if (var < min_var) {
                        min_var = var;
                        for (int c = 0; c < 3; c++) {
                            best_mean[c] = sum[c] / count;
                        }
                    }
                }
            }

            int out_idx = (y * width + x) * 3;
            for (int c = 0; c < 3; c++) {
                tmp[out_idx + c] = (uint8_t)best_mean[c];
            }
        }
    }

    memcpy(img, tmp, height * width * 3 * sizeof(unsigned char));
    free(tmp);
}

int main(int argc, char *argv[])
{
  struct frame *f = frame_read(0);

  while ((f = frame_read(f))) {
    kuwahara(f->data, f->width, f->height, 7);
    frame_write(f);
  }

  free(f);
}


