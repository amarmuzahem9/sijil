# الترقية من 015 إلى main (016 حتى 019) على سيرفر عليه بيانات حقيقية

دليل لمرة واحدة لمن يشغّل السيرفر. السيرفر يعمل بالفيزة 015 (`af9155f`، منشورة بـ `scripts/deploy-staging.sh`)
وعليه بيانات حقيقية، ولا توجد عليه أي نسخة احتياطية لأن 016 لم تُنشر بعد. القواعد في `docs/system.md` §15،
والأدلة العامة في [server.md](server.md) و[backup.md](backup.md).

جُرّب هذا الدليل كاملاً على جهاز محلي ببيانات تجريبية (27 تشرين الثاني 2026): تثبيت 015، ثم الترقية، ومنها
فشل حقيقي برمز 8 والرجوع إلى 015 بالقاعدة المسترجعة، ثم ترقية ناجحة، ونسخة، وتجربة استرجاع، و`go-live`،
وتصدير لا يدخل النسخ.

## قبل البدء

- **ممنوع طول العملية:** `down -v`، حذف مجلدات أو volumes، `alembic downgrade`، تغيير أي كلمة سر أو مفتاح
  موجود في `.env`.
- **لماذا يختلف هذا النشر عن غيره:** `scripts/deploy.sh` يأخذ نسخة «قبل النشر» من خدمة `backup` إذا وجد
  التطبيق شغّالاً، ويرفض بدونها. خدمة `backup` غير موجودة في 015. لذلك، في هذا النشر فقط: نوقف `api`،
  ونأخذ نسخة `pg_dump` يدوية مع الصور، ثم نشغّل `deploy.sh` فيعامله كأول تثبيت. النسخة اليدوية هي نسخة
  «قبل النشر» لهذه المرة.
- **الكود المنشور:** main بعد 576fa6f، وفوقه أدلة فقط بلا كود. `git diff --stat 576fa6f HEAD` يجب ألا يُظهر
  غير ملفات داخل `deploy/` تنتهي بـ `.md` (هذا الملف وسطر الرابط في `server.md`).
- الخطوات 3أ و4 و5 و7 تُنفَّذ **قبل يوم الصيانة** والتطبيق شغّال، ولا تغيّر شيئاً على المستخدمين. الخطوات
  3ب و8 و9 و10 في وقت الصيانة.

---

## 1) قراءة فقط

```bash
cd /opt/sijil
git branch --show-current; git log -1 --oneline; git status --short
git config --get remote.origin.url | sed -E 's#//[^@]*@#//***@#'
ls docker-compose*.yml
docker ps --format '{{.Names}}\t{{.Status}}'
docker exec sijil-api alembic current
grep -E '^(APP_ENV|NPM_NETWORK|POSTGRES_USER|POSTGRES_DB)=' .env
docker network inspect "$(grep -E '^NPM_NETWORK=' .env | cut -d= -f2 | tr -d '\r')" --format '{{.Name}}'
df -h / /var/lib/docker; docker system df
docker exec sijil-db psql -U sijil -d sijil -Atc "select pg_size_pretty(pg_database_size('sijil'))"
docker run --rm -v sijil_uploads:/u:ro alpine du -sh /u
docker run --rm -v sijil_uploads:/u:ro alpine sh -c 'find /u -type f | wc -l'
docker exec sijil-db psql -U sijil -d sijil -Atc "select (select count(*) from requests),(select count(*) from legacy_subscribers),(select count(*) from sas_subscribers),(select count(*) from users)"
docker exec sijil-db psql -U sijil -d sijil -c "select phone, is_active from users where phone in ('07700000001','07700000002','07700000003')"
git reflog -5 --date=iso
docker inspect sijil-api --format '{{.Image}} {{.Created}}'
docker images --format '{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedSince}}\t{{.Size}}' | grep -i sijil
grep -E '^(BACKUP_|EXPORTS_DIR)' .env
sudo ls -la /var/backups/sijil 2>&1 | head
```

