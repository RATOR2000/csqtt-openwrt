const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const resources = path.resolve(__dirname, '../../openwrt/luci-app-csqtt/htdocs/luci-static/resources');
const E = (tag, attrs, children) => ({ tag, attrs, children });
const extend = { extend: value => value };
function load(file, dependencies) {
  const names = Object.keys(dependencies);
  return new Function(...names, fs.readFileSync(path.join(resources, file), 'utf8'))(...names.map(name => dependencies[name]));
}
function formStub() {
  class Option {
    constructor(option) { this.option = option; this.keylist = []; this.vallist = []; }
    value(key, label) { this.keylist.push(String(key)); this.vallist.push(label); }
    renderWidget() { return { keys: this.keylist.slice(), labels: this.vallist.slice() }; }
  }
  class Section {
    constructor(type) { this.type = type; this.options = []; }
    option(Type, name) { const option = new Type(name); this.options.push(option); return option; }
  }
  class Map {
    constructor() { this.sections = []; }
    section(_Type, name) { const section = new Section(name); this.sections.push(section); return section; }
    render() { return Promise.resolve(E('form')); }
  }
  return { Map, GridSection: Section, Value: Option, ListValue: Option, Flag: Option };
}
function modalClone(option, form) {
  // Installed LuCI GridSection.cloneOptions copies own properties to a new option.
  const clone = new form.ListValue(option.option);
  for (const key of Object.keys(option)) {
    if (!['map', 'section', 'option', 'title', 'description', 'subsection'].includes(key)) clone[key] = option[key];
  }
  return clone;
}
async function setup() {
  const form = formStub();
  const entries = [
    { '.type': 'client', '.name': 'main' },
    { '.type': 'group', '.name': 'cfg000aaa', name: 'main' }
  ];
  const uci = { sections: (_package, type) => entries.filter(section => section['.type'] === type) };
  const model = load('csqtt/model.js', { baseclass: extend });
  const view = load('view/csqtt/policies.js', {
    view: extend, form, uci, model, E, L: { resource: value => value }, ui: {}, api: {}
  });
  await view.render([null, { unavailable: true }, {}]);
  return { view, entries, form };
}

test('device and rule modals receive group choices on the cloned option', async () => {
  const { view, form } = await setup();
  for (const type of ['device', 'rule']) {
    const section = view.map.sections.find(section => section.type === type);
    const parent = section.options.find(option => option.option === 'group');
    parent.renderWidget('existing-row', 0, 'cfg000aaa');
    const modal = modalClone(parent, form);
    const widget = modal.renderWidget('new-row', 0, null);
    assert.deepEqual(widget.keys, ['cfg000aaa']);
    assert.equal(widget.labels[0], 'main', 'native select options require a text label');
    assert.deepEqual(parent.keylist, ['cfg000aaa'], 'rendering a modal must not mutate its parent choices');
    assert.notEqual(modal.keylist, parent.keylist);
    assert.equal(modal.validate('new-row', 'cfg000aaa'), true);
    assert.notEqual(modal.validate('new-row', 'main'), true, 'client section main is not a group ID');
    parent.cfgvalue = () => 'cfg000aaa';
    assert.deepEqual(parent.textvalue('existing-row').children, ['main']);
  }
});

test('reopened group selectors include new groups and current display names', async () => {
  const { view, entries, form } = await setup();
  const parent = view.map.sections.find(section => section.type === 'device').options.find(option => option.option === 'group');
  const modal = modalClone(parent, form);
  modal.renderWidget('new-row', 0, null);
  entries[1].name = 'Дом';
  entries.push({ '.type': 'group', '.name': 'new001abc', name: 'Работа' });
  const widget = modal.renderWidget('new-row', 0, 'new001abc');
  assert.deepEqual(widget.keys, ['cfg000aaa', 'new001abc']);
    assert.deepEqual(widget.labels, ['Дом', 'Работа']);
  assert.equal(modal.validate('new-row', 'new001abc'), true);
  entries.splice(1, 1);
  assert.notEqual(modal.validate('new-row', 'cfg000aaa'), true);
});
