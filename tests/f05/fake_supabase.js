/* Plan_Travel F05 QA · fake supabase-js · version 1.3.0-f05
   CHANGE 2026-10-19 F05-QA-02: copied from tests/f04/fake_supabase.js v1.2.0 (+ the F20 suite's in-memory delayMs patch).
   What changed from 1.2.0: (1) Realtime is no longer a stub: channel(name).on('postgres_changes', {event, schema, table,
   filter}, cb).subscribe(cb) registers with the Python backend (op 'rt.subscribe') and, while a channel is open, the page
   polls the backend every 250 ms (op 'rt.poll') for change events. Delivery follows Supabase Postgres Changes: INSERT /
   UPDATE are delivered when the subscriber may SELECT the new row (RLS, decided by the backend) and the binding's
   `col=eq.val` filter matches `new`; DELETE events are NOT filterable and carry only the primary key in `old` (RLS on).
   Payload: {schema, table, commit_timestamp, eventType, new, old, errors:null}. The backend can make Realtime silent
   (subscribe answers SUBSCRIBED but no event is ever delivered) to test the poll path. (2) functions.invoke is unchanged
   (the F05 backend serves 'join-trip' / 'approve-member' through it as well as through the fetch() route).
   Previous version header (kept for history):
   Plan_Travel F04 QA · fake supabase-js · version 1.2.0
   CHANGE 2026-10-12 F04-QA: copied from tests/f03/fake_supabase.js v1.1.0 and extended for F04. What changed from
   1.1.0: (1) auth.verifyOtp({email,token,type}) — routed to the Python backend (tests/f04/test_f04.py F04Backend),
   which accepts a configured code; type 'email_change' keeps the same user id and sets email + email_confirmed_at,
   type 'email' switches the stored session to another configured user (SIGNED_IN emitted), like supabase-js v2;
   (2) auth.signInWithOtp({email, options}) — routed to the backend (records options.shouldCreateUser);
   (3) auth.updateUser keeps working as in 1.1.0 (the backend answers email_exists when configured);
   (4) every auth.* call is also reported to the backend as op 'auth.trace' so tests can assert that NO auth call was
   made (criteria 3, 4); (5) from('trip_join_codes') is served by the backend (RLS: active managers);
   (6) functions.invoke(name, …) carries the function name, so the backend serves 'create-trip' (fake §3.1 endpoint)
   and 'invite-manager' (check returns email) from the same call; (7) auth.resend({type,email}) is routed too.
   Previous version header (kept for history):
   CHANGE 2026-10-05 F03-QA: copied from tests/f02/tests/fake_supabase.js v1.0.0 and extended for F03. What changed
   from 1.0.0: (1) auth.updateUser(attrs, options) is implemented (scripted outcome in the Python backend; the stored
   session's user is replaced by the returned user and USER_UPDATED is emitted, like supabase-js v2); (2) auth.getUser
   result is also written back into the stored session's user (keeps the cache fresh after an email confirmation);
   (3) rpc(fn,args) now returns what the backend answers (data or a PostgREST-shaped error) instead of always failing;
   (4) functions.invoke(name,{body,headers}) is routed to the same backend as the fetch() route of the fake
   invite-manager endpoint, returning {data,error} like supabase-js (FunctionsHttpError with error.context = Response
   on non-2xx); (5) from('platform_admins') is served by the backend (own-row RLS lives there).
   Previous version header (kept for history):
   CHANGE 2026-10-04 F02-QA: first version (no previous version).

   Served by the Playwright route handler IN PLACE OF https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.
   Exposes the same UMD global as the real library: window.supabase.createClient(url, key, options).

   All data + the RLS model live in a Python-side store (FakeBackend in test_f02.py), reached through a
   Playwright binding `window.__fakeBackend(msg)`. That makes the state shared between browser contexts
   (two "devices"), atomic per call, and it survives page reloads. Without the binding every call returns
   an error object (the fake never touches the network).

   What it implements (the parts the F02 spec needs, tolerant of the common supabase-js chain shapes):
   - auth: getSession / signInAnonymously / onAuthStateChange / getUser / signOut / refreshSession /
     setSession. Session persisted like supabase-js v2: JSON under options.auth.storageKey or the default
     `sb-<project ref>-auth-token`, in options.auth.storage or globalThis.localStorage (read at call time).
   - from(table): select / insert / upsert(onConflict, ignoreDuplicates) / update / delete; filters eq neq
     gt gte lt lte like ilike is in match filter not; order / limit / range / single / maybeSingle /
     abortSignal / returns / throwOnError / csv(no). Resolves {data, error, count, status, statusText}.
   - channel / removeChannel / removeAllChannels / getChannels (stubs, logged), rpc and functions.invoke
     (logged, always error), storage.from (logged, always error).
   - Offline: when navigator.onLine is false, or the backend is in 'down' mode, calls resolve with the
     same error shape supabase-js gives for a failed fetch. 'hang' mode never resolves (timeout tests).
   Every call is recorded in window.__fakeLog (this page) and in the backend log (whole test).
   Test control from the page: window.__fake.{state(), log(), setMode(m), link(opts), control(msg)}. */
