'use strict';
'require baseclass';

function fail() {
	// Never include the pasted URL, a password, or a hash in an error.
	throw new Error('Некорректная ссылка CSQTT v2. Проверьте адрес сервера, порт, пароль и хеши.');
}

function validHost(host) {
	if (typeof host !== 'string' || !host || host.length > 253 || /[\s\x00-\x1f\x7f/@?#%\\]/.test(host))
		return false;
	if (host.indexOf(':') !== -1) {
		try { return new URL('http://[' + host.replace(/^\[|\]$/g, '') + ']/').hostname.length > 0; }
		catch (e) { return false; }
	}
	if (/^[0-9.]+$/.test(host))
		return host.split('.').length === 4 && host.split('.').every(function(p) { return /^(0|[1-9][0-9]{0,2})$/.test(p) && +p <= 255; });
	return host.replace(/\.$/, '').split('.').every(function(p) { return /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i.test(p); });
}

function validPeer(value) {
	var match = typeof value === 'string' && value.match(/^(\[[^\]]+\]|[^:]+):([0-9]+)$/);
	return !!match && validHost(match[1]) && +match[2] >= 1 && +match[2] <= 65535;
}

function normalizeHash(value) {
	return String(value || '').trim().replace(/^(?:https?:\/\/)?(?:m\.)?vk\.(?:com|ru)\/call\/join\//i, '').replace(/[?#].*$/, '');
}

function validHash(value) {
	return typeof value === 'string' && /^[A-Za-z0-9_-]{16,1024}$/.test(value);
}

function callLink(value) {
	var hash = normalizeHash(value);
	return validHash(hash) ? 'https://vk.com/call/join/' + hash : '';
}

function validCallLink(value) {
	if (typeof value !== 'string' || !/^https?:\/\//i.test(value.trim())) return false;
	try {
		var url = new URL(value.trim());
		return !url.username && !url.password && !url.port && /^(?:m\.)?vk\.(?:com|ru)$/i.test(url.hostname) &&
			/^\/call\/join\/[A-Za-z0-9_-]{16,1024}$/.test(url.pathname) && validHash(normalizeHash(value));
	} catch (e) { return false; }
}

function validPassword(value) {
	if (typeof value !== 'string' || /[\x00-\x1f\x7f-\x9f|]/.test(value)) return false;
	var bytes = new TextEncoder().encode(value).length;
	return bytes >= 4 && bytes <= 128;
}

function validHashes(values) {
	return Array.isArray(values) && values.length >= 1 && values.length <= 6 &&
		values.every(validHash) && new Set(values).size === values.length;
}

function validMac(value) {
	return typeof value === 'string' && /^(?:[0-9a-f]{2}:){5}[0-9a-f]{2}$/i.test(value) &&
		value !== '00:00:00:00:00:00' && (parseInt(value.slice(0, 2), 16) & 1) === 0;
}

function validPairing(value, now) {
	if (!value || typeof value.uri !== 'string' || value.uri.length > 2048 ||
		!Number.isFinite(Number(value.expires_at)) || Number(value.expires_at) <= now) return false;
	try {
		var uri = new URL(value.uri), params = uri.searchParams;
		if (uri.protocol !== 'csqtt-helper:' || uri.hostname !== 'pair' || uri.port || uri.pathname ||
			uri.username || uri.password || uri.hash) return false;
		var keys = Array.from(params.keys());
		return keys.length === 5 && new Set(keys).size === 5 &&
			keys.every(function(k) { return ['host', 'port', 'grant', 'pin', 'id'].indexOf(k) >= 0; }) &&
			validHost(params.get('host')) && /^[0-9]+$/.test(params.get('port')) &&
			+params.get('port') >= 1 && +params.get('port') <= 65535 &&
			/^[0-9a-f]{64}$/i.test(params.get('grant')) && /^[0-9a-f]{64}$/i.test(params.get('pin')) &&
			/^[A-Za-z0-9_-]{1,128}$/.test(params.get('id'));
	} catch (e) { return false; }
}

function parseLink(raw) {
	if (typeof raw !== 'string' || raw.length > 16384) fail();
	var match = raw.trim().match(/^csqtt:\/\/connect\?([^#]+)$/i);
	if (!match) fail();
	var params = Object.create(null);
	var query = match[1].replace(/&amp;/g, '&');
	// Older Android builds also exported parameters without separators.
	if (query.indexOf('&') < 0 && query.indexOf(';') < 0) {
		var compact = query.match(/^v=2host=(.+?)peer=([0-9]+)password=(.+)$/);
		if (!compact) fail();
		// Only split a hash suffix if it can be unambiguously identified.
		var suffix = compact[3].match(/^(.*?)hashes=([^=]+)$/);
		params.v = '2'; params.host = compact[1]; params.peer = compact[2];
		params.password = suffix ? suffix[1] : compact[3];
		if (suffix) params.hashes = suffix[2];
	} else {
		query.split(/[&;]/).forEach(function(part) {
			var pos = part.indexOf('=');
			if (pos < 1) fail();
			var key;
			try { key = decodeURIComponent(part.slice(0, pos)); } catch (e) { fail(); }
			if (['v', 'host', 'peer', 'password', 'hashes'].indexOf(key) < 0 || Object.prototype.hasOwnProperty.call(params, key)) fail();
			params[key] = part.slice(pos + 1);
		});
	}
	function decode(key) {
		if (typeof params[key] !== 'string') fail();
		try { return decodeURIComponent(params[key]); } catch (e) { fail(); }
	}
	if (decode('v') !== '2') fail();
	var host = decode('host'), port = decode('peer'), password = decode('password');
	if (!validHost(host) || !/^[0-9]+$/.test(port) || +port < 1 || +port > 65535 || !validPassword(password)) fail();
	var hashes = null;
	if (Object.prototype.hasOwnProperty.call(params, 'hashes')) {
		hashes = params.hashes.split('+').map(function(h) {
			try { return normalizeHash(decodeURIComponent(h)); } catch (e) { fail(); }
		});
		if (!validHashes(hashes)) fail();
	}
	host = host.replace(/^\[|\]$/g, '');
	return { peer: (host.indexOf(':') >= 0 ? '[' + host + ']' : host) + ':' + Number(port), password: password, vk_hashes: hashes };
}

function validDestination(value, localDomain) {
	if (typeof value !== 'string' || !value || value.length > 253) return false;
	var parts = value.split('/');
	if (parts.length > 2 || value.indexOf(':') >= 0) return false;
	if (parts.length === 2) return /^[0-9.]+$/.test(parts[0]) && validHost(parts[0]) && /^(?:[0-9]|[12][0-9]|3[0-2])$/.test(parts[1]);
	if (!validHost(value) || value.indexOf('.') < 0) return false;
	if (localDomain && !/^[0-9.]+$/.test(value)) {
		var domain = value.toLowerCase().replace(/\.$/, '');
		var local = String(localDomain).toLowerCase().replace(/\.$/, '');
		if (domain === local || domain.endsWith('.' + local)) return false;
	}
	return true;
}

return baseclass.extend({
	parseLink: parseLink,
	validPeer: validPeer,
	validHost: validHost,
	validHash: validHash,
	validHashes: validHashes,
	validCallLink: validCallLink,
	callLink: callLink,
	validPassword: validPassword,
	validMac: validMac,
	validPairing: validPairing,
	normalizeHash: normalizeHash,
	validDestination: validDestination,
	workerLimit: function(count) { return Number.isInteger(count) && count > 0 && count <= 6 ? Math.min(126, count * 27) : 0; },
	stateLabel: function(state) {
		var labels = { stopped: 'Остановлено', starting: 'Запуск', connecting: 'Подключение', connected: 'Подключено', captcha_required: 'Нужна CAPTCHA', error: 'Ошибка', disabled: 'Выключено' };
		return Object.prototype.hasOwnProperty.call(labels, state) ? labels[state] : 'Нет данных';
	},
	bytes: function(value) {
		var n = Number(value || 0), units = ['Б', 'КиБ', 'МиБ', 'ГиБ', 'ТиБ'], i = 0;
		if (!Number.isFinite(n) || n < 0) return '—';
		while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
		return n.toFixed(i ? 1 : 0) + ' ' + units[i];
	}
});
