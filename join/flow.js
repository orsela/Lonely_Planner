/* Lonely Planner · join flow · version 3.0.0-alpha.18.6 · F13 stage 1
   CHANGE 2026-11-24 F13-JOIN-01: what changed from 3.0.0-alpha.16: the screens speak Hebrew or English (F13 stage 1, claude/Plan_Travel_F13_spec.md §9). New: a small language engine (device choice
   pt:_device:lang → browser language → Hebrew; active only with the page's LANG_FEATURE 'on', or 'beta' on a device with localStorage['pt-f13-beta']==='1'; inside the app window.__ptF13 decides), the dictionary
   D = {he, en} (every Hebrew string of this file is a key; Hebrew text is verbatim the old text), dir/lang on the mount root (and on <html> + the title for the /join/ page), a "EN / עב" switch in the hero
   (page only, never in the app), <bdi> around names inside English sentences, and ctx.t / ctx.lang for app/js/f07.js. Exports lang(), applyDoc(), t() as well. With the flag off nothing changes: the same Hebrew
   strings, dir="rtl", no switch (= alpha.16). The Vietnam trip stays Hebrew.
   Previous: Lonely Planner · join flow · version 3.0.0-alpha.16 · F07
   CHANGE 2026-11-16 F07-JOIN-01: what changed from 3.0.0-alpha.7: new option opts.relink (set by the page from RELINK_FEATURE='on'; needs app/js/f07.js =
   window.__ptF07). With it, six small hooks call f07.js: the "אני חדש/ה" / "כבר הייתי" switch and name list on the form, the relink pending screen,
   the expired screen, the note on the approved screen. Without it (default, or f07.js missing) nothing here changes from alpha.7.
   Lonely Planner · join flow · version 3.0.0-alpha.7 · F05
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
const VERSION='3.0.0-alpha.18.6'; /* CHANGE 2026-11-24 F13-JOIN-01: was '3.0.0-alpha.16' */ /* CHANGE 2026-11-16 F07-JOIN-01: was '3.0.0-alpha.7' */ /* CHANGE 2026-10-22 F06-JOIN-02: was '3.0.0-alpha.6' */
const POLL_MS=20000,CALL_TIMEOUT_MS=15000;
/* CHANGE 2026-11-24 F13-JOIN-01: new — the language engine and the dictionary (was: const ROLE={manager:'מנהל',editor:'עורך',viewer:'צופה'}; const TX={offline…copied}) */
const FORCED_HE_TRIPS=['f0200000-0000-4000-8000-000000000001'];   /* the Vietnam trip: never English */
function rawGet(k){try{return window.localStorage.getItem(k)}catch(e){return null}}
function langMode(){try{return typeof LANG_FEATURE==='undefined'?'off':String(LANG_FEATURE)}catch(e){return'off'}}
function switchEnabled(){const m=langMode();return m==='on'||(m==='beta'&&rawGet('pt-f13-beta')==='1')}
let forcedHe=false;   /* set when the trip's preview says it is a forced-Hebrew trip */
function lang(){
 if(forcedHe)return'he';
 try{const F=window.__ptF13;if(F&&F.mode&&F.mode!=='off')return F.lang()==='en'?'en':'he'}catch(e){}   /* inside the app, f13.js decides */
 if(!switchEnabled())return'he';
 const pick=v=>{const s=String(v==null?'':v).toLowerCase().slice(0,2);return s==='he'||s==='iw'?'he':s==='en'?'en':null};
 return pick(rawGet('pt:_device:lang'))||pick((navigator.language||(navigator.languages||[])[0]))||'he';
}
function applyDoc(){
 const h=document.documentElement,L=lang();
 h.lang=L;h.dir=L==='en'?'ltr':'rtl';
 document.title=L==='en'?'Join the trip · Lonely Planner':'הצטרפות לטיול · Lonely Planner';
}
const D={
 he:{
  offline:'אין חיבור. נסו שוב כשהרשת תחזור.',rate:'יותר מדי ניסיונות. נסו שוב מאוחר יותר.',generic:'משהו השתבש. נסו שוב.',nameInvalid:'כתבו שם של עד 40 תווים.',copied:'הקוד הועתק',
  rManager:'מנהל',rEditor:'עורך',rViewer:'צופה',
  sub:'הזמנה לקבוצה',kickerM:'הזמנה מ{m} להצטרף לטיול',kicker:'הזמנה להצטרף לטיול',oneDay:'יום אחד',nDays:'{n} ימים',oneMember:'חבר אחד',nMembers:'{n} חברים',
  loading:'טוענים את ההזמנה…',errT:'לא הצלחנו לטעון',retry:'נסו שוב',back:'חזרה',
  invT:'הקישור כבר לא פעיל',invP:'בקשו מהמנהל של הטיול קישור חדש. אם כבר הצטרפתם בעבר, פשוט פתחו את האפליקציה.',
  remT:'הוסרת מהטיול',remP:'פנו למנהל של הטיול אם זו טעות.',
  nameLbl:'איך קוראים לך?',nameHelp:'כך יראו אותך שאר החברים, וכך יירשמו ההוצאות שלך.',submit:'בקשת הצטרפות',sending:'שולחים…',
  tick1:'בלי מייל ובלי סיסמה',tick2M:'אחרי האישור של {m}, הטיול נפתח כאן לבד',tick2:'אחרי אישור המנהל, הטיול נפתח כאן לבד',tick3:'הטלפון הזה יזוהה אוטומטית בפעם הבאה',
  foot:'מה שתזינו בטיול גלוי רק לחברי הקבוצה.',
  taken:'יש כבר "{n}" בטיול. אפשר להוסיף אות או שם משפחה, למשל "{n} ל".',
  pendM:'הבקשה נשלחה ל{m}',pend:'הבקשה נשלחה למנהל',pendP:'אחרי האישור, הטיול ייפתח במסך הזה לבד. אפשר לסגור ולחזור לאותו קישור מאוחר יותר.',
  pill:'ממתין לאישור · {n}',prog:'התקדמות',st1:'הבקשה נשלחה',st2M:'מחכים לאישור של {m}',st2:'מחכים לאישור',st3:'הטיול נפתח',cancel:'ביטול הבקשה',
  rejT:'הבקשה לא אושרה',rejPM:'אם זו טעות, דברו עם {m} ושלחו בקשה חדשה מאותו קישור.',rejP:'אם זו טעות, דברו עם המנהל ושלחו בקשה חדשה מאותו קישור.',again:'בקשה חדשה',rejLim:'עד 3 בקשות ביום מאותו טלפון.',
  appT:'הבקשה אושרה – ברוכים הבאים, {n}!',appP:'הצטרפת לטיול בתפקיד {r}.',
  trT:'מוסיפים את האפליקציה למסך הבית',trP:'באייפון, האפליקציה ממסך הבית לא מכירה את מה שקרה בספארי. הקוד הזה מעביר אליה את החברות שלך.',
  trS1:'לוחצים על כפתור השיתוף בספארי ← "הוספה למסך הבית"',trS2:'פותחים את Lonely Planner ממסך הבית',trS3:'מקלידים את הקוד',
  trCode:'קוד ההעברה שלך',trValid:'בתוקף 24 שעות · פעם אחת',copyAria:'העתקת הקוד',copy:'העתקה',openLater:'לא עכשיו – פתיחת הטיול כאן',open:'פתיחת הטיול',
  installNote:'אפשר גם להתקין את האפליקציה – היא תמשיך עם אותה זהות.',copyHint:'אפשר לסמן את הקוד ולהעתיק.',
  /* the F07 relink screens (app/js/f07.js, /join/ side) */
  'f7.modeNew':'אני חדש/ה בטיול','f7.modeBack':'כבר הייתי בטיול','f7.modeAria':'סוג ההצטרפות','f7.who':'מי אתם ברשימה?',
  'f7.pickHelp':'המנהל יאשר שזה אתם. השם, התפקיד והרשומות שלכם נשמרים.','f7.pickErr':'בחרו את השם שלכם מהרשימה.',
  'f7.send':'בקשה לחבר את הטלפון הזה','f7.gone':'השם הזה כבר לא ברשימה. בחרו שוב.','f7.acct':'כבר בטיול? כניסה עם החשבון',
  'f7.lostNote':'מסמכים ושינויים שנשמרו רק בטלפון הקודם לא עוברים.',
  'f7.pendP':'אחרי האישור הטיול ייפתח כאן לבד, עם אותו שם ואותו תפקיד. אפשר לסגור ולחזור לאותו קישור.','f7.pillNew':'מכשיר חדש · {n}','f7.until':'בתוקף עד {t}',
  'f7.waMsg':'היי, זה {n}. ביקשתי לחבר טלפון חדש לטיול {trip} – אפשר לאשר?','f7.wa':'שליחת הודעה למנהל בווטסאפ',
  'f7.expT':'הבקשה פגה','f7.expP':'הבקשה לא אושרה תוך 24 שעות. אפשר לשלוח בקשה חדשה.','f7.expPN':'הבקשה של {n} לא אושרה תוך 24 שעות. אפשר לשלוח בקשה חדשה.',
  'f7.again':'בקשה חדשה','f7.backName':'חזרה לבחירת שם','f7.sending':'שולחים…'
 },
 en:{
  offline:'No connection. Try again when the network is back.',rate:'Too many attempts. Try again later.',generic:'Something went wrong. Try again.',nameInvalid:'Enter a name of up to 40 characters.',copied:'Code copied',
  rManager:'Manager',rEditor:'Editor',rViewer:'Viewer',
  sub:'Group invitation',kickerM:'Invitation from {m} to join the trip',kicker:'Invitation to join the trip',oneDay:'One day',nDays:'{n} days',oneMember:'One member',nMembers:'{n} members',
  loading:'Loading the invitation…',errT:"Couldn't load",retry:'Try again',back:'Back',
  invT:'This link is no longer active',invP:'Ask the trip manager for a new link. If you already joined, just open the app.',
  remT:'You were removed from the trip',remP:'Contact the trip manager if this is a mistake.',
  nameLbl:"What's your name?",nameHelp:'This is how the other members will see you, and how your expenses will be recorded.',submit:'Request to join',sending:'Sending…',
  tick1:'No email, no password',tick2M:'After {m} approves, the trip opens here by itself',tick2:'After the manager approves, the trip opens here by itself',tick3:'This phone will be recognised automatically next time',
  foot:"What you enter in the trip is visible only to the group's members.",
  taken:'There is already a "{n}" in the trip. You can add a letter or a last name, for example "{n} K".',
  pendM:'Request sent to {m}',pend:'Request sent to the manager',pendP:'Once approved, the trip will open on this screen by itself. You can close this and come back to the same link later.',
  pill:'Waiting for approval · {n}',prog:'Progress',st1:'Request sent',st2M:'Waiting for {m} to approve',st2:'Waiting for approval',st3:'Trip opens',cancel:'Cancel request',
  rejT:'Request not approved',rejPM:'If this is a mistake, talk to {m} and send a new request from the same link.',rejP:'If this is a mistake, talk to the manager and send a new request from the same link.',again:'New request',rejLim:'Up to 3 requests a day from the same phone.',
  appT:'Request approved – welcome, {n}!',appP:'You joined the trip as {r}.',
  trT:'Add the app to your home screen',trP:"On iPhone, the home-screen app doesn't know what happened in Safari. This code transfers your membership to it.",
  trS1:'Tap the Share button in Safari → "Add to Home Screen"',trS2:'Open Lonely Planner from the home screen',trS3:'Type the code',
  trCode:'Your transfer code',trValid:'Valid for 24 hours · single use',copyAria:'Copy the code',copy:'Copy',openLater:'Not now – open the trip here',open:'Open the trip',
  installNote:'You can also install the app – it keeps the same identity.',copyHint:'You can select the code and copy it.',
  'f7.modeNew':"I'm new to the trip",'f7.modeBack':"I've been on the trip before",'f7.modeAria':'Type of joining','f7.who':'Who are you on the list?',
  'f7.pickHelp':"The manager will confirm it's you. Your name, role and records are kept.",'f7.pickErr':'Pick your name from the list.',
  'f7.send':'Request to link this phone','f7.gone':'That name is no longer on the list. Pick again.','f7.acct':'Already on the trip? Sign in with your account',
  'f7.lostNote':'Documents and changes saved only on the previous phone do not carry over.',
  'f7.pendP':'Once approved, the trip will open here by itself, with the same name and role. You can close this and come back to the same link.','f7.pillNew':'New device · {n}','f7.until':'Valid until {t}',
  'f7.waMsg':'Hi, this is {n}. I asked to link a new phone to the trip {trip} – can you approve?','f7.wa':'Message the manager on WhatsApp',
  'f7.expT':'The request expired','f7.expP':'The request was not approved within 24 hours. You can send a new request.','f7.expPN':'The request of {n} was not approved within 24 hours. You can send a new request.',
  'f7.again':'New request','f7.backName':'Back to choosing a name','f7.sending':'Sending…'
 }
};
/* tr(key, params, html): the text in the current language; params are escaped and, in English only, wrapped in <bdi> when html is true (names keep their own direction inside a sentence) */
function tr(k,p,html){
 const L=lang(),s=(D[L]&&D[L][k])!=null?D[L][k]:(D.he[k]!=null?D.he[k]:String(k));
 return s.replace(/\{([a-z]+)\}/g,(all,n)=>{
  if(!p||p[n]==null)return all;
  const v=String(p[n]);
  return html?(L==='en'?'<bdi>'+esc(v)+'</bdi>':esc(v)):v;
 });
}
const ROLEK={manager:'rManager',editor:'rEditor',viewer:'rViewer'};
const ROLE=new Proxy({},{get:(o,r)=>ROLEK[r]?tr(ROLEK[r]):undefined});   /* ROLE[role] keeps working for f07.js (ctx.ROLE) */
const TX={get offline(){return tr('offline')},get rate(){return tr('rate')},get generic(){return tr('generic')},get nameInvalid(){return tr('nameInvalid')},get copied(){return tr('copied')}};
const CSS=`
.lpj[dir=ltr]{direction:ltr}
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
.lpj-lang{min-height:44px;min-width:44px;margin:-8px 0;padding:0 4px;border:0;background:transparent;color:#fff;cursor:pointer;font-family:inherit}
.lpj-lang span{display:inline-block;border:1px solid rgba(255,255,255,.6);border-radius:14px;padding:6px 10px;font-size:12px;font-weight:700;line-height:1}
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
 const el=document.createElement('div');el.className='lpj';el.id='lpJoin';el.setAttribute('dir',lang()==='en'?'ltr':'rtl');el.setAttribute('lang',lang());
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
 /* CHANGE 2026-11-16 F07-JOIN-01: new — the F07 hooks (null unless opts.relink and f07.js loaded) */
 function f7(){return(o.relink&&window.__ptF07&&window.__ptF07.ok)?window.__ptF07:null}
 function f7ctx(){return{el,$,paint,esc,st,fn,toast,hero,back,route,load,showForm,cancel,watch,errText,online,ROLE,inApp:o.inApp,t:tr,lang}}

 function hero(small){
  const t=st.trip||{};
  const dates=t.start_date&&t.end_date?dmy(t.start_date)+' – '+dmy(t.end_date,true):'';
  if(small)return'<header class="lpj-hero sm"><div class="lpj-top"><span class="lpj-brand">Lonely Planner</span><span class="lpj-sub">'+esc(dates)+'</span>'+langBtn()+'</div><h1><bdi>'+esc(t.name||'')+'</bdi></h1></header>';
  const meta=[dates,t.days?(t.days===1?tr('oneDay'):tr('nDays',{n:t.days})):'',t.members!=null?(t.members===1?tr('oneMember'):tr('nMembers',{n:t.members})):''].filter(Boolean).join(' · ');
  return'<header class="lpj-hero"><div class="lpj-top"><span class="lpj-brand">Lonely Planner</span><span class="lpj-sub">'+tr('sub')+'</span>'+langBtn()+'</div>'+
   '<div class="lpj-kicker">'+(t.manager?tr('kickerM',{m:t.manager},true):tr('kicker'))+'</div>'+
   '<h1 id="lpjTitle"><bdi>'+esc(t.name||'')+'</bdi></h1><div class="lpj-meta">'+esc(meta)+'</div></header>';
 }
 function back(){return o.inApp&&o.onBack?'<button type="button" class="lpj-link" id="lpjBack">'+tr('back')+'</button>':''}
 /* CHANGE 2026-11-24 F13-JOIN-01: new — the language switch (page only, never in the app; only when the feature is enabled and the trip is not forced Hebrew) */
 function langBtn(){
  if(o.inApp||forcedHe||!switchEnabled())return'';
  const en=lang()==='en';
  return'<button type="button" class="lpj-lang" data-lpj-lang="'+(en?'he':'en')+'" aria-label="'+(en?'עברית':'English')+'" lang="'+(en?'he':'en')+'"><span>'+(en?'עב':'EN')+'</span></button>';
 }
 function relang(){
  const L=lang();el.setAttribute('dir',L==='en'?'ltr':'rtl');el.setAttribute('lang',L);
  if(!o.inApp)applyDoc();
 }
 function wireLang(){
  const b=el.querySelector('[data-lpj-lang]');if(!b)return;
  b.onclick=()=>{
   const inp=$('lpjName');if(inp)st.name=String(inp.value||'').trim();
   try{window.localStorage.setItem('pt:_device:lang',b.getAttribute('data-lpj-lang'))}catch(e){}
   relang();stop();load();
  };
 }
 function paint(screen,html){
  el.dataset.screen=screen;el.innerHTML=html;wireLang();
  const b=$('lpjBack');if(b)b.onclick=()=>{stop();o.onBack()};
 }
 function stop(){if(st.timer){clearInterval(st.timer);st.timer=null}if(st.chan){try{st.client.removeChannel(st.chan)}catch{}st.chan=null}}

 /* --- screens --- */
 function showLoading(){paint('loading','<header class="lpj-hero sm"><div class="lpj-top"><span class="lpj-brand">Lonely Planner</span></div><h1 id="lpjTitle">'+tr('loading')+'</h1></header>')}
 function showError(msg,retry){
  paint('error','<header class="lpj-hero sm"><div class="lpj-top"><span class="lpj-brand">Lonely Planner</span></div><h1 id="lpjTitle">'+tr('errT')+'</h1></header>'+
   '<div class="lpj-body"><section class="lpj-card" role="alert"><p style="margin:0 0 12px;font-size:14px;color:#3a443d">'+esc(msg)+'</p><button type="button" class="lpj-btn" id="lpjRetry">'+tr('retry')+'</button></section>'+back()+'</div>');
  $('lpjRetry').onclick=retry;
 }
 function showInvalid(){
  stop();
  paint('invalid','<header class="lpj-hero sm"><div class="lpj-top"><span class="lpj-brand">Lonely Planner</span></div></header>'+
   '<div class="lpj-body"><section class="lpj-card" style="display:flex;gap:12px;align-items:flex-start" role="alert">'+
   '<span class="lpj-ring" style="width:48px;height:48px;background:#fdecea;flex-shrink:0">'+ICON.brokenLink.replace(/34/g,'24')+'</span>'+
   '<div><h1 id="lpjTitle" style="margin:0;font-size:16px">'+tr('invT')+'</h1><p style="margin:4px 0 0;font-size:13px;color:#3a443d;line-height:1.5">'+tr('invP')+'</p></div></section>'+back()+'</div>');
 }
 function showRemoved(){
  stop();
  paint('removed',hero(true)+'<div class="lpj-body"><div class="lpj-center"><span class="lpj-ring" style="background:#f1f0ea">'+ICON.no+'</span>'+
   '<h2 id="lpjTitle">'+tr('remT')+'</h2><p>'+tr('remP')+'</p></div>'+back()+'</div>');
 }
 function showForm(prefill,err){
  stop();
  const t=st.trip||{};
  paint('form',hero(false)+'<div class="lpj-body"><section class="lpj-card lift">'+
   '<label class="lpj-lbl" for="lpjName">'+tr('nameLbl')+'</label>'+
   '<input id="lpjName" class="lpj-in" maxlength="40" autocomplete="given-name" enterkeyhint="send" value="'+esc(prefill||'')+'"'+(err?' aria-invalid="true" aria-describedby="lpjNameErr"':' aria-describedby="lpjNameHelp"')+'>'+
   (err?'<div class="lpj-err" id="lpjNameErr" role="alert">'+ICON.alert+'<span>'+esc(err)+'</span></div>'
       :'<p class="lpj-help" id="lpjNameHelp">'+tr('nameHelp')+'</p>')+
   '<div style="height:14px"></div><button type="button" class="lpj-btn" id="lpjSubmit">'+tr('submit')+'</button></section>'+
   '<div class="lpj-ticks">'+
   '<div class="lpj-tick">'+ICON.check+'<span>'+tr('tick1')+'</span></div>'+
   '<div class="lpj-tick">'+ICON.check+'<span>'+(t.manager?tr('tick2M',{m:t.manager},true):tr('tick2'))+'</span></div>'+
   '<div class="lpj-tick">'+ICON.check+'<span>'+tr('tick3')+'</span></div></div>'+back()+'</div>'+
   '<p class="lpj-foot">'+tr('foot')+'</p>');
  const inp=$('lpjName');
  $('lpjSubmit').onclick=submit;
  inp.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();submit()}};
  if(!err&&!prefill)setTimeout(()=>{try{inp.focus()}catch{}},50);
  const F=f7();if(F){try{F.form(f7ctx())}catch(e){console.warn('[lpj] f07 form',e)}}   /* CHANGE 2026-11-16 F07-JOIN-01 */
 }
 function showPending(){
  const t=st.trip||{},me=st.me||{};
  paint('pending',hero(true)+'<div class="lpj-body"><div class="lpj-center"><span class="lpj-ring" style="background:#fef3e2">'+ICON.clock+'</span>'+
   '<h2 id="lpjTitle">'+(t.manager?tr('pendM',{m:t.manager},true):tr('pend'))+'</h2>'+
   '<p>'+tr('pendP')+'</p>'+
   '<span class="lpj-pill">'+tr('pill',{n:me.display_name||st.name},true)+'</span></div>'+
   '<section class="lpj-steps" aria-label="'+tr('prog')+'">'+
   '<div class="lpj-step"><span class="lpj-dot" style="background:#edf8f3">'+ICON.smallCheck+'</span><span>'+tr('st1')+'</span></div>'+
   '<div class="lpj-step"><span class="lpj-dot" style="border:2px solid #d97706"></span><b>'+(t.manager?tr('st2M',{m:t.manager},true):tr('st2'))+'</b></div>'+
   '<div class="lpj-step" style="color:#5f6861"><span class="lpj-dot" style="border:2px solid #c9ccc4"></span><span>'+tr('st3')+'</span></div></section>'+
   '<button type="button" class="lpj-btn ghost" id="lpjCancel">'+tr('cancel')+'</button></div>');
  $('lpjCancel').onclick=cancel;
  watch();
 }
 function showRejected(){
  stop();
  const t=st.trip||{};
  paint('rejected',hero(true)+'<div class="lpj-body"><section class="lpj-card" style="display:flex;gap:12px;align-items:flex-start" role="alert">'+
   '<span class="lpj-ring" style="width:48px;height:48px;background:#f1f0ea;flex-shrink:0">'+ICON.no.replace(/34/g,'24')+'</span>'+
   '<div><h1 id="lpjTitle" style="margin:0;font-size:16px">'+tr('rejT')+'</h1><p style="margin:4px 0 0;font-size:13px;color:#3a443d;line-height:1.5">'+(t.manager?tr('rejPM',{m:t.manager},true):tr('rejP'))+'</p>'+
   '<button type="button" class="lpj-btn out" id="lpjAgain" style="width:auto;margin-top:10px;padding:0 16px;min-height:44px">'+tr('again')+'</button>'+
   '<p style="margin:6px 0 0;font-size:11.5px;color:#5f6861">'+tr('rejLim')+'</p></div></section>'+back()+'</div>');
  $('lpjAgain').onclick=()=>showForm(st.name);
 }
 async function showApproved(){
  stop();
  const t=st.trip||{},me=st.me||{};
  const transfer=!o.inApp&&isIos()&&!isStandalone();
  paint('approved',hero(true)+'<div class="lpj-body"><div class="lpj-center" style="padding-top:18px"><span class="lpj-ring" style="width:68px;height:68px;background:#edf8f3">'+ICON.bigCheck+'</span>'+
   '<h2 id="lpjTitle">'+tr('appT',{n:me.display_name||st.name},true)+'</h2>'+
   '<p>'+tr('appP',{r:ROLE[me.role]||me.role||''},true)+'</p></div>'+
   (f7()&&st.relinkInfo?f7().approvedNote():'')+   /* CHANGE 2026-11-16 F07-JOIN-01: relink note (nothing from the old phone's local data moves) */
   (transfer?'<section class="lpj-card" style="border-color:#cfe1d7" id="lpjTransfer"><b style="display:block;font-size:14.5px;margin-bottom:4px">'+tr('trT')+'</b>'+
    '<p style="margin:0 0 12px;font-size:12.5px;color:#5f6861;line-height:1.5">'+tr('trP')+'</p>'+
    '<div style="display:flex;flex-direction:column;gap:8px;margin-bottom:14px">'+
    '<div class="lpj-tick"><span class="lpj-n">1</span><span>'+tr('trS1')+'</span></div>'+
    '<div class="lpj-tick"><span class="lpj-n">2</span><span>'+tr('trS2')+'</span></div>'+
    '<div class="lpj-tick"><span class="lpj-n">3</span><span>'+tr('trS3')+'</span></div></div>'+
    '<div class="lpj-code"><div style="font-size:11.5px;font-weight:700;color:#5f6861">'+tr('trCode')+'</div><b id="lpjCode" aria-live="polite">· · ·</b>'+
    '<div style="font-size:11.5px;color:#5f6861">'+tr('trValid')+'</div>'+
    '<button type="button" class="lpj-link" id="lpjCopy" aria-label="'+tr('copyAria')+'" disabled>'+tr('copy')+'</button></div></section>'+
    '<button type="button" class="lpj-btn out" id="lpjOpen">'+tr('openLater')+'</button>'
   :'<button type="button" class="lpj-btn" id="lpjOpen">'+tr('open')+'</button>'+
    (o.inApp?'':'<p style="margin:0;text-align:center;font-size:12px;color:#5f6861">'+tr('installNote')+'</p>'))+
   '</div>');
  $('lpjOpen').onclick=()=>{stop();if(f7()&&st.relinkInfo)f7().markNotice();try{o.onEnter(t.trip_id,me.role,me.display_name||st.name)}catch(e){console.warn('[lpj] enter failed',e)}};
  if(transfer){
   try{
    const r=await fn({action:'issue_transfer',trip_id:t.trip_id});
    const codeEl=$('lpjCode');if(!codeEl)return;
    codeEl.textContent=r.code.slice(0,3)+' '+r.code.slice(3);
    const cp=$('lpjCopy');cp.disabled=false;
    cp.onclick=async()=>{let ok=false;try{if(navigator.clipboard){await navigator.clipboard.writeText(r.code);ok=true}}catch{}toast(ok?TX.copied:tr('copyHint'))};
   }catch(e){const c=$('lpjCode');if(c)c.textContent='—';toast(errText(e))}
  }
 }

 /* --- actions --- */
 function route(me){
  st.me=me||null;
  if(!me){showForm(st.name);return}
  if(me.status==='active'){showApproved();return}
  if(me.status==='pending'){const F=f7();if(F&&st.relinkInfo){F.pending(f7ctx());return}showPending();return}   /* CHANGE 2026-11-16 F07-JOIN-01: relink pending screen */
  if(me.status==='removed'){showRemoved();return}
  showForm(st.name);
 }
 async function load(){
  if(!st.code){showInvalid();return}
  if(!online()){showError(TX.offline,load);return}
  showLoading();
  try{
   const p=await fn({action:'preview',code:st.code});
   st.trip=p;
   if(p&&FORCED_HE_TRIPS.indexOf(p.trip_id)>=0){forcedHe=true;relang()}   /* CHANGE 2026-11-24 F13-JOIN-01: the Vietnam trip stays Hebrew */
   /* CHANGE 2026-11-16 F07-JOIN-01: relink state of this identity (pending → its screen; expired → reported once by the server, D5) */
   st.relinkInfo=(p.relink&&p.relink.status==='pending')?p.relink:null;
   const F=f7();if(F&&p.relink&&p.relink.status==='expired'&&!p.me){F.expired(f7ctx(),p.relink);return}
   route(p.me);
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
  st.busy=true;const b=$('lpjSubmit');if(b){b.disabled=true;b.textContent=tr('sending')}
  try{
   const r=await fn({action:'request',code:st.code,display_name:name});
   st.trip=Object.assign({},st.trip,{trip_id:r.trip_id});
   route({member_id:r.member_id,status:r.status,role:r.role,display_name:r.display_name});
  }catch(e){
   if(e.code==='name_taken')showForm(name,tr('taken',{n:name}));
   else if(e.code==='name_invalid')showForm(name,TX.nameInvalid);
   else if(e.code==='code_invalid')showInvalid();
   else if(e.code==='member_removed')showRemoved();
   else{toast(errText(e));const bb=$('lpjSubmit');if(bb){bb.disabled=false;bb.textContent=tr('submit')}}
  }finally{st.busy=false}
 }
 async function cancel(){
  if(st.busy)return;
  if(!online()){toast(TX.offline);return}
  st.busy=true;
  try{await fn({action:'cancel',trip_id:st.trip.trip_id});st.relinkInfo=null;showForm(st.name||(st.me&&st.me.display_name)||'')}
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

try{Object.defineProperty(window,'LPJoin',{value:Object.freeze({version:VERSION,mount,normCode,lang,applyDoc,t:tr}),writable:false,configurable:false})}catch{window.LPJoin={version:VERSION,mount,normCode,lang,applyDoc,t:tr}}
})();
