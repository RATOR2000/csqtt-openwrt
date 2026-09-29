'use strict';
'require view';
'require form';
'require uci';
'require ui';
'require csqtt.api as api';
'require csqtt.model as model';

return view.extend({
	load: function() {
		return Promise.all([uci.load('csqtt'), api.call('devices').catch(function() { return { unavailable: true }; })]);
	},
	render: function(data) {
		var m = new form.Map('csqtt', 'Устройства и политики', 'Группа задаёт обычный маршрут устройств. Исключения проверяются сверху вниз: действует первое совпадение для этой группы.');
		this.map = m;
		var discovered = Array.isArray(data[1].devices) ? data[1].devices : [];
		function groupOption(section) {
			var o = section.option(form.ListValue, 'group', 'Группа');
			o.rmempty = false;
			// Rebuild choices after adding or renaming a group in the same form.
			o.renderWidget = function(sectionId, optionIndex, cfgvalue) {
				this.keylist = []; this.vallist = [];
				uci.sections('csqtt', 'group').forEach(function(g) { o.value(g['.name'], E('span', {}, [g.name || g['.name']])); });
				return form.ListValue.prototype.renderWidget.call(this, sectionId, optionIndex, cfgvalue);
			};
			o.validate = function(id, value) {
				return uci.sections('csqtt', 'group').some(function(g) { return g['.name'] === value; }) || 'Сначала добавьте и сохраните группу.';
			};
			return o;
		}
		function actionOption(section, key, label) {
			var o = section.option(form.ListValue, key, label);
			o.value('vpn', 'Через VPN'); o.value('wan', 'Напрямую (WAN)');
			o.default = 'vpn'; o.rmempty = false;
			return o;
		}
		var s = m.section(form.GridSection, 'group', 'Группы', 'Например: «Дом», «Работа», «ТВ». Устройства без группы используют WAN.');
		s.anonymous = true; s.addremove = true; s.addbtntitle = 'Добавить группу';
		s.handleRemove = function(sectionId, ev) {
			var used = ['device', 'rule'].some(function(type) {
				return uci.sections('csqtt', type).some(function(row) { return row.group === sectionId; });
			});
			if (used) {
				ui.addNotification(null, E('p', {}, 'Сначала перенесите или удалите устройства и правила этой группы.'), 'warning');
				return Promise.resolve();
			}
			return form.GridSection.prototype.handleRemove.call(this, sectionId, ev);
		};
		var o = s.option(form.Value, 'name', 'Название'); o.rmempty = false;
		o.validate = function(id, value) { return !!value.trim() && value.length <= 64 && !/[\x00-\x1f\x7f]/.test(value) || 'Введите название длиной от 1 до 64 символов.'; };
		actionOption(s, 'default_action', 'Обычный маршрут');

		s = m.section(form.GridSection, 'device', 'Назначенные устройства', 'Одно устройство может входить только в одну группу. Если телефон меняет частный MAC-адрес, закрепите его для этой Wi-Fi сети.');
		s.anonymous = true; s.addremove = true; s.addbtntitle = 'Добавить устройство';
		o = s.option(form.Value, 'name', 'Название');
		o.validate = function(id, value) { return value.length <= 64 && !/[\x00-\x1f\x7f]/.test(value) || 'Не более 64 символов без управляющих символов.'; };
		var mac = s.option(form.Value, 'mac', 'MAC-адрес'); mac.rmempty = false;
		discovered.forEach(function(d) { if (model.validMac(d.mac)) mac.value(d.mac.toUpperCase(), E('span', {}, [[d.name || 'Без имени', d.ip || '', d.mac].join(' · ')])); });
		mac.validate = function(id, value) {
			if (!model.validMac(value)) return 'Укажите MAC-адрес устройства, например 02:12:34:56:78:9A.';
			var duplicate = uci.sections('csqtt', 'device').some(function(d) {
				var other = mac.formvalue(d['.name']);
				if (other == null) other = d.mac;
				return d['.name'] !== id && String(other || '').toLowerCase() === value.toLowerCase();
			});
			return !duplicate || 'Это устройство уже назначено группе. Измените существующую строку.';
		};
		mac.write = function(id, value) { uci.set('csqtt', id, 'mac', value.toUpperCase()); };
		groupOption(s);

		s = m.section(form.GridSection, 'rule', 'Исключения и приоритеты', 'Перемещайте строки стрелками: верхнее совпавшее правило важнее нижних. Домен включает поддомены. Если совпадений нет, действует обычный маршрут группы.');
		s.anonymous = true; s.addremove = true; s.sortable = true; s.addbtntitle = 'Добавить исключение';
		o = s.option(form.Flag, 'enabled', 'Включено'); o.default = '1'; o.rmempty = false;
		groupOption(s);
		o = s.option(form.Value, 'destination', 'Домен, IPv4 или подсеть'); o.placeholder = 'example.org или 203.0.113.0/24'; o.rmempty = false;
		o.validate = function(id, value) { return model.validDestination(value) || 'Укажите домен без протокола и пути, IPv4-адрес или подсеть IPv4/CIDR.'; };
		o.write = function(id, value) { uci.set('csqtt', id, 'destination', value.toLowerCase().replace(/\.$/, '')); };
		actionOption(s, 'action', 'Маршрут');

		var rows = [E('tr', {}, [E('th', {}, 'Имя'), E('th', {}, 'Адрес IPv4'), E('th', {}, 'MAC-адрес')])];
		discovered.forEach(function(d) { rows.push(E('tr', {}, [E('td', {}, [String(d.name || '—')]), E('td', {}, [String(d.ip || '—')]), E('td', {}, [String(d.mac || '—')])])); });
		return m.render().then(function(node) {
			return E('div', { 'class': 'csqtt-shell' }, [
				E('link', { rel: 'stylesheet', href: L.resource('csqtt/style.css') }),
				E('div', { 'class': 'csqtt-note' }, 'При обрыве туннеля трафик, назначенный VPN, блокируется. Прямые исключения продолжают работать. Доступ к роутеру и локальной сети сохраняется.'),
				node,
				E('h3', {}, 'Обнаружены в локальной сети'),
				discovered.length ? E('div', { 'class': 'csqtt-table-wrap' }, E('table', { 'class': 'table' }, rows)) : E('p', { 'class': 'csqtt-muted' }, data[1].unavailable ? 'Не удалось получить список устройств.' : 'Активных DHCP-записей пока нет. MAC-адрес можно ввести вручную.'),
				E('p', { 'class': 'csqtt-small' }, 'Адреса из этого списка доступны в поле MAC-адрес при добавлении устройства.'),
				E('div', { 'class': 'csqtt-note csqtt-warning' }, 'Для доменных исключений устройства должны использовать DNS роутера. Кеш DNS, общие IP-адреса сайтов и отдельный DNS через HTTPS могут влиять на результат. В группах, использующих VPN, интернет по IPv6 блокируется; локальный IPv6 остаётся доступен.')
			]);
		});
	},
	handleSave: function() { return this.map.save(); }
});
