# Installer checkpoint

Updated 2026-09-30. Owner: installer_validate subagent; root owns release signing,
SDK builds, release workflow and repository checkpoints.

## Source

`install.sh` restricts the board to GL-MT6000 and checks OpenWrt 25.12.5,
mediatek/filogic, aarch64_cortex-a53 and 64 MiB free overlay space. It accepts
exactly one core, CAPTCHA and LuCI APK, with bounded filenames and sizes.
Native APK verification uses a temporary directory containing only the pinned
release public key. No unsigned-package bypass is used, and APK_CONFIG is set
to /dev/null to avoid inherited unsafe verification settings.

On stock routers without OpenSSL, only after all three native APK signatures
pass, the script installs openssl-util through signed official 25.12.5 feeds.
That dependency/cache can remain after a later manifest verification failure.
The signed manifest and APK checksums must pass before DNS, configuration,
CSQTT packages or persistent trust are changed.

The script copies the installed APK database/world to a private temporary root,
disables all package scripts there, checks DNS removal for unrelated package
removals, simulates the release dependency solution, then stages it with cache
predownload. A fresh clone of the original database proves the same solution
works offline. The live install uses that cache and adds only release package
roots plus dnsmasq-full, rather than making every dependency a world root.
Official feed URLs and the 25.12.5 kernel ABI are pinned in the script.

Before replacing plain dnsmasq, its exact installed version must be downloaded
and signature checked. A private UCI archive, DHCP file and APK world snapshot
are retained under /etc/csqtt/backups. On installation, restart or trapped signal
failure, first-install DNS replacement removes newly introduced CSQTT roots and
restores the cached original dnsmasq package, DHCP and world. Failed diagnostics
are retained privately; successful temporary downloads are removed. Upgrade
failure does not claim rollback of all previously installed package versions.
An upgrade restarts the core service, whose init script respects the enabled
UCI setting and keeps policy guards on transport stop. CAPTCHA is restarted
after both first installs and upgrades so the new binary is used.

## Checks and limits

- Git bundled `usr/bin/sh.exe -n install.sh`: passed.
- `node --check tests/installer/fake.cjs`: passed.
- `python tests/installer/installer_test.py`: 5 tests / 26 scenario runs passed
  in 101 seconds before the final upgrade restart edit.
- `python -m unittest tests.installer.installer_test.InstallerTest.test_first_install_and_repeat tests.installer.installer_test.InstallerTest.test_install_service_and_signal_failures_restore_exact_dns tests.installer.installer_test.InstallerTest.test_upgrade_transport_restart_failure_retains_full_dns`:
  3 tests / 9 scenario runs passed in 58 seconds after the upgrade restart edit.
  Together these runs cover all 27 scenarios in the current six test methods.
- Final shell syntax, Node syntax and scoped `git diff --check`: passed.

The harness runs the real shell source with only literal router paths rewritten
into disposable `.work/installer-tests` directories. Command doubles simulate
APK signatures/solver, JSON filtering, services and archive creation; checksum
checks use Node crypto. It never writes host /etc, /lib or live router paths.

Source review used the official OpenWrt 25.12.5 APK Makefile (APK 3.0.5 commit
b5a31c0d865342ad80be10d68f1bb3d3ad9b0866) and the corresponding Alpine apk-tools
add/query/cache/database sources. Native APK signatures, staged-root cache
behavior, BusyBox/ash, real package scripts and real router DNS rollback have
not been executed. No signed installable release exists yet.

Root-relative key/cache semantics were confirmed in that commit: context.c
loads an explicit keys_dir with apk_dir_foreach_file(ac->root_fd,...), and
database.c opens cache_dir with openat(db->root_fd,...). Copied database files
are dereferenced with cp -aL so symlinks cannot alias live database files.

Next: exercise real signed SDK
APKs with native APK 3.0.5 in disposable OpenWrt roots before publishing an
installer command. Live GL-MT6000 testing still requires connection details
and task scope. Power loss or SIGKILL cannot run shell rollback traps.
