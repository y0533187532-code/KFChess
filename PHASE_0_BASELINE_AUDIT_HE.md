# שלב 0 — בדיקת בסיס ושער החלטה לממשק המהלכים

## סטטוס

- תאריך בדיקה: 20 ביולי 2026.
- סביבת בדיקה: Windows, Python 3.11.1.
- פקודת בדיקה: `py -3.11 -m pytest -q`.
- תוצאה: **518 בדיקות עברו**.
- כיסוי כולל: **90%**.
- לא בוצע שינוי בקוד המשחק הקיים במסגרת הבדיקה.

## ממצאים מאומתים מהמאגר

1. `Piece` כבר מכיל `piece_id` מספרי.
2. `PieceRegistry` מקצה מזהים ייחודיים בתוך לוח משחק אחד ומונע כפילויות.
3. הזהות נשמרת כאשר כלי זז וכאשר חייל מקודם לכלי אחר.
4. `PieceSnapshot`, ‏`MoveEventSnapshot` ו־`MotionSnapshot` כבר כוללים `piece_id`.
5. `GameSnapshot` מספק ללקוח תצוגה מלאה ובלתי משתנה של מצב המשחק.
6. `GameEngine.request_move` מקבל כיום קואורדינטות מקור ויעד.
7. `Controller` הקיים מתרגם לחיצות עכבר לקואורדינטות וקורא ישירות ל־`GameEngine`; הוא מתאים למצב offline ולא לחוזה רשת סמכותי.
8. ניתן לשמור את `Piece`, ‏`Board`, ‏`GameEngine` וה־Controller המקומי ללא שינוי, ולהוסיף מסביבם `NetworkController`, ‏`GameService` ו־`NetworkGameAdapter` חדשים.

## שער החלטה

לפני קיבוע schema של `move_request`, נדרשת תשובת המרצה לשאלה הבאה:

> במימוש הקיים, לכל כלי כבר יש `piece_id` מספרי יציב המופיע ב־`GameSnapshot`, אבל הממשק הציבורי של `GameEngine` מקבל קואורדינטות באמצעות `request_move(from_row, from_col, to_row, to_col)`. האם מקובל להשאיר את מנוע המשחק והיישום המקומי ללא שינוי, ולהוסיף בשכבת השרת Adapter שמקבל הודעת רשת הכוללת `game_id`, ‏`piece_id`, ‏`expected_from` ו־`target`, מאתר את הכלי ב־snapshot, מאמת בעלות/מצב/מיקום ומתרגם את הבקשה לקריאה הקיימת לפי קואורדינטות? או שנדרש לשנות את ה־API של `GameEngine` כך שיקבל `piece_id` ישירות? ההעדפה הארכיטקטונית שלנו היא Adapter, כדי לשמור על backward compatibility, הפרדת אחריות ואי־תלות של מנוע המשחק ברשת.

## עבודה שניתן להמשיך לפני התשובה

- להגדיר מעטפת הודעה אחידה עם `protocol_version`, ‏`type`, ‏`request_id`, ‏`timestamp_ms` ו־`payload`.
- להגדיר קודי שגיאה ולוקליזציה בלי לקבע עדיין את payload הסופי של `move_request`.
- להגדיר `GameSession` עם `asyncio.Queue` ו־worker יחיד.
- לתכנן Authentication token ו־Game token כשני tokens נפרדים הנשמרים ב־SQLite כ־hash.
- להוסיף schemas לטבלאות `auth_sessions` ו־`game_session_tokens` בתכנון מסד הנתונים.
- להוסיף בדיקות חוזה שאינן תלויות בהחלטת המהלך: message envelope, הודעה כפולה, token שגוי ו־sequence gaps.

## פעולות חסומות עד תשובת המרצה

- קיבוע payload סופי של `move_request` ו־`jump_request`.
- מימוש `NetworkGameAdapter`.
- שינוי אפשרי של הממשק הציבורי של `GameEngine`.
- חיבור `NetworkController` לפעולות הכלים.

## כלל שמירת המצב הקיים

כל עבודה חדשה תתווסף מחוץ ללוגיקת המשחק הקיימת ככל האפשר. בדיקות הבסיס של 518 המקרים ישמשו שער regression: לאחר כל אבן דרך כל הבדיקות הקיימות חייבות להמשיך לעבור, בנוסף לבדיקות השרת החדשות.
