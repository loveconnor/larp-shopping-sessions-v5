#include <cpuid.h>
#include <limits.h>
#include <string.h>
#include <unistd.h>

static unsigned cpu_family(unsigned signature) {
    unsigned base = (signature >> 8) & 15;
    return base == 15 ? base + ((signature >> 20) & 255) : base;
}

static int use_family19_profile(void) {
    unsigned signature, ebx, ecx, edx;
    return __builtin_cpu_is("amd") && __get_cpuid(1, &signature, &ebx, &ecx, &edx)
        && cpu_family(signature) == 0x19;
}

int main(int argc, char **argv) {
    char path[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path) - 6);
    if (n < 0 || n >= (ssize_t)sizeof(path) - 6) return 1;
    const char *engine = ".base";
    if (__builtin_cpu_supports("x86-64-v4")) {
        engine = ".n4";
        if (__builtin_cpu_supports("avx512vbmi2")) {
            if (use_family19_profile()) engine = ".p19";
            else if (__builtin_cpu_is("intel")) engine = ".istr";
            else engine = ".wide";
        }
    } else if (__builtin_cpu_supports("x86-64-v3")) {
        engine = ".v3";
    }
    strcpy(path + n, engine);
    execv(path, argv);
    return 1;
}
