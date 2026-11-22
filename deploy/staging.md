# النشر التجريبي (staging) على سيرفر الشركة — خلف Nginx Proxy Manager

هذا الدليل لتشغيل سِجلّ على `https://sijil.t3cftth.net` في سيرفر عليه **Nginx Proxy Manager (NPM)** داخل Docker.

## كيف يعمل

```
الهاتف/المتصفح ──HTTPS──▶ NPM (80/443، شهادة Let's Encrypt)
                              │  http://sijil-web:80 عبر شبكة Docker الخاصة بـ NPM
                              ▼
                       sijil-web (الواجهة، HTTP على 80 داخلياً فقط)
                         └── /api/*  ──▶ sijil-api (FastAPI)
                                           sijil-db (PostgreSQL) — داخلي فقط
```

- **NPM وحده** يمسك المنفذين 80 و443 ويصدر الشهادة.
- **سِجلّ لا يفتح أي منفذ على السيرفر.** لا 80 ولا 443، ولا المنافذ المستخدمة 3000 و8080 و5433، ولا منفذ قاعدة البيانات.
- مشروع compose اسمه `sijil`، والحاويات باسم `sijil-web` و`sijil-api` و`sijil-db`.
- حاوية `sijil-web` تنضم لشبكة NPM، فيصل إليها NPM باسمها عبر HTTP فقط، بدون شهادة من Caddy. هي التي تعرض الواجهة وتوجّه `/api` إلى `sijil-api`.
- حاوية `proxy` (Caddy مع HTTPS) للتطوير المحلي فقط، ولا تعمل على السيرفر.
- الملفات المستخدمة:
  - `docker-compose.yml` مع `docker-compose.staging.yml`
  - `web/Caddyfile`
  - `scripts/deploy-staging.sh`

> ⚠️ على السيرفر لا تشغّل `docker compose up` بدون `-f`، لأنه يحمّل وضع التطوير ويحاول فتح 80/443. استعمل السكربت دائماً.

---

## 1) المتطلبات

**على جهازك:**
- تأكد أن النطاق يشير إلى السيرفر:
  ```bash
  nslookup sijil.t3cftth.net
  ```
  يجب أن يظهر عنوان IP السيرفر.

**على السيرفر:**
- Docker مع Compose v2، و`git` و`curl`.
- NPM شغّال، ولوحته تفتح عادة على المنفذ 81.

## 2) معرفة اسم شبكة NPM

```bash
# اسم حاوية NPM
docker ps --format '{{.Names}}\t{{.Image}}' | grep -i nginx-proxy-manager

# الشبكات التي تنضم لها (ضع اسم الحاوية مكان <npm>)
docker inspect <npm> --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}'
```

**احفظ اسم الشبكة** (مثل `npm_default` أو `nginx-proxy-manager_default`)، لأنك ستضعه في `NPM_NETWORK` بالخطوة 3.

**إذا ظهرت الشبكة `bridge` وحدها** فهي الشبكة الافتراضية ولا تصلح للوصول بالاسم. أنشئ شبكة مخصّصة وأضف NPM لها:

```bash
docker network create npm_proxy
docker network connect npm_proxy <npm>
```

ولكي يبقى NPM عليها بعد إعادة إنشاء حاويته، أضفها أيضاً في ملف compose الخاص بـ NPM:
```yaml
networks:
  npm_proxy:
    external: true
```
ثم أضف تحت خدمته `networks: [default, npm_proxy]`.

## 3) تنزيل المشروع وملف `.env`

```bash
sudo mkdir -p /opt/sijil && sudo chown "$USER" /opt/sijil
git clone <رابط مستودع git> /opt/sijil
cd /opt/sijil
git checkout 001-project-skeleton-auth
cp .env.example .env
chmod 600 .env
```

ولّد أسراراً جديدة. استعمل `-hex` حتى لا تظهر رموز تكسر رابط قاعدة البيانات:

```bash
openssl rand -hex 24   # نفّذه مرة لكل سر وانسخ الناتج
```

عدّل `.env` (مثلاً `nano .env`). **كل قيمة `change-me` يجب أن تُستبدل**، وإلا يرفض التطبيق والسكربت العمل:

