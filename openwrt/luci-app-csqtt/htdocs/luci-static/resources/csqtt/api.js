'use strict';
'require baseclass';
'require rpc';

var calls = {};
// Commit only this configuration; do not apply unrelated pending LuCI edits.
var commitConfig = rpc.declare({ object: 'uci', method: 'commit', params: ['config'], reject: true });
['status', 'start', 'stop', 'restart', 'apply', 'diagnostics', 'devices', 'captcha_begin', 'captcha_cancel'].forEach(function(method) {
	calls[method] = rpc.declare({ object: 'csqtt', method: method, expect: { '': {} } });
});

return baseclass.extend({
	commitConfig: function() { return commitConfig('csqtt'); },
	call: function(method) {
		if (!Object.prototype.hasOwnProperty.call(calls, method)) return Promise.reject(new Error('Неизвестное действие.'));
		return calls[method]().then(function(result) {
			if (!result || result.ok === false) throw new Error('Не удалось выполнить действие. Подробности — в диагностике CSQTT.');
			return result;
		});
	}
});
