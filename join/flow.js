/* Lonely Planner · join flow · version 3.0.0-alpha.7 · F05
   CHANGE 2026-10-22 F06-JOIN-02: version only (VERSION 'alpha.6' → 'alpha.7'); no logic change. With the F06 server (D2) a
   removed identity gets me=null / a new pending row, so the 'removed' screen below is no longer reached (kept for alpha.6).
   CHANGE 2026-10-19 F05-JOIN-02: new file (no previous version). The member-join screens of docs/F05_spec.md §1.1–1.3 and
   §1.6 (artboards F05_Join, F05_Pending, F05_Approved, F05_Invalid), shared by the /join/ page (outside the PWA scope) and
   the app's not-connected screen ("יש לי קישור הצטרפות", §1.4), which loads this file on demand.
   Exposes only window.LPJoin = {version, mount(root, opts)}. No storage of its own except sessionStorage 'lp:join_code'
   (set by the /join/ page so a reload keeps the code); the join code and transfer code are never logged.

   opts = {
     getClient: async () => supabase client with a session (anonymous is fine),
     fnUrl:     '<SUPABASE_URL>/functions/v1/join-trip',
     apiKey:    the publishable key (sent as `apikey`),
     code:      the 8-char join code (or a pasted link),
     inApp:     true inside the installed app / app page (no transfer-code card; "פתיחת הטיול" calls onEnter),
     onEnter:   (trip_id, role, display_name) => void,
     onBack?:   () => void  (in-app: back to the not-connected screen)
   }
   Stable ids for QA: #lpJoin[data-screen = loading|form|pending|approved|invalid|rejected|removed|error], #lpjTitle,
   #lpjName, #lpjNameErr, #lpjSubmit, #lpjCancel, #lpjCode, #lpjCopy, #lpjOpen, #lpjAgain, #lpjRetry, #lpjToast. */