| المتوقع | إذا اختلف |
|---|---|
| الفرع `main`، `git status` فارغ | توقف |
| الـ commit `af9155f`، **أو** commit أحدث سُحب بلا نشر (مثل `2816f63`) | انظر «كود أحدث على القرص» تحت |
| حاوية `sijil-api` أُنشئت بعد سحب `af9155f` بدقيقة أو أقل (قارن `reflog` بـ `Created`) | توقف: الصورة الشغّالة ليست 015 الأخير |
| حاويات `sijil-web` و`sijil-api` و`sijil-db` و`sijil-ocr` شغّالة، **بلا** `sijil-backup` | توقف |
| `alembic current` = `0018 (head)` (أسطر `INFO` قبله طبيعية) | توقف |
| `APP_ENV=staging`، شبكة NPM موجودة | توقف |
| `POSTGRES_USER` و`POSTGRES_DB` = `sijil` | بدّل `-U sijil -d sijil` في كل الأوامر بالقيمة الصحيحة |
| `grep BACKUP_` لا يطبع شيئاً | أرسل الأسطر قبل الخطوة 5: لا تضف مكرراً |
| `/var/backups/sijil` غير موجود، **أو** موجود وفارغ (10001، 700) | إن كان فيه `key.age` أو أي ملف: توقف قبل الخطوة 7 |
| المساحة تكفي (انظر «المساحة» تحت) | توقف، ولا تحذف شيئاً قبل قراءة القائمة الآمنة |

**احفظ** الأعداد (الطلبات|القدامى|SAS|المستخدمين) وعدد ملفات الصور: تُقارن بها بعد كل خطوة.

### كود أحدث على القرص

إن كان أحدٌ قد سحب commit بعد `af9155f` بلا نشر (`git reflog` يُظهر `pull` بلا تغيّر في الحاويات)، فالتطبيق
الشغّال ما زال 015، لكن:

- `docker-compose.staging.yml` غير موجود على القرص. **حتى الخطوة 8 لا تستعمل `docker compose` لإعادة تشغيل
  015**؛ عند الحاجة `docker restart sijil-api` فقط. بدون `-f` يحمّل compose وضع التطوير ويحاول فتح 80/443
  التي يمسكها NPM. ولا تشغّل `deploy-staging.sh` (صار `deploy.sh`).
- الرجوع (الخطوة 9) لا يتغيّر: `git checkout af9155f` يعيد `docker-compose.staging.yml`، وهو نفس الكود الشغّال
  إن تحقق شرط وقت إنشاء `sijil-api` في الجدول.
- `git pull` في الخطوة 4 يتقدّم من الـ commit الموجود (fast-forward).

### المساحة

بيانات سِجلّ صغيرة عادةً؛ المساحة تذهب للصور (images):

| | تقريباً |
|---|---|
| النسخة اليدوية والنسخ المشفّرة وتجربة الاسترجاع | 3 × (القاعدة + الصور) |
| صور `api` و`backup` و`web` الجديدة | 1–2 GB |
| `ocr` إن أُعيد بناؤه من الصفر (build cache ممسوح) | 4.5 GB إضافية |
| النسخ تحذّر تحت 4 GB فارغة وترفض تحت 2 GB | — |

يكفي: **المجموع أعلاه + 6 GB هامش**. `docker system df` يُظهر حجم Build Cache؛ إن كان صفراً فاحسب `ocr`.
القرص قد يكون مشتركاً مع مشاريع أخرى، وامتلاؤه يوقف قواعد بياناتها أيضاً.

**ممنوع لتوفير المساحة:** `docker system prune`، `docker volume prune` (يحذف volumes مشاريع متوقفة)،
`docker image prune -a`، `docker builder prune` (يمسح cache الـ `ocr` نفسه)، وحذف سجلات حاويات مشاريع أخرى.
**آمن ولا يلمس أي مشروع:** `sudo apt-get clean`، `sudo journalctl --vacuum-size=200M`،
`docker image prune --filter label=com.docker.compose.project=sijil` (صور سِجلّ القديمة بلا اسم فقط). وإن كان
في الـ VG مساحة غير مستعملة (`sudo vgs`، عمود `VFree`): `sudo lvextend -r -l +100%FREE /dev/<vg>/<lv>`.

## 2) `staging` وليس `production`

- يبقى `APP_ENV=staging` في هذا النشر. الأسرار والـ Cookie والـ OTP تعمل بنفس الطريقة في الوضعين. الفرق:
  في staging يشغّل `deploy.sh` الأمر `seed-demo`؛ في production يرفض أوضاع `fake` ويرفض النشر ما دام حساب
  تجريبي فعّالاً.
