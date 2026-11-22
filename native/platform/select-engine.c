#include <limits.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char path[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 4);
    if (n < 0 || n >= (ssize_t)sizeof(path) - 4) return 1;
    strcpy(path + n, __builtin_cpu_supports("x86-64-v4") ? ".v4" : ".v3");
    execv(path, argv);
    return 1;
}
