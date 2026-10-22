#!/usr/bin/env python3
"""Keep install.sh standalone while retaining separately testable helper sources."""
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[1]
path = root / 'install.sh'
text = path.read_text(encoding='utf-8')
marker = '# BEGIN PORTABLE INSTALLER (generated; edit scripts helpers)\n'
end = '# END PORTABLE INSTALLER\n'
if marker in text:
    legacy = text.split(end, 1)[1]
else:
    legacy = text.removeprefix('#!/bin/sh\n')
helpers = ''.join((root / 'scripts' / name).read_text(encoding='utf-8').removeprefix('#!/bin/sh\n').rstrip() + '\n' for name in ('platform-probe.sh', 'portable-install.sh'))
dispatch = '''case "${1:-}" in
    --check|--preflight) csqtt_probe_main; exit $? ;;
    --portable) shift; csqtt_portable_main "${1:-latest}"; exit $? ;;
esac
# Exact signed9 compatibility remains on its original transaction path.
CS_DISPATCH_RELEASE=$(csqtt_release_value /etc/openwrt_release DISTRIB_RELEASE)
CS_DISPATCH_TARGET=$(csqtt_release_value /etc/openwrt_release DISTRIB_TARGET)
CS_DISPATCH_ARCH=$(csqtt_release_value /etc/openwrt_release DISTRIB_ARCH)
CS_DISPATCH_VENDOR=$(csqtt_metadata_line /etc/glversion)
if [ "$CS_DISPATCH_RELEASE:$CS_DISPATCH_TARGET:$CS_DISPATCH_ARCH:$CS_DISPATCH_VENDOR" != '25.12.5:mediatek/filogic:aarch64_cortex-a53:' ]; then
    csqtt_portable_main "${1:-latest}"; exit $?
fi
'''
result = '#!/bin/sh\n' + marker + helpers + dispatch + end + legacy
if '--check' in sys.argv:
    raise SystemExit(0 if result == text else 'Embedded installer helpers are stale')
path.write_text(result, encoding='utf-8', newline='\n')
