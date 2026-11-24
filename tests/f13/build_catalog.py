"""Lonely Planner F13 · builds app/i18n/en.json from the hand-written shell strings below + app/countries.json + app/currencies.json · version 3.0.0-alpha.18.9
CHANGE 2026-11-24 F13-TOOL-02: new file (no previous version). Stage 4a: app shell (tabs, home, itinerary, journal, budget, more menu, dialogs, wizard-adjacent). Run: python3 -I tests/f13/build_catalog.py
Country / currency names come from the app's own he/en fields, so they never drift. Hand strings: English wording by Claude, pending Or's approval."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
EXACT = """
בית|Home
‹|›
›|‹
←|→
→|←
מסלול|Itinerary
יומן|Journal
תקציב|Budget
עוד|More
מסע של חלומות|A dream journey
שעון מקומי|Local time
🏠 שעון ישראל|🏠 Israel time
פתח מסלול|Open itinerary
ימים|Days
נקודות עניין|Points of interest
הזמנות|Bookings
תמונות|Photos
היום|Today
ויאטנם|Vietnam
📍 מקומי|📍 Local
🏠 ישראל|🏠 Israel
🌍 מפה אמיתית|🌍 Real map
📍 צ'ק-אין — איפה אנחנו עכשיו?|📍 Check-in — where are we now?
נק' עניין|POIs
מקומות שביקרנו — פתיחת המפה של היום|Places we visited — open today's map
ביקרנו|Visited
אין עדיין הזמנות|No bookings yet
מסלול ומפה|Itinerary & map
בחירת יום|Pick a day
🗺️ מפה|🗺️ Map
📅 ציר זמן|📅 Timeline
🎯 פעילויות|🎯 Activities
🏨 מלון|🏨 Hotel
עוד פרטים|More details
💰 עלות מתוכננת|💰 Planned cost
💡 דגשים|💡 Highlights
📍 נקודות עניין|📍 Points of interest
➕ הוסף מ־Maps|➕ Add from Maps
🏨 הזמנה|🏨 Booking
פתח חיפוש ב־Booking|Open search on Booking
הוספת הזמנה מאושרת|Add a confirmed booking
📍 היום|📍 Today
🗺️ כל המסלול|🗺️ Whole itinerary
🧭 נק' עניין|🧭 POIs
הצג תכנון|Show plan
📍 פתח מיקום ב־Google Maps|📍 Open location in Google Maps
⏱️ זמן נסיעה בין נקודות|⏱️ Travel time between points
📍 מסלול בפועל מ-Timeline|📍 Actual route from Timeline
אפשר להעלות קובץ Timeline שיוצא מהטלפון, והאפליקציה תצייר על המפה בדיוק איפה הייתם בפועל, לצד המסלול המתוכנן. הקובץ נשמר במאגר המשותף למשפחה -- רק מי שמעלה בוחר קובץ, כולם רואים את התוצאה.|You can upload a Timeline file exported from your phone, and the app will draw on the map exactly where you actually were, next to the planned route. The file is saved in the family's shared storage -- only the uploader picks the file, everyone sees the result.
⬆️ העלאת קובץ Timeline|⬆️ Upload Timeline file
איך מוציאים את הקובץ? הגדרות ← מיקום ← Timeline ← "ייצוא נתוני Timeline" 📄|How do I export the file? Settings → Location → Timeline → "Export Timeline data" 📄
נקודות מיקום|Location points
ימים מכוסים|Days covered
הצג על המפה|Show on map
🔄 החלפת קובץ|🔄 Replace file
🗑️ הסרה|🗑️ Remove
הוספת רשומה חדשה (לא מוחקת שום דבר שכבר נכתב)|Add a new entry (doesn't delete anything already written)
+ הוסף רשומה|+ Add entry
אלבום|Album
כל התמונות|All photos
לפי ימים|By day
תקציב והוצאות|Budget & expenses
💸 יצא עד כה|💸 Spent so far
✅ זמין להוצאה|✅ Available to spend
תקציב יעד (₪)|Target budget (₪)
שמור יעד|Save target
➕ הוספת הוצאה|➕ Add expense
בחירת יום להוצאה|Pick a day for the expense
תיאור|Description
שולם ב־|Paid in
סכום בש״ח|Amount in ₪
⚠️ הזן סכום תקין|⚠️ Enter a valid amount
🔄 חשב לשקלים|🔄 Convert to shekels
לינה|Lodging
אוכל|Food
נסיעות|Transport
שווקים וקניות|Markets & shopping
אטרקציות|Attractions
אחר|Other
שמור הוצאה|Save expense
ביטול עריכה|Cancel editing
📋 פירוט הוצאות|📋 Expense details
💱 מחשבון המרה|💱 Currency converter
אפשר לעדכן שערי חליפין אוטומטית מהרשת (מומלץ לפני הנסיעה ומדי כמה ימים), או להזין אותם ידנית. השערים שנשמרים משותפים לכל בני המשפחה.|Exchange rates can be updated automatically from the web (recommended before the trip and every few days), or entered manually. Saved rates are shared by the whole family.
🔄 עדכן שערים אוטומטית|🔄 Update rates automatically
שמור שערים|Save rates
סכום להמרה|Amount to convert
בחרו מטבעות: לחיצה ראשונה = מקור, לחיצה שנייה = יעד|Pick currencies: first tap = from, second tap = to
מקור|From
יעד|To
ירוק = מקור|Green = from
אפור = יעד|Grey = to
חשב|Calculate
הוסף לתקציב|Add to budget
יעד אישי (₪)|Personal target (₪)
שמור|Save
כספת מסמכים|Document vault
זמין ללא אינטרנט|Available offline
הזמנות וארנק נסיעה|Bookings & travel wallet
טיסות, לינה, הסעות ופעילויות|Flights, lodging, transfers and activities
תמונות הטיול|Trip photos
קישור לתיקיית Google Photos המשותפת|Link to the shared Google Photos folder
ניהול|Management
משתמשים, הגדרות מסע, גיבוי|Users, trip settings, backup
סנכרון בענן פעיל|Cloud sync active
משתמשים|Users
הגדרות מסע|Trip settings
מטבעות|Currencies
שערי המרה|Exchange rates
גיבוי וטעינה|Backup & restore
ניקוי תמונות ישנות|Clean up old photos
מחיקת תמונות האלבום מהענן|Delete album photos from the cloud
הגיבוי בענן פעיל|Cloud backup is active
הנתונים מעודכנים|Data is up to date
גיבוי אחרון|Last backup
⬇️ גיבוי / טעינה עכשיו|⬇️ Back up / restore now
כולל אקסל, JSON, והעתקה ללוח — הכל בחלונית אחת. שימו לב: הגיבוי כולל את נתוני המסלול בלבד (לא יומן/תמונות/הוצאות).|Includes Excel, JSON and copy to clipboard — all in one window. Note: the backup covers itinerary data only (not journal / photos / expenses).
💱 המרת מטבע|💱 Currency conversion
סגירה|Close
סכום|Amount
➕ הוסף כהוצאה|➕ Add as expense
מופיע רק כשהיעד הוא ₪|Shown only when the target is ₪
אפשר לחפש (גם מבין נקודות שכבר שמורות בטיול, וגם הצעות כתובת), או להדביק קישור Google Maps.|You can search (among points already saved in the trip, plus address suggestions), or paste a Google Maps link.
📍 נקודה א׳|📍 Point A
חפשו נקודה שמורה או כתובת...|Search a saved point or an address...
📍 נקודה ב׳|📍 Point B
חשב זמני נסיעה|Calculate travel times
נסיעה|Drive
הליכה|Walk
לחיצה על אחת האפשרויות פותחת ניווט ב-Google Maps באותו מצב|Tapping an option opens navigation in Google Maps in that mode
🌦️ מזג אוויר למחר|🌦️ Tomorrow's weather
🔐 כספת מסמכים|🔐 Document vault
המסמכים נשמרים מקומית במכשיר וזמינים גם ללא אינטרנט. תמונות נדחסות אוטומטית; קובצי PDF נתמכים עד 3MB (מגבלת אחסון המכשיר).|Documents are stored locally on the device and available offline. Images are compressed automatically; PDF files are supported up to 3MB (device storage limit).
שייך ל|Belongs to
✈️ טיסות|✈️ Flights
🛂 דרכונים / ויזות|🛂 Passports / visas
🏨 מלונות|🏨 Hotels
🛡️ ביטוח|🛡️ Insurance
🚗 תחבורה|🚗 Transport
📎 אחר|📎 Other
שם המסמך|Document name
➕ הוסף מסמך|➕ Add document
📷 תמונות הטיול|📷 Trip photos
האלבום בתוך האפליקציה הוחלף בקישור לתיקיית Google Photos משותפת — כלי תמונות ייעודי ונוח יותר. הקישור משותף לכל המשפחה.|The in-app album was replaced by a link to a shared Google Photos folder — a dedicated, more convenient photo tool. The link is shared by the whole family.
🔗 קישור לתיקיית Google Photos המשותפת|🔗 Link to the shared Google Photos folder
💾 שמירת קישור|💾 Save link
📷 פתיחה ב-Google Photos|📷 Open in Google Photos
🗑️ ניקוי תמונות ישנות|🗑️ Clean up old photos
האלבום באפליקציה הוחלף בקישור ל-Google Photos משותף. כלי זה מוחק לצמיתות מהענן את כל התמונות שהועלו בעבר דרך היומן — רשומות הטקסט של היומן עצמן לא נפגעות. פעולה זו בלתי הפיכה.|The in-app album was replaced by a link to a shared Google Photos. This tool permanently deletes from the cloud all photos previously uploaded through the journal — the journal's text entries are not affected. This action cannot be undone.
🔍 סריקת תמונות קיימות|🔍 Scan existing photos
שיתוף מסמך|Share document
📤 שיתוף|📤 Share
🖼️ פתח תמונה|🖼️ Open image
💾 שמור במכשיר|💾 Save to device
פעולות על המסמך|Document actions
העברה בין תיקייה / תגית|Move between folder / tag
שיתוף|Share
מחיקה|Delete
🔀 העברת מסמך|🔀 Move document
תקייה|Folder
💾 שמירה|💾 Save
ביטול|Cancel
🧭 הגדרות מסע|🧭 Trip settings
שם הטיול|Trip name
סגור|Close
✎ עריכת יום|✎ Edit day
תאריך DD/MM/YYYY|Date DD/MM/YYYY
אזור|Area
כותרת|Title
מלון|Hotel
עלות|Cost
שמור שינויים|Save changes
מחק יום|Delete day
👋 מי נכנס לאפליקציה?|👋 Who's using the app?
הבחירה תסומן בכל תמונה, רשומה, הוצאה, נקודת עניין והזמנה.|Your choice is marked on every photo, entry, expense, point of interest and booking.
או שם אחר|Or another name
כניסה|Enter
💡 לוחצים על תג המצלמה כדי להוסיף תמונת פנים אישית (נשמרת בלי צורך באינטרנט)|💡 Tap the camera badge to add a personal face photo (saved without needing internet)
📍 הוספת נקודת עניין|📍 Add a point of interest
קישור Google Maps או קואורדינטות|Google Maps link or coordinates
קישור מלא או 21.0285,105.8542|Full link or 21.0285,105.8542
חלץ|Extract
שם המקום|Place name
הערות|Notes
שמור נקודה|Save point
🏨 הזמנה מאושרת|🏨 Confirmed booking
מלון בפועל|Actual hotel
מספר אישור|Confirmation number
מחיר כולל בש״ח|Total price in ₪
קישור למלון (עמוד ההזמנה הספציפי, לא חיפוש כללי)|Hotel link (the specific booking page, not a general search)
טווח שהייה בפועל|Actual stay range
⚙️ בחירה ידנית של ימים ספציפיים|⚙️ Manually pick specific days
מיקום המלון בפועל (לעדכון המפה — אופציונלי)|Actual hotel location (to update the map — optional)
שמור הזמנה|Save booking
🎫 הזמנות וארנק נסיעה|🎫 Bookings & travel wallet
הכל|All
🏨 לינה|🏨 Lodging
🚐 הסעות|🚐 Transfers
🚢 קרוזים|🚢 Cruises
🎟️ פעילויות|🎟️ Activities
🛡️ ביטוח/ויזה|🛡️ Insurance/visa
➕ הוספת הזמנה|➕ Add booking
הזמנה חדשה|New booking
סוג|Type
✈️ טיסה|✈️ Flight
🏨 מלון / לינה|🏨 Hotel / lodging
🚐 הסעה / תחבורה|🚐 Transfer / transport
🚢 קרוז|🚢 Cruise
🎟️ פעילות / סדנה|🎟️ Activity / workshop
🛂 ויזה / דרכון|🛂 Visa / passport
כותרת (למשל: טיסה TLV→HAN)|Title (e.g. Flight TLV→HAN)
ספק|Provider
סטטוס|Status
אוטומטי — לפי מספר אישור|Automatic — by confirmation number
⏳ סמן כ״ממתין לאישור״ (גם בלי מספר אישור)|⏳ Mark as "pending confirmation" (even without a confirmation number)
💡 הסכום ייכנס לתקציב/לינה בפועל רק כשההזמנה מסומנת "אושר" (יש מספר אישור).|💡 The amount enters the budget / actual lodging only when the booking is marked "confirmed" (has a confirmation number).
טלפון|Phone
תאריך / שעה|Date / time
כתובת / נקודת מפגש|Address / meeting point
קישור (אתר / הזמנה)|Link (website / booking)
מחובר ליום במסלול|Linked to a day in the itinerary
החל על כל רצף השהייה (כמו בהזמנת מלון רגילה)|Apply to the whole stay (like a regular hotel booking)
🏨 עבור מלון, הסכום ייכנס אוטומטית לסעיף|🏨 For a hotel, the amount goes automatically into the
בתקציב — בדיוק כמו "הוספת הזמנה מאושרת" הקיים. אין צורך לבחור קטגוריה.|lodging line of the budget — exactly like the existing "Add a confirmed booking". No need to pick a category.
עלות (₪ / ₫)|Cost (₪ / ₫)
מסמכים מצורפים|Attached documents
🔗 קשר מהכספת|🔗 Link from the vault
📷 העלה חדש|📷 Upload new
🗑️ מחיקה|🗑️ Delete
🔗 קישור מהכספת|🔗 Link from the vault
בחרו מסמכים קיימים מהכספת כדי לקשר אותם להזמנה זו.|Pick existing documents from the vault to link them to this booking.
סיום|Done
💾 גיבוי וייבוא נתוני מסלול|💾 Back up & import itinerary data
מומלץ אקסל לעריכה נוחה (נפתח כטבלה), או JSON לגיבוי מלא ומדויק.|Excel is recommended for easy editing (opens as a table), or JSON for a full, exact backup.
📊 הורדה כאקסל|📊 Download as Excel
⬇️ הורדה כ-JSON|⬇️ Download as JSON
📋 העתק JSON ללוח|📋 Copy JSON to clipboard
📂 ייבוא|📂 Import
מחליף את כל המסלול הנוכחי. יש לשמור על מבנה העמודות/השדות כפי שהוא בקובץ שהורדתם מכאן.|Replaces the entire current itinerary. Keep the column / field structure exactly as in the file you downloaded from here.
בחר קובץ אקסל (.xlsx)|Choose an Excel file (.xlsx)
בחר קובץ JSON|Choose a JSON file
המרת מטבע|Currency conversion
שאלות על הטיול|Questions about the trip
📍 איפה אתם?|📍 Where are you?
הערה (לא חובה)|Note (optional)
למשל: הקפה הכי טוב בטיול ☕|e.g. The best coffee of the trip ☕
שמור צ'ק-אין|Save check-in
🔒 השיחה נשמרת רק במכשיר הזה|🔒 The chat is saved only on this device
צירוף תמונה|Attach a photo
שאל שאלה על הטיול…|Ask a question about the trip…
שליחה|Send
עלות (₪)|Cost (₪)
🔍 חיפוש מקום|🔍 Search a place
שם של מקום, מסעדה, אטרקציה…|Name of a place, restaurant, attraction…
או: קישור Google Maps / קואורדינטות|Or: Google Maps link / coordinates
שם|Name
🔗 הוספת קישור Drive|🔗 Add Drive link
קישור לקובץ ב-Google Drive|Link to a file in Google Drive
קישור Drive (הוספה / עדכון)|Drive link (add / update)
＋ הוצאה מהירה|＋ Quick expense
מטבע|Currency
קטגוריה|Category
🍜 אוכל|🍜 Food
🛏️ לינה|🛏️ Lodging
🚕 נסיעות|🚕 Transport
🛍️ קניות|🛍️ Shopping
🎟️ אטרקציות|🎟️ Attractions
📦 אחר|📦 Other
תיאור קצר (לא חובה)|Short description (optional)
⚠️ הזינו סכום|⚠️ Enter an amount
🧾 הוצאות אחרונות|🧾 Recent expenses
עריכת היום ופעולות|Edit day & actions
דרכונים וטיסות|Passports & flights
המלון להיום|Today's hotel
ניווט לנקודה הבאה|Navigate to the next point
הוצאה מהירה|Quick expense
🎯 הלו"ז להיום|🎯 Today's schedule
👣 ביקרנו ·|👣 Visited ·
סנכרון|Sync
🏨 המלון להיום|🏨 Today's hotel
היום הקודם|Previous day
בחירת יום ביומן|Pick a day in the journal
היום הבא|Next day
לא משויך ליום מסוים|Not tied to a specific day
יום ההוצאה|Expense day
ללא יום|No day
ניהול מטבעות|Manage currencies
ים סין הדרומי|South China Sea
מדינות לפי ימים|Countries by day
כתובת תמונה|Photo URL
הוספה|Add
החשבון שלי|My account
קישור מייל לחשבון|Link an email to the account
אימות במייל · החברות בטיול נשארת|Email verification · your trip membership stays
הטיול|The trip
ניהול מערכת|System administration
קבוצות והזמנת מנהלים|Groups & inviting managers
סופר-אדמין|Super admin
היי! אני כאן לעזור עם שאלות על המסלול. אפשר לשאול אותי כל דבר, או ללחוץ על אחת ההצעות למטה.|Hi! I'm here to help with questions about the itinerary. Ask me anything, or tap one of the suggestions below.
חברים וקישור|Members & link
אני בטיול|I'm on the trip
יציאה מהטיול|Leave the trip
כל חבר יכול לצאת בעצמו|Any member can leave on their own
שם, תאריכים · השם מתעדכן לכל הקבוצה|Name, dates · the name updates for the whole group
טרם הוזמן|Not booked yet
טרם|Not yet
אין נקודות|No points
✈ יום טיסה|✈ Flight day
מדינה ביום הזה|Country on this day
מדינה ביום הזה – מדינה|Country on this day – country
מדינה ביום הזה – עיר|Country on this day – city
עיר (לא חובה)|City (optional)
אזור זמן:|Time zone:
מהטווח; שינוי כאן חל רק על היום הזה.|From the range; a change here applies to this day only.
🗺️ מפה סכמטית|🗺️ Schematic map
מפה סכמטית · בלי רקע מפה|Schematic map · no map background
התחזית תתעדכן קרוב יותר למועד.|The forecast will update closer to the date.
בדרך כלל בעונה זו: חם ולח, עם סיכוי לגשמי אחר-צהריים מקומיים.|Usually at this time of year: hot and humid, with a chance of local afternoon showers.
◔ יעודכן בהמשך|◔ To be updated later
עוד אין הוצאות|No expenses yet
חיפוש ב-Booking|Search on Booking
חיפוש ב-Google Hotels|Search on Google Hotels
העיר והלילות נלקחים מטווח הימים של המסלול. באתר אפשר למיין לפי מחיר או דירוג.|The city and nights are taken from the itinerary's date range. On the site you can sort by price or rating.
עודכן לאחרונה זה עתה|Last updated just now
זה עתה|Just now
עודכן זה עתה|Updated just now
⚠️ לא הצלחנו לטעון את Google Maps (בעיית רשת) — עברנו למפה הסכמטית.|⚠️ Couldn't load Google Maps (network issue) — switched to the schematic map.
🌍 נסה שוב Google Maps|🌍 Retry Google Maps
זהה לשעון ישראל|Same as Israel time
תכנון|Plan
בפועל|Actual
✓ שייך ליום המוצג|✓ Belongs to the day shown
תאריך|Date
סעיף|Item
פרוט|Details
אין עדיין הוצאות רשומות|No expenses recorded yet
ארנק יומי|Daily wallet
נשאר להוציא ליום|Left to spend per day
✓ במסגרת|✓ Within budget
תחזית למחר|Tomorrow's forecast
התחזית עדיין לא זמינה. היא תתעדכן קרוב יותר למועד.|The forecast isn't available yet. It will update closer to the date.
📴 אין חיבור לרשת · המסמכים השמורים במכשיר זמינים|📴 No network connection · documents saved on the device are available
לכל פרטי היום|Full day details
צעדים ראשונים|First steps
הקמת הטיול|Trip set up
שליחת קישור לקבוצה|Send the link to the group
הוספת היעד הראשון ליום 1|Add the first destination to day 1
שליחה בווטסאפ|Send on WhatsApp
הוספת נקודה|Add a point
עוד לא נוספו נקודות|No points added yet
שערים בשקלים|Rates in shekels
שערים ברירת מחדל משוערים — כדאי לעדכן לפני הנסיעה|Approximate default rates — worth updating before the trip
"""
PATTERNS = """
יום {a} מתוך {b}|Day {a} of {b}
יום {a} מתוך {b} ·|Day {a} of {b} ·
יום {n} · {d}|Day {n} · {d}
יום {n} · עוד לא נוספו נקודות|Day {n} · no points added yet
יומן יום {n}|Journal · day {n}
יום {n}|Day {n}
{n} ימים|{n} days
{n} לילות|{n} nights
עוד {n} ימים לטיול|{n} days to go
{n} ימים נותרו|{n} days left
{a} מתוך {b}|{a} of {b}
תמונות ({a} מתוך {b})|Photos ({a} of {b})
{a} מתוך {b} הזמנות מאושרות|{a} of {b} bookings confirmed
{n} חברים · תפקידים · קישור הצטרפות|{n} members · roles · join link
{a} – {b} · {n} ימים|{a} – {b} · {n} days
{n}% מהיעד|{n}% of target
מתוך יעד {x} ₪|of a {x} ₪ target
{x} ₪ זמינים|{x} ₪ available
{n} אורחים · מחברי הטיול|{n} guests · from the trip members
אורח אחד · מחברי הטיול|1 guest · from the trip members
עוד אין לינה ל-{a} עד {b}|No lodging yet for {a} to {b}
הוצאות אישיות שלך עד כה: {x} ₪ (לא הוגדר יעד אישי)|Your personal expenses so far: {x} ₪ (no personal target set)
גרסה {v}|Version {v}
{flag} · {n} ימים|{flag} · {n} days
"""
def parse(blk):
    for ln in blk.strip().split("\n"):
        he, en = ln.split("|", 1)
        yield he.strip(), en.strip()
def main():
    exact = dict(parse(EXACT))
    for c in json.loads((ROOT / "app/countries.json").read_text(encoding="utf-8")):
        if c.get("he") and c.get("en"): exact.setdefault(c["he"], c["en"])
    cur = ROOT / "app/currencies.json"
    if cur.exists():
        for c in json.loads(cur.read_text(encoding="utf-8")):
            if c.get("he") and c.get("en"): exact.setdefault(c["he"], c["en"])
    pats = [{"he": h, "en": e} for h, e in parse(PATTERNS)]
    out = {"version": 2, "_note": "F13 English catalog. exact: Hebrew source text -> English (plain text; emoji / ·/ arrows around it are handled by the runtime). patterns: with {placeholders}. keys: for new code, t('key'). Generated by tests/f13/build_catalog.py (3.0.0-alpha.18.9); countries + currencies come from app/countries.json / currencies.json.",
           "exact": exact, "patterns": pats, "keys": {}}
    (ROOT / "app/i18n/en.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("exact", len(exact), "patterns", len(pats))
main()