- لا تحوّل إلى production الآن: `go-live --check` يُشغَّل داخل `api` القديم، و015 لا يعرف هذا الأمر.
- `seed-demo` لا ينشئ حساباً إذا كان `07700000001` موجوداً، ولا يعيد تفعيله بعد `go-live`.
- الطريق إلى production لاحقاً: `go-live` (الخطوة 10)، ثم `APP_ENV=production` و`bash scripts/deploy.sh`
  ([server.md](server.md) الخطوة 9). ذلك النشر يأخذ نسخة `pre_deploy` بنفسه.

## 3) النسخة اليدوية

### 3أ) تجربة قبل يوم الصيانة (والتطبيق شغّال)

```bash
install -d -m 700 "$HOME/sijil-pre016" && cd "$HOME/sijil-pre016"
docker pull alpine; docker pull postgres:16-alpine
docker exec sijil-db pg_dump -U sijil -d sijil -Fc > db-rehearsal.dump
docker run -d --name sijil-dumpcheck --network none -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16-alpine
docker exec sijil-dumpcheck pg_isready -h 127.0.0.1 -U postgres     # كرّر حتى: accepting connections
docker exec sijil-dumpcheck createdb -U postgres check
docker exec -i sijil-dumpcheck pg_restore -U postgres -d check --no-owner < db-rehearsal.dump
docker exec sijil-dumpcheck psql -U postgres -d check -Atc "select (select count(*) from requests),(select count(*) from legacy_subscribers),(select count(*) from sas_subscribers),(select count(*) from users); select version_num from alembic_version"
docker rm -f -v sijil-dumpcheck
```

- **المتوقع:** أعداد الخطوة 1 (أو أكثر بقليل إن أُدخلت طلبات بعدها)، ثم `0018`.
- `-h 127.0.0.1` مقصود: الصورة تشغّل Postgres مؤقتاً على الـ socket ثم تعيد تشغيله، فـ `pg_isready` بدونه
  قد يقول «جاهز» مبكراً.
- الحاوية بلا شبكة وتُمسح كاملة بـ `rm -f -v`.

### 3ب) النسخة الحقيقية في وقت الصيانة (بعد إيقاف `api`، الخطوة 8)

```bash
cd "$HOME/sijil-pre016"
docker exec sijil-db pg_dump -U sijil -d sijil -Fc > db-pre016.dump
docker run --rm --network none -v sijil_uploads:/u:ro -v "$PWD":/out alpine tar -C /u -cf /out/uploads-pre016.tar .
docker exec -i sijil-db pg_restore -l < db-pre016.dump > /dev/null && echo DUMP-OK
tar -tf uploads-pre016.tar | grep -vc '/$'
docker run --rm -v sijil_uploads:/u:ro alpine sh -c 'find /u -type f | wc -l'
sha256sum db-pre016.dump uploads-pre016.tar > SHA256SUMS
```

- **المتوقع:** `DUMP-OK`، والعددان متساويان. بدونهما لا تكمل.
- محاولة ثانية = نسخة جديدة بأسماء جديدة (`db-pre016-2.dump`، `uploads-pre016-2.tar`).

### الحفظ خارج السيرفر

الملفات فيها كل البيانات الشخصية (الأرقام الوطنية وصور البطاقات):

1. شفّر على السيرفر: `gpg --symmetric --cipher-algo AES256 db-pre016.dump`، ومثله للـ tar. كلمة سر هذا
   التشفير تُكتب على ورق، مثل كلمة سر النسخ.
2. انقل ملفات `.gpg` و`SHA256SUMS` فقط بـ `scp` إلى هارد أو لابتوب مشفّر بالكامل (BitLocker/LUKS)، يُحفظ
   في مكان مقفل. لا Google Drive، لا واتساب، لا بريد.
3. تأكد هناك: `gpg -d db-pre016.dump.gpg | sha256sum` يطابق سطره في `SHA256SUMS`، ومثله للـ tar.
4. النسخة غير المشفّرة تبقى في `~/sijil-pre016` (صلاحية 700) للرجوع السريع.

