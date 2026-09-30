# Installer checkpoint

Updated 2026-09-30. Owner: apk_signature_fix subagent; root owns release signing,
SDK builds, release workflow and repository checkpoints.

Authoritative latest result: CI36717531786 at b21f3dd, SDK job109894580250,
passed the complete native APK suite: strict/negative signatures, payload
audit, packaged ARM64 smoke, real TUN lifecycle, staged dependency cache,
offline install and exact baseline/world rollback. The query enumeration fix
is verified. Corrected secret1 passed actual pinned-key preflight. Project
signing verified the core APK but left CAPTCHA/LuCI unsigned: APK3.0.5 adbsign
retains signatures_written across its file arguments. build-sdk now calls a
new process per APK, rejects diagnostics and strictly verifies each. This same
per-file pattern passed native fixture signing; full project rerun pending.
The prior8cf1ae4 last-byte tamper fixture sometimes changed compression padding;
uncompressed packages with a known signed description byte fix this. The
corrected real native suite passed at e430c0b, including exact rollback.
Older pending/failure notes below are history.
Stock OpenWrt mbedTLS APK, BusyBox ash, package scripts and live DNS rollback
still require actual router acceptance.

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
disables package scripts for every staged add/del operation, checks DNS removal
for unrelated package
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
- After the APK3 read/mutation option correction:
  `python tests/installer/installer_test.py`: all 6 tests / 27 scenarios passed
  in 121.871 seconds. Shell/Node syntax, compilation of the native runner's
  four Python blocks, and scoped `git diff --check` passed.

The harness runs the real shell source with only literal router paths rewritten
into disposable `.work/installer-tests` directories. Command doubles simulate
APK signatures/solver, JSON filtering, services and archive creation; checksum
checks use Node crypto. It never writes host /etc, /lib or live router paths.

Source review used the official OpenWrt 25.12.5 APK Makefile (APK 3.0.5 commit
b5a31c0d865342ad80be10d68f1bb3d3ad9b0866) and the corresponding Alpine apk-tools
add/query/cache/database sources. CI 36683192758 at aa5b35f compiled all three
SDK APKs and passed strict/negative signatures, payload permissions and
dependencies, upstream license, packaged ARM64 smoke and real Linux TUN
lifecycle. Its native transaction suite stopped at the offline installed-state
assertion because an unqualified query returned []. The enumeration correction
awaits CI; complete offline/rollback acceptance, BusyBox/ash, real package
scripts and real router DNS rollback remain unverified. No signed installable
release exists yet.

Root-relative key/cache semantics were confirmed in that commit: context.c
loads an explicit keys_dir with apk_dir_foreach_file(ac->root_fd,...), and
database.c opens cache_dir with openat(db->root_fd,...). Copied database files
are dereferenced with cp -aL so symlinks cannot alias live database files.

Next: complete the corrected native APK3 installed-state and exact rollback
checks in disposable roots before publishing an installer command.
Live GL-MT6000 testing still requires connection details
and task scope. Power loss or SIGKILL cannot run shell rollback traps.

## Prepared native APK check

`scripts/test-native-apk.sh /absolute/sdk/staging_dir/host/bin/apk /absolute/dist`
is intended to run as root in the isolated Linux CI job. All APK commands have
an explicit disposable --root, and all installation/removal commands disable
package scripts. It creates an ephemeral P-256 key, signs copies of all three
compiled SDK APKs, verifies the correct key, rejects a wrong key, and checks
that the original build artifacts were unchanged. Private fixture keys are
removed on success and failure; they are never printed or committed.

Native mkpkg/mkndx fixtures use versioned DNS providers, an explicit
!csqtt-native-old conflict in the full provider's dependencies, and an
application with a transitive dependency. Checks cover missing dependencies,
conflict rejection before DNS removal, isolated stage/predownload, dependency
remaining outside world roots, relative key/cache paths, unchanged baseline,
missing offline cache rejection, network-free installation after stopping the
loopback-only repository server, disabled script status, and exact original
DNS/world restoration. Unsigned and byte-tampered APKs must also be rejected.

CI 36640955080 at b30a0b76 failed before completing the first signed SDK APK
verification. In the pinned APK source, adbsign parses the existing package
before loading public trust and returns zero even after a per-file failure.
The runner now scopes --allow-untrusted to adbsign transforming copies of local
build artifacts or removing fixture signatures. Every verify, mkpkg, mkndx and
install command retains strict trust. Unexpected adbsign diagnostics abort the
runner because its exit status alone cannot prove success. Each synthetic APK
and its signed index are explicitly verified before cache/install checks.

The payload audit extracts each verified SDK copy into a separate disposable
directory with APK3 extract, which never executes package scripts. It checks
the core/CAPTCHA ARM64 architecture and LuCI's all architecture, required
dependencies, the executables and LuCI resources, mode 0600 for the UCI config
and guard, and the original upstream license. Packaged/stripped client and
broker executables then run the existing Cortex-A53 QEMU smoke script. These
checks and the packaged client's real Linux TUN lifecycle passed in
CI 36683192758 at aa5b35f.

Pinned app_extract.c, app_info.c and app_query.c confirmed that --no-scripts
belongs to the add/del option group. Native installed-package queries and
installer stage_info now use read applets without that unsupported flag;
mutations retain it. The installer command double rejects the unsupported
combination so the isolated scenarios cover the real CLI boundary.

The same CI reached offline installation but its snapshot query returned [].
Pinned [query.c](https://github.com/alpinelinux/apk-tools/blob/b5a31c0d865342ad80be10d68f1bb3d3ad9b0866/src/query.c)
iterates explicit selection terms; app_query does not set empty_matches_all,
while app_info does. root_query now uses --installed --all-matches with a
quoted '*' selection term. A real CLI baseline assertion requires exactly the
original package/version/installed status before any stage work, preventing
empty baseline and rollback snapshots from comparing equal. Offline status
must be exactly ['installed'], which also rejects APK's singular broken-script
status. Installer queries already provide names and stage_info enumerates
installed packages by design, so this correction does not change install.sh.

Review of [context.c](https://github.com/alpinelinux/apk-tools/blob/b5a31c0d865342ad80be10d68f1bb3d3ad9b0866/src/context.c),
[app_adbsign.c](https://github.com/alpinelinux/apk-tools/blob/b5a31c0d865342ad80be10d68f1bb3d3ad9b0866/src/app_adbsign.c)
and [adb.c](https://github.com/alpinelinux/apk-tools/blob/b5a31c0d865342ad80be10d68f1bb3d3ad9b0866/src/adb.c)
confirmed the cause. APK3 trust compares the key fingerprint, so fixture.pem
and csqtt-public.pem naming is valid; relative key/cache paths remain valid.
No installer change is needed for this signing-only failure.

Git bundled sh -n, Python block compilation, local baseline snapshot assertion
checks (valid original accepted; [] and broken status rejected), and scoped
git diff --check passed after the enumeration fix.
**The corrected suite passed CI36685991129; see the authoritative result above.**
Root owns the CI/build-sdk hookup. The SDK host binary uses the OpenSSL backend;
passing this runner will still leave the stock router's mbedTLS APK backend,
real CSQTT package scripts and live router rollback unverified.
