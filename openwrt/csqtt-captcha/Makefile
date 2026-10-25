include $(TOPDIR)/rules.mk

PKG_NAME:=csqtt-captcha
PKG_VERSION:=0.1.0
PKG_RELEASE:=$(if $(CSQTT_PACKAGE_RELEASE),$(CSQTT_PACKAGE_RELEASE),1)
PKG_LICENSE:=PolyForm-Noncommercial-1.0.0
include $(INCLUDE_DIR)/package.mk

define Package/csqtt-captcha
  SECTION:=net
  CATEGORY:=Network
  TITLE:=CSQTT Android CAPTCHA bridge
  DEPENDS:=+csqtt +ca-bundle
endef

define Package/csqtt-captcha/conffiles
/etc/csqtt/captcha/
endef

define Build/Prepare
	$(call Build/Prepare/Default)
	test -f "$(CSQTT_CAPTCHA_BINARY)"
	$(CP) $(CSQTT_CAPTCHA_BINARY) $(PKG_BUILD_DIR)/csqtt-captcha
endef

define Build/Compile
endef

define Package/csqtt-captcha/install
	$(INSTALL_DIR) $(1)/usr/bin $(1)/etc/init.d $(1)/etc/hotplug.d/iface
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/csqtt-captcha $(1)/usr/bin/csqtt-captcha
	$(INSTALL_BIN) ./files/csqtt-captcha.init $(1)/etc/init.d/csqtt-captcha
	$(INSTALL_BIN) ./files/91-csqtt-captcha $(1)/etc/hotplug.d/iface/91-csqtt-captcha
endef

$(eval $(call BuildPackage,csqtt-captcha))
