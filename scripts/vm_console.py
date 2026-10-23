"""Boot-console synchronization and fixed, bounded, non-secret diagnostics."""
import re
import secrets

CONSOLE_LIMIT = 64 * 1024
ACTIVATION = 'Please press Enter to activate this console'
ROOT_MARKER = 'CSQTT_ROOT_UID0_'
READY = 'CSQTT_CONSOLE_READY_'
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


def prepare_guest_console(guest, public_key, phase):
    """Require an executing UID0 shell, independent of hostname or prompt style."""
    try:
        phase('boot_activation_wait')
        guest.expect(ACTIVATION)
        phase('boot_console_activate')
        guest.sendline('')
        nonce = secrets.token_hex(16)
        phase('boot_root_check')
        # Split arguments keep the full output marker out of echoed commands.
        guest.sendline('test "$(id -u)" = 0 && printf \'%s%s\\n\' \'' + ROOT_MARKER + "' '" + nonce + "'")
        phase('boot_root_check_wait')
        guest.expect(r'(?m)^' + re.escape(ROOT_MARKER + nonce) + r'\r*$')
        phase('boot_console_provision')
        guest.sendline("set -eu; stty -echo; mkdir -p /etc/dropbear; printf '%s\\n' '" + public_key + "' > /etc/dropbear/authorized_keys; chmod 600 /etc/dropbear/authorized_keys; uci set network.lan.proto=dhcp; uci commit network; /etc/init.d/dropbear restart; /etc/init.d/network restart; printf '%s%s\\n' '" + READY + "' '" + nonce + "'")
        phase('boot_console_ready_wait')
        guest.expect(r'(?m)^' + re.escape(READY + nonce) + r'\r*$', timeout=90)
    except Exception:
        # Console text may include echoed commands or keys after provisioning.
        # Never emit that text, exceptions, or matched substrings.
        print('OpenWrt VM boot signals: ' + ','.join(boot_signals(getattr(guest, 'before', None))), flush=True)
        raise