## 4) قبل يوم الصيانة: حفظ صور 015 وسحب الكود

```bash
cd /opt/sijil
docker tag sijil-api:latest sijil-api:pre016; docker tag sijil-web:latest sijil-web:pre016
git pull --ff-only
git log -1 --oneline
git diff --stat 576fa6f HEAD          # ملفات deploy/*.md فقط، بلا كود
```

- الحاويات الشغّالة لا تتأثر بتغيّر الملفات.
- الوسم `pre016` يحفظ الصورة الشغّالة فعلاً، فلا تضيع حين يُعاد البناء.
- لا تشغّل `deploy-staging.sh` ولا `deploy.sh` قبل الخطوة 8.
- إذا رفض `--ff-only`: لم يتغيّر شيء؛ توقف.

## 5) `.env`: إضافة فقط

```bash
install -m 600 .env "$HOME/sijil-pre016/env.pre016"
git diff af9155f 576fa6f -- .env.example
comm -13 <(grep -oE '^[A-Z_]+=' .env | sort -u) <(grep -oE '^[A-Z_]+=' .env.example | sort -u)
```

المتوقع من `comm`: `BACKUP_AGE_RECIPIENT` و`BACKUP_EXTERNAL_DIR` و`BACKUP_MIN_FREE_GB` و`BACKUP_NIGHTLY_AT`
و`EXPORTS_DIR`. (`BACKUP_DIR` لا يظهر لأنه معلّق في المثال، لكنه مطلوب.)

أضف في **آخر** الملف (`nano .env`)، بدون تعديل أي سطر موجود:

```
EXPORTS_DIR=/data/exports
BACKUP_DIR=/var/backups/sijil
BACKUP_AGE_RECIPIENT=
BACKUP_EXTERNAL_DIR=/media/sijil-external
BACKUP_NIGHTLY_AT=03:00
BACKUP_MIN_FREE_GB=2
```

**التأكد:** `diff "$HOME/sijil-pre016/env.pre016" .env` يُظهر أسطراً مضافة فقط (`>` أو `+`)، ولا سطراً
محذوفاً أو متغيّراً. كود 015 يتجاهل المتغيرات الزائدة، فهي آمنة حتى لو رجعنا إليه.

## 6) `deploy-staging.sh` و`deploy.sh`

| | `deploy-staging.sh` في 015 | `deploy.sh` |
|---|---|---|
| الوضع | staging فقط | `staging` أو `production` حسب `APP_ENV` |
| ملف compose | `docker-compose.staging.yml` | `docker-compose.server.yml` (نفس المشروع `sijil` ونفس الأسماء، فنفس البيانات) |
| مجلد النسخ والمفتاح | لا يفحص | يرفض بدونهما |
| Docker socket | لا يفحص | يرفض إن رُكّب |
| نسخة «قبل النشر» | لا | نعم إن كان التطبيق شغّالاً، ويتوقف إن فشلت |
| production | — | يرفض `fake` والحساب التجريبي الفعّال |
| فشل التشغيل | رمز 1 | رمز 8 مع خطوات رجوع، ويُسجَّل النشر في صفحة النسخ |
| `seed-demo` | دائماً | staging فقط |

في main صار `deploy-staging.sh` سطراً واحداً يشغّل `deploy.sh`.

## 7) قبل يوم الصيانة: النسخ لمرة واحدة والبناء المسبق

```bash
sudo mkdir -p /var/backups/sijil
sudo chown 10001:10001 /var/backups/sijil && sudo chmod 700 /var/backups/sijil
sudo stat -c '%u %a' /var/backups/sijil                      # 10001 700
bash scripts/backup.sh init-key
```

- أول مرة يبني صورة `backup` (دقائق)، ثم يسأل كلمة السر: **Enter** يقترح كلمة سر من 10 كلمات.
- **اكتبها على ورق في نسختين:** عندك وعند صاحب الشركة، خارج غرفة السيرفر. ليست في `.env` ولا git ولا رسالة
  ولا صورة. **إن ضاعت لا تُفتح أي نسخة.**
