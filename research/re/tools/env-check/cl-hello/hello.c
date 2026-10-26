#include <stdio.h>
/* a float leaf so the listing shows x87 (fmul/fadd) under /arch:IA32 rather than SSE (mulss/addss) */
float __cdecl fma_leaf(float a, float b) { return a * b + 1.0f; }
int main(void) { volatile float x = 1.5f; printf("hello 32-bit %g\n", fma_leaf(x, 2.0f)); return 0; }
