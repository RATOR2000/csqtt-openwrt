# GNU Make conditional contract from OpenWrt v25.12.5 include/package.mk:325.
# This fixture tests the switch semantics, not an SDK build or GPL compliance.
.PHONY: check
check:
ifneq ($(CONFIG_AUTOREMOVE),)
	@echo cleanup-enabled
else
	@echo source-preserved
endif
