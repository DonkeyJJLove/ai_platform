'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {composerEquivalent}=require('../src/browser.cjs');

test('composer equivalence accepts only observed newline flattening',()=>{
 const expected='line-1\nline-2\r\nline-3\rline-4';
 assert.equal(composerEquivalent(expected,expected),true);
 assert.equal(composerEquivalent('line-1line-2line-3line-4',expected),true);
 assert.equal(composerEquivalent('line-1 line-2line-3line-4',expected),false);
 assert.equal(composerEquivalent('line-1line-2line-3line-X',expected),false);
});
