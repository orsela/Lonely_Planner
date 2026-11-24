/* Lonely Planner · F07 (a member who changed phones gets back into the trip) · page side · version 3.0.0-alpha.18.6
   CHANGE 2026-11-24 F13-JOIN-02: what changed from 3.0.0-alpha.16: the /join/ side (form, pending, expired, approvedNote) speaks the language of join/flow.js through J() = window.LPJoin.t with the keys 'f7.*'
   (dictionary in join/flow.js); with no LPJoin (or English off) the same Hebrew strings as before. The app side of this file is untouched (stage 4).
   Previous: Lonely Planner · F07 · page side · version 3.0.0-alpha.16
   CHANGE 2026-11-16 F07-UI-02: what changed from conversation 2 (same version 3.0.0-alpha.16, f07-build 2f3243b): the APP side was added at the end of this file
   (spec §3, mockup row 13 screens 4, 5, 6): devices per person in "חברים וקישור" (grouped by person, "ניתוק" per device, never on the current device or a
   person's last device), the "המכשירים שלי" card in "אני · <שם>" (F22a screen), the manager's login-notice card (C8, "הבנתי" / ניתוק), the device_revoked
   sign-out (C4), offline states (buttons disabled + the offline line), a 60 s refresh. New exports: attach, start, refresh, people, devsHtml, foot, meCard,
   onTouchError (+ pure helpers under t). Nothing of conversation 2 changed. Everything is a no-op unless RELINK_FEATURE='on' (and cloud mode).
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
const VERSION='3.0.0-alpha.18.6'; /* CHANGE 2026-11-24 F13-JOIN-02: was '3.0.0-alpha.16' */
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
/* CHANGE 2026-11-24 F13-JOIN-02: new — J(key, params, html): the /join/ text in the current language (Hebrew fallback = TX / the old inline text) */
function J(k,p,h,fb){try{const L=window.LPJoin;if(L&&L.t)return L.t(k,p,h)}catch(e){}return fb}
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
.pt7-devs{display:flex;flex-direction:column;gap:2px;margin:0 0 6px;padding-inline-start:46px}
.pt7-dev{display:flex;align-items:center;gap:8px;min-height:44px}
.pt7-dev .pt7-dnm{flex:1;min-width:0}
.pt7-dev .pt7-dnm b{display:block;font-size:12.5px;font-weight:700;overflow-wrap:anywhere}
.pt7-sub{display:block;font-size:11.5px;color:#6b746d}
.pt7-dbtn{min-width:64px;min-height:44px;border:1px solid #e4e6df;border-radius:12px;background:#fff;color:#b42318;font:inherit;font-size:12.5px;font-weight:700;cursor:pointer;padding:0 10px}
.pt7-dbtn.arm{background:#b42318;color:#fff;border-color:#b42318}
.pt7-dbtn[disabled]{opacity:.5;cursor:default}
.pt7-foot{margin:4px 2px 0;font-size:11.5px;color:#6b746d;line-height:1.5}
.pt7-card{background:#fff;border:1.5px solid #cfe0f5;border-radius:18px;padding:12px 14px;margin:0 0 10px;display:flex;flex-direction:column;gap:10px}
.pt7-nh{display:flex;justify-content:space-between;align-items:center;gap:8px}
.pt7-nh b{font-size:14.5px}
.pt7-n{display:flex;flex-direction:column;gap:6px;border-top:1px solid #e9eef6;padding-top:8px}
.pt7-n:first-of-type{border-top:0;padding-top:0}
.pt7-n p{margin:0;font-size:13.5px;line-height:1.5}
.pt7-nacts{display:flex;gap:8px;flex-wrap:wrap}
.pt7-nacts button{min-height:44px;border-radius:12px;border:1px solid #e4e6df;background:#fff;color:#17211b;font:inherit;font-size:13px;font-weight:700;padding:0 14px;cursor:pointer}
.pt7-nacts button.ok{background:#0f6b4f;color:#fff;border-color:#0f6b4f}
.pt7-nacts button.arm{background:#b42318;color:#fff;border-color:#b42318}
.pt7-nacts button[disabled]{opacity:.5;cursor:default}
.pt7-off{margin:0;font-size:12px;color:#8a4a03}
#pt7Rev{position:fixed;inset:0;z-index:5000;background:#fff;display:flex;align-items:center;justify-content:center;padding:24px;text-align:center}
#pt7Rev .in{max-width:380px;display:flex;flex-direction:column;gap:14px}
#pt7Rev h2{margin:0;font-size:20px}#pt7Rev p{margin:0;font-size:14px;line-height:1.6;color:#3a443d}
#pt7Rev button{min-height:48px;border:0;border-radius:12px;background:#0f6b4f;color:#fff;font:inherit;font-size:15px;font-weight:700;cursor:pointer}
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
 const sw=document.createElement('div');sw.className='lpj-sw';sw.setAttribute('role','group');sw.setAttribute('aria-label',J('f7.modeAria',0,0,'סוג ההצטרפות'));
 sw.innerHTML='<button type="button" id="lpjModeNew" aria-pressed="'+(mode==='new')+'">'+J('f7.modeNew',0,0,TX.modeNew)+'</button>'+
  '<button type="button" id="lpjModeBack" aria-pressed="'+(mode==='back')+'">'+J('f7.modeBack',0,0,TX.modeBack)+'</button>';
 card.parentNode.insertBefore(sw,card);
 c.$('lpjModeNew').onclick=()=>{if(c.st.f07mode!=='new'){c.st.f07mode='new';c.showForm(c.st.name)}};
 c.$('lpjModeBack').onclick=()=>{if(c.st.f07mode!=='back'){c.st.f07mode='back';c.showForm(c.st.name)}};
 if(mode!=='back')return;
 card.innerHTML='<fieldset class="lpj-rad" id="lpjPeople" style="margin:0;padding:0;border:0"><legend class="lpj-lbl">'+J('f7.who',0,0,TX.who)+'</legend>'+
  people.map((p,i)=>'<label><input type="radio" name="lpjPerson" value="'+c.esc(p.person_id)+'"'+(c.st.f07person===p.person_id?' checked':'')+'><span>'+c.esc(p.display_name)+'</span></label>').join('')+
  '</fieldset><div class="lpj-err" id="lpjRelinkErr" role="alert" hidden></div>'+
  '<p class="lpj-help">'+J('f7.pickHelp',0,0,TX.pickHelp)+'</p><div style="height:12px"></div>'+
  '<button type="button" class="lpj-btn" id="lpjRelink">'+J('f7.send',0,0,TX.send)+'</button>'+
  (c.inApp?'':'<div style="text-align:center"><a class="lpj-link" id="lpjAcct" href="../app/">'+J('f7.acct',0,0,TX.acct)+'</a></div>');
 card.querySelectorAll('input[name="lpjPerson"]').forEach(r=>r.onchange=()=>{c.st.f07person=r.value;const e=c.$('lpjRelinkErr');if(e)e.hidden=true});
 c.$('lpjRelink').onclick=()=>request(c,c.st.f07person);
}
function showErr(c,msg){const e=c.$('lpjRelinkErr');if(e){e.textContent=msg;e.hidden=false}else c.toast(msg)}
async function request(c,personId){
 if(c.st.busy)return;
 if(!personId){showErr(c,J('f7.pickErr',0,0,TX.pickErr));return}
 if(!c.online()){c.toast(J('offline',0,0,TX.offline));return}
 c.st.busy=true;const b=c.$('lpjRelink')||c.$('lpjRelinkAgain');if(b){b.disabled=true;b.textContent=J('f7.sending',0,0,TX.sending)}
 try{
  const r=await c.fn({action:'request',code:c.st.code,person:personId});
  c.st.trip=Object.assign({},c.st.trip,{trip_id:r.trip_id});
  c.st.relinkInfo=r.relink?{display_name:r.display_name,role:r.role,expires_at:r.expires_at}:null;
  c.st.busy=false;
  c.route({member_id:r.member_id,status:r.status,role:r.role,display_name:r.display_name});
 }catch(e){
  c.st.busy=false;
  const k=e&&e.code;
  if(k==='person_invalid'||k==='already_member'||k==='code_invalid'){if(k==='person_invalid')c.toast(J('f7.gone',0,0,TX.gone));c.st.f07person=null;c.load();return}
  if(b){b.disabled=false;b.textContent=J('f7.send',0,0,TX.send)}
  c.toast(c.errText(e));
 }
}

/* ---------- /join/ : waiting (F07_Pending) ---------- */
function pending(c){
 css();
 const t=c.st.trip||{},ri=c.st.relinkInfo||{},me=c.st.me||{};
 const name=ri.display_name||me.display_name||c.st.name||'',role=ri.role||me.role;
 const until=ri.expires_at?hm(ri.expires_at):'';
 const wa='https://wa.me/?text='+encodeURIComponent(J('f7.waMsg',{n:name,trip:t.name||''},0,'היי, זה '+name+'. ביקשתי לחבר טלפון חדש לטיול '+(t.name||'')+' – אפשר לאשר?'));
 c.paint('pending',c.hero(true)+'<div class="lpj-body"><div class="lpj-center"><span class="lpj-ring" style="background:#fef3e2"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#b45309" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg></span>'+
  '<h2 id="lpjTitle">'+(t.manager?J('pendM',{m:t.manager},1,'הבקשה נשלחה ל'+c.esc(t.manager)):J('pend',0,0,'הבקשה נשלחה למנהל'))+'</h2>'+
  '<p>'+J('f7.pendP',0,0,'אחרי האישור הטיול ייפתח כאן לבד, עם אותו שם ואותו תפקיד. אפשר לסגור ולחזור לאותו קישור.')+'</p>'+
  '<span class="lpj-pill">'+J('f7.pillNew',{n:name},1,'מכשיר חדש · '+c.esc(name))+(role&&c.ROLE[role]?' · '+c.esc(c.ROLE[role]):'')+'</span>'+
  (until?'<p id="lpjUntil" style="margin-top:10px;font-size:12.5px;color:#5f6861">'+J('f7.until',{t:until},1,'בתוקף עד '+c.esc(until))+'</p>':'')+'</div>'+
  '<a class="lpj-btn out lpj-wa" id="lpjWa" href="'+wa+'" target="_blank" rel="noopener noreferrer">'+J('f7.wa',0,0,'שליחת הודעה למנהל בווטסאפ')+'</a>'+
  '<button type="button" class="lpj-btn ghost" id="lpjCancel">'+J('cancel',0,0,'ביטול הבקשה')+'</button></div>');
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
  '<h2 id="lpjTitle">'+J('f7.expT',0,0,'הבקשה פגה')+'</h2><p>'+(rl&&rl.display_name?J('f7.expPN',{n:rl.display_name},1,'הבקשה של '+c.esc(rl.display_name)+' לא אושרה תוך 24 שעות. אפשר לשלוח בקשה חדשה.'):J('f7.expP',0,0,'הבקשה לא אושרה תוך 24 שעות. אפשר לשלוח בקשה חדשה.'))+'</p></div>'+
  (who?'<button type="button" class="lpj-btn" id="lpjRelinkAgain">'+J('f7.again',0,0,'בקשה חדשה')+'</button>':'')+
  '<button type="button" class="lpj-btn out" id="lpjBackToName">'+J('f7.backName',0,0,'חזרה לבחירת שם')+'</button>'+c.back()+'</div>');
 const a=c.$('lpjRelinkAgain');if(a)a.onclick=()=>request(c,who.person_id);
 c.$('lpjBackToName').onclick=()=>{c.st.f07mode='back';c.st.f07person=who?who.person_id:null;c.showForm(c.st.name)};
}

/* ---------- /join/ : after the approval ---------- */
function approvedNote(){return'<div class="lpj-note" id="lpjLostNote" role="note">'+J('f7.lostNote',0,0,TX.lostNote)+'</div>'}
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


/* ---------- app side (conversation 3): devices per person, "המכשירים שלי", login notice (C8), device_revoked ---------- */
const AX={
 offline:'אין חיבור – אפשר לנתק כשהרשת תחזור.',
 thisDev:'המכשיר הזה',
 dis:'ניתוק',disArm:'לנתק? לחצו שוב',
 gone:'המכשיר נותק',
 lastDev:'זה המכשיר היחיד של החבר – אי אפשר לנתק אותו',
 notMgr:'רק מנהלים יכולים לנתק מכשיר של חבר אחר',
 fail:'משהו השתבש. נסו שוב.',
 footMgr:'ניתוק מכשיר לא מסיר את החבר מהטיול. שינוי תפקיד או הסרה חלים על כל המכשירים.',
 mineT:'המכשירים שלי',
 mineOne:'זה המכשיר היחיד שלך בטיול. אפשר לחבר מכשיר נוסף דרך קישור ההצטרפות ("כבר הייתי בטיול") או דרך חשבון כניסה.',
 mineFoot:'ניתוק מכשיר לא מסיר אותך מהטיול. מסמכים שנשמרו רק במכשיר שמנותק לא יועברו.',
 noticeT:'כניסה ממכשיר חדש',noticeSub:'רק מנהלים רואים',
 ack:'הבנתי',notMe:'זה לא הוא/היא · ניתוק',
 revT:'המכשיר הזה נותק מהטיול',
 revP:'המכשיר נותק – על ידי מנהל הטיול או על ידי החבר עצמו מטלפון אחר. כדי לחזור לטיול אפשר להיכנס שוב עם החשבון, או לבקש חיבור מחדש מהקישור.',
 revBtn:'המשך',
 loading:'טוען…'
};
const DKEY='pt7_devices';
const S={persons:[],notices:[],current:null,my:null,isMgr:false,loaded:false,busy:false,at:0,rv:false,armed:null,armT:null,started:false,again:null};
let A=null,H={};
const $=id=>document.getElementById(id);
function esc(x){return String(x==null?'':x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c])}
function flagOn(){
 try{return typeof RELINK_FEATURE!=='undefined'&&RELINK_FEATURE==='on'&&typeof STORAGE_BACKEND!=='undefined'&&STORAGE_BACKEND==='cloud'}catch(e){return false}
}
function isOn(){return flagOn()&&!!A}
function netOk(){return navigator.onLine!==false}
function tripNow(){try{const t=A&&A.tripId();return t&&t!=='local'?t:null}catch(e){return null}}
function ago(iso){
 if(!iso)return'עוד לא נכנס/ה';
 const d=new Date(iso);if(!isFinite(d.getTime()))return'עוד לא נכנס/ה';
 const a=new Date();a.setHours(0,0,0,0);const b=new Date(d);b.setHours(0,0,0,0);
 const n=Math.round((a-b)/86400000);
 return n<=0?'פעיל/ה היום':n===1?'פעיל/ה אתמול':'לפני '+n+' ימים';
}
function viaName(v){
 const m={email:'קוד למייל',google:'Google',facebook:'Facebook',twitter:'X',x:'X',whatsapp:'WhatsApp'};
 const k=String(v||'').toLowerCase();
 if(!k||k==='anon')return'';
 return m[k]||(k.charAt(0).toUpperCase()+k.slice(1));
}
function devTitle(d){return(d&&d.label)||(d&&d.via&&d.via!=='anon'?'מכשיר · '+viaName(d.via):'טלפון')}
function isCurrent(d){
 if(!d)return false;
 if(d.session_id&&S.current)return d.session_id===S.current;
 try{return!!(H.myMemberId&&d.member_id===H.myMemberId())}catch(e){return false}
}
function devSub(d){
 const v=viaName(d.via);
 return(isCurrent(d)?AX.thisDev:ago(d.last_seen_at))+(v?' · '+v:'');
}
/* one representative row per person (the viewer's own row first), keeps the order of the list */
function people(list,uid){
 const out=[],at=new Map();
 (list||[]).forEach(m=>{
  const k=m.person_id||m.id,i=at.get(k);
  if(i==null){at.set(k,out.length);out.push(m)}
  else if(m.user_id===uid&&out[i].user_id!==uid)out[i]=m;
 });
 return out;
}
function personOf(m){const k=m&&(m.person_id||m.id);return S.persons.find(p=>p.person_id===k)||null}
function keyOf(a,m,s){return a+':'+m+':'+(s||'')}
function devRow(d,canCut,off,who){
 const k=keyOf('dis',d.member_id,d.session_id),arm=S.armed===k;
 return'<div class="pt7-dev" data-pt7-dev="'+esc(d.member_id)+'"><span aria-hidden="true">'+(d.via&&d.via!=='anon'?'🔑':'📱')+'</span>'+
  '<div class="pt7-dnm"><b>'+esc(devTitle(d))+'</b><span class="pt7-sub">'+esc(devSub(d))+'</span></div>'+
  (canCut?'<button type="button" class="pt7-dbtn'+(arm?' arm':'')+'" data-pt7="dis" data-m="'+esc(d.member_id)+'" data-s="'+esc(d.session_id||'')+'"'+(off?' disabled':'')+
   ' aria-label="ניתוק המכשיר '+esc(devTitle(d))+(who?' של '+esc(who):'')+'">'+(arm?AX.disArm:AX.dis)+'</button>':'')+'</div>';
}
/* under a person's row in "חברים וקישור" (F06 paintMembers) */
function devsHtml(m){
 if(!isOn())return'';
 const p=personOf(m);if(!p||!Array.isArray(p.devices)||!p.devices.length)return'';
 const off=!netOk(),many=p.devices.length>1;
 return'<div class="pt7-devs" data-pt7-person="'+esc(p.person_id)+'">'+p.devices.map(d=>devRow(d,many&&!isCurrent(d),off,p.display_name)).join('')+'</div>';
}
function foot(){return isOn()?'<p class="pt7-foot" id="pt7Foot">'+AX.footMgr+'</p>':''}
/* "אני · <שם>" → "המכשירים שלי" (F22a screen, after the account card) */
function mineHtml(){
 const off=!netOk(),p=S.persons.find(x=>x.person_id===S.my)||null;
 let h='<div class="pt22-head"><b id="pt7MineT">'+AX.mineT+'</b></div>';
 if(!p){h+='<p class="pt22-small" id="pt7MineWait">'+(S.loaded||!netOk()?AX.offline.replace('לנתק','לראות'):AX.loading)+'</p>';return h}
 const many=p.devices.length>1;
 h+='<div class="pt7-devs" style="padding-inline-start:0" id="pt7MineList">'+p.devices.map(d=>devRow(d,many&&!isCurrent(d),off,'')).join('')+'</div>';
 h+='<p class="pt7-foot" id="pt7MineFoot">'+(many?AX.mineFoot:AX.mineOne)+'</p>';
 if(off)h+='<p class="pt7-off" role="status" id="pt7MineOff">'+AX.offline+'</p>';
 return h;
}
function paintMine(){
 if(!flagOn()||!A)return;
 const body=$('ptF22MeBody'),acct=$('ptF22Acct');
 if(!body||!acct)return;
 let sec=$('pt7Mine');
 if(!sec){sec=document.createElement('section');sec.id='pt7Mine';sec.className='pt22-card';sec.setAttribute('aria-labelledby','pt7MineT');acct.parentNode.insertBefore(sec,acct.nextSibling)}
 sec.innerHTML=mineHtml();
}
function meCard(){
 if(!isOn())return;
 paintMine();
 if(Date.now()-S.at>20000)refresh(true);
}
/* the managers' login notice (C8) on home */
function homePanel(){try{return(typeof HOME_LAYOUT!=='undefined'&&HOME_LAYOUT==='v2')?$('homeV2'):$('home')}catch(e){return null}}
function noticeHtml(){
 const off=!netOk();
 let h='<div class="pt7-nh"><b id="pt7NoticeT">'+AX.noticeT+'</b><span class="pt7-sub">'+AX.noticeSub+'</span></div>';
 S.notices.forEach(n=>{
  const kd=keyOf('nodis',n.member_id,n.session_id),arm=S.armed===kd,v=viaName(n.via);
  h+='<div class="pt7-n" data-pt7-notice="'+esc(n.session_id)+'"><p><b>'+esc(n.display_name)+'</b> נכנס/ה ממכשיר חדש'+(v?' · '+esc(v):'')+'</p>'+
   '<span class="pt7-sub">'+esc(n.label||'מכשיר')+' · '+esc(ago(n.created_at))+'</span>'+
   '<div class="pt7-nacts"><button type="button" class="ok" data-pt7="ack" data-s="'+esc(n.session_id)+'"'+(off?' disabled':'')+'>'+AX.ack+'</button>'+
   '<button type="button"'+(arm?' class="arm"':'')+' data-pt7="nodis" data-m="'+esc(n.member_id)+'" data-s="'+esc(n.session_id)+'"'+(off?' disabled':'')+'>'+(arm?AX.disArm:AX.notMe)+'</button></div></div>';
 });
 if(off)h+='<p class="pt7-off" role="status">'+AX.offline.replace('לנתק','לאשר או לנתק')+'</p>';
 return h;
}
function paintNotices(){
 let card=$('pt7Notice');
 if(!flagOn()||!A||!S.isMgr||!S.notices.length){if(card)card.remove();return}
 const panel=homePanel();if(!panel)return;
 const p5=$('ptF05Pending');
 if(!card){
  card=document.createElement('section');card.id='pt7Notice';card.className='pt7-card';card.setAttribute('aria-labelledby','pt7NoticeT');
  const fs=$('ptFirstSteps');
  const anchor=(p5&&p5.parentNode===panel)?p5.nextSibling:((fs&&fs.parentNode===panel)?fs:(panel.querySelector('.hv2-map-hero')||(panel.querySelector('.topbar')&&panel.querySelector('.topbar').nextSibling)||panel.firstChild));
  panel.insertBefore(card,anchor);
 }else if(p5&&p5.parentNode===panel&&p5.nextSibling!==card)panel.insertBefore(card,p5.nextSibling);   /* requests first, notices under them */
 const html=noticeHtml();
 if(card.innerHTML!==html)card.innerHTML=html;
}
/* ---- network ---- */
async function callFn(body){
 const c=A&&A.client();if(!c)throw Object.assign(new Error('no client'),{code:'offline'});
 if(!netOk())throw Object.assign(new Error('offline'),{code:'offline'});
 const g=await c.auth.getSession();const tok=g&&g.data&&g.data.session&&g.data.session.access_token;
 if(!tok)throw Object.assign(new Error('no session'),{code:'unauthorized'});
 const ac=typeof AbortController!=='undefined'?new AbortController():null;
 const t=setTimeout(()=>{try{ac&&ac.abort()}catch(e){}},15000);
 let r;
 try{r=await fetch(A.endpoint,{method:'POST',headers:{'content-type':'application/json',apikey:A.key,authorization:'Bearer '+tok},body:JSON.stringify(body),signal:ac?ac.signal:undefined})}
 catch(e){throw Object.assign(new Error('network'),{code:netOk()?'network':'offline'})}
 finally{clearTimeout(t)}
 let j={};try{j=await r.json()}catch(e){}
 if(!r.ok||j.error)throw Object.assign(new Error(j.error||'http_'+r.status),{code:j.error||'http_'+r.status});
 return j;
}
function repaint(){
 paintNotices();paintMine();
 try{H.repaintMembers&&H.repaintMembers()}catch(e){}
}
function cacheSave(){try{localStorage.setItem(DKEY,JSON.stringify({persons:S.persons,notices:S.notices,current:S.current,my:S.my,isMgr:S.isMgr}))}catch(e){}}
function cacheLoad(){
 try{
  const c=JSON.parse(localStorage.getItem(DKEY)||'null');
  if(c&&Array.isArray(c.persons)){S.persons=c.persons;S.notices=Array.isArray(c.notices)?c.notices:[];S.current=c.current||null;S.my=c.my||null;S.isMgr=!!c.isMgr;S.loaded=true}
 }catch(e){}
}
async function refresh(force){
 if(!isOn()||S.busy||S.rv)return;
 const t=tripNow();if(!t||!netOk())return;
 if(!force&&Date.now()-S.at<1500){            /* a burst of members events = one call, and the last one always runs */
  if(!S.again)S.again=setTimeout(()=>{S.again=null;refresh(true)},1600);
  return;
 }
 S.busy=true;
 try{
  const r=await callFn({action:'devices',trip_id:t});
  S.persons=Array.isArray(r.persons)?r.persons:[];S.notices=Array.isArray(r.notices)?r.notices:[];
  S.current=r.current_session||null;S.my=r.my_person_id||null;S.isMgr=r.is_manager===true;S.loaded=true;S.at=Date.now();
  cacheSave();
 }catch(e){onTouchError(e)}
 finally{S.busy=false}
 repaint();
}
function arm(k){
 S.armed=k;clearTimeout(S.armT);
 S.armT=setTimeout(()=>{S.armed=null;repaint()},4000);
 repaint();
}
async function disconnect(m,s){
 const t=tripNow();if(!t)return;
 if(!netOk()){say(AX.offline);return}
 try{
  await callFn({action:'disconnect_device',trip_id:t,member_id:m,session_id:s||null});
  say(AX.gone);
 }catch(e){
  const c=e&&e.code;
  say(c==='offline'?AX.offline:c==='last_device'?AX.lastDev:c==='not_manager'?AX.notMgr:AX.fail);
 }
 S.armed=null;
 await refresh(true);
 try{H.reloadMembers&&H.reloadMembers()}catch(e){}
}
async function ackNotice(s){
 const t=tripNow();if(!t)return;
 if(!netOk()){say(AX.offline);return}
 try{await callFn({action:'ack_device_notice',trip_id:t,session_id:s})}catch(e){say((e&&e.code)==='offline'?AX.offline:AX.fail)}
 await refresh(true);
}
function say(m){try{H.toast&&H.toast(m)}catch(e){}}
function onClick(ev){
 const b=ev.target&&ev.target.closest&&ev.target.closest('[data-pt7]');
 if(!b||b.disabled)return;
 const a=b.getAttribute('data-pt7'),m=b.getAttribute('data-m'),s=b.getAttribute('data-s')||null;
 if(a==='ack'){ackNotice(s);return}
 const k=keyOf(a,m,s);
 if(S.armed!==k){arm(k);return}
 clearTimeout(S.armT);
 disconnect(m,s);
}
/* ---- device_revoked / dead session (C4): the next touch tells a disconnected device to sign out ---- */
function revoked(){
 if(S.rv)return;S.rv=true;
 /* CHANGE 2026-11-24 F12-REVOKE-01: new line (no alpha.17.1 equivalent), additive. This device was disconnected: the shared-vault copies saved on it (Cache API pt-docs-v1, F12) are deleted. f12.js missing: nothing happens. */
 try{if(window.__ptF12&&typeof window.__ptF12.clearAll==='function')window.__ptF12.clearAll()}catch(e){}
 try{const c=A&&A.client();if(c&&c.auth&&c.auth.signOut)c.auth.signOut({scope:'local'}).catch(()=>{})}catch(e){}
 css();
 const o=document.createElement('div');o.id='pt7Rev';o.setAttribute('role','alertdialog');o.setAttribute('aria-modal','true');o.setAttribute('aria-labelledby','pt7RevT');o.setAttribute('dir','rtl');
 o.innerHTML='<div class="in"><h2 id="pt7RevT">'+AX.revT+'</h2><p>'+AX.revP+'</p><button type="button" id="pt7RevBtn">'+AX.revBtn+'</button></div>';
 document.body.appendChild(o);
 const btn=$('pt7RevBtn');if(btn){btn.onclick=()=>{try{location.reload()}catch(e){}};try{btn.focus()}catch(e){}}
}
async function onTouchError(e){
 if(!flagOn()||!A||S.rv)return;
 const c=e&&e.code;
 if(c==='device_revoked'){revoked();return}
 if(c==='unauthorized'||c==='http_401'){
  try{                                                /* a plain 401 can also be a refresh hiccup: only a dead session signs out */
   const r=await A.client().auth.getUser(),er=r&&r.error;
   if(er&&(er.status===401||er.status===403||/session|jwt|token/i.test(String(er.message||''))))revoked();
  }catch(x){}
 }
}
function attach(a,h){
 if(A||!a||typeof a!=='object')return;
 A=a;H=h&&typeof h==='object'?h:{};
}
function start(){
 if(!isOn()||S.started)return;
 S.started=true;css();cacheLoad();
 document.addEventListener('click',onClick);
 window.addEventListener('online',()=>refresh(true));
 window.addEventListener('offline',repaint);
 setInterval(()=>{if(document.visibilityState==='visible'&&S.isMgr)refresh(true)},60000);
 try{const p=homePanel();if(p)new MutationObserver(()=>{if(S.notices.length&&S.isMgr&&!$('pt7Notice'))paintNotices()}).observe(p,{childList:true})}catch(e){}
 refresh(true);
}

try{Object.defineProperty(window,'__ptF07',{value:Object.freeze({ok:true,version:VERSION,form,pending,expired,approvedNote,markNotice,tag,mgrOpenHtml,mountApp,attach,start,refresh,people,devsHtml,foot,meCard,onTouchError,t:{viaName,devTitle,isCurrent,devSub,ago,_S:S,_AX:AX}}),writable:false,configurable:false})}
catch(e){window.__ptF07={ok:true,version:VERSION,form,pending,expired,approvedNote,markNotice,tag,mgrOpenHtml,mountApp,attach,start,refresh,people,devsHtml,foot,meCard,onTouchError,t:{viaName,devTitle,isCurrent,devSub,ago,_S:S,_AX:AX}}}
})();