| المتغير | القيمة |
|---|---|
| `APP_ENV` | احذف `#` من بداية السطر واجعله `APP_ENV=staging` |
| `NPM_NETWORK` | احذف `#` واكتب اسم شبكة NPM من الخطوة 2 |
| `POSTGRES_PASSWORD` | سر جديد |
| `DATABASE_URL` | `postgresql+psycopg://sijil:<نفس POSTGRES_PASSWORD>@db:5432/sijil` |
| `JWT_SECRET` | سر جديد (48 حرفاً على الأقل يكفي) |
| `COOKIE_SECURE` | `true` |
| `SUPERADMIN_PHONE` / `SUPERADMIN_NAME` | رقم واسم الأدمن الرئيسي الحقيقي |
| `SUPERADMIN_PASSWORD` | كلمة سر مؤقتة، تُطلب تغييرها عند أول دخول |
| `DEMO_MARKETER_PASSWORD` | كلمة سر المسوّق التجريبي `07700000001` |

ملاحظات:
- `SITE_ADDRESS` و`HTTP_PORT` و`HTTPS_PORT` لا تُستخدم في staging.
- ملف `.env` يبقى على السيرفر فقط، ولا يُرفع إلى git أبداً.

## 4) التشغيل الأول

```bash
cd /opt/sijil
bash scripts/deploy-staging.sh
```

**ما يفعله السكربت:**
1. يتأكد من `.env`، ومن وجود شبكة NPM، ومن عدم فتح أي منفذ.
2. يسحب الكود ويبني ويشغّل الحاويات.
3. يفحص صحة الـ API من الداخل.
4. ينشئ الحساب التجريبي.
5. يجرّب `https://sijil.t3cftth.net/api/health`.

**في التشغيل الأول** ينتهي السكربت برسالة أن الرابط العام غير متاح (رمز خروج 2). هذا متوقع لأن Proxy Host لم يُضف بعد في NPM، وهو الخطوة 5.

**تأكد أنه لا يوجد أي منفذ مفتوح لسِجلّ:**

```bash
docker compose -f docker-compose.yml -f docker-compose.staging.yml ps --format '{{.Name}}  {{.Ports}}'
```

يجب ألا يظهر أي `0.0.0.0:`. وتأكد أن NPM يصل إلى سِجلّ:

```bash
docker exec <npm> curl -s http://sijil-web/api/health
# المتوقع: {"status":"ok","db":"ok"}
```

## 5) إضافة Proxy Host في لوحة NPM مع شهادة Let's Encrypt

1. افتح لوحة NPM (عادة `http://<IP السيرفر>:81`) وسجّل الدخول.
2. **Hosts ← Proxy Hosts ← Add Proxy Host**
3. تبويب **Details**:
   | الحقل | القيمة |
   |---|---|
   | Domain Names | `sijil.t3cftth.net` |
   | Scheme | `http` |
   | Forward Hostname / IP | `sijil-web` |
   | Forward Port | `80` |
   | Cache Assets | **مطفأ**، حتى لا تبقى نسخة قديمة من التطبيق أو من `sw.js` |
   | Block Common Exploits | مفعّل |
   | Websockets Support | مفعّل (لا يضر) |
4. تبويب **SSL**:
   | الحقل | القيمة |
   |---|---|
   | SSL Certificate | **Request a new SSL Certificate** |
   | Force SSL | مفعّل |
   | HTTP/2 Support | مفعّل |
   | HSTS Enabled | مفعّل |
   | Email | بريد الشركة لتنبيهات Let's Encrypt |
   | I Agree to the Let's Encrypt Terms | ✓ |
5. تبويب **Advanced** ← Custom Nginx Configuration، أضف السطر التالي (الفيزة 005). بدونه يرفض NPM أي صورة أكبر من 1 ميغابايت قبل أن تصل للتطبيق، والتطبيق نفسه يقبل حتى 5 ميغابايت:
   ```nginx
   client_max_body_size 6m;
   ```
6. اضغط **Save**. خلال دقيقة تُصدر الشهادة ويصبح الـ Host بحالة Online.

**إذا فشل إصدار الشهادة:** تأكد أن الـ DNS يشير للسيرفر، وأن المنفذ 80 مفتوح في جدار الحماية لـ NPM.

**لاحقاً (الفيزة 004، رفع صور البطاقات):** أضف في تبويب **Advanced** السطر `client_max_body_size 20m;`.

## 5ب) مفتاح Google Maps (الفيزة 005)

الخريطة اختيارية: بدون مفتاح تعمل الاستمارة، ويظهر «الخريطة غير متوفرة حالياً»، ويبقى زر «استخدم موقعي الحالي» ومربع «إدخال إحداثية» يعملان.

