# Superseded GL vendor experiments

These unqualified prototypes are retained for source history and isolated tests.
They are excluded from official OpenWrt packages, installers, runtime imports,
and the native release qualification pipeline. They are not installation-ready.

`policy.uc` is the frozen prototype renderer, including its original helper
functions; modern production policy lives in `openwrt/csqtt/files/policy.uc`.
The Node harness loads this copy only for isolated historical regression tests.
