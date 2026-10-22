include $(TOPDIR)/rules.mk

PKG_NAME:=csqtt
PKG_VERSION:=0.1.0
PKG_RELEASE:=$(if $(CSQTT_PACKAGE_RELEASE),$(CSQTT_PACKAGE_RELEASE),1)
PKG_LICENSE:=PolyForm-Noncommercial-1.0.0

include $(INCLUDE_DIR)/package.mk

define Package/csqtt
  SECTION:=net
  CATEGORY:=Network
  TITLE:=CSQTT native client and guarded device policies
  DEPENDS:=+kmod-tun +ip-full +firewall4 +nftables-json $(if $(CSQTT_DNSMASQ_BINARY),+libubus +libubox +libnftnl +libmnl,+dnsmasq-full) $(if $(CSQTT_RUNTIME_DIR),,+ucode +ucode-mod-fs +ucode-mod-uci +ucode-mod-ubus) +jsonfilter +conntrack
endef

define Package/csqtt/conffiles
/etc/config/csqtt
/etc/csqtt/
endef

define Build/Prepare
	$(call Build/Prepare/Default)
	test -n "$(CSQTT_BINARY)"
	test -f "$(CSQTT_BINARY)"
	$(CP) $(CSQTT_BINARY) $(PKG_BUILD_DIR)/csqtt-client
	$(CP) $(if $(CSQTT_PLATFORM_PROBE),$(CSQTT_PLATFORM_PROBE),./files/platform-probe) $(PKG_BUILD_DIR)/platform-probe
	$(if $(CSQTT_DNSMASQ_BINARY),test -f "$(CSQTT_DNSMASQ_BINARY)" && $(CP) "$(CSQTT_DNSMASQ_BINARY)" $(PKG_BUILD_DIR)/dnsmasq,true)
	$(if $(CSQTT_RUNTIME_DIR),test -x "$(CSQTT_RUNTIME_DIR)/usr/libexec/csqtt/ucode" && test -d "$(CSQTT_RUNTIME_DIR)/usr/libexec/csqtt/ucode-runtime",true)
endef

define Build/Compile
endef

define Package/csqtt/install
	$(INSTALL_DIR) $(1)/usr/bin $(1)/usr/libexec/csqtt $(1)/usr/share/csqtt $(1)/usr/share/licenses/csqtt $(1)/etc/config $(1)/etc/init.d $(1)/etc/csqtt $(1)/etc/hotplug.d/iface
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/csqtt-client $(1)/usr/bin/csqtt-client
	$(INSTALL_BIN) ./files/manage $(1)/usr/libexec/csqtt/manage
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/platform-probe $(1)/usr/libexec/csqtt/platform-probe
	$(if $(CSQTT_DNSMASQ_BINARY),$(INSTALL_BIN) $(PKG_BUILD_DIR)/dnsmasq $(1)/usr/libexec/csqtt/dnsmasq,true)
	$(if $(CSQTT_RUNTIME_DIR),$(INSTALL_BIN) "$(CSQTT_RUNTIME_DIR)/usr/libexec/csqtt/ucode" $(1)/usr/libexec/csqtt/ucode,true)
	$(if $(CSQTT_RUNTIME_DIR),$(CP) "$(CSQTT_RUNTIME_DIR)/usr/libexec/csqtt/ucode-runtime" $(1)/usr/libexec/csqtt/,true)
	$(INSTALL_DATA) ./files/lifecycle.sh $(1)/usr/libexec/csqtt/lifecycle.sh
	$(INSTALL_BIN) ./files/monitor $(1)/usr/libexec/csqtt/monitor
	$(INSTALL_BIN) ./files/tun-hook $(1)/usr/libexec/csqtt/tun-hook
	$(INSTALL_DATA) ./files/policy.uc $(1)/usr/share/csqtt/policy.uc
	$(INSTALL_DATA) ./files/runtime.uc $(1)/usr/share/csqtt/runtime.uc
	$(INSTALL_DATA) ./files/health.uc $(1)/usr/share/csqtt/health.uc
	$(INSTALL_DATA) ./files/LICENSE $(1)/usr/share/licenses/csqtt/LICENSE
	$(INSTALL_CONF) ./files/csqtt.config $(1)/etc/config/csqtt
	$(INSTALL_CONF) ./files/guard.nft $(1)/etc/csqtt/policy.nft
	$(INSTALL_BIN) ./files/csqtt.init $(1)/etc/init.d/csqtt
	$(INSTALL_BIN) ./files/csqtt-dns.init $(1)/etc/init.d/csqtt-dns
	$(INSTALL_BIN) ./files/csqtt-health.init $(1)/etc/init.d/csqtt-health
	$(INSTALL_BIN) ./files/90-csqtt $(1)/etc/hotplug.d/iface/90-csqtt
endef

define Package/csqtt/postinst
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] && exit 0
chmod 0700 /etc/csqtt
chmod 0600 /etc/config/csqtt
/etc/init.d/csqtt enable
/etc/init.d/csqtt-health enable
exit 0
endef

define Package/csqtt/prerm
#!/bin/sh
[ -n "$$IPKG_INSTROOT" ] && exit 0
/etc/init.d/csqtt stop
/etc/init.d/csqtt-health stop
# Retain the guard and configuration on package removal. Explicitly deactivate
# policies first if direct connectivity is desired.
exit 0
endef

$(eval $(call BuildPackage,csqtt))
