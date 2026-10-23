"""Boot-console synchronization and fixed, bounded, non-secret diagnostics."""
import re

CONSOLE_LIMIT = 64 * 1024
ACTIVATION = 'Please press Enter to activate this console'
ROOT_PROMPT = r'root@OpenWrt:.*#'
READY = 'CSQTT_CONSOLE_READY'
SIGNALS = (
    ('kernel_panic', r'Kernel panic|not syncing:'),
    ('root_mount_failure', r'Waiting for root device|Waiting for device PARTUUID|VFS: Cannot open root device|VFS: Unable to mount root fs|unknown-block\('),
    ('boot_media_failure', r'No bootable device|Boot failed|not a bootable disk|could not read from boot disk'),
    ('grub', r'\bGRUB\b'),
    ('linux', r'Linux version |Booting Linux|Starting kernel'),
    ('root_mounted', r'VFS: Mounted root'),
    ('openwrt_banner', r'OpenWrt (?:[0-9]{2}\.[0-9]{2}|SNAPSHOT)'),
    ('activation_prompt', re.escape(ACTIVATION)),
    ('root_prompt', r'root@OpenWrt:[^\r\n]{0,200}#'),
    ('console_ready', READY),
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
    """Preserve the stock boot handshake and provision only its temporary key."""
    try:
        phase('boot_activation_wait')
        guest.expect(ACTIVATION)
        phase('boot_console_activate')
        guest.sendline('')
        phase('boot_root_prompt_wait')
        guest.expect(ROOT_PROMPT)
        phase('boot_console_provision')
        guest.sendline("stty -echo; mkdir -p /etc/dropbear; printf '%s\\n' '" + public_key + "' > /etc/dropbear/authorized_keys; chmod 600 /etc/dropbear/authorized_keys; uci set network.lan.proto=dhcp; uci commit network; /etc/init.d/dropbear restart; /etc/init.d/network restart; echo CSQTT_CONSOLE_READY")
        phase('boot_console_ready_wait')
        guest.expect(READY, timeout=90)
    except Exception:
        # Console text may include echoed commands or keys after provisioning.
        # Never emit that text, exceptions, or matched substrings.
        print('OpenWrt VM boot signals: ' + ','.join(boot_signals(getattr(guest, 'before', None))), flush=True)
        raise
