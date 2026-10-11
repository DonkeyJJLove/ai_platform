'use strict';

// Desktop shortcut means the native Electron shell, never an external URL.
// A second launch selects the LPCL Panel without changing conversation,
// provider bindings, mission state, SaaS queue or authentication.
function restoreDesktopPanel(win,selectRightTab){
 if(!win||typeof win.isDestroyed!=='function'||win.isDestroyed())return false;
 if(typeof selectRightTab!=='function')throw Error('DESKTOP_TAB_SELECTOR_REQUIRED');
 selectRightTab('panel');
 if(typeof win.isMinimized==='function'&&win.isMinimized()&&typeof win.restore==='function')win.restore();
 win.show();
 win.focus();
 return true;
}

module.exports={restoreDesktopPanel};
