# سِجلّ

تطبيق يستخدمه مسوّقو **تكنولوجي للإنترنت** لتسجيل طلبات اشتراك الإنترنت (FTTH) مع مستمسكات المشترك، ومنع تسجيل نفس البيت أو نفس الشخص مرتين.

- قواعد العمل كاملة: [docs/system.md](docs/system.md)
- مبادئ المشروع: [.specify/memory/constitution.md](.specify/memory/constitution.md)
- مواصفات الفيزات: مجلد [specs/](specs/)

## الفيزات المنجزة

| # | الفيزة | ما تقدّمه |
|---|---|---|
| 001 | هيكل المشروع والدخول | دخول بالهاتف وكلمة السر، ثلاثة أدوار، قفل بعد 5 محاولات، إجبار تغيير كلمة السر، PWA |
| 002 | الحسابات والصلاحيات | إضافة الأدمنية وصلاحياتهم، إدارة المسوّقين (إضافة، تعديل، إيقاف، تصفير كلمة السر)، «حسابي»، صفحة سجل العمليات |

## المكوّنات

| المجلد | المحتوى |
|---|---|
| `api/` | الخادم: Python 3.12 + FastAPI + SQLAlchemy 2 + Alembic |
| `web/` | الواجهة: React + TypeScript + Vite، تطبيق PWA عربي RTL |
| `e2e/` | اختبارات Playwright للتطبيق كاملاً |
| `deploy/` | إعدادات Caddy (HTTPS وتوجيه `/api` إلى الخادم) |
| `scripts/` | سكربتات الاختبار والنشر |

## المتطلبات

- Docker مع Docker Compose v2 (على ويندوز: Docker Desktop).
- لا تحتاج تثبيت Python أو Node على جهازك لتشغيل التطبيق.

## التشغيل المحلي

```bash
cp .env.example .env          # على ويندوز: copy .env.example .env
docker compose up -d --build
docker compose exec api python -m app.cli seed-demo
```

- افتح `https://localhost` في المتصفح.
- أول مرة سيظهر تحذير من الشهادة، لأن Caddy يصدر شهادة محلية. اضغط «متقدم» ثم «المتابعة إلى localhost».
- لإزالة التحذير نهائياً، ثبّت شهادة Caddy المحلية كشهادة موثوقة:
  ```bash
  docker compose cp proxy:/data/caddy/pki/authorities/local/root.crt caddy-root.crt
  ```
  ثم افتح الملف `caddy-root.crt` وثبّته ضمن «Trusted Root Certification Authorities».

### الحسابات التجريبية (بيانات وهمية)

| الحساب | الهاتف | كلمة السر |
|---|---|---|
| الأدمن الرئيسي (يُنشأ تلقائياً عند أول تشغيل) | قيمة `SUPERADMIN_PHONE` في `.env` | قيمة `SUPERADMIN_PASSWORD`، ويُطلب تغييرها عند أول دخول |
| مسوّق تجريبي (بعد `seed-demo`) | `07700000001` | قيمة `DEMO_MARKETER_PASSWORD` |

### أوامر مفيدة

```bash
docker compose logs -f api        # سجل الخادم
docker compose down               # إيقاف التطبيق (البيانات تبقى)
docker compose down -v            # إيقاف وحذف كل البيانات المحلية
```

ملف `docker-compose.override.yml` يُحمَّل تلقائياً على جهاز المطوّر، ويشغّل وضع التطوير مع تحديث فوري عند تعديل الكود.

## الاختبارات

```bash
docker compose exec api pytest              # اختبارات الخادم
docker compose exec web npm test            # اختبارات الواجهة
scripts/e2e.sh                              # Playwright، وعلى ويندوز: scripts\e2e.ps1
scripts/test-all.sh                         # كل الفحوصات، وعلى ويندوز: scripts\test-all.ps1
```

- اختبارات Playwright تشغّل نسخة منفصلة من التطبيق بقاعدة بيانات فارغة، ثم تحذفها بعد الانتهاء، فلا تتأثر بياناتك المحلية.
- لا تُدمج أي فيزة إلا إذا نجحت كل الفحوصات (مبدأ الدستور VIII).

## التجربة من الهاتف

تجربة الهاتف الحقيقي وتثبيت التطبيق على الشاشة الرئيسية تتم على السيرفر التجريبي `https://sijil.t3cftth.net`، لأن تثبيت التطبيق يحتاج شهادة HTTPS حقيقية. لا تتم عبر الشبكة المحلية.

طريقة النشر التجريبي موثّقة في [deploy/staging.md](deploy/staging.md). على السيرفر يمسك Nginx Proxy Manager المنفذين 80 و443 ويصدر الشهادة، ويوجّه الطلبات إلى حاوية `sijil-web` عبر شبكة Docker، ولا يفتح سِجلّ أي منفذ.

على الكمبيوتر يمكن محاكاة الهاتف من أدوات المطوّر: اضغط F12 ثم Ctrl+Shift+M واختر جهازاً.

## الأمان

- لا ترفع ملف `.env` أو أي مفتاح أو كلمة سر إلى git. ملف `.env.example` يوضح المتغيرات المطلوبة فقط.
- لا تستخدم صور بطاقات حقيقية أو بيانات مشتركين حقيقيين في الاختبارات أو الأمثلة.
- على السيرفر استعمل `scripts/deploy-staging.sh` دائماً. الأمر `docker compose up` بدون `-f` يحمّل وضع التطوير.
