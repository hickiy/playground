#include <stdio.h>

__declspec(dllexport) void hello_from_c() {
    printf("Hello, World!\n");
}

// gcc -shared -o hello.dll hello.c