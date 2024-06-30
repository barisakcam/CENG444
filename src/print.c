#include <stdio.h>

// TODO: STRINGS
void __vox_print__(long argc, long argv[]){
    //printf("%ld: %ld: %ld, %ld\n", argc, argv, argv[0], argv[1]);

    if (argc == -1) {
        printf("%s\n", argv);
    } else if (argc == 1) {
        printf("%ld\n", argv[0]);
    }
    else {
        long **temp = (long**) argv;
        printf("[");
        for (int i = 0; i < argc - 1; i ++) {
            printf("%ld, ", temp[0][i]);
        }
        printf("%ld", temp[0][argc - 1]);
        printf("]\n");
    }
}