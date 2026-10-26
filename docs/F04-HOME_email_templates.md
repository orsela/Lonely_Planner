# F04-HOME — Supabase Auth email templates (Or pastes these in the dashboard)

<!-- CHANGE 2026-10-26 F04H-DOCS-02: new file (no previous version). Supersedes F04 spec §5.1 ("keeping the link"). -->

Where: Supabase → project `plan-travel` → Authentication → Emails → Templates.
Two templates get the **same** subject and body: **"Change email address"** (a new manager links their email) and
**"Magic link"** (an existing manager signs in). Nothing else changes (SMTP, sender, other templates).

## Subject (both templates)

```
{{ .Token }} – קוד הכניסה ל-Lonely Planner
```

## Body (both templates) — paste as is

```html
<div dir="rtl" style="font-family:Arial,'Segoe UI',sans-serif;background:#f7f6f1;padding:24px 12px;color:#17211b">
  <div style="max-width:420px;margin:0 auto;background:#ffffff;border:1px solid #e4e6df;border-radius:18px;padding:24px 18px;text-align:center">
    <div style="font-size:18px;font-weight:900;color:#0f6b4f">Lonely Planner</div>
    <p style="margin:18px 0 8px;font-size:15px;color:#3a443d">קוד האימות שלך:</p>
    <div dir="ltr" style="display:inline-block;font-family:Menlo,Consolas,monospace;font-size:32px;font-weight:800;letter-spacing:6px;background:#f7f6f1;border:1px dashed #d6d9cf;border-radius:12px;padding:10px 18px">{{ .Token }}</div>
    <p style="margin:18px 0 0;font-size:13.5px;line-height:1.6;color:#5f6861">חוזרים לאפליקציה ומקלידים את הקוד. הוא תקף שעה ופעם אחת.<br>לא ביקשת קוד? אפשר להתעלם מהמייל.</p>
  </div>
</div>
```

Notes
- No `{{ .ConfirmationURL }}`: the app verifies by code only (F04 D1); the link opened a second window and confused people.
- `{{ .Token }}` in the subject is supported (Supabase's own default reauthentication subject uses it).
- Check after saving: request one code, confirm the notification shows the 6 digits and the mail has no link.
