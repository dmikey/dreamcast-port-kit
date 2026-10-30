#define _POSIX_C_SOURCE 200809L
#include <execinfo.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void sh4_dump_native_stack(const char *tag) {
    void *frames[48];
    int count = backtrace(frames, 48);
    fprintf(stderr, "[STACK %s]\n", tag);
    backtrace_symbols_fd(frames, count, STDERR_FILENO);
}

static void runtime_fault(int sig) {
    sh4_dump_native_stack("native-fault");
    _Exit(128 + sig);
}

extern void port_runtime_trace(void);
static void runtime_trace(int sig) {
    (void)sig;
    port_runtime_trace();
    sh4_dump_native_stack("requested-sample");
}

void sh4_install_crash_handler(void) {
    struct sigaction handler = {0};
    handler.sa_handler = runtime_fault;
    sigemptyset(&handler.sa_mask);
    sigaction(SIGSEGV, &handler, NULL);
    sigaction(SIGBUS, &handler, NULL);
    sigaction(SIGABRT, &handler, NULL);
    sigaction(SIGILL, &handler, NULL);
    handler.sa_handler = runtime_trace;
    sigaction(SIGUSR1, &handler, NULL);
}