(function () {
  'use strict';
  var LOG = (window.__fakeLog = window.__fakeLog || []);
  var FAKE_VERSION = '1.3.0-f05';

  function now() { return Date.now(); }
  function clone(x) { return x === undefined ? undefined : JSON.parse(JSON.stringify(x)); }
  function log(kind, extra) {
    var e = Object.assign({ t: now(), kind: kind, page: String(location.pathname) }, extra || {});
    LOG.push(e);
    // CHANGE 2026-10-12 F04-QA: every auth call is traced in the backend (survives reloads; criteria 3/4 "no auth call").
    if (kind.indexOf('auth.') === 0 && kind !== 'auth.event' && kind !== 'auth.onAuthStateChange' && typeof window.__fakeBackend === 'function') {
      try { window.__fakeBackend({ op: 'auth.trace', kind: kind, page: String(location.pathname) }); } catch (x) {}
    }
    return e;
  }
  function backend(msg) {
    if (typeof window.__fakeBackend !== 'function') {
      return Promise.resolve({ error: { message: 'fake backend not attached', code: 'FAKE', details: '', hint: '' }, status: 500 });
    }
    msg.online = navigator.onLine !== false;
    msg.page = String(location.pathname);
    return window.__fakeBackend(msg);
  }
  var NEVER = function () { return new Promise(function () {}); };
  function fetchError() {
    return { message: 'TypeError: Failed to fetch', details: 'TypeError: Failed to fetch', hint: '', code: '' };
  }

  function projectRef(url) {
    try { return new URL(url).hostname.split('.')[0]; } catch (e) { return 'unknown'; }
  }

  function createClient(url, key, options) {
    options = options || {};
    var authOpts = options.auth || {};
    var ref = projectRef(url);
    var storageKey = authOpts.storageKey || ('sb-' + ref + '-auth-token');
    var persist = authOpts.persistSession !== false;
    var memSession = null;
    var listeners = [];
    var clientId = Math.random().toString(36).slice(2, 10);

    var created = log('createClient', {
      url: String(url), key: String(key), clientId: clientId, storageKey: storageKey,
      persistSession: persist, customStorage: !!authOpts.storage,
      autoRefreshToken: authOpts.autoRefreshToken !== false,
      optionKeys: Object.keys(options)
    });
    backend({ op: 'log', entry: created });

    function store() { return authOpts.storage || globalThis.localStorage; }
    async function readSession() {
      if (!persist) return memSession;
      try {
        var raw = await store().getItem(storageKey);
        return raw ? JSON.parse(raw) : null;
      } catch (e) { return null; }
    }
    async function writeSession(s) {
      if (!persist) { memSession = s; return; }
      try {
        if (s) await store().setItem(storageKey, JSON.stringify(s));
        else await store().removeItem(storageKey);
      } catch (e) {}
    }
    function emit(event, session) {
      log('auth.event', { event: event, uid: session && session.user ? session.user.id : null });
      listeners.slice().forEach(function (l) {
        setTimeout(function () { try { l.cb(event, session); } catch (e) { console.error(e); } }, 0);
      });
    }
    async function token() {
      var s = await readSession();
      return s && s.access_token ? s.access_token : null;
    }

    var auth = {
      getSession: async function () {
        var s = await readSession();
        log('auth.getSession', { clientId: clientId, uid: s && s.user ? s.user.id : null });
        return { data: { session: s }, error: null };
      },
      getUser: async function (jwt) {
        var t = jwt || (await token());
        log('auth.getUser', { clientId: clientId });
        if (!t) return { data: { user: null }, error: { name: 'AuthSessionMissingError', message: 'Auth session missing!', status: 400 } };
        var r = await backend({ op: 'auth.getUser', url: url, key: key, token: t });
        if (r && r.hang) return NEVER();
        if (r && r.error) return { data: { user: null }, error: r.error };
        try { var cur = await readSession(); if (cur && !jwt) { cur.user = r.user; await writeSession(cur); } } catch (e) {}
        return { data: { user: r.user }, error: null };
      },
      signInAnonymously: async function (creds) {
        log('auth.signInAnonymously', { clientId: clientId, url: String(url) });
        var r = await backend({ op: 'auth.signInAnonymously', url: url, key: key, options: creds && creds.options ? clone(creds.options) : null });
        if (r && r.hang) return NEVER();
        if (!r || r.error) {
          return { data: { user: null, session: null }, error: (r && r.error) || { name: 'AuthRetryableFetchError', message: 'Failed to fetch', status: 0 } };
        }
        await writeSession(r.session);
        emit('SIGNED_IN', r.session);
        return { data: { user: r.session.user, session: r.session }, error: null };
      },
      updateUser: async function (attrs, opts) {
        var t = await token();
        log('auth.updateUser', { clientId: clientId, attrs: clone(attrs || {}), options: clone(opts || {}) });
        if (!t) return { data: { user: null }, error: { name: 'AuthSessionMissingError', message: 'Auth session missing!', status: 400 } };
        var r = await backend({ op: 'auth.updateUser', url: url, key: key, token: t, attrs: clone(attrs || {}), options: clone(opts || {}) });
        if (r && r.hang) return NEVER();
        if (!r || r.error) {
          return { data: { user: null }, error: (r && r.error) || { name: 'AuthRetryableFetchError', message: 'Failed to fetch', status: 0 } };
        }
        var s = await readSession();
        if (s) { s.user = r.user; await writeSession(s); emit('USER_UPDATED', s); }
        return { data: { user: r.user }, error: null };
      },
      /* CHANGE 2026-10-12 F04-QA: email OTP. The backend decides; 'email_change' returns the same user with the email
         confirmed (session kept, USER_UPDATED), 'email'/'magiclink' returns a NEW session of the account that owns the
         email (session replaced, SIGNED_IN). Errors are AuthApiError-shaped with a `code` like supabase-js v2. */
      verifyOtp: async function (params) {
        params = params || {};
        var t = await token();
        log('auth.verifyOtp', { clientId: clientId, type: params.type, hasEmail: !!params.email, tokenLen: String(params.token || '').length });
        var r = await backend({ op: 'auth.verifyOtp', url: url, key: key, token: t, params: clone(params) });
        if (r && r.hang) return NEVER();
        if (!r || r.error) {
          return { data: { user: null, session: null }, error: (r && r.error) || { name: 'AuthRetryableFetchError', message: 'Failed to fetch', status: 0 } };
        }
        if (r.session) {
          await writeSession(r.session);
          emit(params.type === 'email_change' ? 'USER_UPDATED' : 'SIGNED_IN', r.session);
          return { data: { user: r.session.user, session: r.session }, error: null };
        }
        var s = await readSession();
        if (s) { s.user = r.user; await writeSession(s); emit('USER_UPDATED', s); }
        return { data: { user: r.user, session: s }, error: null };
      },
      signInWithOtp: async function (creds) {
        creds = creds || {};
        log('auth.signInWithOtp', { clientId: clientId, hasEmail: !!creds.email, options: clone(creds.options || {}) });
        var r = await backend({ op: 'auth.signInWithOtp', url: url, key: key, token: await token(), creds: clone(creds) });
        if (r && r.hang) return NEVER();
        if (!r || r.error) {
          return { data: { user: null, session: null }, error: (r && r.error) || { name: 'AuthRetryableFetchError', message: 'Failed to fetch', status: 0 } };
        }
        return { data: { user: null, session: null, messageId: r.messageId || null }, error: null };
      },
      resend: async function (creds) {
        creds = creds || {};
        log('auth.resend', { clientId: clientId, type: creds.type });
        var r = await backend({ op: 'auth.resend', url: url, key: key, token: await token(), creds: clone(creds) });
        if (r && r.hang) return NEVER();
        if (!r || r.error) return { data: { user: null, session: null }, error: (r && r.error) || { name: 'AuthRetryableFetchError', message: 'Failed to fetch', status: 0 } };
        return { data: { user: null, session: null }, error: null };
      },
      onAuthStateChange: function (cb) {
        var id = Math.random().toString(36).slice(2);
        var entry = { id: id, cb: cb };
        listeners.push(entry);
        log('auth.onAuthStateChange', { clientId: clientId });
        readSession().then(function (s) {
          setTimeout(function () { try { cb('INITIAL_SESSION', s); } catch (e) { console.error(e); } }, 0);
        });
        return { data: { subscription: { id: id, callback: cb, unsubscribe: function () {
          listeners = listeners.filter(function (l) { return l !== entry; });
        } } } };
      },
      signOut: async function () {
        log('auth.signOut', { clientId: clientId });
        await writeSession(null);
        emit('SIGNED_OUT', null);
        return { error: null };
      },
      refreshSession: async function () {
        var s = await readSession();
        log('auth.refreshSession', { clientId: clientId });
        if (!s) return { data: { user: null, session: null }, error: { name: 'AuthSessionMissingError', message: 'Auth session missing!', status: 400 } };
        if (navigator.onLine === false) return { data: { user: null, session: null }, error: { name: 'AuthRetryableFetchError', message: 'Failed to fetch', status: 0 } };
        s.expires_at = Math.floor(now() / 1000) + 3600;
        await writeSession(s);
        emit('TOKEN_REFRESHED', s);
        return { data: { user: s.user, session: s }, error: null };
      },
      setSession: async function (tokens) {
        log('auth.setSession', { clientId: clientId });
        var s = await readSession();
        if (s && tokens && tokens.access_token === s.access_token) return { data: { user: s.user, session: s }, error: null };
        return { data: { user: null, session: null }, error: { message: 'fake: setSession only accepts the stored session', status: 400 } };
      },
      startAutoRefresh: async function () {}, stopAutoRefresh: async function () {},
      admin: {}
    };

    /* ---------- query builder ---------- */
    function Builder(table) {
      this.req = { table: String(table), action: 'select', columns: '*', values: null, options: {},
                   filters: [], order: [], limit: null, range: null, single: false, maybe: false,
                   returning: false, count: null, head: false };
      this._throw = false;
      this._promise = null;
    }
    var B = Builder.prototype;
    B.select = function (columns, opts) {
      opts = opts || {};
      if (this.req.action === 'select') {
        this.req.columns = columns == null ? '*' : String(columns);
        this.req.count = opts.count || null;
        this.req.head = !!opts.head;
      } else {
        this.req.returning = true;
        this.req.columns = columns == null ? '*' : String(columns);
      }
      return this;
    };
    B.insert = function (values, opts) { this.req.action = 'insert'; this.req.values = clone(values); this.req.options = clone(opts || {}); return this; };
    B.upsert = function (values, opts) { this.req.action = 'upsert'; this.req.values = clone(values); this.req.options = clone(opts || {}); return this; };
    B.update = function (values, opts) { this.req.action = 'update'; this.req.values = clone(values); this.req.options = clone(opts || {}); return this; };
    B['delete'] = function (opts) { this.req.action = 'delete'; this.req.options = clone(opts || {}); return this; };
    function f(op) { return function (col, val) { this.req.filters.push({ op: op, col: String(col), val: clone(val) }); return this; }; }
    ['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'like', 'ilike', 'is', 'in', 'contains', 'containedBy'].forEach(function (op) { B[op] = f(op); });
    B.likeAllOf = function (col, pats) { var s = this; (pats || []).forEach(function (p) { s.like(col, p); }); return this; };
    B.match = function (obj) { var s = this; Object.keys(obj || {}).forEach(function (k) { s.eq(k, obj[k]); }); return this; };
    B.filter = function (col, op, val) {
      op = String(op);
      if (op === 'in' && typeof val === 'string') val = val.replace(/^\(|\)$/g, '').split(',').map(function (x) { return x.trim().replace(/^"|"$/g, ''); });
      this.req.filters.push({ op: op, col: String(col), val: clone(val) });
      return this;
    };
    B.not = function (col, op, val) { this.req.filters.push({ op: 'not.' + String(op), col: String(col), val: clone(val) }); return this; };
    B.or = function (expr) { this.req.filters.push({ op: 'or', col: '', val: String(expr) }); return this; };
    B.order = function (col, opts) { opts = opts || {}; this.req.order.push({ col: String(col), asc: opts.ascending !== false, nullsFirst: !!opts.nullsFirst }); return this; };
    B.limit = function (n) { this.req.limit = Number(n); return this; };
    B.range = function (a, b) { this.req.range = [Number(a), Number(b)]; return this; };
    B.single = function () { this.req.single = true; return this; };
    B.maybeSingle = function () { this.req.maybe = true; return this; };
    B.abortSignal = function () { return this; };
    B.returns = function () { return this; };
    B.overrideTypes = function () { return this; };
    B.csv = function () { this.req.csv = true; return this; };
    B.explain = function () { return this; };
    B.throwOnError = function () { this._throw = true; return this; };
    B.setHeader = function () { return this; };
    B._run = function () {
      if (this._promise) return this._promise;
      var req = this.req, self = this;
      this._promise = (async function () {
        var t = await token();
        var entry = log('query', { clientId: clientId, url: String(url), table: req.table, action: req.action, req: clone(req), hasToken: !!t });
        var r = await backend({ op: 'query', url: url, key: key, token: t, req: req, logId: entry.t });
        if (r && r.hang) return NEVER();
        if (r && r.delayMs) { await new Promise(function (res) { setTimeout(res, r.delayMs); }); r = r.after; if (r && r.hang) return NEVER(); }
        var res = { data: r && 'data' in r ? r.data : null, error: (r && r.error) || null,
                    count: r && 'count' in r ? r.count : null, status: (r && r.status) || 0,
                    statusText: (r && r.statusText) || '' };
        entry.result = { status: res.status, error: res.error, rows: Array.isArray(res.data) ? res.data.length : (res.data ? 1 : 0) };
        if (self._throw && res.error) { var err = new Error(res.error.message); Object.assign(err, res.error); throw err; }
        return res;
      })();
      return this._promise;
    };
    B.then = function (onOk, onErr) { return this._run().then(onOk, onErr); };
    B['catch'] = function (onErr) { return this._run()['catch'](onErr); };
    B['finally'] = function (fn) { return this._run()['finally'](fn); };

    function from(table) { return new Builder(table); }

    /* ---------- realtime / functions / rpc / storage stubs ---------- */
    var channels = [];
    var rtTimer = null, rtBusy = false;
    function rtMatch(b, ev) {
      var f = b.filter || {};
      if (b.type !== 'postgres_changes') return false;
      if (f.schema && f.schema !== '*' && f.schema !== ev.schema) return false;
      if (f.table && f.table !== '*' && f.table !== ev.table) return false;
      var e = String(f.event || '*').toUpperCase();
      if (e !== '*' && e !== ev.eventType) return false;
      if (ev.eventType === 'DELETE') return true;            // Supabase: delete events are not filterable
      if (f.filter) {
        var m = /^([a-z_]+)=eq\.(.*)$/.exec(String(f.filter));
        if (!m) return false;
        if (String((ev['new'] || {})[m[1]]) !== m[2]) return false;
      }
      return true;
    }
    async function rtPoll() {
      if (rtBusy) return;
      var open = channels.filter(function (c) { return c.state === 'joined'; });
      if (!open.length) return;
      if (navigator.onLine === false) return;
      rtBusy = true;
      try {
        for (var i = 0; i < open.length; i++) {
          var ch = open[i];
          var r = await backend({ op: 'rt.poll', url: url, key: key, token: await token(), since: ch.cursor, name: ch.name });
          if (!r || !r.events) continue;
          ch.cursor = r.cursor;
          r.events.forEach(function (ev) {
            ch.bindings.forEach(function (b) {
              if (!rtMatch(b, ev)) return;
              log('realtime.deliver', { name: ch.name, eventType: ev.eventType, table: ev.table });
              try { b.cb && b.cb(clone(ev)); } catch (e) { console.error(e); }
            });
          });
        }
      } finally { rtBusy = false; }
    }
    function channel(name, opts) {
      log('realtime.channel', { clientId: clientId, name: String(name) });
      var ch = {
        topic: 'realtime:' + name, name: String(name), bindings: [], state: 'closed', cursor: null,
        on: function (type, filter, cb) {
          ch.bindings.push({ type: type, filter: clone(filter), cb: cb });
          log('realtime.on', { name: String(name), type: type, filter: clone(filter) });
          return ch;
        },
        subscribe: function (cb) {
          log('realtime.subscribe', { name: String(name), bindings: ch.bindings.map(function (b) { return { type: b.type, filter: b.filter }; }) });
          (async function () {
            var st;
            if (navigator.onLine === false) st = 'CHANNEL_ERROR';
            else {
              var r = await backend({ op: 'rt.subscribe', url: url, key: key, token: await token(), name: String(name),
                                      bindings: ch.bindings.map(function (b) { return { type: b.type, filter: b.filter }; }) });
              if (r && r.ok) { ch.cursor = r.cursor; ch.state = 'joined'; st = 'SUBSCRIBED'; }
              else st = (r && r.status) || 'CHANNEL_ERROR';
            }
            if (!rtTimer) rtTimer = setInterval(rtPoll, 250);
            if (cb) setTimeout(function () { try { cb(st); } catch (e) { console.error(e); } }, 0);
          })();
          return ch;
        },
        unsubscribe: function () { ch.state = 'closed'; log('realtime.unsubscribe', { name: String(name) }); return Promise.resolve('ok'); },
        send: function () { return Promise.resolve('ok'); },
        track: function () { return Promise.resolve('ok'); }, untrack: function () { return Promise.resolve('ok'); },
        presenceState: function () { return {}; }
      };
      channels.push(ch);
      return ch;
    }
    async function rpc(fn, args) {
      log('rpc', { clientId: clientId, fn: String(fn) });
      var r = await backend({ op: 'rpc', url: url, key: key, token: await token(), fn: String(fn), args: clone(args || {}) });
      if (r && r.hang) return NEVER();
      if (!r || r.error) return { data: null, error: (r && r.error) || { message: 'fake: rpc not available', code: 'PGRST202' }, status: (r && r.status) || 404, statusText: 'Error' };
      return { data: 'data' in r ? r.data : null, error: null, status: r.status || 200, statusText: 'OK', count: null };
    }
    var functions = {
      invoke: async function (name, opts) {
        opts = opts || {};
        var body = opts.body;
        if (typeof body === 'string') { try { body = JSON.parse(body); } catch (e) {} }
        var t = await token();
        log('functions.invoke', { clientId: clientId, name: String(name), action: body && body.action });
        var r = await backend({ op: 'functions.invoke', url: url, key: key, token: t, name: String(name), body: clone(body),
                                headers: clone(opts.headers || {}) });
        if (r && r.hang) return NEVER();
        if (!r || r.offline || r.error && !('httpStatus' in r)) {
          return { data: null, error: { name: 'FunctionsFetchError', message: 'Failed to send a request to the Edge Function', context: {} } };
        }
        var status = r.httpStatus, json = r.json;
        if (status >= 200 && status < 300) return { data: json, error: null, response: new Response(JSON.stringify(json), { status: status }) };
        var resp = new Response(JSON.stringify(json), { status: status, headers: { 'Content-Type': 'application/json' } });
        return { data: null, error: { name: 'FunctionsHttpError', message: 'Edge Function returned a non-2xx status code', context: resp }, response: resp };
      },
      setAuth: function () {}
    };
    var storage = {
      from: function (bucket) {
        log('storage.from', { clientId: clientId, bucket: String(bucket) });
        var err = async function () { return { data: null, error: { message: 'fake: storage not available' } }; };
        return { upload: err, download: err, remove: err, list: err, createSignedUrl: err, getPublicUrl: function () { return { data: { publicUrl: '' } }; } };
      }
    };

    return {
      supabaseUrl: url, supabaseKey: key, auth: auth, from: from, schema: function () { return { from: from, rpc: rpc }; },
      rpc: rpc, functions: functions, storage: storage, channel: channel,
      getChannels: function () { return channels.slice(); },
      removeChannel: function (ch) { if (ch) ch.state = 'closed'; channels = channels.filter(function (c) { return c !== ch; }); log('realtime.removeChannel', { name: ch && ch.name }); return Promise.resolve('ok'); },
      removeAllChannels: function () { channels.forEach(function (c) { c.state = 'closed'; }); channels = []; log('realtime.removeAllChannels', {}); return Promise.resolve(['ok']); },
      realtime: { setAuth: function () {}, connect: function () {}, disconnect: function () {} },
      __fake: true
    };
  }

  window.supabase = { createClient: createClient, __fake: true, __fakeVersion: FAKE_VERSION };
  window.__fake = {
    version: FAKE_VERSION,
    log: function () { return LOG.slice(); },
    control: function (msg) { return backend(Object.assign({ op: 'control' }, msg)); },
    state: function () { return backend({ op: 'control', action: 'state' }); },
    setMode: function (mode) { return backend({ op: 'control', action: 'setMode', mode: mode }); },
    link: function (opts) { return backend(Object.assign({ op: 'control', action: 'link' }, opts || {})); }
  };
  log('fake.loaded', { version: FAKE_VERSION });
})();
