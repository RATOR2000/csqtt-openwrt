include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI interface for CSQTT
LUCI_DEPENDS:=+csqtt +csqtt-captcha +luci-base +luci-mod-admin-full +luci-theme-bootstrap +luci-i18n-base-ru +uhttpd +uhttpd-mod-ubus +rpcd +rpcd-mod-ucode
LUCI_PKGARCH:=all
PKG_VERSION:=0.1.0
PKG_RELEASE:=$(if $(CSQTT_PACKAGE_RELEASE),$(CSQTT_PACKAGE_RELEASE),1)
PKG_LICENSE:=PolyForm-Noncommercial-1.0.0
PKG_MAINTAINER:=CSQTT OpenWrt contributors

include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
