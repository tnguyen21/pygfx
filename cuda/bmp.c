#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#pragma pack(push, 1)
typedef struct {
    uint16_t type;
    uint32_t size;
    uint16_t reserved1;
    uint16_t reserved2;
    uint32_t offset;
} BMPHeader;

typedef struct {
    uint32_t size;
    int32_t width;
    int32_t height;
    uint16_t planes;
    uint16_t bits_per_pixel;
    uint32_t compression;
    uint32_t image_size;
    int32_t x_pixels_per_meter;
    int32_t y_pixels_per_meter;
    uint32_t colors_used;
    uint32_t important_colors;
} BMPInfoHeader;
#pragma pack(pop)

uint8_t*** read_bmp_to_tensor(const char* filename, int* width, int* height) {
    FILE* file = fopen(filename, "rb");
    if (!file) {
        fprintf(stderr, "Error opening file\n");
        return NULL;
    }

    BMPHeader header;
    BMPInfoHeader info_header;

    fread(&header, sizeof(BMPHeader), 1, file);
    fread(&info_header, sizeof(BMPInfoHeader), 1, file);

    if (header.type != 0x4D42) {
        fprintf(stderr, "Not a BMP file\n");
        fclose(file);
        return NULL;
    }

    if (info_header.bits_per_pixel != 24) {
        fprintf(stderr, "Only 24-bit BMP files are supported\n");
        fclose(file);
        return NULL;
    }

    *width = info_header.width;
    *height = info_header.height;

    int padding = (4 - ((*width * 3) % 4)) % 4;

    uint8_t*** tensor = (uint8_t***)malloc(*height * sizeof(uint8_t**));
    for (int i = 0; i < *height; i++) {
        tensor[i] = (uint8_t**)malloc(*width * sizeof(uint8_t*));
        for (int j = 0; j < *width; j++) {
            tensor[i][j] = (uint8_t*)malloc(3 * sizeof(uint8_t));
        }
    }

    fseek(file, header.offset, SEEK_SET);

    for (int i = *height - 1; i >= 0; i--) {
        for (int j = 0; j < *width; j++) {
            fread(tensor[i][j], sizeof(uint8_t), 3, file);
            // Swap BGR to RGB
            uint8_t temp = tensor[i][j][0];
            tensor[i][j][0] = tensor[i][j][2];
            tensor[i][j][2] = temp;
        }
        fseek(file, padding, SEEK_CUR);
    }

    fclose(file);
    return tensor;
}

void free_tensor(uint8_t*** tensor, int height, int width) {
    for (int i = 0; i < height; i++) {
        for (int j = 0; j < width; j++) {
            free(tensor[i][j]);
        }
        free(tensor[i]);
    }
    free(tensor);
}

void convert_to_greyscale(uint8_t*** tensor, int height, int width) {
    for (int i = 0; i < height; i++) {
        for (int j = 0; j < width; j++) {
            // Calculate greyscale value using the luminosity method
            uint8_t grey = (uint8_t)(0.21 * tensor[i][j][0] + 0.72 * tensor[i][j][1] + 0.07 * tensor[i][j][2]);
            
            // Set all color channels to the grey value
            tensor[i][j][0] = grey;
            tensor[i][j][1] = grey;
            tensor[i][j][2] = grey;
        }
    }
}

void write_tensor_to_bmp(const char* filename, uint8_t*** tensor, int width, int height) {
    FILE* file = fopen(filename, "wb");
    if (!file) {
        fprintf(stderr, "Error opening file for writing\n");
        return;
    }

    int padding = (4 - ((width * 3) % 4)) % 4;
    int rowSize = width * 3 + padding;
    int imageSize = rowSize * height;

    BMPHeader header = {
        .type = 0x4D42,
        .size = sizeof(BMPHeader) + sizeof(BMPInfoHeader) + imageSize,
        .reserved1 = 0,
        .reserved2 = 0,
        .offset = sizeof(BMPHeader) + sizeof(BMPInfoHeader)
    };

    BMPInfoHeader infoHeader = {
        .size = sizeof(BMPInfoHeader),
        .width = width,
        .height = height,
        .planes = 1,
        .bits_per_pixel = 24,
        .compression = 0,
        .image_size = imageSize,
        .x_pixels_per_meter = 2835, // 72 DPI
        .y_pixels_per_meter = 2835, // 72 DPI
        .colors_used = 0,
        .important_colors = 0
    };

    fwrite(&header, sizeof(BMPHeader), 1, file);
    fwrite(&infoHeader, sizeof(BMPInfoHeader), 1, file);

    uint8_t padBuffer[3] = {0, 0, 0};

    for (int i = height - 1; i >= 0; i--) {
        for (int j = 0; j < width; j++) {
            // Write BGR (reverse order)
            fputc(tensor[i][j][2], file);
            fputc(tensor[i][j][1], file);
            fputc(tensor[i][j][0], file);
        }
        fwrite(padBuffer, 1, padding, file);
    }

    fclose(file);
}

int main(int argc, char* argv[]) {
    if (argc != 3) {
        printf("Usage: %s <input_file.bmp> <output_file.bmp>\n", argv[0]);
        printf("Converts a BMP image to greyscale.\n");
        return 1;
    }

    const char* input_filename = argv[1];
    const char* output_filename = argv[2];

    // Check if input file has .bmp extension
    const char* input_ext = strrchr(input_filename, '.');
    if (!input_ext || strcmp(input_ext, ".bmp") != 0) {
        fprintf(stderr, "Error: Input file must have .bmp extension\n");
        return 1;
    }

    // Check if output file has .bmp extension
    const char* output_ext = strrchr(output_filename, '.');
    if (!output_ext || strcmp(output_ext, ".bmp") != 0) {
        fprintf(stderr, "Error: Output file must have .bmp extension\n");
        return 1;
    }

    int width, height;
    uint8_t*** tensor = read_bmp_to_tensor(input_filename, &width, &height);

    if (tensor) {
        printf("BMP file read successfully!\n");
        printf("Width: %d, Height: %d\n", width, height);

        // Convert the image to greyscale
        convert_to_greyscale(tensor, height, width);

        // Write the modified tensor back to a new BMP file
        write_tensor_to_bmp(output_filename, tensor, width, height);
        printf("Greyscale image saved as %s\n", output_filename);

        // Free the tensor
        free_tensor(tensor, height, width);
    } else {
        fprintf(stderr, "Failed to read input file: %s\n", input_filename);
        return 1;
    }

    return 0;
}
