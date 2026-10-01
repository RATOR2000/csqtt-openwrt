# CSQTT OpenWrt

Клиент оригинального [CSQTT](https://github.com/amurcanov/csqtt) для OpenWrt:
вкладка LuCI, группы устройств, правила по доменам/IP и Android-помощник для
ручной CAPTCHA. Сервер разворачивается из оригинального Android-приложения.

Доступен подписанный экспериментальный
[v0.1.0-preview.2](https://github.com/RATOR2000/csqtt-openwrt/releases/tag/v0.1.0-preview.2)
для GL.iNet GL-MT6000 / OpenWrt 25.12.5 / aarch64_cortex-a53. Установка,
обновление, подключение VK и основные политики IPv4 проверены на этой модели.
Полный список проверок и оставшихся ограничений — в [STATUS.md](docs/STATUS.md).

## Установка или обновление

Выполните от root на указанной модели и версии OpenWrt:

```sh
uclient-fetch -O /tmp/csqtt-install.sh https://github.com/RATOR2000/csqtt-openwrt/releases/download/v0.1.0-preview.2/install.sh && sh /tmp/csqtt-install.sh v0.1.0-preview.2
```

Затем откройте **Службы → CSQTT** в LuCI. Установщик проверяет подписи и
контрольные суммы, сохраняет настройки и создаёт закрытую резервную копию
на роутере. Это предварительный выпуск; условия стабильного выпуска ещё
не выполнены.

## Документация

- [Текущее состояние и следующий шаг](docs/STATUS.md)
- [Требования и интерфейсы компонентов](docs/IMPLEMENTATION.md)
- [Настройка подключения, групп и CAPTCHA](docs/USAGE.md)
- [Сборка, подпись и условия выпуска](docs/BUILD.md)
- [Инструкции для продолжения разработки](AGENTS.md)

Исходное ядро: amurcanov/csqtt v2.1.9. Лицензия: PolyForm Noncommercial 1.0.0;
авторство и обязательные уведомления сохранены в [LICENSE](LICENSE).