- ضع السطر المطبوع `BACKUP_AGE_RECIPIENT=age1…` مكان السطر الفارغ في `.env` (مفتاح عام، ليس سراً).
- الآن فقط، قبل أي نسخة، يجوز حذف `key.age` وإعادة الأمر إن شككت بالورقة. بعد أول نسخة: أبداً.
- إن كان المجلد موجوداً من قبل (الخطوة 1)، الأوامر الثلاثة الأولى لا تغيّر شيئاً. إن قال `init-key` إن المفتاح
  موجود: توقف، فهذا مفتاح لا نعرف كلمة سره.

```bash
sudo ls -l /var/backups/sijil/key.age                       # مالكه 10001
grep -c '^BACKUP_AGE_RECIPIENT=age1' .env                    # 1
docker compose -f docker-compose.yml -f docker-compose.server.yml build    # كل الخدمات ومنها ocr
docker ps --format '{{.Names}}\t{{.Status}}'                # حاويات 015 كما هي
```

البناء المسبق يجعل التوقف قصيراً، ويشمل `ocr` حتى لا يُبنى من الصفر داخل وقت الصيانة إن كان cache السيرفر
ممسوحاً.

## 8) يوم الصيانة

**الوقت:** في الليل، بعد 03:00 بتوقيت بغداد وقبل منتصف الليل (مثلاً 22:00). أبلغ المسوّقين قبلها.

1. `docker stop sijil-api` — من هنا يرى المستخدمون «تعذّر الاتصال».
2. الخطوة 3ب كاملة. **بدون `DUMP-OK` والعددين المتساويين لا تكمل.**
3. ```bash
   cd /opt/sijil && bash scripts/deploy.sh
   ```
   المتوقع:
   ```
   deploy: first install (the app is not running): no pre-deploy backup
   deploy: seed-demo (staging)
   seed-demo: 0 account(s) created, 1 already present
   deploy: OK — staging (…) is up at https://sijil.t3cftth.net.
   ```

**الترحيلات** (يشغّلها `api` عند البدء: `alembic upgrade head`)، كلها إضافات ولا تغيّر صفاً موجوداً:

- 0019: جداول النسخ (`backup_runs`، `backup_events`، `backup_status`)، فارغة.
- 0020: جداول العمولات المدفوعة (`commission_payments`، `commission_payment_requests`)، فارغة.
- 0021: جدول `exports`، فهرس `requests_submitted_at_idx` (يقفل الكتابة على الطلبات ثوانٍ، والتطبيق مغلق)،
  وتوسيع شرط `image_access_log.purpose` ليقبل `export`.

**مدة التوقف:** مدة النسخة اليدوية + دقيقة إلى 3 دقائق. إن فشلت خدمة، يظهر رمز 8 بعد حوالي 3 دقائق (مهلة فحص
الصحة).

## 9) التأكد، والرجوع

```bash
alias sijil='docker compose -f docker-compose.yml -f docker-compose.server.yml'
sijil ps --format '{{.Name}}  {{.Status}}  {{.Ports}}'    # الخمسة healthy ومنها sijil-backup، بلا 0.0.0.0:
docker exec sijil-api alembic current                      # 0021 (head)
docker exec sijil-db psql -U sijil -d sijil -Atc "select (select count(*) from requests),(select count(*) from legacy_subscribers),(select count(*) from sas_subscribers),(select count(*) from users)"
```

الأعداد = 3ب بالضبط. ثم من المتصفح بالأدمن الرئيسي: طلب قديم بصورته، مشترك قديم، سجل SAS، صفحة «النسخ
الاحتياطي»، وOTP واحد لرقمك. **بعدها فقط** افتح التطبيق للمستخدمين.

### الرجوع

| متى | ماذا تفعل |
|---|---|
| قبل الخطوة 8 | لا شيء تغيّر على المستخدمين. `git checkout af9155f` إن أردت إرجاع الملفات |
| `deploy.sh` برمز 1 | لم يتغيّر شيء. `docker start sijil-api` يعيد حاوية 015 نفسها؛ تأكد `alembic current` = `0018` |
| رمز 8 أو فحص فاشل، **قبل فتح التطبيق** | الأوامر تحت |
| بعد فتح التطبيق للمستخدمين | لا ترجع القاعدة (يضيع ما أدخلوه). أصلح للأمام |

