/* Lonely Planner · F07 (a member who changed phones gets back into the trip) · page side · version 3.0.0-alpha.16
   CHANGE 2026-11-16 F07-UI-01: new file (no previous version). Conversation 2 of 3 (docs/F07_spec.md §3, mockup row 13 screens 1, 2, 3, 7):
   - the /join/ side (used by join/flow.js, which calls these hooks only when RELINK_FEATURE='on' and this file is loaded): the switch
     "אני חדש/ה בטיול" / "כבר הייתי בטיול" (D1), the name list as radio buttons (D2), the pending screen with "בתוקף עד" and a WhatsApp button
     to the manager, the expired screen (D5, "הבקשה פגה"), the note for a member whose relink was approved;
   - the manager's home side (used by the F05 block of app/index.html): the "מכשיר חדש" tag and the request body without a role picker (C6);
   - a one-time toast in the app after a relink was approved on this device.
   Everything here is additive: with RELINK_FEATURE='off' nobody calls it. Conversation 3 adds devices per member, "אני · <שם>" and the login notice.
   Exposes only window.__ptF07 = {ok, version, form, pending, expired, approvedNote, markNotice, tag, mgrOpenHtml, mountApp}.
   No network of its own: requests go through the caller's ctx.fn (join-trip, action 'request' with `person`). No storage except the one flag
   pt:_device:relink_notice (set when the member opens the trip, read once by mountApp). */
