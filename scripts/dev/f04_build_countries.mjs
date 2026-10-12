// CHANGE 2026-10-12 F04-DATA-01: new file (no previous version). Dev generator for app/countries.json and
// app/currencies.json (docs/F04_spec.md §4). Only the generated JSON is shipped; this script is not loaded by the app.
//
// Sources (all local, no network — the sandbox's npm/PyPI registries were blocked):
//   - ISO-3166 codes + every country's IANA zones: tzdata `zone.tab` (default /usr/share/zoneinfo/zone.tab)
//   - Hebrew / English country names, currency names, symbols: CLDR via Node's ICU (Intl.DisplayNames, NumberFormat),
//     with HE_NAME / CUR_HE overrides for common Israeli usage
//   - primary currency per country: CLDR territory currencies (table PRIMARY below, dumped from CLDR 47 via babel
//     2.18 get_territory_currencies(), first tender; BT/LS/NA use their own currency, PS → ILS, ZW/PA → USD)
//   - capitals {he, en, lat, lng} and the capital's zone: CAPITALS below (hand-authored; coordinates ±0.01°)
//
// usage: node scripts/dev/f04_build_countries.mjs [zone.tab path]   → writes app/countries.json, app/currencies.json
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const ZONE_TAB = process.argv[2] || "/usr/share/zoneinfo/zone.tab";

const PRIMARY = Object.fromEntries(("AD:EUR AE:AED AF:AFN AG:XCD AI:XCD AL:ALL AM:AMD AO:AOA AQ:USD AR:ARS AS:USD AT:EUR AU:AUD " +
  "AW:AWG AX:EUR AZ:AZN BA:BAM BB:BBD BD:BDT BE:EUR BF:XOF BG:BGN BH:BHD BI:BIF BJ:XOF BL:EUR BM:BMD BN:BND BO:BOB BQ:USD " +
  "BR:BRL BS:BSD BT:BTN BV:NOK BW:BWP BY:BYN BZ:BZD CA:CAD CC:AUD CD:CDF CF:XAF CG:XAF CH:CHF CI:XOF CK:NZD CL:CLP CM:XAF " +
  "CN:CNY CO:COP CR:CRC CU:CUP CV:CVE CW:XCG CX:AUD CY:EUR CZ:CZK DE:EUR DJ:DJF DK:DKK DM:XCD DO:DOP DZ:DZD EC:USD EE:EUR " +
  "EG:EGP EH:MAD ER:ERN ES:EUR ET:ETB FI:EUR FJ:FJD FK:FKP FM:USD FO:DKK FR:EUR GA:XAF GB:GBP GD:XCD GE:GEL GF:EUR GG:GBP " +
  "GH:GHS GI:GIP GL:DKK GM:GMD GN:GNF GP:EUR GQ:XAF GR:EUR GS:GBP GT:GTQ GU:USD GW:XOF GY:GYD HK:HKD HM:AUD HN:HNL HR:EUR " +
  "HT:HTG HU:HUF ID:IDR IE:EUR IL:ILS IM:GBP IN:INR IO:USD IQ:IQD IR:IRR IS:ISK IT:EUR JE:GBP JM:JMD JO:JOD JP:JPY KE:KES " +
  "KG:KGS KH:KHR KI:AUD KM:KMF KN:XCD KP:KPW KR:KRW KW:KWD KY:KYD KZ:KZT LA:LAK LB:LBP LC:XCD LI:CHF LK:LKR LR:LRD LS:LSL " +
  "LT:EUR LU:EUR LV:EUR LY:LYD MA:MAD MC:EUR MD:MDL ME:EUR MF:EUR MG:MGA MH:USD MK:MKD ML:XOF MM:MMK MN:MNT MO:MOP MP:USD " +
  "MQ:EUR MR:MRU MS:XCD MT:EUR MU:MUR MV:MVR MW:MWK MX:MXN MY:MYR MZ:MZN NA:NAD NC:XPF NE:XOF NF:AUD NG:NGN NI:NIO NL:EUR " +
  "NO:NOK NP:NPR NR:AUD NU:NZD NZ:NZD OM:OMR PA:USD PE:PEN PF:XPF PG:PGK PH:PHP PK:PKR PL:PLN PM:EUR PN:NZD PR:USD PS:ILS " +
  "PT:EUR PW:USD PY:PYG QA:QAR RE:EUR RO:RON RS:RSD RU:RUB RW:RWF SA:SAR SB:SBD SC:SCR SD:SDG SE:SEK SG:SGD SH:SHP SI:EUR " +
  "SJ:NOK SK:EUR SL:SLE SM:EUR SN:XOF SO:SOS SR:SRD SS:SSP ST:STN SV:USD SX:XCG SY:SYP SZ:SZL TC:USD TD:XAF TF:EUR TG:XOF " +
  "TH:THB TJ:TJS TK:NZD TL:USD TM:TMT TN:TND TO:TOP TR:TRY TT:TTD TV:AUD TW:TWD TZ:TZS UA:UAH UG:UGX UM:USD US:USD UY:UYU " +
  "UZ:UZS VA:EUR VC:XCD VE:VES VG:USD VI:USD VN:VND VU:VUV WF:XPF WS:WST YE:YER YT:EUR ZA:ZAR ZM:ZMW ZW:USD")
  .split(" ").map((p) => p.split(":")));

