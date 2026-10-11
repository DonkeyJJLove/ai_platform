'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {restoreDesktopPanel}=require('../src/desktop-entry.cjs');

test('desktop second instance restores native LPCL tab before focusing same Electron window',()=>{
 const calls=[];
 const win={isDestroyed:()=>false,isMinimized:()=>true,
  restore:()=>calls.push('restore'),show:()=>calls.push('show'),focus:()=>calls.push('focus')};
 const changed=restoreDesktopPanel(win,name=>calls.push('tab:'+name));
 assert.equal(changed,true);
 assert.deepEqual(calls,['tab:panel','restore','show','focus']);
});

test('already visible native window is focused without a new renderer or navigation',()=>{
 const calls=[];
 const win={isDestroyed:()=>false,isMinimized:()=>false,
  restore:()=>calls.push('restore'),show:()=>calls.push('show'),focus:()=>calls.push('focus')};
 assert.equal(restoreDesktopPanel(win,name=>calls.push('tab:'+name)),true);
 assert.deepEqual(calls,['tab:panel','show','focus']);
});

test('closed or missing native window fails closed without UI action',()=>{
 assert.equal(restoreDesktopPanel(null,()=>assert.fail('called')),false);
 assert.equal(restoreDesktopPanel({isDestroyed:()=>true},()=>assert.fail('called')),false);
});

test('native shell requires a real tab selector, not a URL',()=>{
 const win={isDestroyed:()=>false,show:()=>{},focus:()=>{}};
 assert.throws(()=>restoreDesktopPanel(win,null),/DESKTOP_TAB_SELECTOR_REQUIRED/);
});

test('main process owns panel/SaaS tab navigation, not external browser',()=>{
 const main=fs.readFileSync(path.join(__dirname,'../src/main.cjs'),'utf8');
 assert.match(main,/app\.on\('second-instance',\(\)=>\{restoreDesktopPanel\(win,selectRightTab\)\}\)/);
 assert.match(main,/selectRightTab\('panel'\);win\.on\('closed'/);
 assert.match(main,/label:'Przejdź do LPCL Panel \(desktop\)',click:\(\)=>selectRightTab\('panel'\)/);
 assert.match(main,/label:'Otwórz projekt SaaS',click:\(\)=>\{selectRightTab\('saas'\);saas\.webContents\.loadURL\(PROJECT\)/);
 assert.match(main,/wc\.setWindowOpenHandler\(\(\)=>\(\{action:'deny'\}\)\)/);
 assert.doesNotMatch(main,/shell\.openExternal/);
});

test('Windows Desktop shortcut installer is explicit, not web shortcut or autorun',()=>{
 const launcher=fs.readFileSync(path.join(__dirname,'../Install-LION-Desktop-Link.ps1'),'utf8');
 assert.match(launcher,/\[switch\]\$Apply/);
 assert.match(launcher,/\[switch\]\$ReplaceExisting/);
 assert.match(launcher,/\[string\]\$ShortcutName/);
 assert.match(launcher,/Start-LION-Browser-ISE\.ps1/);
 assert.match(launcher,/DesktopDirectory/);
 assert.match(launcher,/CreateShortcut\(\$LionLink\)/);
 assert.match(launcher,/\$LionResult\['result'\] = 'PREVIEW_ONLY'/);
 assert.match(launcher,/\$LionResult\['result'\] = 'DESKTOP_SHORTCUT_VERIFIED'/);
 assert.match(launcher,/\$LionShortcut\.TargetPath = \$LionPowerShell/);
 assert.match(launcher,/\$LionShortcut\.WorkingDirectory = \$LionAppRoot/);
 assert.doesNotMatch(launcher,/-ExecutionPolicy\s+Bypass|Start-Process|https?:\/\/|Register-ScheduledTask|New-Service/i);
});
