'use strict';
'require view';
'require uci';
'require ui';
'require csqtt.api as api';
'require csqtt.model as model';

return view.extend({
	load: function() {
		return Promise.all([uci.load('csqtt'), api.call('devices').catch(function() { return { devices: [] }; })]);
	},
	render: function(data) {
		var self = this, main = uci.get('csqtt', 'main') || {};
		var overview = L.url('admin/services/csqtt/overview');
		if (!model.needsSetup(main)) return E('div', { 'class': 'csqtt-shell' }, [
			E('h2', {}, 'CSQTT уже настроен'),
			E('p', {}, 'Сохранённые настройки используются и после обновления. Управляйте подключением на странице «Обзор».'),
			E('a', { href: overview, 'class': 'cbi-button cbi-button-positive' }, 'Открыть обзор'),
			E('a', { href: L.url('admin/services/csqtt/settings'), 'class': 'cbi-button' }, 'Изменить подключение')
		]);
		var page = E('div', { 'class': 'csqtt-shell csqtt-setup' }), body = E('div'), message = E('p', { role: 'status', 'class': 'csqtt-note' });
		var step = 0, busy = false, finished = false, timer = null, cancelled = false, attempts = 0, deadline = 0;
		var peer = E('input', { type: 'text', autocomplete: 'off', placeholder: 'vpn.example:46000', 'aria-label': 'Адрес сервера' });
		var password = E('input', { type: 'password', autocomplete: 'new-password', 'aria-label': 'Пароль подключения' });
		var imported = E('input', { type: 'password', autocomplete: 'new-password', placeholder: 'csqtt://connect?v=2&host=…', 'aria-label': 'Ссылка подключения из Android' });
		peer.value = main.peer || ''; password.value = main.password || '';
		var hashes = main.vk_hashes || []; if (!Array.isArray(hashes)) hashes = [hashes];
		var links = [0, 1, 2, 3, 4, 5].map(function(slot) {
			var field = E('input', { type: 'text', autocomplete: 'off', spellcheck: false, placeholder: 'https://vk.com/call/join/…', 'aria-label': 'Ссылка на звонок ' + (slot + 1) });
			field.value = model.callLink(hashes[slot]); return field;
		});
		var selected = {}, seen = {}, devices = [];
		// Retain any saved assignment from an interrupted/manual configuration.
		(uci.sections('csqtt', 'device') || []).forEach(function(device) { seen[String(device.mac || '').toLowerCase()] = true; });
		((data[1] || {}).devices || []).forEach(function(device) {
			var mac = String(device.mac || '').toLowerCase();
			if (!model.validMac(mac) || seen[mac]) return;
			seen[mac] = true;
			devices.push({ mac: mac, name: String(device.name || '').slice(0, 64), ip: String(device.ip || '').slice(0, 45) });
		});
		function text(value) { message.replaceChildren(value); }
		function button(label, handler, positive) {
			return E('button', { type: 'button', 'class': 'cbi-button ' + (positive ? 'cbi-button-positive' : ''), click: ui.createHandlerFn(self, handler) }, label);
		}
		function field(label, node, help) { return E('label', { 'class': 'csqtt-setup-field' }, [E('strong', {}, label), node, help ? E('span', { 'class': 'csqtt-subtle' }, help) : null]); }
		function connection() {
			var calls = links.map(function(node) { return String(node.value || '').trim(); }).filter(function(value) { return value !== ''; });
			if (!model.validPeer(peer.value) || !model.validPassword(password.value) || !calls.every(model.validCallLink) || !model.validHashes(calls.map(model.normalizeHash))) {
				text('Проверьте адрес с портом, пароль и от одной до шести разных полных ссылок на звонки VK. Пароль: 4–128 байт, без знака | и управляющих символов.'); return null;
			}
			return { peer: peer.value, password: password.value, vk_hashes: calls.map(model.normalizeHash) };
		}
		function show() {
			text('Шаг ' + (step + 1) + ' из 3. До завершения мастера VPN не включается.');
			if (step === 0) {
				body.replaceChildren(E('h3', {}, '1. Подключение к вашему серверу'),
					E('p', {}, 'Возьмите эти параметры в исходном приложении CSQTT для Android или у владельца сервера.'),
					field('Ссылка подключения из Android (необязательно)', imported, 'Заполняет поля ниже. Ссылка содержит пароль: не публикуйте её.'),
					button('Заполнить из ссылки', function() {
						try {
							var value = model.parseLink(imported.value); peer.value = value.peer; password.value = value.password;
							if (value.vk_hashes !== null) links.forEach(function(node, i) { node.value = model.callLink(value.vk_hashes[i]); });
							text('Параметры перенесены в поля. Проверьте ссылки на звонки и продолжите.');
						} catch (e) { text('Не удалось прочитать ссылку. Используйте ссылку CSQTT v2 или заполните поля вручную.'); }
						imported.value = '';
					}),
					field('Адрес сервера и порт', peer, 'Например vpn.example:46000. Это адрес сервера CSQTT, а не ссылка на звонок.'),
					field('Пароль подключения', password, 'Пароль вашего сервера CSQTT.'),
					E('p', {}, 'Ссылки на звонки ВКонтакте: первая обязательна. Каждый звонок — в отдельном поле.'),
					E('div', {}, links.map(function(node, i) { return field('Звонок ' + (i + 1), node); })),
					button('Далее: устройства', function() { if (connection()) { step = 1; show(); } }, true));
			} else if (step === 1) {
				var rows = devices.map(function(device) {
					var check = E('input', { type: 'checkbox', 'aria-label': 'VPN для ' + device.mac, change: function(ev) { selected[device.mac] = ev.target.checked; } });
					check.checked = selected[device.mac] === true;
					return E('label', { 'class': 'csqtt-setup-device' }, [check, E('span', {}, [device.name || 'Без имени', ' · ', device.ip || 'IP неизвестен', ' · ', device.mac])]);
				});
				body.replaceChildren(E('h3', {}, '2. Устройства для VPN'),
					E('p', {}, 'Отметьте устройства вашей локальной сети. Мастер создаст для них группу «VPN». Неотмеченные устройства используют обычный WAN.'),
					E('p', {}, 'При обрыве VPN выбранные устройства останутся без доступа в Интернет. Доступ к роутеру по локальному адресу сохранится. Для этой группы внешний IPv6 блокируется.'),
					E('div', {}, rows.length ? rows : [E('p', {}, 'Устройства пока не обнаружены. Можно завершить без выбора и добавить их позже в «Устройства и политики».')]),
					E('p', { 'class': 'csqtt-subtle' }, 'Имена и IP показаны по DHCP/ARP и могут быть устаревшими. Правило привязывается к MAC; частный MAC телефона может меняться.'),
					E('div', { 'class': 'csqtt-actions' }, [button('Назад', function() { step = 0; show(); }), button('Далее: подключение', function() { step = 2; show(); }, true)]));
			} else {
				var count = devices.filter(function(device) { return selected[device.mac]; }).length;
				body.replaceChildren(E('h3', {}, '3. Сохранить и подключить'),
					E('p', {}, ['Устройств для VPN: ', String(count), '. После нажатия ниже клиент сохранит параметры и включит подключение, в том числе после перезагрузки.']),
					E('p', {}, 'Автоматический профиль начинает с 9 потоков. Автовосстановление выключено; его можно включить позже. Отдельные группы, правила сайтов и дополнительные параметры доступны после настройки.'),
					E('p', {}, 'Проверка занимает до 90 секунд и использует наблюдения DNS/HTTPS через VPN. Если VK запросит CAPTCHA, мастер предложит открыть «Обзор» и подтвердить её в Android Helper.'),
					E('div', { 'class': 'csqtt-actions' }, [button('Назад', function() { step = 1; show(); }), button('Завершить и подключить', finish, true)]));
			}
		}
		function boundedStatus() {
			return new Promise(function(resolve, reject) {
				var limit = window.setTimeout(function() { reject(new Error('status_timeout')); }, Math.max(1, Math.min(8000, deadline - Date.now())));
				api.call('status').then(function(value) { window.clearTimeout(limit); resolve(value); }, function() { window.clearTimeout(limit); reject(new Error('status_unavailable')); });
			});
		}
		function outcome(value, status) {
			var labels = {
				healthy: 'Подключение проверено: DNS и HTTPS через VPN доступны. Проверьте нужный сайт с выбранного устройства.',
				captcha: 'ВКонтакте запросил CAPTCHA. Откройте «Обзор», нажмите «Решить на Android» и подтвердите запрос в CSQTT Helper. Мастер не считает подключение проверенным.',
				incompatible: 'Активация заблокирована проверкой совместимости. Откройте диагностику. Параметры сохранены.',
				stopped: 'Клиент остановлен. Параметры сохранены; откройте «Обзор» для управления.',
				wan_down: 'Нет подтверждённого доступа через WAN. Проверьте обычное подключение роутера; проверка VPN не завершена.',
				error: 'Подключение не подтверждено. Проверьте параметры сервера и откройте диагностику.',
				timeout: 'За 90 секунд доступ через VPN не подтверждён. Клиент продолжает подключение. Откройте «Обзор» или диагностику; повторная настройка не нужна.'
			};
			var challenge = status && (status.captcha || (status.core || {}).captcha);
			var captcha = challenge && challenge.id && Number(challenge.expires_at) > Date.now() / 1000;
			text(labels[value] + (value === 'healthy' && captcha ? ' Для части соединений VK запрашивает CAPTCHA. Остальные потоки работают; подтверждение доступно на странице «Обзор».' : ''));
			body.replaceChildren(E('h3', {}, 'Настройки сохранены'), E('div', { 'class': 'csqtt-actions' }, [
				E('a', { href: overview, 'class': 'cbi-button cbi-button-positive' }, value === 'captcha' || captcha ? 'Открыть обзор и CAPTCHA' : 'Открыть обзор'),
				E('a', { href: L.url('admin/services/csqtt/policies'), 'class': 'cbi-button' }, 'Устройства и политики'),
				E('a', { href: L.url('admin/services/csqtt/diagnostics'), 'class': 'cbi-button' }, 'Диагностика')
			]));
		}
		function observe() {
			if (cancelled) return Promise.resolve();
			if (attempts >= 30 || Date.now() >= deadline) { outcome('timeout'); return Promise.resolve(); }
			attempts++;
			return boundedStatus().catch(function() { return { unavailable: true }; }).then(function(status) {
				if (cancelled) return;
				var value = model.setupCheck(status);
				if (Date.now() >= deadline) { outcome('timeout'); return; }
				if (value !== 'waiting') { outcome(value, status); return; }
				text('Подключаемся и проверяем DNS/HTTPS через VPN… Осталось до ' + Math.max(0, Math.ceil((deadline - Date.now()) / 1000)) + ' с.');
				timer = window.setTimeout(observe, Math.min(3000, Math.max(0, deadline - Date.now())));
			});
		}
		function finish() {
			if (busy || finished) return Promise.resolve();
			var value = connection(); if (!value) return Promise.resolve();
			// Recheck the loaded configuration before constructing first-run rows.
			if (!model.needsSetup(uci.get('csqtt', 'main'))) { text('Настройка уже сохранена. Откройте «Обзор».'); return Promise.resolve(); }
			var scope = main.lan_device || 'auto';
			if (!Array.isArray(scope)) scope = [scope];
			if (scope.indexOf('auto') >= 0) {
				scope = (data[1] || {}).lan_devices;
				if (!Array.isArray(scope) || !scope.length || !scope.every(function(device) { return /^[a-zA-Z0-9_.:-]{1,15}$/.test(device) && device !== 'auto' && device !== 'lo' && device !== 'csqtt0'; })) {
					text('Не удалось определить локальную сеть. Откройте «Подключение → Дополнительно» и укажите локальные интерфейсы. VPN не включён.'); return Promise.resolve();
				}
			}
			busy = true;
			if (!main.lan_device || (Array.isArray(main.lan_device) ? main.lan_device.indexOf('auto') >= 0 : main.lan_device === 'auto')) uci.set('csqtt', 'main', 'lan_device', scope);
			Object.keys(value).forEach(function(key) { uci.set('csqtt', 'main', key, value[key]); });
			if (!main.workers) uci.set('csqtt', 'main', 'workers', 'auto');
			var chosen = devices.filter(function(device) { return selected[device.mac]; });
			if (chosen.length) {
				var group = 'setupvpn', suffix = 0;
				while (uci.get('csqtt', group)) group = 'setupvpn' + (++suffix);
				// Named ID remains stable when rpcd persists the new section, so
				// device references cannot retain a temporary LuCI new ID.
				uci.add('csqtt', 'group', group); uci.set('csqtt', group, 'name', 'VPN'); uci.set('csqtt', group, 'default_action', 'vpn');
				chosen.forEach(function(device) {
					var id = uci.add('csqtt', 'device');
					uci.set('csqtt', id, 'name', device.name || device.mac); uci.set('csqtt', id, 'mac', device.mac); uci.set('csqtt', id, 'group', group);
				});
			}
			uci.set('csqtt', 'main', 'setup_complete', '1');
			text('Сохраняем параметры и запускаем подключение…');
			body.replaceChildren(E('p', {}, 'Подождите. Выбранные устройства будут защищены правилами VPN при запуске.'));
			return uci.save().then(function() { return api.commitConfig(); }).then(function() {
				finished = true;
				// Only the user's final action enables transport. Existing start
				// applies the same guarded transaction as the Overview button.
				return api.call('start');
			}).then(function() {
				imported.value = ''; password.value = ''; links.forEach(function(node) { node.value = ''; });
				deadline = Date.now() + 90000; return observe();
			}).catch(function() {
				text('Не удалось завершить сохранение или запуск. Проверьте «Обзор» и диагностику. Подключение не подтверждено; не повторяйте мастер, если настройки уже сохранены.');
				body.replaceChildren(E('a', { href: overview, 'class': 'cbi-button' }, 'Открыть обзор'));
			}).then(function() { busy = false; });
		}
		if (window.addEventListener) window.addEventListener('pagehide', function() {
			cancelled = true; if (timer) window.clearTimeout(timer);
			imported.value = ''; password.value = ''; links.forEach(function(node) { node.value = ''; });
		}, { once: true });
		page.appendChild(E('link', { rel: 'stylesheet', href: L.resource('csqtt/style.css') }));
		page.appendChild(E('h2', {}, 'Первая настройка CSQTT')); page.appendChild(message); page.appendChild(body); show();
		return page;
	},
	handleSaveApply: null, handleSave: null, handleReset: null
});
