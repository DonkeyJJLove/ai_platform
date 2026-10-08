'use strict';
const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('lionObserver',Object.freeze({
 snapshot:()=>ipcRenderer.invoke('lion:observe-readonly')
}));
