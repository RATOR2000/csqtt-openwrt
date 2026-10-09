'use strict';
'require view';
'require poll';
'require ui';
'require csqtt.api as api';
'require csqtt.model as model';

return view.extend({
	load: function() { return api.call('status').catch(function() { return { unavailable: true }; }); },
	render: function(initial) {
		var self = this, pairing = null, currentChallenge = null, pairingTimer = null;
		var statusNode = E('div'), captchaNode = E('div');
		function notify() { ui.addNotification(null, E('p', {}, 'Не удалось связаться со службой CSQTT. Откройте диагностику.'), 'error'); }
		function closePairing() {
			if (pairingTimer) window.clearTimeout(pairingTimer);
			pairingTimer = null;
			if (pairing) {
				pairing.field.value = '';
				if (pairing.link) pairing.link.removeAttribute('href');
				pairing = null; ui.hideModal();
			}
		}
		function showPairing(result) {
			if (!model.validPairing(result, Date.now() / 1000) || !currentChallenge ||
				new URL(result.uri).searchParams.get('id') !== currentChallenge.id) throw new Error('invalid_pairing');
			closePairing();
			var field = E('textarea', { 'class': 'csqtt-pairing', readonly: true, spellcheck: false, autocomplete: 'off', 'aria-label': 'Одноразовая ссылка для Android' });
			field.value = result.uri;
			var helperLink = null;
			if (/Android/i.test(window.navigator.userAgent || '')) {
				// Keep the launch on a direct user tap. Chrome can return to LuCI if
				// the installed helper cannot handle it; the fallback contains no grant.
				var fallback = new URL(L.url('admin/services/csqtt/overview'), window.location.origin);
				if (fallback.origin !== window.location.origin || !/^https?:$/.test(fallback.protocol) || fallback.search || fallback.hash) throw new Error('invalid_fallback');
				var intentUri = 'intent://pair' + new URL(result.uri).search +
					'#Intent;scheme=csqtt-helper;package=org.csqtt.openwrt.helper;S.browser_fallback_url=' + encodeURIComponent(fallback.href) + ';end';
				helperLink = E('a', { href: intentUri, 'class': 'cbi-button cbi-button-action', rel: 'noreferrer' }, 'Открыть CSQTT Helper');
			}
			pairing = { id: currentChallenge.id, expires_at: Number(result.expires_at) };
			pairing.field = field; pairing.link = helperLink;
			ui.showModal('Решить CAPTCHA на Android', [
				E('p', {}, 'Подключите телефон к локальной сети роутера и откройте ссылку в CSQTT Helper. Ссылка одноразовая; не публикуйте её.'),
				E('p', {}, helperLink ? 'Нажмите «Открыть CSQTT Helper». Если приложение не открылось, скопируйте ссылку и вставьте её в помощник вручную. После возврата на «Обзор» создайте новую ссылку.' : 'Скопируйте ссылку и вставьте её в CSQTT Helper на Android. Затем нажмите в приложении «Открыть проверку VK».'),
				field,
				E('p', { 'class': 'csqtt-small' }, 'Действует до ' + new Date(pairing.expires_at * 1000).toLocaleTimeString()),
				E('div', { 'class': 'csqtt-actions' }, [
					helperLink,
					E('button', { 'class': 'cbi-button', click: ui.createHandlerFn(self, function() {
						if (window.navigator.clipboard && window.isSecureContext) return window.navigator.clipboard.writeText(field.value).catch(function() { field.focus(); field.select(); });
						field.focus(); field.select();
					}) }, 'Скопировать ссылку'),
					E('button', { 'class': 'cbi-button', click: closePairing }, 'Скрыть')
				])
			]);
			pairingTimer = window.setTimeout(closePairing, Math.max(0, pairing.expires_at * 1000 - Date.now()));
		}
		function card(label, value, detail) {
			return E('div', { 'class': 'csqtt-card' }, [E('div', { 'class': 'csqtt-card-label' }, [label]), E('div', { 'class': 'csqtt-card-value' }, [value]), E('div', { 'class': 'csqtt-subtle' }, [detail || ''])]);
		}
		function update(status) {
			var tunnel = status.tunnel || {}, core = status.core || status.transport || status;
			var state = status.unavailable ? 'unknown' : status.state || core.state || (status.running ? 'connecting' : 'stopped');
			statusNode.replaceChildren(E('div', { 'class': 'csqtt-hero' }, [
				E('p', { 'class': 'csqtt-eyebrow' }, 'CSQTT · OpenWrt'),
				E('h2', {}, 'Ваше соединение'),
				E('span', { 'class': 'csqtt-status', 'data-state': state, 'role': 'status' }, status.unavailable ? 'Служба недоступна' : model.stateLabel(state)),
				E('p', { 'class': 'csqtt-muted' }, 'Устройства используют VPN по выбранным политикам. Остальная сеть подключается напрямую.')
			]), E('div', { 'class': 'csqtt-cards' }, [
				card('Туннель', tunnel.ip || core.tunnel_ip || '—', tunnel.device || core.tun_device || 'csqtt0'),
				card('Активные потоки', String(core.active_workers || 0), 'Соединения с узлами TURN'),
				card('Получено', model.bytes(core.bytes_down), 'За текущий сеанс'),
				card('Отправлено', model.bytes(core.bytes_up), 'За текущий сеанс')
			]), E('div', { 'class': 'csqtt-note' }, status.policies_active ?
				'Защита политик включена. Если VPN остановится, предназначенный ему трафик будет заблокирован; прямые исключения продолжат работать.' :
				'Создайте группу устройств и назначьте ей VPN на странице «Устройства и политики». Не назначенные группе устройства используют обычное подключение.'));
			if (status.error || core.error_code) statusNode.appendChild(E('p', { 'class': 'csqtt-note csqtt-warning' }, 'Не удалось установить соединение. Проверьте настройки и откройте диагностику.'));
			var challenge = status.captcha || core.captcha;
			if (challenge && (!challenge.id || Number(challenge.expires_at) <= Date.now() / 1000)) challenge = null;
			currentChallenge = challenge;
			if (pairing && (!challenge || challenge.id !== pairing.id || pairing.expires_at <= Date.now() / 1000)) closePairing();
			captchaNode.replaceChildren();
			if (!challenge) return;
			var content = [E('h3', {}, 'Подтверждение ВКонтакте'), E('p', {}, challenge.state === 'auto' ? 'Клиент пытается решить CAPTCHA автоматически.' : 'Для продолжения соединения решите CAPTCHA на Android, подключённом к этой локальной сети.')];
			content.push(E('button', { 'class': 'cbi-button cbi-button-action', click: ui.createHandlerFn(self, function() {
				return api.call('captcha_begin').then(function(result) {
					showPairing(result);
					return refresh();
				}).catch(notify);
			}) }, 'Решить на Android'));
			content.push(E('button', { 'class': 'cbi-button', style: 'margin-left:.6rem', click: ui.createHandlerFn(self, function() {
				closePairing();
				return api.call('captcha_cancel').then(refresh).catch(notify);
			}) }, 'Отменить запрос'));
			captchaNode.appendChild(E('div', { 'class': 'csqtt-note csqtt-warning' }, content));
		}
		function refresh() { return api.call('status').then(update).catch(function() { closePairing(); update({ unavailable: true }); }); }
		function action(method) { return ui.createHandlerFn(self, function() { closePairing(); return api.call(method).then(refresh).catch(notify); }); }
		update(initial);
		poll.add(refresh, 5);
		return E('div', { 'class': 'csqtt-shell' }, [
			E('link', { rel: 'stylesheet', href: L.resource('csqtt/style.css') }), statusNode,
			E('div', { 'class': 'csqtt-actions' }, [
				E('button', { 'class': 'cbi-button cbi-button-positive', click: action('start') }, 'Подключить'),
				E('button', { 'class': 'cbi-button', click: action('restart') }, 'Переподключить'),
				E('button', { 'class': 'cbi-button cbi-button-negative', click: action('stop') }, 'Остановить'),
				E('a', { 'class': 'cbi-button cbi-button-action', href: L.url('admin/services/csqtt/settings') }, 'Настроить подключение')
			]), captchaNode,
			E('p', { 'class': 'csqtt-subtle' }, 'Сервер и список его клиентов управляются в оригинальном приложении CSQTT для Android и на серверной веб-панели.')
		]);
	},
	handleSaveApply: null, handleSave: null, handleReset: null
});
