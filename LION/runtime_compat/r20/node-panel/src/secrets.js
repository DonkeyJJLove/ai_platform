'use strict';
const fs=require('node:fs');
const path=require('node:path');
const cp=require('node:child_process');
function readProtectedSecret(file,helper){
  const p=path.resolve(file);
  if(path.extname(p).toLowerCase()!=='.dpapi'){
    const value=fs.readFileSync(p,'utf8').trim();
    if(value.length<32)throw new Error('secret unavailable');
    return value;
  }
  const py='C:\\Users\\d2j3\\AppData\\Roaming\\uv\\python\\cpython-3.13-windows-x86_64-none\\python.exe';
  const pyHelper=path.resolve(path.dirname(helper),'unprotect_secret.py');
  const out=cp.spawnSync(py,[pyHelper,p],{encoding:'utf8',windowsHide:true,timeout:10000});
  if(out.status!==0)throw new Error('DPAPI unprotect failed');
  const value=String(out.stdout||'').trim();
  if(value.length<32)throw new Error('DPAPI secret unavailable');
  return value;
}
module.exports={readProtectedSecret};
