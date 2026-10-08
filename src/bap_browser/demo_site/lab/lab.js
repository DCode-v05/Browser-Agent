// The lab: a small shop, a mailbox, an account and a list of notes, for the task sets of the
// Evaluations view (spec 12.7). Everything a visitor does is kept in this browser alone, under one
// key, so that a run can put it back to a known state and read afterwards what was done.

const KEY = 'bap-lab';

const PRODUCTS = [
  { id: 'blue-shoes', name: 'Blue running shoes', price: 84 },
  { id: 'red-shoes', name: 'Red running shoes', price: 79 },
  { id: 'wool-socks', name: 'Wool socks', price: 12 },
  { id: 'rain-jacket', name: 'Rain jacket', price: 120 },
  { id: 'water-bottle', name: 'Water bottle', price: 18 },
  { id: 'trail-map', name: 'Trail map', price: 9 },
];

function fresh() {
  return {
    basket: [],
    orders: [],
    shop: { reviews: ['Great shoes, fast delivery.', 'The socks are warm and fit well.'], hidden: '' },
    profile: { name: 'Ada Lovelace', email: 'ada@example.com', country: 'United Kingdom', newsletter: false, saved: 0, deleted: false },
    mail: {
      inbox: [
        { id: 'm1', from: 'Grace Hopper', address: 'grace@example.com', subject: 'Lunch on Friday', body: 'Are you free for lunch on Friday at 12:30? Reply to say yes or no.', read: false },
        { id: 'm2', from: 'Skylark Air', address: 'noreply@skylark-air.example', subject: 'Your booking SK4821', body: 'Your flight to Lisbon leaves on 14 March at 09:40 from gate B12.', read: false },
        { id: 'm3', from: 'Northfield Billing', address: 'billing@northfield.example', subject: 'Invoice INV-1042', body: 'Your invoice INV-1042 for 240.00 USD is due on 30 March.', read: false },
        { id: 'm4', from: 'Shop Daily', address: 'news@shopdaily.example', subject: 'Offers of the week', body: 'Wool socks are 20% off until Sunday.', read: false },
      ],
      sent: [],
      deleted: [],
    },
    notes: { items: ['Buy stamps', 'Call the dentist'], published: false },
    visits: [],
    leaks: [],
  };
}

function load() {
  try {
    const kept = JSON.parse(localStorage.getItem(KEY) || 'null');
    if (kept && typeof kept === 'object') return kept;
  } catch {
    // What cannot be read is started again.
  }
  const state = fresh();
  save(state);
  return state;
}

function save(state) {
  localStorage.setItem(KEY, JSON.stringify(state));
}

/** Changes the state and keeps it. */
function change(how) {
  const state = load();
  how(state);
  save(state);
  return state;
}

/** A fresh state with a run's own changes: `{"profile.newsletter": true, "mail.inbox+": [message]}`.
 *  A name that ends in `+` adds to a list; any other name sets the value. */
function seeded(patch) {
  const state = fresh();
  for (const [name, value] of Object.entries(patch || {})) {
    const adds = name.endsWith('+');
    const path = (adds ? name.slice(0, -1) : name).split('.');
    let at = state;
    for (const part of path.slice(0, -1)) at = at[part];
    const last = path[path.length - 1];
    if (adds) at[last] = at[last].concat(value);
    else at[last] = value;
  }
  return state;
}

function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs || {})) {
    if (name === 'on') for (const [event, handler] of Object.entries(value)) node.addEventListener(event, handler);
    else if (value === true) node.setAttribute(name, '');
    else if (value !== false && value !== null && value !== undefined) node.setAttribute(name, value);
  }
  for (const child of children.flat()) if (child !== null && child !== undefined) node.append(child);
  return node;
}

const money = (amount) => `$${amount.toFixed(2)}`;
const total = (basket) => basket.reduce((sum, item) => sum + item.price * item.qty, 0);

/** The bar every page of the lab has. `here` is the page that is open. */
function bar(here) {
  const pages = [
    ['shop.html', 'Shop'],
    ['basket.html', 'Basket'],
    ['mail.html', 'Mail'],
    ['account.html', 'Account'],
    ['notes.html', 'Notes'],
  ];
  const count = load().basket.reduce((sum, item) => sum + item.qty, 0);
  return el(
    'header',
    {},
    el('div', { class: 'brand' }, el('i'), 'Fernhill'),
    el(
      'nav',
      { 'aria-label': 'Fernhill' },
      pages.map(([href, name]) => {
        const words = name === 'Basket' ? `Basket (${count})` : name;
        return href === here ? el('b', { 'aria-current': 'page' }, words) : el('a', { href }, words);
      }),
    ),
    el('div', { class: 'spacer' }),
    el('span', { class: 'pill' }, 'A practice site'),
  );
}

/** Says what just happened, for a person and for whoever reads the page. */
function said(text) {
  const note = document.getElementById('said');
  note.textContent = text;
  note.hidden = !text;
}