// code: [he, en, lat, lng, capital zone (only when it is not the first zone.tab entry / absent)]
const CAPITALS = {
  AD: ["אנדורה לה ולה", "Andorra la Vella", 42.51, 1.52], AE: ["אבו דאבי", "Abu Dhabi", 24.45, 54.38],
  AF: ["קאבול", "Kabul", 34.53, 69.17], AG: ["סנט ג'ונס", "Saint John's", 17.12, -61.85],
  AI: ["דה ואלי", "The Valley", 18.22, -63.06], AL: ["טירנה", "Tirana", 41.33, 19.82],
  AM: ["ירוואן", "Yerevan", 40.18, 44.51], AO: ["לואנדה", "Luanda", -8.84, 13.23],
  AQ: ["מקמרדו", "McMurdo Station", -77.85, 166.67, "Antarctica/McMurdo"], AR: ["בואנוס איירס", "Buenos Aires", -34.60, -58.38],
  AS: ["פאגו פאגו", "Pago Pago", -14.28, -170.70], AT: ["וינה", "Vienna", 48.21, 16.37],
  AU: ["קנברה", "Canberra", -35.28, 149.13, "Australia/Sydney"], AW: ["אורנייסטאד", "Oranjestad", 12.52, -70.03],
  AX: ["מריהאמן", "Mariehamn", 60.10, 19.94], AZ: ["באקו", "Baku", 40.41, 49.87],
  BA: ["סרייבו", "Sarajevo", 43.86, 18.41], BB: ["ברידג'טאון", "Bridgetown", 13.10, -59.62],
  BD: ["דאקה", "Dhaka", 23.81, 90.41], BE: ["בריסל", "Brussels", 50.85, 4.35],
  BF: ["ואגדוגו", "Ouagadougou", 12.37, -1.52], BG: ["סופיה", "Sofia", 42.70, 23.32],
  BH: ["מנאמה", "Manama", 26.23, 50.59], BI: ["גיטגה", "Gitega", -3.43, 29.93],
  BJ: ["פורטו נובו", "Porto-Novo", 6.50, 2.60], BL: ["גוסטביה", "Gustavia", 17.90, -62.85],
  BM: ["המילטון", "Hamilton", 32.29, -64.78], BN: ["בנדר סרי בגוואן", "Bandar Seri Begawan", 4.90, 114.94],
  BO: ["סוקרה", "Sucre", -19.04, -65.26], BQ: ["קרלנדייק", "Kralendijk", 12.15, -68.27],
  BR: ["ברזיליה", "Brasília", -15.79, -47.88, "America/Sao_Paulo"], BS: ["נסאו", "Nassau", 25.04, -77.35],
  BT: ["טימפו", "Thimphu", 27.47, 89.64], BV: ["האי בובה", "Bouvet Island", -54.42, 3.36, "Etc/UTC"],
  BW: ["גבורונה", "Gaborone", -24.65, 25.91], BY: ["מינסק", "Minsk", 53.90, 27.56],
  BZ: ["בלמופן", "Belmopan", 17.25, -88.76], CA: ["אוטווה", "Ottawa", 45.42, -75.70, "America/Toronto"],
  CC: ["ווסט איילנד", "West Island", -12.19, 96.83], CD: ["קינשאסה", "Kinshasa", -4.44, 15.27],
  CF: ["בנגי", "Bangui", 4.39, 18.56], CG: ["ברזוויל", "Brazzaville", -4.27, 15.28],
  CH: ["ברן", "Bern", 46.95, 7.45], CI: ["יאמוסוקרו", "Yamoussoukro", 6.83, -5.29],
  CK: ["אווארואה", "Avarua", -21.21, -159.78], CL: ["סנטיאגו", "Santiago", -33.45, -70.67],
  CM: ["יאונדה", "Yaoundé", 3.85, 11.50], CN: ["בייג'ינג", "Beijing", 39.90, 116.41],
  CO: ["בוגוטה", "Bogotá", 4.71, -74.07], CR: ["סן חוסה", "San José", 9.93, -84.08],
  CU: ["הוואנה", "Havana", 23.11, -82.37], CV: ["פראיה", "Praia", 14.93, -23.51],
  CW: ["וילמסטד", "Willemstad", 12.11, -68.93], CX: ["פליינג פיש קוב", "Flying Fish Cove", -10.42, 105.68],
  CY: ["ניקוסיה", "Nicosia", 35.19, 33.38], CZ: ["פראג", "Prague", 50.08, 14.44],
  DE: ["ברלין", "Berlin", 52.52, 13.40], DJ: ["ג'יבוטי", "Djibouti", 11.59, 43.15],
  DK: ["קופנהגן", "Copenhagen", 55.68, 12.57], DM: ["רוזו", "Roseau", 15.30, -61.39],
  DO: ["סנטו דומינגו", "Santo Domingo", 18.49, -69.93], DZ: ["אלג'יר", "Algiers", 36.75, 3.06],
  EC: ["קיטו", "Quito", -0.18, -78.47], EE: ["טאלין", "Tallinn", 59.44, 24.75],
  EG: ["קהיר", "Cairo", 30.04, 31.24], EH: ["אל-עיון", "Laayoune", 27.15, -13.20],
  ER: ["אסמרה", "Asmara", 15.32, 38.93], ES: ["מדריד", "Madrid", 40.42, -3.70],
  ET: ["אדיס אבבה", "Addis Ababa", 9.03, 38.74], FI: ["הלסינקי", "Helsinki", 60.17, 24.94],
  FJ: ["סובה", "Suva", -18.14, 178.44], FK: ["סטנלי", "Stanley", -51.70, -57.85],
  FM: ["פאליקיר", "Palikir", 6.92, 158.16, "Pacific/Pohnpei"], FO: ["טורסהאבן", "Tórshavn", 62.01, -6.77],
  FR: ["פריז", "Paris", 48.86, 2.35], GA: ["ליברוויל", "Libreville", 0.42, 9.47],
  GB: ["לונדון", "London", 51.51, -0.13], GD: ["סנט ג'ורג'ס", "St. George's", 12.06, -61.75],
  GE: ["טביליסי", "Tbilisi", 41.72, 44.79], GF: ["קאיין", "Cayenne", 4.92, -52.33],
  GG: ["סנט פיטר פורט", "St Peter Port", 49.46, -2.54], GH: ["אקרה", "Accra", 5.60, -0.19],
  GI: ["גיברלטר", "Gibraltar", 36.14, -5.35], GL: ["נואוק", "Nuuk", 64.18, -51.69],
  GM: ["בנג'ול", "Banjul", 13.45, -16.58], GN: ["קונאקרי", "Conakry", 9.64, -13.58],
  GP: ["באס-טר", "Basse-Terre", 16.00, -61.73], GQ: ["מלאבו", "Malabo", 3.75, 8.78],
  GR: ["אתונה", "Athens", 37.98, 23.73], GS: ["קינג אדוארד פוינט", "King Edward Point", -54.28, -36.49],
  GT: ["גואטמלה סיטי", "Guatemala City", 14.63, -90.51], GU: ["הגאטניה", "Hagåtña", 13.48, 144.75],
  GW: ["ביסאו", "Bissau", 11.86, -15.60], GY: ["ג'ורג'טאון", "Georgetown", 6.80, -58.16],
  HK: ["הונג קונג", "Hong Kong", 22.32, 114.17], HM: ["איי הרד ומקדונלד", "Heard Island", -53.08, 73.50, "Indian/Kerguelen"],
  HN: ["טגוסיגלפה", "Tegucigalpa", 14.07, -87.19], HR: ["זאגרב", "Zagreb", 45.81, 15.98],
  HT: ["פורט או פרינס", "Port-au-Prince", 18.59, -72.31], HU: ["בודפשט", "Budapest", 47.50, 19.04],
  ID: ["ג'קרטה", "Jakarta", -6.21, 106.85], IE: ["דבלין", "Dublin", 53.35, -6.26],
  IL: ["ירושלים", "Jerusalem", 31.77, 35.21], IM: ["דאגלס", "Douglas", 54.15, -4.48],
  IN: ["ניו דלהי", "New Delhi", 28.61, 77.21], IO: ["דייגו גרסיה", "Diego Garcia", -7.31, 72.41],
  IQ: ["בגדאד", "Baghdad", 33.31, 44.36], IR: ["טהרן", "Tehran", 35.69, 51.39],
  IS: ["רייקיאוויק", "Reykjavík", 64.15, -21.94], IT: ["רומא", "Rome", 41.90, 12.50],
  JE: ["סנט הלייר", "Saint Helier", 49.19, -2.11], JM: ["קינגסטון", "Kingston", 18.02, -76.80],
  JO: ["עמאן", "Amman", 31.95, 35.93], JP: ["טוקיו", "Tokyo", 35.68, 139.69],
  KE: ["ניירובי", "Nairobi", -1.29, 36.82], KG: ["בישקק", "Bishkek", 42.87, 74.59],
  KH: ["פנום פן", "Phnom Penh", 11.56, 104.93], KI: ["טאראווה", "South Tarawa", 1.33, 172.98, "Pacific/Tarawa"],
  KM: ["מורוני", "Moroni", -11.70, 43.26], KN: ["בסטר", "Basseterre", 17.30, -62.72],
  KP: ["פיונגיאנג", "Pyongyang", 39.04, 125.76], KR: ["סיאול", "Seoul", 37.57, 126.98],
  KW: ["כווית סיטי", "Kuwait City", 29.38, 47.99], KY: ["ג'ורג' טאון", "George Town", 19.29, -81.38],
  KZ: ["אסטנה", "Astana", 51.17, 71.45, "Asia/Almaty"], LA: ["ויינטיאן", "Vientiane", 17.98, 102.63],
  LB: ["ביירות", "Beirut", 33.89, 35.50], LC: ["קסטריס", "Castries", 14.01, -60.99],
  LI: ["ואדוץ", "Vaduz", 47.14, 9.52], LK: ["קולומבו", "Colombo", 6.93, 79.86],
  LR: ["מונרוביה", "Monrovia", 6.30, -10.80], LS: ["מאסרו", "Maseru", -29.31, 27.48],
  LT: ["וילנה", "Vilnius", 54.69, 25.28], LU: ["לוקסמבורג", "Luxembourg", 49.61, 6.13],
  LV: ["ריגה", "Riga", 56.95, 24.11], LY: ["טריפולי", "Tripoli", 32.89, 13.19],
  MA: ["רבאט", "Rabat", 34.02, -6.83], MC: ["מונקו", "Monaco", 43.73, 7.42],
  MD: ["קישינב", "Chișinău", 47.01, 28.86], ME: ["פודגוריצה", "Podgorica", 42.44, 19.26],
  MF: ["מריגו", "Marigot", 18.07, -63.08], MG: ["אנטננריבו", "Antananarivo", -18.88, 47.51],
  MH: ["מג'ורו", "Majuro", 7.09, 171.38, "Pacific/Majuro"], MK: ["סקופיה", "Skopje", 42.00, 21.43],
  ML: ["במאקו", "Bamako", 12.64, -8.00], MM: ["נייפידו", "Naypyidaw", 19.76, 96.08],
  MN: ["אולן בטור", "Ulaanbaatar", 47.89, 106.91], MO: ["מקאו", "Macau", 22.20, 113.54],
  MP: ["סאיפן", "Saipan", 15.18, 145.75], MQ: ["פור-דה-פרנס", "Fort-de-France", 14.62, -61.06],
  MR: ["נואקשוט", "Nouakchott", 18.08, -15.98], MS: ["בריידס", "Brades", 16.79, -62.21],
  MT: ["ולטה", "Valletta", 35.90, 14.51], MU: ["פורט לואי", "Port Louis", -20.16, 57.50],
  MV: ["מאלה", "Malé", 4.18, 73.51], MW: ["לילונגווה", "Lilongwe", -13.96, 33.79],
  MX: ["מקסיקו סיטי", "Mexico City", 19.43, -99.13, "America/Mexico_City"], MY: ["קואלה לומפור", "Kuala Lumpur", 3.14, 101.69],
  MZ: ["מאפוטו", "Maputo", -25.97, 32.57], NA: ["וינדהוק", "Windhoek", -22.56, 17.08],
  NC: ["נומאה", "Nouméa", -22.28, 166.46], NE: ["ניאמיי", "Niamey", 13.51, 2.11],
  NF: ["קינגסטון", "Kingston", -29.05, 167.96], NG: ["אבוג'ה", "Abuja", 9.08, 7.40],
  NI: ["מנגואה", "Managua", 12.11, -86.24], NL: ["אמסטרדם", "Amsterdam", 52.37, 4.90],
  NO: ["אוסלו", "Oslo", 59.91, 10.75], NP: ["קטמנדו", "Kathmandu", 27.72, 85.32],
  NR: ["יארן", "Yaren", -0.55, 166.92], NU: ["אלופי", "Alofi", -19.06, -169.92],
  NZ: ["ולינגטון", "Wellington", -41.29, 174.78], OM: ["מוסקט", "Muscat", 23.59, 58.41],
  PA: ["פנמה סיטי", "Panama City", 8.98, -79.52], PE: ["לימה", "Lima", -12.05, -77.04],
  PF: ["פאפאטה", "Papeete", -17.54, -149.57], PG: ["פורט מורסבי", "Port Moresby", -9.44, 147.18],
  PH: ["מנילה", "Manila", 14.60, 120.98], PK: ["איסלאמבאד", "Islamabad", 33.68, 73.05],
  PL: ["ורשה", "Warsaw", 52.23, 21.01], PM: ["סן-פייר", "Saint-Pierre", 46.78, -56.18],
  PN: ["אדמסטאון", "Adamstown", -25.07, -130.10], PR: ["סן חואן", "San Juan", 18.47, -66.11],
  PS: ["רמאללה", "Ramallah", 31.90, 35.20, "Asia/Hebron"], PT: ["ליסבון", "Lisbon", 38.72, -9.14],
  PW: ["נגרולמוד", "Ngerulmud", 7.50, 134.62], PY: ["אסונסיון", "Asunción", -25.26, -57.58],
  QA: ["דוחה", "Doha", 25.29, 51.53], RE: ["סן-דני", "Saint-Denis", -20.88, 55.45],
  RO: ["בוקרשט", "Bucharest", 44.43, 26.10], RS: ["בלגרד", "Belgrade", 44.79, 20.45],
  RU: ["מוסקבה", "Moscow", 55.76, 37.62, "Europe/Moscow"], RW: ["קיגלי", "Kigali", -1.94, 30.06],
  SA: ["ריאד", "Riyadh", 24.71, 46.68], SB: ["הוניארה", "Honiara", -9.43, 159.95],
  SC: ["ויקטוריה", "Victoria", -4.62, 55.45], SD: ["חרטום", "Khartoum", 15.50, 32.56],
  SE: ["שטוקהולם", "Stockholm", 59.33, 18.07], SG: ["סינגפור", "Singapore", 1.29, 103.85],
  SH: ["ג'יימסטאון", "Jamestown", -15.92, -5.72], SI: ["ליובליאנה", "Ljubljana", 46.06, 14.51],
  SJ: ["לונגיירביין", "Longyearbyen", 78.22, 15.65], SK: ["ברטיסלאבה", "Bratislava", 48.15, 17.11],
  SL: ["פריטאון", "Freetown", 8.48, -13.23], SM: ["סן מרינו", "San Marino", 43.94, 12.45],
  SN: ["דקר", "Dakar", 14.72, -17.47], SO: ["מוגדישו", "Mogadishu", 2.05, 45.32],
  SR: ["פרמריבו", "Paramaribo", 5.85, -55.20], SS: ["ג'ובה", "Juba", 4.85, 31.58],
  ST: ["סאו טומה", "São Tomé", 0.34, 6.73], SV: ["סן סלבדור", "San Salvador", 13.69, -89.22],
  SX: ["פיליפסבורג", "Philipsburg", 18.03, -63.05], SY: ["דמשק", "Damascus", 33.51, 36.29],
  SZ: ["מבבנה", "Mbabane", -26.31, 31.14], TC: ["קוקברן טאון", "Cockburn Town", 21.46, -71.14],
  TD: ["נג'מנה", "N'Djamena", 12.13, 15.06], TF: ["פור-או-פרנסה", "Port-aux-Français", -49.35, 70.22],
  TG: ["לומה", "Lomé", 6.13, 1.22], TH: ["בנגקוק", "Bangkok", 13.76, 100.50],
  TJ: ["דושנבה", "Dushanbe", 38.56, 68.79], TK: ["פקאופו", "Fakaofo", -9.38, -171.22],
  TL: ["דילי", "Dili", -8.56, 125.56], TM: ["אשגבט", "Ashgabat", 37.96, 58.33],
  TN: ["תוניס", "Tunis", 36.81, 10.18], TO: ["נוקואלופה", "Nukuʻalofa", -21.14, -175.20],
  TR: ["אנקרה", "Ankara", 39.93, 32.86], TT: ["פורט אוף ספיין", "Port of Spain", 10.66, -61.51],
  TV: ["פונאפוטי", "Funafuti", -8.52, 179.20], TW: ["טאיפיי", "Taipei", 25.03, 121.57],
  TZ: ["דודומה", "Dodoma", -6.16, 35.75], UA: ["קייב", "Kyiv", 50.45, 30.52, "Europe/Kyiv"],
  UG: ["קמפלה", "Kampala", 0.35, 32.58], UM: ["האי וייק", "Wake Island", 19.28, 166.65, "Pacific/Wake"],
  US: ["וושינגטון", "Washington, D.C.", 38.91, -77.04, "America/New_York"], UY: ["מונטווידאו", "Montevideo", -34.90, -56.16],
  UZ: ["טשקנט", "Tashkent", 41.30, 69.24, "Asia/Tashkent"], VA: ["הוותיקן", "Vatican City", 41.90, 12.45],
  VC: ["קינגסטאון", "Kingstown", 13.16, -61.23], VE: ["קראקס", "Caracas", 10.48, -66.90],
  VG: ["רוד טאון", "Road Town", 18.43, -64.62], VI: ["שרלוט אמלי", "Charlotte Amalie", 18.34, -64.93],
  VN: ["האנוי", "Hanoi", 21.03, 105.85], VU: ["פורט וילה", "Port Vila", -17.73, 168.32],
  WF: ["מאטה-אוטו", "Mata-Utu", -13.28, -176.17], WS: ["אפיה", "Apia", -13.83, -171.76],
  YE: ["צנעא", "Sana'a", 15.37, 44.19], YT: ["מאמודזו", "Mamoudzou", -12.78, 45.23],
  ZA: ["פרטוריה", "Pretoria", -25.75, 28.19], ZM: ["לוסקה", "Lusaka", -15.39, 28.32],
  ZW: ["הרארה", "Harare", -17.83, 31.05],
};