**رمز 8:** خطوات الرجوع التي يطبعها `deploy.sh` **غير صحيحة في هذا النشر** (يطبع الـ commit الجديد و
`restore.sh -` لأنه لا توجد نسخة `pre_deploy`). تجاهلها ونفّذ:

```bash
cd /opt/sijil
sijil stop api backup
docker exec sijil-db createdb -U sijil sijil_pre016
docker exec -i sijil-db pg_restore -U sijil -d sijil_pre016 --no-owner < "$HOME/sijil-pre016/db-pre016.dump"
F="sijil_failed016_$(date +%H%M)"
docker exec sijil-db psql -U sijil -d postgres -c "ALTER DATABASE sijil RENAME TO $F" -c "ALTER DATABASE sijil_pre016 RENAME TO sijil"
git checkout af9155f
docker compose -f docker-compose.yml -f docker-compose.staging.yml up -d --build --remove-orphans --wait
docker exec sijil-api alembic current                      # 0018 (head)
```

- قارن الأعداد وعدد الصور بالخطوة 3ب.
- الترحيلات لا تلمس الصور والتطبيق كان مغلقاً، فالصور لا تحتاج استرجاعاً؛ الـ tar احتياط.
- القاعدة الفاشلة تبقى باسم `sijil_failed016_…`، ومجلد النسخ يبقى، و`--remove-orphans` يزيل حاوية
  `sijil-backup` فقط. لا يُحذف أي بيانات.
- للمحاولة التالية: `git checkout main`، ثم الخطوة 8 من أولها بنسخة جديدة بأسماء جديدة.
- إن استعملت نسخة 3ب ثانية (`-2`)، استعمل اسمها في `pg_restore`.

## 10) بعد النجاح

**نسخة وتجربة استرجاع فوراً** (تثبت أن كلمة السر على الورق صحيحة):

```bash
bash scripts/backup.sh now        # «تم النسخ: … (… صورة)»
bash scripts/backup.sh drill      # كلمة السر من الورقة ← «تجربة الاسترجاع نجحت»، والأعداد = 3ب
bash scripts/backup.sh status     # رمز 1 بسبب «النسخة الأسبوعية متأخرة» فقط — متوقع حتى أول weekly
```

إن فشلت التجربة بسبب كلمة السر: لا تحذف شيئاً، والنسخة اليدوية موجودة.

**إيقاف الحساب التجريبي:**

```bash
sijil exec api python -m app.cli go-live
sijil exec api python -m app.cli go-live --check     # لا يطبع شيئاً، رمزه 0
```

يوقف الحسابات التجريبية بلا حذف، تنتهي جلساتها، ويُسجَّل `system.go_live` في سجل العمليات.

**النسخة الليلية:**

- إن نشرت بعد 03:00 بغداد، تظهر نسخة `nightly` في `bash scripts/backup.sh list` خلال دقائق (تعوّض اليوم،
  مقصود).
- صباح الغد: نسخة `nightly` جديدة بوقت 03:00 تقريباً، و`status` بلا «فشل آخر نسخ احتياطي» وبلا «خدمة النسخ
  متوقفة». النسخة الفاشلة تُعاد بعد ساعة، 3 مرات في اليوم على الأكثر؛ السبب في `sijil logs backup`.
- كرّر 7 صباحات قبل التفكير في production.

**ملفات التصدير لا تدخل النسخ:**

```bash
docker inspect sijil-backup --format '{{range .Mounts}}{{.Destination}}{{"\n"}}{{end}}'   # /data/backups و/data/uploads فقط
sijil exec backup ls /data/exports      # فارغ: مجلد من الصورة، غير مركّب
```

ثم: تصدير صغير من الشاشة حتى «تنزيل»، و`bash scripts/backup.sh now`، و
`sudo find /var/backups/sijil \( -iname '*.zip' -o -iname '*.xlsx' \) | wc -l` يطبع `0`، وعدد الصور في آخر سطر
من `list` = ما قبله. أي ملف تصدير في النسخ = توقف.

**بعدها:**

- أول نسخة على الهارد الخارجي خلال أيام ([backup.md](backup.md) الخطوة 4).
- مسح `~/sijil-pre016` بـ `shred` والقواعد `sijil_failed016_*`: قرار صاحب النظام، بعد 7 ليالٍ ناجحة.