1. في Google Cloud Console فعّل **Maps JavaScript API** و**Places API (New)** (لشريط «ابحث عن مكان»)، وأنشئ **API key**. لا تفعّل «Places API» القديمة؛ الكود يستعمل الجديدة.
2. قيّد المفتاح (**Edit API key**):
   - Application restrictions: **Websites**، والعنوان `https://sijil.t3cftth.net/*`
   - API restrictions: **Maps JavaScript API** و**Places API (New)** فقط
3. من **Map Management** أنشئ **Map ID** من نوع JavaScript (يحتاجه الدبوس القابل للسحب).
4. ضعهما في `.env` على السيرفر فقط، ولا يدخلان git أبداً:
   ```bash
   GOOGLE_MAPS_API_KEY=...
   GOOGLE_MAPS_MAP_ID=...
   MAP_DEFAULT_CENTER=33.3152,44.3661   # مركز الخريطة عند عدم وجود موقع
   ```
5. أعد تشغيل الخادم (`sijil up -d api`)، وافتح الاستمارة. يجب أن تظهر صور القمر الصناعي، وألا تظهر أخطاء CSP في Console المتصفح.
6. جرّب «ابحث عن مكان» واكتب «ساحة». إذا ظهر «البحث عن الأماكن غير متاح حالياً» فـ Places API (New) غير مفعّلة أو غير مضافة لقيود المفتاح (في Console يظهر `REQUEST_DENIED` أو `PERMISSION_DENIED`).

## 5ج) قارئ البطاقة `sijil-ocr` (الفيزة 006)

قراءة البطاقة الوطنية تعمل في حاوية مستقلة اسمها `sijil-ocr`، فيها المشروع المفتوح ID_Iraqi_Project
(رخصة AGPL-3.0، انظر `ocr/UPSTREAM.md`). الحاوية:

- **بلا إنترنت:** على شبكة Docker داخلية `ocr_net` لا طريق منها للخارج، ولا تنشر أي منفذ. لا يصلها إلا `sijil-api`.
- **محدودة الموارد:** معالجان و2 GB ذاكرة. تستهلك فعلياً حوالي 1.4 GB.
- **لا تحفظ شيئاً:** لا صوراً ولا نتائج، ولا تكتب بيانات البطاقة في السجلات.
- **إذا توقفت:** الاستمارة تبقى تعمل، ويظهر للمسوّق «تعذّرت القراءة الآلية، أكمل يدوياً».

**المتطلبات على السيرفر:** حوالي 5 GB مساحة فارغة لصورة الحاوية (4.3 GB). البناء وحده يحتاج إنترنت: يحمّل
المكتبات وأوزان النماذج من release المشروع ويتحقق منها بـ SHA256، ويفشل البناء إذا لم تطابق.

1. في `.env` على السيرفر:
   ```bash
   OCR_MODE=http
   OCR_URL=http://ocr:8080
   OCR_SOURCE_URL=https://github.com/<حساب الشركة>/<النسخة العامة من ocr>   # انظر الخطوة 4
   ```
2. البناء والتشغيل مع باقي الخدمات (`scripts/deploy-staging.sh` يبني `ocr` أيضاً). أول بناء يأخذ عدة دقائق.
3. الفحوص بعد التشغيل:
   ```bash
   sijil ps ocr                                   # Up (healthy)، بلا منافذ منشورة
   sijil exec api python -c "import httpx; print(httpx.get('http://ocr:8080/health').json())"
   sijil exec ocr python -c "import urllib.request; urllib.request.urlopen('https://github.com', timeout=5)"   # يجب أن يفشل: لا إنترنت
   docker stats --no-stream sijil-ocr             # الحد: 2 GiB
   ```
4. **رخصة AGPL:** قبل كل نشر يغيّر مجلد `ocr/`، انشر مجلد `ocr/` إلى النسخة العامة (fork عام على حساب الشركة)،
   ورابطها هو `OCR_SOURCE_URL`. المستخدمون يرون الرابط في «حسابي» ← «رخص البرمجيات المفتوحة». كود سِجلّ نفسه
   (`api/` و`web/`) يبقى خاصاً ولا يُنشر.
5. لا تشغّل القارئ على صور بطاقات حقيقية خارج التطبيق إلا في حاوية بلا شبكة، ولا تحفظ النتائج (انظر
   `python -m service.evaluate` في `ocr/UPSTREAM.md`).

## 6) التشغيل الثاني والتأكد

```bash
bash scripts/deploy-staging.sh
# المتوقع في النهاية: deploy-staging: OK — https://sijil.t3cftth.net is up.
```