// Hebrew country names in common Israeli usage where CLDR differs (CLDR is used for everything else)
const HE_NAME = {
  KR: "דרום קוריאה", KP: "צפון קוריאה", AE: "איחוד האמירויות", CD: "הרפובליקה הדמוקרטית של קונגו", CG: "קונגו",
  HK: "הונג קונג", MO: "מקאו", MM: "מיאנמר", TL: "מזרח טימור", BS: "בהאמה", CZ: "צ'כיה", CL: "צ'ילה",
  TD: "צ'אד", AZ: "אזרבייג'ן", DZ: "אלג'יריה", DJ: "ג'יבוטי", FJ: "פיג'י", JM: "ג'מייקה", JE: "ג'רזי",
  TJ: "טג'יקיסטן", NE: "ניז'ר", BA: "בוסניה והרצגובינה", VN: "וייטנאם", US: "ארצות הברית", GB: "בריטניה",
  TW: "טייוואן", MV: "האיים המלדיביים", CV: "כף ורדה", VA: "הוותיקן",
  GS: "ג'ורג'יה הדרומית ואיי סנדוויץ' הדרומיים",
};
const EN_NAME = { HK: "Hong Kong", MO: "Macao", MM: "Myanmar", PS: "Palestinian Territories" };

// Short Hebrew currency names (as shown in step 2: "¥ ין · JPY"); CLDR names for the rest
const CUR_HE = {
  ILS: "שקל", USD: "דולר", EUR: "יורו", JPY: "ין", KRW: "וון", THB: "באט", VND: "דונג", GBP: "לירה שטרלינג",
  CHF: "פרנק שווייצרי", CZK: "קורונה צ'כית", HUF: "פורינט", GEL: "לארי", INR: "רופי", MXN: "פסו מקסיקני",
  AED: "דירהם", TRY: "לירה טורקית", CAD: "דולר קנדי", AUD: "דולר אוסטרלי", NZD: "דולר ניו זילנדי", CNY: "יואן",
  PLN: "זלוטי", SEK: "כתר שוודי", NOK: "כתר נורווגי", DKK: "כתר דני", ISK: "כתר איסלנדי", RON: "ליי רומני",
  BGN: "לב בולגרי", EGP: "לירה מצרית", JOD: "דינר ירדני", MAD: "דירהם מרוקאי", SGD: "דולר סינגפורי",
  HKD: "דולר הונג קונגי", MYR: "רינגיט", IDR: "רופיה", PHP: "פסו פיליפיני", KHR: "ריאל קמבודי", LAK: "קיפ",
  LKR: "רופי סרי לנקי", NPR: "רופי נפאלי", ZAR: "ראנד", BRL: "ריאל ברזילאי", ARS: "פסו ארגנטינאי", PEN: "סול",
  CLP: "פסו צ'יליאני", COP: "פסו קולומביאני", RSD: "דינר סרבי", ALL: "לק", MKD: "דינר מקדוני", BAM: "מארק בוסני",
  TWD: "דולר טייוואני", KES: "שילינג קנייתי", TZS: "שילינג טנזני", MVR: "רופיה מלדיבית", AMD: "דראם",
  AZN: "מנאט", UAH: "הריבניה", RUB: "רובל", CRC: "קולון", DOP: "פסו דומיניקני", CUP: "פסו קובני", GTQ: "קצל",
  MMK: "קיאט", MNT: "טוגרוג", UZS: "סום אוזבקי", KZT: "טנגה", BDT: "טאקה", PKR: "רופי פקיסטני", XCG: "גילדר קריבי",
  ZWG: "זהב זימבבואה",
};
const CUR_EN = { XCG: "Caribbean Guilder", ZWG: "Zimbabwe Gold" };
const COMMON = new Set(("ILS USD EUR GBP CHF JPY THB VND KRW CZK HUF GEL INR MXN AED TRY CAD AUD NZD CNY PLN SEK NOK DKK " +
  "ISK RON BGN EGP JOD MAD SGD HKD MYR IDR PHP KHR LAK LKR NPR ZAR BRL ARS PEN TWD").split(" "));
