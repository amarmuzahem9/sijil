# التجربة اليدوية — الفيزة 016: النشر والنسخ الاحتياطي

كل الخطوات **على جهازك فقط**، ببيانات تجريبية. لا تشغّل نشراً ولا `go-live` ولا استرجاعاً على السيرفر الحقيقي
أثناء هذه التجربة. قسم «بعد الدمج على السيرفر» في الآخر هو ما تفحصه هناك لاحقاً.

كلمة سر مفتاح التجربة المحلي هي التي طبعها `scripts/backup.sh init-key --dev` في الدفعة الثانية.

## قبل البدء

```powershell
docker compose up -d --build --wait
docker compose ps backup        # Up (healthy)
```

## أ) التجارب التلقائية الثلاث

```powershell
bash scripts/backup-e2e.sh      # المتوقع في النهاية: 22 passed, 0 failed
bash scripts/deploy-e2e.sh      # المتوقع: 25 passed, 0 failed
bash scripts/e2e.sh             # Playwright كاملاً
```

كلها تبني نسخاً مؤقتة وتمسحها، ولا تلمس بياناتك. بعدها:
```powershell
docker volume ls | findstr "bk-e2e dp-e2e drill"     # لا شيء
```

## ب) النسخة الليلية والنسخة اليدوية

1. `bash scripts/backup.sh list` ← النسخ بتوقيت بغداد، مع أعداد الطلبات والصور والحجم.
2. `bash scripts/backup.sh now` ← «تم النسخ…» بحجم صغير (الصور لا تتكرر).
3. للنسخة الليلية: اجعل `BACKUP_NIGHTLY_AT` في `.env` بعد دقيقتين بتوقيت بغداد، ثم
   `docker compose up -d backup`. بعد دقيقتين تظهر نسخة «ليلية» (إن لم تكن هناك نسخة ليلية اليوم). **أرجعه
   إلى `03:00`.**
4. لا مفتاح مكشوف: `docker compose exec backup sh -c "grep -rl AGE-SECRET-KEY /data/backups || echo OK"` ← `OK`.
5. الـ api لا يرى النسخ: `docker compose exec api sh -c "ls -A /data/backups | wc -l"` ← `0`.

## ج) صفحة «النسخ الاحتياطي» والتحذيرات

1. ادخل بالأدمن الرئيسي، افتح «النسخ الاحتياطي»: آخر نسخة، النسخ المحفوظة، الهارد، تجربة الاسترجاع، السيرفر،
   آخر عمليات النشر.
2. «نسخة يدوية الآن» ← «جارٍ النسخ…» ثم نسخة «يدوية · ناجحة» خلال نصف دقيقة. ضغطة ثانية أثناءها لا تبدأ نسخة ثانية.
3. `docker compose stop backup`، وبعد 10 دقائق حدّث الصفحة ← «خدمة النسخ متوقفة»، والزر يرفض بنفس الرسالة.
   `docker compose start backup` ← يختفي التحذير خلال 15 ثانية.
4. الرئيسية `/admin` ← التحذيرات بالأحمر مع رابط «صفحة النسخ الاحتياطي».
5. أدمن مضاف (حتى بكل الصلاحيات): لا يرى «النسخ الاحتياطي» في القائمة، و`/admin/backup` يرجعه للرئيسية، ولا
   يرى أي تحذير نسخ.
6. `bash scripts/backup.sh status` ← آخر نسخة، آخر نسخة على الهارد، آخر تجربة، والتحذيرات.

## د) تجربة الاسترجاع

1. `bash scripts/backup.sh drill` ← يطلب كلمة السر، ثم «تجربة الاسترجاع نجحت» مع الأعداد.
2. `docker volume ls | findstr drill` ← لا شيء بعد انتهائها.
3. الصفحة ← «تجربة الاسترجاع: نجحت» بتاريخ اليوم.

## هـ) الاسترجاع الفعلي (على جهازك)

1. `bash scripts/backup.sh now`، ثم غيّر شيئاً من التطبيق (مسودة جديدة مثلاً).
2. `bash scripts/restore.sh` ← يعرض النسخة والتحذير ويطلب تاريخها.
   - اكتب تاريخاً خاطئاً ← «التاريخ غير مطابق، لم يتغيّر شيء».
   - شغّله مرة ثانية واكتب التاريخ الصحيح، ثم كلمة السر ← يتوقف التطبيق دقائق ثم يرجع.
