# CSQTT OpenWrt

Клиент оригинального [CSQTT](https://github.com/amurcanov/csqtt) для OpenWrt:
вкладка LuCI, группы устройств, правила по доменам/IP и Android-помощник для
ручной CAPTCHA. Сервер разворачивается из оригинального Android-приложения.

**В разработке. Проверенного установочного релиза пока нет.** Первая целевая
платформа — GL.iNet GL-MT6000 / OpenWrt 25.12.5 / aarch64_cortex-a53.

- [Текущее состояние и следующий шаг](docs/STATUS.md)
- [Требования и интерфейсы компонентов](docs/IMPLEMENTATION.md)
- [Настройка подключения, групп и CAPTCHA](docs/USAGE.md)
- [Сборка, подпись и условия выпуска](docs/BUILD.md)
- [Инструкции для продолжения разработки](AGENTS.md)

Исходное ядро: amurcanov/csqtt v2.1.9. Лицензия: PolyForm Noncommercial 1.0.0;
авторство и обязательные уведомления сохранены в [LICENSE](LICENSE).
