'use strict';
const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('lionLocal',Object.freeze({
 status:()=>ipcRenderer.invoke('lion:local-health'),
 send:(prompt,history)=>ipcRenderer.invoke('lion:local-advisory',{prompt,history})
}));
