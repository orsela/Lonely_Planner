# OFFMAP – הכנת חבילות מפה (כלי, גרסה 0.1)
<!-- CHANGE 2026-11-24 OFFMAP-TOOL-01: new file (no previous version). -->
מריצים על מחשב עם רשת, פעם אחת לטיול. לא חלק מהאפליקציה.

1. התקנת `pmtiles`: מ-https://github.com/protomaps/go-pmtiles/releases (קובץ בינארי למערכת שלך), או `brew install pmtiles`.
2. כתובת build עדכני של Protomaps: https://maps.protomaps.com/builds → מעתיקים קישור `.pmtiles` (כ-120 GB; `extract` קורא רק טווחי בתים, לא מוריד הכול).
3. **מדידת גודל (לא בונה כלום):**
   `python3 tools/offmap/build_packs.py tools/offmap/packs_romania.json --source <URL> --out out --dry-run`
   שולחים לי את הפלט. אם סכום החבילות > 80 MB נתקן bbox / maxzoom ב-`packs_romania.json`.
4. **בנייה:** אותה פקודה בלי `--dry-run`. נוצרים `out/*.pmtiles` ו-`out/manifest.json` (גודל + sha256).
5. העלאה לענף `maps-data` בתיקייה `maps/romania/` (אני אכין את הענף ואת ההוראות המדויקות אחרי שנראה גדלים). כל קובץ ≤ 100 MB.
