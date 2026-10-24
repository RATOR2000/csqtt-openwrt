/* Test-only command deadline for disposable x86_64 OpenWrt VMs.
 * Compiled statically on the host; never installed as a firmware dependency.
 * TERM gets the last 100ms of the supplied maximum; KILL closes that bound.
 */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t interrupted;
static void remember_signal(int value) { interrupted = value; }

static int64_t milliseconds(void)
{
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0)
        return -1;
    return (int64_t)value.tv_sec * 1000 + value.tv_nsec / 1000000;
}

int main(int argc, char **argv)
{
    struct sigaction action = {0};
    struct timespec pause = {0, 10000000};
    const int signals[] = {SIGHUP, SIGINT, SIGTERM};
    char *end;
    long seconds;
    int status, result = 0;
    int64_t start, deadline, now, kill_at = -1;
    pid_t child, waited;

    if (argc < 3 || !argv[1][0])
        return 125;
    for (char *p = argv[1]; *p; p++)
        if (*p < '0' || *p > '9')
            return 125;
    errno = 0;
    seconds = strtol(argv[1], &end, 10);
    if (errno || *end || seconds < 1 || seconds > 3600)
        return 125;
    start = milliseconds();
    if (start < 0)
        return 125;
    deadline = start + seconds * 1000;
    action.sa_handler = remember_signal;
    sigemptyset(&action.sa_mask);
    for (unsigned i = 0; i < sizeof(signals) / sizeof(signals[0]); i++)
        if (sigaction(signals[i], &action, NULL) != 0)
            return 125;
    child = fork();
    if (child < 0)
        return 125;
    if (child == 0) {
        action.sa_handler = SIG_DFL;
        for (unsigned i = 0; i < sizeof(signals) / sizeof(signals[0]); i++)
            if (sigaction(signals[i], &action, NULL) != 0)
                _exit(125);
        if (setpgid(0, 0) != 0)
            _exit(125);
        execvp(argv[2], argv + 2);
        _exit(errno == ENOENT ? 127 : 126);
    }
    /* Both sides establish the group, closing the fork/exec signal race. */
    if (setpgid(child, child) != 0 && errno != EACCES && errno != ESRCH) {
        kill(child, SIGKILL);
        while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
        return 125;
    }
    for (;;) {
        now = milliseconds();
        if (now < 0) {
            result = 125;
            kill_at = 0;
            now = 0;
        }
        if (kill_at < 0 && interrupted) {
            result = 128 + interrupted;
            kill_at = now + 100;
            kill(-child, interrupted);
        }
        if (kill_at < 0 && now >= deadline - 100) {
            result = 124;
            kill_at = deadline;
            kill(-child, SIGTERM);
        }
        if (kill_at >= 0 && now >= kill_at) {
            kill(-child, SIGKILL);
            while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
            return result;
        }
        /* Keep an exited child unreaped during cancellation, reserving its PID
         * until the process-group KILL. Successful commands retain services
         * they intentionally started, matching the ordinary timeout contract. */
        if (kill_at < 0) {
            waited = waitpid(child, &status, WNOHANG);
            if (waited == child)
                return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
            if (waited < 0 && errno != EINTR) {
                kill(-child, SIGKILL);
                return 125;
            }
        }
        nanosleep(&pause, NULL);
    }
}
