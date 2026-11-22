#include <limits.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char path[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 6);
    if (n < 0 || n >= (ssize_t)sizeof(path) - 6) return 1;
    const char *engine = ".base";
    if (__builtin_cpu_supports("x86-64-v4")) {
        engine = ".v4";
    } else if (__builtin_cpu_supports("x86-64-v3")) {
        engine = ".v3";
    }
    strcpy(path + n, engine);
    execv(path, argv);
    return 1;
}
