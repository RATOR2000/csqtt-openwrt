"""Boot-console synchronization and fixed, bounded, non-secret diagnostics."""
import re
import secrets
import time

CONSOLE_LIMIT = 64 * 1024
ACTIVATION = 'Please press Enter to activate this console'
ROOT_MARKER = 'CSQTT_ROOT_UID0_'
READY = 'CSQTT_CONSOLE_READY_'
STEP_OK = 'CSQTT_STEP_OK_'
STEP_FAIL = 'CSQTT_STEP_FAIL_'
ROOT_PROBE_WINDOW = 2
ROOT_PROBE_DEADLINE = 180
ROOT_PROBE_ATTEMPTS = 90
SIGNALS = (
    ('kernel_panic', r'Kernel panic|not syncing:'),
    ('root_mount_failure', r'Waiting for root device|Waiting for device PARTUUID|VFS: Cannot open root device|VFS: Unable to mount root fs|unknown-block\('),
    ('boot_media_failure', r'No bootable device|Boot failed|not a bootable disk|could not read from boot disk'),
    ('grub', r'\bGRUB\b'),
    ('linux', r'Linux version |Booting Linux|Starting kernel'),
    ('root_mounted', r'VFS: Mounted root'),
    ('openwrt_banner', r'OpenWrt (?:[0-9]{2}\.[0-9]{2}|SNAPSHOT)'),
    ('activation_prompt', re.escape(ACTIVATION)),
    ('root_uid0', r'(?m)^' + ROOT_MARKER + r'[0-9a-f]{32}\r*$'),
    ('console_ready', r'(?m)^' + READY + r'[0-9a-f]{32}\r*$'),
    ('provision_step_ok', r'(?m)^' + STEP_OK + r'[0-9a-f]{32}\r*$'),
    ('provision_step_failed', r'(?m)^' + STEP_FAIL + r'[0-9a-f]{32}\r*$'),
)


def boot_signals(value):
    """Inspect at most the final 64 KiB; return only predefined signal names."""
    if isinstance(value, str):
        value = value[-CONSOLE_LIMIT:].encode('utf-8', errors='replace')
    if not isinstance(value, bytes):
        value = b''
    text = value[-CONSOLE_LIMIT:].decode('utf-8', errors='replace')
    found = [name for name, pattern in SIGNALS if re.search(pattern, text, re.IGNORECASE)]
    return found or ['unclassified_output' if text else 'no_output']


def _console_step(guest, phase, name, command, ready=False):
    """Confirm each disposable step with UID0 and a fresh echo-proof result."""
    nonce = secrets.token_hex(16)
    prefix = READY if ready else STEP_OK
    phase(name)
    # The leading LF separates a result from a non-newline prompt even when
    # console echo is disabled; the split marker still cannot match an echo.
    guest.sendline('if test "$(id -u)" = 0 && ( ' + command +
                   "); then printf '\\n%s%s\\n' '" + prefix + "' '" + nonce +
                   "'; else printf '\\n%s%s\\n' '" + STEP_FAIL + "' '" + nonce + "'; fi")
    patterns = [r'(?m)^' + re.escape(p + nonce) + r'\r*$' for p in (prefix, STEP_FAIL)]
    if guest.expect(patterns, timeout=90) != 0:
        raise ValueError('Disposable console provisioning step failed')


def _root_shell(guest, phase, timeout_error):
    """Retry only a harmless UID0 probe while askfirst starts its shell."""
    nonce = secrets.token_hex(16)
    # Leading LF separates a non-newline prompt; split arguments keep the full
    # output marker out of echoed commands.
    command = 'test "$(id -u)" = 0 && printf \'\\n%s%s\\n\' \'' + ROOT_MARKER + "' '" + nonce + "'"
    pattern = r'(?m)^' + re.escape(ROOT_MARKER + nonce) + r'\r*$'
    phase('boot_root_check')
    deadline = time.monotonic() + ROOT_PROBE_DEADLINE
    for attempt in range(ROOT_PROBE_ATTEMPTS):
        if time.monotonic() >= deadline:
            raise timeout_error('Disposable UID0 console handshake timeout')
        guest.sendline(command)
        if attempt == 0:
            phase('boot_root_check_wait')
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise timeout_error('Disposable UID0 console handshake timeout')
        try:
            guest.expect(pattern, timeout=min(ROOT_PROBE_WINDOW, remaining))
            return
        except timeout_error:
            if attempt + 1 == ROOT_PROBE_ATTEMPTS:
                raise


def prepare_guest_console(guest, public_key, phase, *, timeout_error):
    """Require an executing UID0 shell, independent of hostname or prompt style."""
    try:
        phase('boot_activation_wait')
        guest.expect(ACTIVATION)
        phase('boot_console_activate')
        guest.sendline('')
        _root_shell(guest, phase, timeout_error)
        # Stock images generate network on first boot, after console activation.
        # Wait for its real LAN section rather than creating one speculatively.
        _console_step(guest, phase, 'boot_network_config_wait',
                      'n=0; while [ "$(uci -q get network.lan 2>/dev/null)" != interface ]; do '
                      'n=$((n+1)); [ "$n" -lt 60 ] || exit 1; sleep 1 || exit 1; done')
        # Minimal official images do not provide stty. Fresh markers are already
        # echo-proof, so disabling console echo is unnecessary.
        _console_step(guest, phase, 'boot_authorized_key',
                      "umask 077 && mkdir -p /etc/dropbear && chmod 700 /etc/dropbear && "
                      "printf '%s\\n' '" + public_key + "' > /etc/dropbear/authorized_keys && "
                      'chmod 600 /etc/dropbear/authorized_keys')
        _console_step(guest, phase, 'boot_network_uci',
                      'test "$(uci -q get network.lan)" = interface && '
                      'uci set network.lan.proto=dhcp && uci commit network')
        _console_step(guest, phase, 'boot_dropbear_restart', '/etc/init.d/dropbear restart')
        _console_step(guest, phase, 'boot_network_restart', '/etc/init.d/network restart', ready=True)
    except Exception:
        # Console text may include echoed commands or keys after provisioning.
        # Never emit that text, exceptions, or matched substrings.
        print('OpenWrt VM boot signals: ' + ','.join(boot_signals(getattr(guest, 'before', None))), flush=True)
        raise