const POPULAR = ["TH", "GR", "US", "IT", "ES", "FR", "GB", "DE", "PT", "CY", "GE", "VN", "JP", "IN", "NL", "CZ", "HU", "AT", "MX", "AE"];

// ---------------------------------------------------------------------------------------------------
const zones = {};
for (const line of fs.readFileSync(ZONE_TAB, "utf8").split("\n")) {
  if (!line || line.startsWith("#")) continue;
  const [cc, , tz] = line.split("\t");
  (zones[cc] = zones[cc] || []).push(tz);
}
const codes = Object.keys(CAPITALS).sort();
const heR = new Intl.DisplayNames(["he"], { type: "region" }), enR = new Intl.DisplayNames(["en"], { type: "region" });
const heC = new Intl.DisplayNames(["he"], { type: "currency" }), enC = new Intl.DisplayNames(["en"], { type: "currency" });
const flag = (c) => String.fromCodePoint(0x1F1E6 + c.charCodeAt(0) - 65, 0x1F1E6 + c.charCodeAt(1) - 65);
const validTz = (z) => { try { new Intl.DateTimeFormat("en", { timeZone: z }); return true; } catch { return false; } };

const errors = [];
const countries = codes.map((code) => {
  const [he, en, lat, lng, capTz] = CAPITALS[code];
  const list = zones[code] || [];
  const tz = capTz ? [capTz, ...list.filter((z) => z !== capTz)] : list.slice();
  if (!tz.length) errors.push(`${code}: no time zone`);
  for (const z of tz) if (!validTz(z)) errors.push(`${code}: invalid tz ${z}`);
  const currency = PRIMARY[code];
  if (!currency) errors.push(`${code}: no currency`);
  return {
    code, he: (HE_NAME[code] || heR.of(code)).replace(/\u05F3/g, "'").replace(/\u05F4/g, '"'), en: EN_NAME[code] || enR.of(code), flag: flag(code), currency, tz,
    capital: { he, en, lat, lng }, popular: POPULAR.includes(code),
  };
});
const allCodes = new Set(Object.keys(zones).concat(["BV", "HM"]));
for (const c of allCodes) if (!CAPITALS[c]) errors.push(`${c}: missing from CAPITALS`);

const curCodes = [...new Set(countries.map((c) => c.currency).concat(["ILS", "USD", "EUR"]))].sort();
const symbol = (c) => {
  try {
    return new Intl.NumberFormat("en", { style: "currency", currency: c, currencyDisplay: "narrowSymbol" })
      .formatToParts(1).find((p) => p.type === "currency").value;
  } catch { return c; }
};
const currencies = curCodes.map((code) => {
  let he = CUR_HE[code] || heC.of(code);
  if (!he || he === code) he = CUR_EN[code] || enC.of(code);
  he = he.replace(/\u05F3/g, "'").replace(/\u05F4/g, '"');
  return { code, symbol: symbol(code), he, en: CUR_EN[code] || enC.of(code), common: COMMON.has(code) };
});

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
fs.writeFileSync(path.join(ROOT, "app/countries.json"), JSON.stringify(countries) + "\n");
fs.writeFileSync(path.join(ROOT, "app/currencies.json"), JSON.stringify(currencies) + "\n");
console.log(`countries.json: ${countries.length} · currencies.json: ${currencies.length}`);
