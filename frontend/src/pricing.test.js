import test from 'node:test';
import assert from 'node:assert/strict';
import {quote} from './pricing.js';

const start = {name: 'Urganch'};
const end = {name: 'Xiva'};
const car = {routeRates: [{from: start.name, to: end.name, amount: 500003}]};

test('booking uses the exact directional fare and rounds the deposit to whole so‘m', () => {
  assert.deepEqual(quote(car, start, end), {total: 500003, deposit: 100001, remainder: 400002});
});

test('reverse routes and cars without a matching fare cannot be quoted', () => {
  assert.equal(quote(car, end, start), null);
  assert.equal(quote({base: 500000, perKm: 2000}, start, end), null);
});
