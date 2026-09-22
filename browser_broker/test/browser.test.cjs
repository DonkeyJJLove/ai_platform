'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const {composerEquivalent,chatExperience,observeScript}=require('../src/browser.cjs');

test('composer equivalence accepts only observed newline flattening',()=>{
 const expected='line-1\nline-2\r\nline-3\rline-4';
 assert.equal(composerEquivalent(expected,expected),true);
 assert.equal(composerEquivalent('line-1line-2line-3line-4',expected),true);
 assert.equal(composerEquivalent('line-1 line-2line-3line-4',expected),false);
 assert.equal(composerEquivalent('line-1line-2line-3line-X',expected),false);
});

test('project conversation is Chat-only and Work markers are rejected',()=>{
 assert.equal(chatExperience('/g/g-p-test/c/thread-one','',[]),'CHAT');
 assert.equal(chatExperience('/g/g-p-test/c/thread-one','','Chat'.split('|')),'CHAT');
 assert.equal(chatExperience('/g/g-p-test/c/thread-one','',['Work']),'WORK');
 assert.equal(chatExperience('/work/g/g-p-test/c/thread-one','',[]),'WORK');
 assert.equal(chatExperience('/g/g-p-test/c/thread-one','?experience=work',[]),'WORK');
});

test('renderer observeScript is syntactically valid JavaScript',()=>{
 assert.doesNotThrow(()=>new Function(observeScript));
});

test('renderer Work detection uses project Chat/Work radiogroup state and header fallback',()=>{
 assert.match(observeScript,/role="radiogroup"/);
 assert.match(observeScript,/data-state/);
 assert.match(observeScript,/headerWork/);
 assert.match(observeScript,/workOn/);
 assert.match(observeScript,/chatOn/);
});
