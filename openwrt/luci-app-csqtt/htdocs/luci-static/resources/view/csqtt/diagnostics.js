'use strict';
'require view';
'require ui';
'require csqtt.api as api';
'require csqtt.model as model';

var checks = {
	config: ['Настройки подключения', 'Проверьте адрес сервера, пароль, хеши и число потоков.'],
	dnsmasq: ['DNS с поддержкой nftset', 'Нужен пакет dnsmasq-full с поддержкой nftset.'],
	dnsmasq_nftset: ['DNS с поддержкой nftset', 'Нужен пакет dnsmasq-full с поддержкой nftset.'],
	tun: ['Интерфейс TUN', 'Проверьте установку kmod-tun и состояние соединения.'],
	firewall: ['Межсетевой экран', 'Проверьте firewall4 и nftables.'],
	policy: ['Политики устройств', 'Проверьте группы, назначения устройств и исключения.'],
	pbr: ['Совместимость с PBR', 'Отключите другую службу маршрутизации по правилам перед включением CSQTT.'],
	mwan3: ['Совместимость с mwan3', 'Отключите mwan3 перед включением CSQTT.'],
	broker: ['Помощник CAPTCHA', 'Проверьте установку и запуск csqtt-captcha.']
};

function summary(result) {
	var status = result.status || {}, core = status.core || status;
	var rows = [
		['Соединение', model.stateLabel(core.state)],
		['Защита политик', status.policies_active === true ? 'Включена' : 'Не активна']
	];
	(Array.isArray(result.checks) ? result.checks : []).forEach(function(check) {
		var entry = checks[check.name];
		if (entry) rows.push([entry[0], check.ok === true ? 'В порядке' : 'Требует внимания', check.ok === true ? '' : entry[1]]);
	});
	return rows;
}

return view.extend({
	load: function() { return api.call('diagnostics').catch(function() { return { unavailable: true }; }); },
	render: function(initial) {
		var self = this, output = E('div'), report = '';
		function update(result) {
			if (result.unavailable) {
				report = 'CSQTT: служба диагностики недоступна.';
				output.replaceChildren(E('p', { 'class': 'csqtt-note csqtt-warning' }, 'Не удалось получить диагностику. Проверьте, что пакет csqtt установлен, и повторите запрос.'));
				return;
			}
			var rows = summary(result);
			report = ['Диагностика CSQTT', new Date().toISOString()].concat(rows.map(function(row) { return row.filter(Boolean).join(': '); })).join('\n');
			output.replaceChildren(E('div', { 'class': 'csqtt-table-wrap' }, E('table', { 'class': 'table' }, rows.map(function(row) {
				return E('tr', {}, [E('th', {}, row[0]), E('td', {}, row[1]), E('td', {}, row[2] || '')]);
			}))));
		}
		function refresh() { return api.call('diagnostics').then(update).catch(function() { update({ unavailable: true }); }); }
		update(initial);
		return E('div', { 'class': 'csqtt-shell' }, [
			E('link', { rel: 'stylesheet', href: L.resource('csqtt/style.css') }),
			E('h2', {}, 'Диагностика CSQTT'),
			E('p', { 'class': 'csqtt-muted' }, 'Проверки подключения и маршрутизации. Отчёт содержит только состояние компонентов, без пароля, хешей звонков и ссылок CAPTCHA.'),
			output,
			E('div', { 'class': 'csqtt-actions' }, [
				E('button', { 'class': 'cbi-button cbi-button-action', click: ui.createHandlerFn(self, refresh) }, 'Обновить проверки'),
				E('button', { 'class': 'cbi-button', click: ui.createHandlerFn(self, function() {
					var url = URL.createObjectURL(new Blob([report + '\n'], { type: 'text/plain;charset=utf-8' }));
					var link = E('a', { href: url, download: 'csqtt-diagnostics.txt' });
					link.click(); window.setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
				}) }, 'Скачать отчёт'),
				E('button', { 'class': 'cbi-button', click: ui.createHandlerFn(self, function() {
					return api.call('apply').then(refresh).catch(function() {
						ui.addNotification(null, E('p', {}, 'Не удалось применить сохранённые политики. Проверьте настройки и повторите диагностику.'), 'error');
						return refresh();
					});
				}) }, 'Повторно применить политики')
			]),
			E('div', { 'class': 'csqtt-note' }, 'Если ВКонтакте запросит CAPTCHA, откройте «Обзор» и выберите «Решить на Android». При изменении групп или исключений нажмите «Сохранить и применить» на странице политик.'),
			E('p', { 'class': 'csqtt-small' }, 'Проверки компонентов не подтверждают доступность каждого сайта или завершение CAPTCHA. Фактическое состояние туннеля отображается на странице «Обзор».')
		]);
	},
	handleSaveApply: null, handleSave: null, handleReset: null
});
