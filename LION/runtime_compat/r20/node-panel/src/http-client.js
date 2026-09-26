'use strict';
async function jsonRequest(base, pathname, options={}) {
  const method=options.method||'GET';
  const headers={Accept:'application/json',...(options.headers||{})};
  let body;
  if(options.body!==undefined){body=JSON.stringify(options.body);headers['Content-Type']='application/json';}
  const response=await fetch(new URL(pathname,base),{method,headers,body,signal:AbortSignal.timeout(options.timeoutMs||5000),redirect:'error'});
  const text=await response.text();
  let value={};
  if(text){try{value=JSON.parse(text)}catch{value={raw:text.slice(0,1000)}}}
  if(!response.ok){const e=new Error('HTTP_'+response.status+' '+JSON.stringify(value).slice(0,500));e.status=response.status;throw e;}
  return value;
}
module.exports={jsonRequest};