3. تغييرك اختفى، و`bash scripts/backup.sh list` فيه نسخة «pre_restore».
4. `docker compose exec db psql -U sijil -c "select action, entity_id, after from audit_log where action='backup.restore'"`
   ← سطر واحد بلا بيانات شخصية.
5. الصفحة ما زالت تتحدّث بعد الاسترجاع (النسخ الجديدة تظهر).

## و) الهارد الخارجي (مجلد مؤقت مكان الهارد)

على Windows لا يوجد `mountpoint`، فالمجلد المؤقت يُقبل فقط مع متغيرات التجربة:

```powershell
mkdir C:\tmp\sijil-drive
$env:BACKUP_EXTERNAL_DIR="C:/tmp/sijil-drive"
bash scripts/backup.sh weekly                      # يرفض: ليس هارداً مركّباً، ولا يكتب شيئاً
$env:SIJIL_E2E="1"; $env:SIJIL_E2E_NO_MOUNTPOINT="1"
bash scripts/backup.sh weekly                      # يرفض: الهارد بلا علامة
bash scripts/backup.sh init-external
bash scripts/backup.sh weekly                      # نسخ + تحقق + تجربة استرجاع من الهارد + «يمكن فصل الهارد الآن»
bash scripts/backup.sh weekly                      # «موجودة على الهارد من قبل»، لا يتغيّر أي ملف
```

الصفحة ← «الهارد الخارجي» بتاريخ اليوم، وتحذير «النسخة الأسبوعية متأخرة» اختفى. للتنظيف:

```powershell
Remove-Item -Recurse C:\tmp\sijil-drive
Remove-Item Env:SIJIL_E2E, Env:SIJIL_E2E_NO_MOUNTPOINT, Env:BACKUP_EXTERNAL_DIR
```

## ز) النشر و`go-live`

`deploy-e2e.sh` (الخطوة أ) جرّب كل حالات النشر على مشروع مؤقت. على جهازك فقط يمكن أيضاً:

```powershell
docker compose exec api python -m app.cli go-live --check   # يذكر إن بقي حساب تجريبي فعّال
```

لا تشغّل `go-live` بدون `--check` إلا إن أردت إيقاف الحساب التجريبي على جهازك.

## ح) الأدلة

- [deploy/server.md](../../deploy/server.md): التثبيت، التحديث، الانتقال إلى production (الخطوة 9)، إذا فشل النشر.
- [deploy/backup.md](../../deploy/backup.md): ماذا يُحفظ وأين وكم، كلمة السر، الهارد أسبوعياً، الاسترجاع، سيرفر جديد،
  فتح نسخة يدوياً، التحذيرات.

اقرأهما مرة كاملة قبل الدمج: هما ما ستتبعه على السيرفر.

---

## بعد الدمج على السيرفر (لا يُجرَّب الآن)

حين تقرر النشر على السيرفر، بالترتيب، من [deploy/backup.md](../../deploy/backup.md) و[deploy/server.md](../../deploy/server.md):

1. مجلد النسخ (backup.md الخطوة 1) والمفتاح (الخطوة 2). **اكتب كلمة السر على ورق.**
2. `.env`: `BACKUP_DIR`، `BACKUP_AGE_RECIPIENT`، `BACKUP_EXTERNAL_DIR`، ثم `bash scripts/deploy.sh` (ما زال staging).
3. **7 ليالٍ متتالية** (SC-001): كل صباح «النسخ الاحتياطي» ← نسخة ليلية ناجحة جديدة، بلا تحذير «فشل».
4. أول نسخة أسبوعية على الهارد (backup.md الخطوة 4) مع تجربة الاسترجاع منه.
5. **وقت الاسترجاع** (SC-003): `bash scripts/backup.sh drill` وسجّل كم أخذ؛ الهدف أقل من 30 دقيقة.
6. قبل التجربة الميدانية فقط: server.md الخطوة 9 (`go-live` ثم `APP_ENV=production`).