**من جهازك:**
- افتح `https://sijil.t3cftth.net`. يجب أن تظهر صفحة الدخول بالقفل الأخضر، بدون تحذير.
- نفّذ **الجزء الثاني** من [manual-test-ar.md](../specs/001-project-skeleton-auth/manual-test-ar.md) (S1–S6): الأدمن من الكمبيوتر، والمسوّق من هاتف Android وiPhone حقيقيين، وتثبيت التطبيق.

## 7) التحديث لاحقاً

```bash
cd /opt/sijil
git checkout <الفرع المطلوب>   # عند الحاجة
bash scripts/deploy-staging.sh      # يسحب آخر كود ويعيد البناء، والبيانات تبقى
```

## 8) أوامر مفيدة

```bash
alias sijil='docker compose -f docker-compose.yml -f docker-compose.staging.yml'
sijil ps                 # حالة الحاويات
sijil logs -f api        # سجل الخادم (لا يحتوي كلمات سر أو tokens)
sijil restart api        # إعادة تشغيل الخادم
sijil down               # إيقاف (البيانات تبقى في volume باسم sijil_pgdata وصور البطاقات في sijil_uploads)
sijil exec api python -m app.cli prune-uploads   # حذف ملفات صور يتيمة (لا مسودة تشير إليها، أقدم من ساعة)
```

**لا تستعمل `down -v` على السيرفر**، لأنه يحذف قاعدة البيانات وصور البطاقات.

### نسخ صور البطاقات احتياطياً (الفيزة 005)

صور البطاقات محفوظة في volume باسم `sijil_uploads`، داخل حاوية `api` فقط، ولا تُعرض برابط عام. **يجب أن تدخل في كل نسخة احتياطية** مع قاعدة البيانات. النسخ الليلي التلقائي يأتي في الفيزة 015، وحتى ذلك الحين هذه الأوامر اليدوية:

```bash
mkdir -p ~/sijil-backups
# نسخة من الصور (ملف tar مضغوط، بتاريخ اليوم)
docker run --rm -v sijil_uploads:/data:ro -v ~/sijil-backups:/backup alpine   tar czf /backup/uploads-$(date +%F).tar.gz -C /data .
# نسخة من قاعدة البيانات في نفس الوقت
sijil exec -T db pg_dump -U sijil -Fc sijil > ~/sijil-backups/db-$(date +%F).dump
```

الاستعادة (بعد إيقاف `api`):

```bash
sijil stop api
docker run --rm -v sijil_uploads:/data -v ~/sijil-backups:/backup alpine   sh -c 'rm -rf /data/* && tar xzf /backup/uploads-YYYY-MM-DD.tar.gz -C /data && chown -R 10001:10001 /data'
sijil start api
```

احفظ ملفات `~/sijil-backups` خارج السيرفر أيضاً (الهارد الخارجي)، لأنها تحتوي صور بطاقات حقيقية. لا ترسلها لأي طرف خارجي.

## 9) قبل الإطلاق الفعلي (الفيزة 014)

1. أوقف الحسابات التجريبية. لا تحذفها، فالحذف ممنوع حسب الدستور:
   ```bash
   sijil exec db psql -U sijil -c "UPDATE users SET is_active=false WHERE phone LIKE '077000000%';"
   ```
2. غيّر في `.env` إلى `APP_ENV=production` (بعدها يرفض `seed-demo` العمل)، ثم شغّل السكربت. السكربت الحالي خاص بـ staging، وسيُحدَّث في الفيزة 014 مع النسخ الاحتياطي.

## حل المشاكل

| المشكلة | السبب المحتمل / الحل |
|---|---|
| `502 Bad Gateway` من NPM | NPM ليس على نفس الشبكة، أو الاسم خطأ. راجع الخطوة 2، وجرّب `docker exec <npm> curl http://sijil-web/api/health` |
| السكربت: `network ... does not exist` | قيمة `NPM_NETWORK` في `.env` لا تطابق اسم الشبكة |
| السكربت: `still 'change-me'` | بقيت قيمة افتراضية في `.env` |
| السكربت: `DATABASE_URL must contain the same password` | كلمة السر في `DATABASE_URL` تختلف عن `POSTGRES_PASSWORD` |
| الـ API لا يبدأ: `Refusing to start in staging` | سر أقصر من 32 حرفاً أو `COOKIE_SECURE=false`. شاهد `sijil logs api` |
| الدخول ينجح ثم يخرج فوراً | الموقع مفتوح بـ `http://` وليس `https://`. فعّل Force SSL في NPM |
| التطبيق لا يتحدّث على الهاتف | أطفئ Cache Assets في NPM، ثم أغلق التطبيق وافتحه |
