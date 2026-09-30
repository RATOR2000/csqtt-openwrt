'use strict';
'require view';
'require form';
'require uci';
'require ui';
'require csqtt.model as model';

return view.extend({
	load: function() { return uci.load('csqtt'); },
	render: function() {
		var self = this, m = new form.Map('csqtt', 'Подключение CSQTT', 'Введите параметры сервера, развёрнутого из Android. Изменения вступят в силу после «Сохранить и применить».');
		this.map = m;
		var s = m.section(form.NamedSection, 'main', 'client');
		s.addremove = false;
		s.tab('connection', 'Сервер и звонки');
		s.tab('advanced', 'Дополнительно');
		var o = s.taboption('connection', form.Flag, 'enabled', 'Запускать автоматически', 'Поднимать VPN после загрузки роутера.');
		o.rmempty = false;
		o = s.taboption('connection', form.Value, 'peer', 'Адрес сервера', 'Адрес и порт, например vpn.example:46000 или 203.0.113.7:46000.');
		o.rmempty = false; o.placeholder = 'vpn.example:46000';
		o.validate = function(id, value) { return model.validPeer(value) || 'Укажите адрес и порт от 1 до 65535.'; };
		var peer = o;
		o = s.taboption('connection', form.Value, 'password', 'Пароль подключения');
		o.password = true; o.rmempty = false;
		o.validate = function(id, value) { return model.validPassword(value) || 'Пароль: от 4 до 128 байт UTF-8, без управляющих символов и знака |.'; };
		var password = o;
		this.callOptions = [];
		[0, 1, 2, 3, 4, 5].forEach(function(slot) {
			var call = s.taboption('connection', form.Value, '_vk_link_' + (slot + 1), 'Ссылка на звонок ' + (slot + 1), slot === 0 ? 'Вставьте полную ссылку VK. Каждый звонок — в отдельном поле; остальные поля можно оставить пустыми.' : null);
			call.placeholder = 'https://vk.com/call/join/…'; call.rmempty = slot !== 0;
			call.cfgvalue = function(id) {
				var values = uci.get('csqtt', id, 'vk_hashes') || [];
				if (!Array.isArray(values)) values = [values];
				return model.callLink(values[slot]);
			};
			call.validate = function(id, value) { return (!value && slot !== 0) || model.validCallLink(value) || 'Вставьте полную ссылку вида https://vk.com/call/join/… или https://vk.ru/call/join/…'; };
			// Only the existing list belongs in UCI; the six fields are a view of it.
			call.write = slot === 0 ? function(id) { return uci.set('csqtt', id, 'vk_hashes', self.callValues(id).map(model.normalizeHash)); } : function() {};
			call.remove = function() {};
			self.callOptions.push(call);
		});
		o = s.taboption('advanced', form.ListValue, 'workers', 'Число потоков', 'Начните с 9. Больше потоков расходуют больше памяти. На каждый хеш доступно до 27 потоков, всего до 126.');
		for (var n = 9; n <= 126; n += 9) o.value(String(n));
		o.default = '9'; o.rmempty = false; this.workersOption = o;
		o = s.taboption('advanced', form.ListValue, 'obfs', 'Маскировка');
		o.value('video', 'Видеозвонок'); o.value('audio', 'Аудиозвонок'); o.default = 'video'; o.rmempty = false;
		o = s.taboption('advanced', form.ListValue, 'turn_transport', 'Транспорт TURN');
		o.value('udp', 'UDP'); o.value('tcp_tls', 'TCP / TLS'); o.default = 'udp'; o.rmempty = false;
		o = s.taboption('advanced', form.ListValue, 'vk_auth_mode', 'Режим авторизации ВКонтакте');
		o.value('vkcalls', 'VK Calls'); o.value('legacy', 'Совместимый режим'); o.default = 'vkcalls'; o.rmempty = false;
		o = s.taboption('advanced', form.ListValue, 'fingerprint', 'Профиль браузера');
		o.value('firefox', 'Firefox'); o.value('chrome', 'Chrome'); o.default = 'firefox'; o.rmempty = false;
		o.value('edge', 'Edge'); o.value('safari', 'Safari'); o.value('opera', 'Opera');
		o = s.taboption('advanced', form.Value, 'client_ids', 'Идентификаторы приложений VK', 'Числовые идентификаторы через запятую.');
		o.default = '8202606,6287487'; o.rmempty = false;
		o.validate = function(id, value) { return value.length <= 128 && /^[0-9]+(?:,[0-9]+)*$/.test(value) || 'Введите числовые ID через запятую, не более 128 символов.'; };
		o = s.taboption('advanced', form.Value, 'turn_host', 'Свой сервер TURN', 'Оставьте пустым для получения адреса от ВКонтакте.');
		o.validate = function(id, value) { return !value || model.validHost(value) || 'Укажите имя сервера или IP-адрес без протокола и порта.'; };
		o = s.taboption('advanced', form.Value, 'turn_port', 'Порт TURN'); o.datatype = 'port';
		o = s.taboption('advanced', form.Value, 'tun_device', 'Интерфейс туннеля');
		o.default = 'csqtt0'; o.rmempty = false;
		o.validate = function(id, value) { return value === 'csqtt0' || 'В этой версии используется интерфейс csqtt0.'; };
		o = s.taboption('advanced', form.Value, 'captcha_timeout_secs', 'Время ожидания CAPTCHA, с');
		o.default = '180'; o.datatype = 'range(30,600)'; o.rmempty = false;
		o = s.taboption('advanced', form.DynamicList, 'lan_device', 'Локальные интерфейсы', 'Политики применяются только к устройствам за этими интерфейсами.');
		o.default = ['br-lan']; o.rmempty = false; this.lanOption = o;
		o.validate = function(id, value) {
			// DynamicList also validates its empty input for adding the next item.
			if (value === '') return true;
			var list = Array.isArray(value) ? value : [value];
			return list.length > 0 && list.every(function(v) { return /^[a-zA-Z0-9_.:-]{1,15}$/.test(v) && v !== 'csqtt0' && v !== 'lo'; }) || 'Укажите локальный интерфейс, например br-lan.';
		};
		o = s.taboption('advanced', form.Value, 'vpn_dns', 'DNS для запросов через VPN', 'Запросы VPN-групп проходят через туннель; при обрыве прямого резервного DNS нет.');
		o.datatype = 'ip4addr'; o.default = '1.1.1.1'; o.rmempty = false;
		o = s.taboption('advanced', form.Value, 'wan_dns', 'DNS для прямых запросов');
		o.datatype = 'ip4addr'; o.default = '9.9.9.9'; o.rmempty = false;
		var input = E('input', { type: 'password', placeholder: 'csqtt://connect?v=2&host=…', autocomplete: 'new-password', spellcheck: false, 'aria-label': 'Ссылка подключения CSQTT' });
		var importPanel = E('div', { 'class': 'csqtt-import' }, [
			E('h3', {}, 'Импорт из Android'),
			E('p', { 'class': 'csqtt-muted' }, 'Вставьте ссылку подключения CSQTT v2. Она заполнит форму; для применения сохраните изменения.'), input,
			E('div', { 'class': 'csqtt-actions' }, E('button', { 'class': 'cbi-button cbi-button-action', click: ui.createHandlerFn(self, function() {
				try {
					var imported = model.parseLink(input.value);
					peer.getUIElement('main').setValue(imported.peer);
					password.getUIElement('main').setValue(imported.password);
					if (imported.vk_hashes !== null) self.callOptions.forEach(function(option, slot) { option.getUIElement('main').setValue(model.callLink(imported.vk_hashes[slot])); });
					input.value = '';
					ui.addNotification(null, E('p', {}, 'Параметры перенесены в форму. Проверьте ссылки на звонки и нажмите «Сохранить и применить».'), 'info');
				} catch (e) {
					ui.addNotification(null, E('p', {}, 'Не удалось импортировать ссылку. Нужна ссылка CSQTT v2 с адресом, портом и паролем.'), 'error');
				} finally {
					input.value = '';
				}
			}) }, 'Заполнить из ссылки'))
		]);
		return m.render().then(function(node) { return E('div', { 'class': 'csqtt-shell' }, [E('link', { rel: 'stylesheet', href: L.resource('csqtt/style.css') }), importPanel, node, E('p', { 'class': 'csqtt-note' }, 'CAPTCHA сначала обрабатывается автоматически. Если понадобится ручное подтверждение, ссылка для Android появится на странице «Обзор». MTU туннеля — 1300.')]); });
	},
	callValues: function(id) {
		return this.callOptions.map(function(option) { return String(option.formvalue(id) || '').trim(); }).filter(function(value) { return value !== ''; });
	},
	handleSave: function(ev) {
		var lan = this.lanOption.formvalue('main');
		if (!Array.isArray(lan) || this.lanOption.validate('main', lan) !== true) {
			ui.addNotification(null, E('p', {}, 'Добавьте локальный интерфейс, например br-lan.'), 'error');
			return Promise.reject(new Error('Некорректные локальные интерфейсы.'));
		}
		var links = this.callValues('main'), values = links.map(model.normalizeHash), workers = Number(this.workersOption.formvalue('main'));
		if (!links.every(model.validCallLink) || !model.validHashes(values)) {
			ui.addNotification(null, E('p', {}, 'Добавьте от одной до шести разных полных ссылок на звонки VK.'), 'error');
			return Promise.reject(new Error('Некорректные ссылки на звонки.'));
		}
		if (workers % 9 !== 0 || workers < 9 || workers > model.workerLimit(values.length)) {
			ui.addNotification(null, E('p', {}, 'Уменьшите число потоков: максимум 27 на хеш и 126 на соединение.'), 'error');
			return Promise.reject(new Error('Некорректное число потоков.'));
		}
		return this.map.save();
	}
});