(function(){
'use strict';
if(window.__ptF07)return;
const VERSION='3.0.0-alpha.16';
const NOTICE_KEY='pt:_device:relink_notice';
const TX={
 modeNew:'אני חדש/ה בטיול',modeBack:'כבר הייתי בטיול',
 who:'מי אתם ברשימה?',
 pickHelp:'המנהל יאשר שזה אתם. השם, התפקיד והרשומות שלכם נשמרים.',
 pickErr:'בחרו את השם שלכם מהרשימה.',
 send:'בקשה לחבר את הטלפון הזה',sending:'שולחים…',
 gone:'השם הזה כבר לא ברשימה. בחרו שוב.',
 acct:'כבר בטיול? כניסה עם החשבון',
 lostNote:'מסמכים ושינויים שנשמרו רק בטלפון הקודם לא עוברים.',
 mgrWarn:'בקשה לחבר מכשיר חדש לחבר קיים. אשרו רק אם זה באמת הוא/היא – השם והתפקיד נשמרים.',
 offline:'אין חיבור. נסו שוב כשהרשת תחזור.'
};
const CSS=`
.lpj-sw{display:flex;gap:4px;background:#e9ece5;border-radius:14px;padding:4px;margin:0 0 12px}
.lpj-sw button{flex:1;min-height:44px;border:0;border-radius:11px;background:transparent;color:#3a443d;font-size:14px;font-weight:700;font-family:inherit;cursor:pointer}
.lpj-sw button[aria-pressed="true"]{background:#fff;color:#0f5c43;box-shadow:0 1px 4px #0000001f}
.lpj-rad{display:flex;flex-direction:column;gap:8px;margin:0;padding:0;border:0}
.lpj-rad label{display:flex;align-items:center;gap:10px;min-height:48px;padding:0 14px;border:1.5px solid #d6d9cf;border-radius:12px;font-size:15px;cursor:pointer}
.lpj-rad input{width:20px;height:20px;accent-color:#0f6b4f;flex-shrink:0}
.lpj-rad label:has(input:checked){border-color:#0f6b4f;background:#edf8f3}
.lpj-note{background:#fef3e2;border:1px solid #f1d9ad;border-radius:14px;padding:12px 14px;font-size:13px;color:#6b3d03;line-height:1.5}
.lpj-wa{text-decoration:none}
.lpj-body a.lpj-link{display:inline-flex;align-items:center;justify-content:center}
.pt7-tag{display:inline-block;margin-inline-start:6px;background:#e3eefb;color:#1a4c8b;border-radius:999px;padding:1px 8px;font-size:11px;font-weight:800;vertical-align:middle}
.pt7-warn{margin:0;font-size:12.5px;line-height:1.5;color:#6b3d03;background:#fef3e2;border-radius:10px;padding:8px 10px}
`;
function css(){
 if(document.getElementById('pt7Css'))return;
 const s=document.createElement('style');s.id='pt7Css';s.textContent=CSS;document.head.appendChild(s);
}
function hm(iso){
 const d=new Date(iso);if(!isFinite(d.getTime()))return'';
 const p=n=>String(n).padStart(2,'0');
 return p(d.getHours())+':'+p(d.getMinutes())+' · '+p(d.getDate())+'/'+p(d.getMonth()+1);
}

/* ---------- /join/ : the form (screen F07_Join) ---------- */
function form(c){
 css();
 const people=(c.st.trip&&c.st.trip.people)||[];
 if(!Array.isArray(people)||!people.length)return;            /* nobody to pick: the plain form stays */
 const card=c.el.querySelector('.lpj-card.lift');if(!card)return;
 const mode=c.st.f07mode==='back'?'back':'new';
 const sw=document.createElement('div');sw.className='lpj-sw';sw.setAttribute('role','group');sw.setAttribute('aria-label','סוג ההצטרפות');
 sw.innerHTML='<button type="button" id="lpjModeNew" aria-pressed="'+(mode==='new')+'">'+TX.modeNew+'</button>'+
  '<button type="button" id="lpjModeBack" aria-pressed="'+(mode==='back')+'">'+TX.modeBack+'</button>';
 card.parentNode.insertBefore(sw,card);
 c.$('lpjModeNew').onclick=()=>{if(c.st.f07mode!=='new'){c.st.f07mode='new';c.showForm(c.st.name)}};
 c.$('lpjModeBack').onclick=()=>{if(c.st.f07mode!=='back'){c.st.f07mode='back';c.showForm(c.st.name)}};
 if(mode!=='back')return;
 card.innerHTML='<fieldset class="lpj-rad" id="lpjPeople" style="margin:0;padding:0;border:0"><legend class="lpj-lbl">'+TX.who+'</legend>'+
  people.map((p,i)=>'<label><input type="radio" name="lpjPerson" value="'+c.esc(p.person_id)+'"'+(c.st.f07person===p.person_id?' checked':'')+'><span>'+c.esc(p.display_name)+'</span></label>').join('')+
  '</fieldset><div class="lpj-err" id="lpjRelinkErr" role="alert" hidden></div>'+
  '<p class="lpj-help">'+TX.pickHelp+'</p><div style="height:12px"></div>'+
  '<button type="button" class="lpj-btn" id="lpjRelink">'+TX.send+'</button>'+
  (c.inApp?'':'<div style="text-align:center"><a class="lpj-link" id="lpjAcct" href="../app/">'+TX.acct+'</a></div>');
 card.querySelectorAll('input[name="lpjPerson"]').forEach(r=>r.onchange=()=>{c.st.f07person=r.value;const e=c.$('lpjRelinkErr');if(e)e.hidden=true});
 c.$('lpjRelink').onclick=()=>request(c,c.st.f07person);
}
function showErr(c,msg){const e=c.$('lpjRelinkErr');if(e){e.textContent=msg;e.hidden=false}else c.toast(msg)}
async function request(c,personId){
 if(c.st.busy)return;
 if(!personId){showErr(c,TX.pickErr);return}
 if(!c.online()){c.toast(TX.offline);return}
 c.st.busy=true;const b=c.$('lpjRelink')||c.$('lpjRelinkAgain');if(b){b.disabled=true;b.textContent=TX.sending}
 try{
  const r=await c.fn({action:'request',code:c.st.code,person:personId});
  c.st.trip=Object.assign({},c.st.trip,{trip_id:r.trip_id});
  c.st.relinkInfo=r.relink?{display_name:r.display_name,role:r.role,expires_at:r.expires_at}:null;
  c.st.busy=false;
  c.route({member_id:r.member_id,status:r.status,role:r.role,display_name:r.display_name});
 }catch(e){
  c.st.busy=false;
  const k=e&&e.code;
  if(k==='person_invalid'||k==='already_member'||k==='code_invalid'){if(k==='person_invalid')c.toast(TX.gone);c.st.f07person=null;c.load();return}
  if(b){b.disabled=false;b.textContent=TX.send}
  c.toast(c.errText(e));
 }
}

/* ---------- /join/ : waiting (F07_Pending) ---------- */
function pending(c){
 css();
 const t=c.st.trip||{},ri=c.st.relinkInfo||{},me=c.st.me||{};
 const name=ri.display_name||me.display_name||c.st.name||'',role=ri.role||me.role;
 const until=ri.expires_at?hm(ri.expires_at):'';
 const wa='https://wa.me/?text='+encodeURIComponent('היי, זה '+name+'. ביקשתי לחבר טלפון חדש לטיול '+(t.name||'')+' – אפשר לאשר?');
 c.paint('pending',c.hero(true)+'<div class="lpj-body"><div class="lpj-center"><span class="lpj-ring" style="background:#fef3e2"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#b45309" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></span>'+
  '<h2 id="lpjTitle">'+(t.manager?'הבקשה נשלחה ל'+c.esc(t.manager):'הבקשה נשלחה למנהל')+'</h2>'+
  '<p>אחרי האישור הטיול ייפתח כאן לבד, עם אותו שם ואותו תפקיד. אפשר לסגור ולחזור לאותו קישור.</p>'+
  '<span class="lpj-pill">מכשיר חדש · '+c.esc(name)+(role&&c.ROLE[role]?' · '+c.esc(c.ROLE[role]):'')+'</span>'+
  (until?'<p id="lpjUntil" style="margin-top:10px;font-size:12.5px;color:#5f6861">בתוקף עד '+c.esc(until)+'</p>':'')+'</div>'+
  '<a class="lpj-btn out lpj-wa" id="lpjWa" href="'+wa+'" target="_blank" rel="noopener noreferrer">שליחת הודעה למנהל בווטסאפ</a>'+
  '<button type="button" class="lpj-btn ghost" id="lpjCancel">ביטול הבקשה</button></div>');
 c.$('lpjCancel').onclick=c.cancel;
 c.watch();
 /* D5: when the 24 h are over the screen reloads the preview, which reports "expired" once */
 const ms=ri.expires_at?Date.parse(ri.expires_at)-Date.now():NaN;
 if(isFinite(ms)){setTimeout(()=>{if(c.el.dataset.screen==='pending')c.load()},Math.min(Math.max(ms,0)+800,2147483000))}
}

/* ---------- /join/ : expired (F07_Expired) ---------- */
function expired(c,rl){
 css();
 const people=(c.st.trip&&c.st.trip.people)||[];
 const who=people.find(p=>p.display_name===(rl&&rl.display_name));
 c.paint('expired',c.hero(true)+'<div class="lpj-body"><div class="lpj-center" style="padding-top:18px"><span class="lpj-ring" style="background:#f1f0ea"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#3a443d" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></span>'+
  '<h2 id="lpjTitle">הבקשה פגה</h2><p>הבקשה'+(rl&&rl.display_name?' של '+c.esc(rl.display_name):'')+' לא אושרה תוך 24 שעות. אפשר לשלוח בקשה חדשה.</p></div>'+
  (who?'<button type="button" class="lpj-btn" id="lpjRelinkAgain">בקשה חדשה</button>':'')+
  '<button type="button" class="lpj-btn out" id="lpjBackToName">חזרה לבחירת שם</button>'+c.back()+'</div>');
 const a=c.$('lpjRelinkAgain');if(a)a.onclick=()=>request(c,who.person_id);
 c.$('lpjBackToName').onclick=()=>{c.st.f07mode='back';c.st.f07person=who?who.person_id:null;c.showForm(c.st.name)};
}

/* ---------- /join/ : after the approval ---------- */
function approvedNote(){return'<div class="lpj-note" id="lpjLostNote" role="note">'+TX.lostNote+'</div>'}
function markNotice(){try{localStorage.setItem(NOTICE_KEY,'1')}catch(e){}}

/* ---------- app: the manager's home card (F07_HomeManager) ---------- */
function tag(){return'<span class="pt7-tag">מכשיר חדש</span>'}
function mgrOpenHtml(o){
 const off=o.off||o.busy;
 return'<p class="pt7-warn" id="pt7Warn">'+TX.mgrWarn+'</p>'+
  '<div class="pt5-acts"><button type="button" class="pt5-btn pt5-grow" data-act="approve"'+(off?' disabled':'')+'>אישור המכשיר</button>'+
  '<button type="button" class="pt5-btn ghost" data-act="reject"'+(off?' disabled':'')+'>דחייה</button></div>';
}

/* ---------- app: one-time toast on the new device ---------- */
function mountApp(o){
 try{
  if(localStorage.getItem(NOTICE_KEY)!=='1')return false;
  localStorage.removeItem(NOTICE_KEY);
  if(o&&typeof o.toast==='function')o.toast(TX.lostNote);
  return true;
 }catch(e){return false}
}

try{Object.defineProperty(window,'__ptF07',{value:Object.freeze({ok:true,version:VERSION,form,pending,expired,approvedNote,markNotice,tag,mgrOpenHtml,mountApp}),writable:false,configurable:false})}
catch(e){window.__ptF07={ok:true,version:VERSION,form,pending,expired,approvedNote,markNotice,tag,mgrOpenHtml,mountApp}}
})();
