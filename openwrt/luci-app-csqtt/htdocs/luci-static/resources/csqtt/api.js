'use strict';
'require baseclass';
'require rpc';

var calls = {};
['status', 'start', 'stop', 'restart', 'apply', 'diagnostics', 'devices', 'captcha_begin', 'captcha_cancel'].forEach(function(method) {
	calls[method] = rpc.declare({ object: 'csqtt', method: method, expect: { '': {} } });
});

return baseclass.extend({
	call: function(method) {
		if (!Object.prototype.hasOwnProperty.call(calls, method)) return Promise.reject(new Error('Неизвестное действие.'));
		return calls[method]().then(function(result) {
			if (!result || result.ok === false) throw new Error('Не удалось выполнить действие. Подробности — в диагностике CSQTT.');
			return result;
		});
	}
});
