/*
 * Ultra-low-latency toggle client for macOS Spotlight.
 * Connects to UNIX domain socket and sends TOGGLE command in < 1ms.
 * Automatically spawns daemon if not running.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <errno.h>

static void get_sock_path(char *buf, size_t maxlen) {
    const char *runtime_dir = getenv("XDG_RUNTIME_DIR");
    if (runtime_dir && strlen(runtime_dir) > 0) {
        snprintf(buf, maxlen, "%s/spotlight.sock", runtime_dir);
    } else {
        snprintf(buf, maxlen, "/run/user/%d/spotlight.sock", getuid());
    }
}

int send_command(const char *cmd) {
    char sock_path[512];
    get_sock_path(sock_path, sizeof(sock_path));

    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) return -1;

    struct sockaddr_un addr;
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strncpy(addr.sun_path, sock_path, sizeof(addr.sun_path) - 1);

    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        close(fd);
        return -1;
    }

    size_t len = strlen(cmd);
    ssize_t written = write(fd, cmd, len);
    close(fd);
    return (written == (ssize_t)len) ? 0 : -1;
}

int main(int argc, char **argv) {
    const char *cmd = "TOGGLE\n";
    if (argc > 1) {
        if (strcmp(argv[1], "--show") == 0) cmd = "SHOW\n";
        else if (strcmp(argv[1], "--hide") == 0) cmd = "HIDE\n";
        else if (strcmp(argv[1], "--reload") == 0) cmd = "RELOAD\n";
    }

    if (send_command(cmd) == 0) {
        return 0;
    }

    // If socket connection failed, daemon is not running. Launch daemon.
    const char *home = getenv("HOME");
    char daemon_path[512];
    if (home) {
        snprintf(daemon_path, sizeof(daemon_path), "%s/.local/share/macos-spotlight/daemon.py", home);
    } else {
        strcpy(daemon_path, "/home/bestfortune/.local/share/macos-spotlight/daemon.py");
    }

    pid_t pid = fork();
    if (pid == 0) {
        // Child: launch daemon detached
        setsid();
        execl("/usr/sbin/python3", "python3", daemon_path, (char *)NULL);
        _exit(1);
    }

    // Wait briefly up to 200ms for daemon to initialize socket
    for (int i = 0; i < 20; i++) {
        usleep(10000); // 10ms
        if (send_command(cmd) == 0) {
            return 0;
        }
    }

    return 1;
}