(function(){
'use strict';
if(window.LPJoin)return;
const VERSION='3.0.0-alpha.7'; /* CHANGE 2026-10-22 F06-JOIN-02: was '3.0.0-alpha.6' */
const POLL_MS=20000,CALL_TIMEOUT_MS=15000;
const ROLE={manager:'מנהל',editor:'עורך',viewer:'צופה'};
const TX={
 offline:'אין חיבור. נסו שוב כשהרשת תחזור.',
 rate:'יותר מדי ניסיונות. נסו שוב מאוחר יותר.',
 generic:'משהו השתבש. נסו שוב.',
 nameInvalid:'כתבו שם של עד 40 תווים.',
 copied:'הקוד הועתק'
};
const CSS=`
.lpj{direction:rtl;color:#17211b;font-family:Arial,'Segoe UI',system-ui,sans-serif;max-width:420px;margin:0 auto;min-height:100%;display:flex;flex-direction:column;background:#f7f6f1;position:relative}
.lpj *{box-sizing:border-box}
.lpj [hidden]{display:none!important}
.lpj-hero{background:#0f5c43;color:#fff;padding:16px 20px 54px}
.lpj-hero.sm{padding-bottom:22px}
.lpj-top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.lpj-brand{font-size:14px;font-weight:900}
.lpj-sub{font-size:11.5px;color:#d5ece2}
.lpj-kicker{margin-top:24px;font-size:13px;color:#d5ece2}
.lpj-hero h1{margin:4px 0 6px;font-size:26px;line-height:1.25;overflow-wrap:anywhere}
.lpj-hero.sm h1{margin-top:14px;font-size:18px}
.lpj-meta{font-size:13.5px;color:#e6f3ee}
.lpj-body{padding:0 16px 24px;margin-top:-34px;display:flex;flex-direction:column;gap:14px}
.lpj-hero.sm+.lpj-body{margin-top:0;padding-top:20px}
.lpj-card{background:#fff;border:1px solid #e4e6df;border-radius:18px;padding:16px}
.lpj-card.lift{box-shadow:0 6px 18px #0000001a}
.lpj-lbl{display:block;font-size:12.5px;font-weight:700;color:#3a443d;margin:0 0 6px}
.lpj-in{width:100%;min-height:46px;padding:11px 14px;border:1.5px solid #d6d9cf;border-radius:12px;background:#fff;color:#17211b;font-size:16px;font-family:inherit}
.lpj-in:focus{outline:none;border-color:#0f6b4f;box-shadow:0 0 0 3px #0f6b4f22}
.lpj-in[aria-invalid="true"]{border-color:#b42318;box-shadow:none}
.lpj-help{margin:6px 2px 0;font-size:11.5px;color:#5f6861;line-height:1.5}
.lpj-err{display:flex;gap:6px;align-items:flex-start;margin-top:6px;font-size:12.5px;color:#b42318;font-weight:700;line-height:1.5}
.lpj-btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;min-height:48px;border:0;border-radius:14px;background:#0f6b4f;color:#fff;font-size:15px;font-weight:800;cursor:pointer;font-family:inherit;text-decoration:none}
.lpj-btn[disabled]{opacity:.6;cursor:default}
.lpj-btn.out{background:#fff;color:#0f6b4f;border:1px solid #0f6b4f}
.lpj-btn.ghost{background:#fff;color:#17211b;border:1px solid #e4e6df}
.lpj-ticks{display:flex;flex-direction:column;gap:8px;padding:0 6px}
.lpj-tick{display:flex;gap:8px;align-items:flex-start;font-size:12.5px;color:#3a443d;line-height:1.5}
.lpj-center{display:flex;flex-direction:column;align-items:center;text-align:center;padding:28px 12px 0}
.lpj-ring{width:80px;height:80px;border-radius:50%;display:flex;align-items:center;justify-content:center}
.lpj-center h2{margin:16px 0 8px;font-size:22px;overflow-wrap:anywhere}
.lpj-center p{margin:0;font-size:14.5px;color:#3a443d;line-height:1.6}
.lpj-pill{display:inline-flex;align-items:center;margin-top:16px;background:#fef3e2;color:#8a4a03;border-radius:999px;padding:6px 14px;font-size:12.5px;font-weight:800}
.lpj-steps{background:#fff;border:1px solid #e4e6df;border-radius:18px;padding:6px 16px}
.lpj-step{display:flex;gap:10px;align-items:center;font-size:13.5px;padding:9px 0;border-top:1px solid #efeee8}
.lpj-step:first-child{border-top:0}
.lpj-dot{width:22px;height:22px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center}
.lpj-n{width:22px;height:22px;border-radius:50%;background:#f1f0ea;color:#3a443d;font-size:12px;font-weight:800;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.lpj-code{background:#f7f6f1;border:1px dashed #b9c9bf;border-radius:14px;padding:12px;text-align:center}
.lpj-code b{display:block;direction:ltr;font-family:ui-monospace,Menlo,monospace;font-size:32px;letter-spacing:6px;color:#0b5841;margin:2px 0}
.lpj-foot{margin:auto 0 0;padding:14px 20px 22px;text-align:center;font-size:11.5px;color:#5f6861}
.lpj-toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#17211b;color:#fff;border-radius:12px;padding:10px 16px;font-size:13.5px;max-width:90vw;z-index:50;display:none}
.lpj-toast.on{display:block}
.lpj-link{border:0;background:none;color:#0f6b4f;font-size:13.5px;font-weight:700;min-height:44px;padding:0 8px;cursor:pointer;font-family:inherit;text-decoration:underline}
`;
const ICON={
 check:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#198754" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex-shrink:0;margin-top:2px"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
 bigCheck:'<svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#146c43" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>',
 clock:'<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#b45309" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
 brokenLink:'<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#b42318" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/><path d="M4 4l16 16"/></svg>',
 no:'<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#3a443d" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M6 6l12 12"/></svg>',
 alert:'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#b42318" stroke-width="2.5" stroke-linecap="round" aria-hidden="true" style="flex-shrink:0;margin-top:3px"><circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16h.01"/></svg>',
 smallCheck:'<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#146c43" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>'
};
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c])}
function online(){return navigator.onLine!==false}
function dmy(iso,withYear){const m=/^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso||''));return m?m[3]+'/'+m[2]+(withYear?'/'+m[1]:''):''}
function isIos(){
 const ua=navigator.userAgent||'';
 return /iPad|iPhone|iPod/.test(ua)||(navigator.platform==='MacIntel'&&(navigator.maxTouchPoints||0)>1);
}
function isStandalone(){
 try{if(navigator.standalone===true)return true;if(window.matchMedia&&window.matchMedia('(display-mode: standalone)').matches)return true}catch{}
 return false;
}
function normCode(v){
 let s=String(v||'').trim();
 const m=/[#?&]code=([A-Za-z0-9]+)/.exec(s);if(m)s=m[1];
 s=s.replace(/[\s-]/g,'').toUpperCase();
 return /^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$/.test(s)?s:null;
}
function injectCss(){
 if(document.getElementById('lpjCss'))return;
 const st=document.createElement('style');st.id='lpjCss';st.textContent=CSS;document.head.appendChild(st);
}

function mount(root,opts){
 injectCss();
 const o=Object.assign({inApp:false},opts||{});
 const st={code:normCode(o.code),trip:null,me:null,name:'',timer:null,chan:null,client:null,busy:false,closed:false};
 root.innerHTML='';
 const el=document.createElement('div');el.className='lpj';el.id='lpJoin';el.setAttribute('dir','rtl');
 root.appendChild(el);
 const toastEl=document.createElement('div');toastEl.className='lpj-toast';toastEl.id='lpjToast';toastEl.setAttribute('role','status');toastEl.setAttribute('aria-live','polite');
 root.appendChild(toastEl);   /* inside the mount root: the app hides every other body child while its not-connected screen shows */
 let toastT=null;
 function toast(msg){toastEl.textContent=msg;toastEl.classList.add('on');clearTimeout(toastT);toastT=setTimeout(()=>toastEl.classList.remove('on'),3200)}
 const $=id=>document.getElementById(id);

 async function client(){if(!st.client)st.client=await o.getClient();return st.client}
 async function fn(body){
  const c=await client();
  const g=await c.auth.getSession();
  const tok=g&&g.data&&g.data.session&&g.data.session.access_token;
  if(!tok)throw Object.assign(new Error('no session'),{code:'unauthorized'});
  const ac=typeof AbortController!=='undefined'?new AbortController():null;
  const t=setTimeout(()=>{try{ac&&ac.abort()}catch{}},CALL_TIMEOUT_MS);
  let r;
  try{r=await fetch(o.fnUrl,{method:'POST',headers:{'content-type':'application/json',apikey:o.apiKey,authorization:'Bearer '+tok},body:JSON.stringify(body),signal:ac?ac.signal:undefined})}
  catch(e){throw Object.assign(new Error('network'),{code:online()?'network':'offline'})}
  finally{clearTimeout(t)}
  let j={};try{j=await r.json()}catch{}
  if(!r.ok||j.error)throw Object.assign(new Error(j.error||'http_'+r.status),{code:j.error||'server_error'});
  return j;
 }
 function errText(e){const c=e&&e.code;return c==='offline'?TX.offline:c==='rate_limited'?TX.rate:TX.generic}

 function hero(small){
  const t=st.trip||{};
  const dates=t.start_date&&t.end_date?dmy(t.start_date)+' – '+dmy(t.end_date,true):'';
  if(small)return'<header class="lpj-hero sm"><div class="lpj-top"><span class="lpj-brand">Lonely Planner</span><span class="lpj-sub">'+esc(dates)+'</span></div><h1>'+esc(t.name||'')+'</h1></header>';
  const meta=[dates,t.days?(t.days===1?'יום אחד':t.days+' ימים'):'',t.members!=null?(t.members===1?'חבר אחד':t.members+' חברים'):''].filter(Boolean).join(' · ');
  return'<header class="lpj-hero"><div class="lpj-top"><span class="lpj-brand">Lonely Planner</span><span class="lpj-sub">הזמנה לקבוצה</span></div>'+
   '<div class="lpj-kicker">'+(t.manager?'הזמנה מ'+esc(t.manager)+' להצטרף לטיול':'הזמנה להצטרף לטיול')+'</div>'+
   '<h1 id="lpjTitle">'+esc(t.name||'')+'</h1><div class="lpj-meta">'+esc(meta)+'</div></header>';
 }
 function back(){return o.inApp&&o.onBack?'<button type="button" class="lpj-link" id="lpjBack">חזרה</button>':''}
 function paint(screen,html){
  el.dataset.screen=screen;el.innerHTML=html;
  const b=$('lpjBack');if(b)b.onclick=()=>{stop();o.onBack()};
 }
 function stop(){if(st.timer){clearInterval(st.timer);st.timer=null}if(st.chan){try{st.client.removeChannel(st.chan)}catch{}st.chan=null}}

 /* --- screens --- */
 function showLoading(){paint('loading','<header class="lpj-hero sm"><div class="lpj-top"><span class="lpj-brand">Lonely Planner</span></div><h1 id="lpjTitle">טוענים את ההזמנה…</h1></header>')}
 function showError(msg,retry){
  paint('error','<header class="lpj-hero sm"><div class="lpj-top"><span class="lpj-brand">Lonely Planner</span></div><h1 id="lpjTitle">לא הצלחנו לטעון</h1></header>'+
   '<div class="lpj-body"><section class="lpj-card" role="alert"><p style="margin:0 0 12px;font-size:14px;color:#3a443d">'+esc(msg)+'</p><button type="button" class="lpj-btn" id="lpjRetry">נסו שוב</button></section>'+back()+'</div>');
  $('lpjRetry').onclick=retry;
 }
 function showInvalid(){
  stop();
  paint('invalid','<header class="lpj-hero sm"><div class="lpj-top"><span class="lpj-brand">Lonely Planner</span></div></header>'+
   '<div class="lpj-body"><section class="lpj-card" style="display:flex;gap:12px;align-items:flex-start" role="alert">'+
   '<span class="lpj-ring" style="width:48px;height:48px;background:#fdecea;flex-shrink:0">'+ICON.brokenLink.replace(/34/g,'24')+'</span>'+
   '<div><h1 id="lpjTitle" style="margin:0;font-size:16px">הקישור כבר לא פעיל</h1><p style="margin:4px 0 0;font-size:13px;color:#3a443d;line-height:1.5">בקשו מהמנהל של הטיול קישור חדש. אם כבר הצטרפתם בעבר, פשוט פתחו את האפליקציה.</p></div></section>'+back()+'</div>');
 }
 function showRemoved(){
  stop();
  paint('removed',hero(true)+'<div class="lpj-body"><div class="lpj-center"><span class="lpj-ring" style="background:#f1f0ea">'+ICON.no+'</span>'+
   '<h2 id="lpjTitle">הוסרת מהטיול</h2><p>פנו למנהל של הטיול אם זו טעות.</p></div>'+back()+'</div>');
 }
 function showForm(prefill,err){
  stop();
  const t=st.trip||{};
  paint('form',hero(false)+'<div class="lpj-body"><section class="lpj-card lift">'+
   '<label class="lpj-lbl" for="lpjName">איך קוראים לך?</label>'+
   '<input id="lpjName" class="lpj-in" maxlength="40" autocomplete="given-name" enterkeyhint="send" value="'+esc(prefill||'')+'"'+(err?' aria-invalid="true" aria-describedby="lpjNameErr"':' aria-describedby="lpjNameHelp"')+'>'+
   (err?'<div class="lpj-err" id="lpjNameErr" role="alert">'+ICON.alert+'<span>'+esc(err)+'</span></div>'
       :'<p class="lpj-help" id="lpjNameHelp">כך יראו אותך שאר החברים, וכך יירשמו ההוצאות שלך.</p>')+
   '<div style="height:14px"></div><button type="button" class="lpj-btn" id="lpjSubmit">בקשת הצטרפות</button></section>'+
   '<div class="lpj-ticks">'+
   '<div class="lpj-tick">'+ICON.check+'<span>בלי מייל ובלי סיסמה</span></div>'+
   '<div class="lpj-tick">'+ICON.check+'<span>'+(t.manager?'אחרי האישור של '+esc(t.manager)+', הטיול נפתח כאן לבד':'אחרי אישור המנהל, הטיול נפתח כאן לבד')+'</span></div>'+
   '<div class="lpj-tick">'+ICON.check+'<span>הטלפון הזה יזוהה אוטומטית בפעם הבאה</span></div></div>'+back()+'</div>'+
   '<p class="lpj-foot">מה שתזינו בטיול גלוי רק לחברי הקבוצה.</p>');
  const inp=$('lpjName');
  $('lpjSubmit').onclick=submit;
  inp.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();submit()}};
  if(!err&&!prefill)setTimeout(()=>{try{inp.focus()}catch{}},50);
 }
 function showPending(){
  const t=st.trip||{},me=st.me||{};
  paint('pending',hero(true)+'<div class="lpj-body"><div class="lpj-center"><span class="lpj-ring" style="background:#fef3e2">'+ICON.clock+'</span>'+
   '<h2 id="lpjTitle">'+(t.manager?'הבקשה נשלחה ל'+esc(t.manager):'הבקשה נשלחה למנהל')+'</h2>'+
   '<p>אחרי האישור, הטיול ייפתח במסך הזה לבד. אפשר לסגור ולחזור לאותו קישור מאוחר יותר.</p>'+
   '<span class="lpj-pill">ממתין לאישור · '+esc(me.display_name||st.name)+'</span></div>'+
   '<section class="lpj-steps" aria-label="התקדמות">'+
   '<div class="lpj-step"><span class="lpj-dot" style="background:#edf8f3">'+ICON.smallCheck+'</span><span>הבקשה נשלחה</span></div>'+
   '<div class="lpj-step"><span class="lpj-dot" style="border:2px solid #d97706"></span><b>'+(t.manager?'מחכים לאישור של '+esc(t.manager):'מחכים לאישור')+'</b></div>'+
   '<div class="lpj-step" style="color:#5f6861"><span class="lpj-dot" style="border:2px solid #c9ccc4"></span><span>הטיול נפתח</span></div></section>'+
   '<button type="button" class="lpj-btn ghost" id="lpjCancel">ביטול הבקשה</button></div>');
  $('lpjCancel').onclick=cancel;
  watch();
 }
 function showRejected(){
  stop();
  const t=st.trip||{};
  paint('rejected',hero(true)+'<div class="lpj-body"><section class="lpj-card" style="display:flex;gap:12px;align-items:flex-start" role="alert">'+
   '<span class="lpj-ring" style="width:48px;height:48px;background:#f1f0ea;flex-shrink:0">'+ICON.no.replace(/34/g,'24')+'</span>'+
   '<div><h1 id="lpjTitle" style="margin:0;font-size:16px">הבקשה לא אושרה</h1><p style="margin:4px 0 0;font-size:13px;color:#3a443d;line-height:1.5">'+(t.manager?'אם זו טעות, דברו עם '+esc(t.manager)+' ושלחו בקשה חדשה מאותו קישור.':'אם זו טעות, דברו עם המנהל ושלחו בקשה חדשה מאותו קישור.')+'</p>'+
   '<button type="button" class="lpj-btn out" id="lpjAgain" style="width:auto;margin-top:10px;padding:0 16px;min-height:44px">בקשה חדשה</button>'+
   '<p style="margin:6px 0 0;font-size:11.5px;color:#5f6861">עד 3 בקשות ביום מאותו טלפון.</p></div></section>'+back()+'</div>');
  $('lpjAgain').onclick=()=>showForm(st.name);
 }
 async function showApproved(){
  stop();
  const t=st.trip||{},me=st.me||{};
  const transfer=!o.inApp&&isIos()&&!isStandalone();
  paint('approved',hero(true)+'<div class="lpj-body"><div class="lpj-center" style="padding-top:18px"><span class="lpj-ring" style="width:68px;height:68px;background:#edf8f3">'+ICON.bigCheck+'</span>'+
   '<h2 id="lpjTitle">הבקשה אושרה – ברוכים הבאים, '+esc(me.display_name||st.name)+'!</h2>'+
   '<p>הצטרפת לטיול בתפקיד '+esc(ROLE[me.role]||me.role||'')+'.</p></div>'+
   (transfer?'<section class="lpj-card" style="border-color:#cfe1d7" id="lpjTransfer"><b style="display:block;font-size:14.5px;margin-bottom:4px">מוסיפים את האפליקציה למסך הבית</b>'+
    '<p style="margin:0 0 12px;font-size:12.5px;color:#5f6861;line-height:1.5">באייפון, האפליקציה ממסך הבית לא מכירה את מה שקרה בספארי. הקוד הזה מעביר אליה את החברות שלך.</p>'+
    '<div style="display:flex;flex-direction:column;gap:8px;margin-bottom:14px">'+
    '<div class="lpj-tick"><span class="lpj-n">1</span><span>לוחצים על כפתור השיתוף בספארי ← "הוספה למסך הבית"</span></div>'+
    '<div class="lpj-tick"><span class="lpj-n">2</span><span>פותחים את Lonely Planner ממסך הבית</span></div>'+
    '<div class="lpj-tick"><span class="lpj-n">3</span><span>מקלידים את הקוד</span></div></div>'+
    '<div class="lpj-code"><div style="font-size:11.5px;font-weight:700;color:#5f6861">קוד ההעברה שלך</div><b id="lpjCode" aria-live="polite">· · ·</b>'+
    '<div style="font-size:11.5px;color:#5f6861">בתוקף 24 שעות · פעם אחת</div>'+
    '<button type="button" class="lpj-link" id="lpjCopy" aria-label="העתקת הקוד" disabled>העתקה</button></div></section>'+
    '<button type="button" class="lpj-btn out" id="lpjOpen">לא עכשיו – פתיחת הטיול כאן</button>'
   :'<button type="button" class="lpj-btn" id="lpjOpen">פתיחת הטיול</button>'+
    (o.inApp?'':'<p style="margin:0;text-align:center;font-size:12px;color:#5f6861">אפשר גם להתקין את האפליקציה – היא תמשיך עם אותה זהות.</p>'))+
   '</div>');
  $('lpjOpen').onclick=()=>{stop();try{o.onEnter(t.trip_id,me.role,me.display_name||st.name)}catch(e){console.warn('[lpj] enter failed',e)}};
  if(transfer){
   try{
    const r=await fn({action:'issue_transfer',trip_id:t.trip_id});
    const codeEl=$('lpjCode');if(!codeEl)return;
    codeEl.textContent=r.code.slice(0,3)+' '+r.code.slice(3);
    const cp=$('lpjCopy');cp.disabled=false;
    cp.onclick=async()=>{let ok=false;try{if(navigator.clipboard){await navigator.clipboard.writeText(r.code);ok=true}}catch{}toast(ok?TX.copied:'אפשר לסמן את הקוד ולהעתיק.')};
   }catch(e){const c=$('lpjCode');if(c)c.textContent='—';toast(errText(e))}
  }
 }

 /* --- actions --- */
 function route(me){
  st.me=me||null;
  if(!me){showForm(st.name);return}
  if(me.status==='active'){showApproved();return}
  if(me.status==='pending'){showPending();return}
  if(me.status==='removed'){showRemoved();return}
  showForm(st.name);
 }
 async function load(){
  if(!st.code){showInvalid();return}
  if(!online()){showError(TX.offline,load);return}
  showLoading();
  try{
   const p=await fn({action:'preview',code:st.code});
   st.trip=p;route(p.me);
  }catch(e){
   if(e.code==='code_invalid'){showInvalid();return}
   showError(errText(e),load);
  }
 }
 async function submit(){
  if(st.busy)return;
  const inp=$('lpjName'),name=String(inp&&inp.value||'').trim().replace(/\s+/g,' ');
  st.name=name;
  if(!name||name.length>40){showForm(name,TX.nameInvalid);return}
  if(!online()){toast(TX.offline);return}
  st.busy=true;const b=$('lpjSubmit');if(b){b.disabled=true;b.textContent='שולחים…'}
  try{
   const r=await fn({action:'request',code:st.code,display_name:name});
   st.trip=Object.assign({},st.trip,{trip_id:r.trip_id});
   route({member_id:r.member_id,status:r.status,role:r.role,display_name:r.display_name});
  }catch(e){
   if(e.code==='name_taken')showForm(name,'יש כבר "'+name+'" בטיול. אפשר להוסיף אות או שם משפחה, למשל "'+name+' ל".');
   else if(e.code==='name_invalid')showForm(name,TX.nameInvalid);
   else if(e.code==='code_invalid')showInvalid();
   else if(e.code==='member_removed')showRemoved();
   else{toast(errText(e));const bb=$('lpjSubmit');if(bb){bb.disabled=false;bb.textContent='בקשת הצטרפות'}}
  }finally{st.busy=false}
 }
 async function cancel(){
  if(st.busy)return;
  if(!online()){toast(TX.offline);return}
  st.busy=true;
  try{await fn({action:'cancel',trip_id:st.trip.trip_id});showForm(st.name||(st.me&&st.me.display_name)||'')}
  catch(e){if(e.code==='not_pending'){await check()}else toast(errText(e))}
  finally{st.busy=false}
 }
 /* the waiting screen: Realtime on the own row + a poll every 20 s and when the page becomes visible (spec §1.2) */
 async function check(){
  if(st.closed||!st.me||!st.me.member_id)return;
  try{
   const c=await client();
   const{data,error}=await c.from('trip_members').select('id,status,role,display_name').eq('id',st.me.member_id).maybeSingle();
   if(error)return;
   if(!data){if(el.dataset.screen==='pending')showRejected();return}
   if(data.status==='active'&&el.dataset.screen==='pending'){st.me=Object.assign({},st.me,{status:'active',role:data.role,display_name:data.display_name});showApproved()}
   else if(data.status==='removed')showRemoved();
  }catch{}
 }
 async function watch(){
  stop();
  st.timer=setInterval(check,POLL_MS);
  try{
   const c=await client();
   if(c.channel&&st.me&&st.me.member_id&&el.dataset.screen==='pending'){
    st.chan=c.channel('lpj-'+st.me.member_id)
     .on('postgres_changes',{event:'*',schema:'public',table:'trip_members',filter:'id=eq.'+st.me.member_id},()=>{check()})
     .subscribe();
   }
  }catch(e){console.warn('[lpj] realtime unavailable; polling only')}
 }
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&el.dataset.screen==='pending')check()});
 window.addEventListener('online',()=>{if(el.dataset.screen==='pending')check()});

 load();
 return{destroy(){st.closed=true;stop();try{toastEl.remove()}catch{}},state:()=>({screen:el.dataset.screen,trip:st.trip&&st.trip.trip_id,me:st.me})};
}

try{Object.defineProperty(window,'LPJoin',{value:Object.freeze({version:VERSION,mount,normCode}),writable:false,configurable:false})}catch{window.LPJoin={version:VERSION,mount,normCode}}
})();
