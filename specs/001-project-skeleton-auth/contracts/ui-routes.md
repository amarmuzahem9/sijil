# UI Contract: Routes & Screens (001)

All screens use `dir="rtl"`, `lang="ar"`, Cairo font, and Arabic text only.

| Path | Access | Screen |
|---|---|---|
| `/login` | signed out (a signed-in user is redirected to their landing page) | Phone + password, «دخول» button, inline «رقم غير صالح», lock message with minutes |
| `/change-password` | signed in; the **only** page while `must_change_password` | Current, new, and confirm fields; «حفظ» |
| `/` | marketer | Dashboard: large disabled «إضافة مشترك جديد», disabled «إضافة اشتراك لمشترك موجود» (caption «قريباً»), card «تم الربط هذا الشهر: 0» |
| `/requests` | marketer | Empty state «قريباً» |
| `/notifications` | marketer | Empty state «قريباً» |
| `/account` | marketer | Name, phone, role «مسوّق», «تغيير كلمة السر», «تسجيل الخروج» |
| `/admin` | super_admin, admin | الرئيسية (empty placeholder) |
| `/admin/pending` | admin roles | طلبات بالانتظار (placeholder) |
| `/admin/awaiting-link` | admin roles | بانتظار الربط |
| `/admin/subscribers` | admin roles | المشتركون |
| `/admin/marketers` | admin roles | المسوّقون |
| `/admin/settings` | admin roles | الإعدادات |
| `/admin/admins` | **super_admin only** | الأدمنية والصلاحيات |
| `/admin/reports` | admin roles | التقارير والتصدير |
| `/admin/import` | admin roles | الاستيراد |
| `/admin/backup` | admin roles | النسخ الاحتياطي |
| `/admin/audit` | admin roles | سجل العمليات |
| `/admin/account` | admin roles | Name, role, change password, sign out |

Redirect rules:
- Signed out → `/login`. After sign-in the user always goes to their role landing page; deep links
  are not followed across roles.
- A marketer on `/admin*` → `/`. An admin on a marketer route → `/admin`.
- `must_change_password` → `/change-password` for every route.

Layout:
- Below `md` (900px), the marketer uses a bottom bar with icons and labels: الرئيسية، الطلبات،
  الإشعارات، حسابي. The admin uses a top app bar plus a slide-in menu listing the 11 pages in
  §10 order.
- From `md` up, both use a permanent right sidebar with the page list and a top bar showing the
  user name and role label (أدمن رئيسي / أدمن / مسوّق).

PWA manifest: `name` and `short_name` «سِجلّ», `lang: ar`, `dir: rtl`, `display: standalone`,
`start_url: /`, a theme color, and icons 192, 512, and 512 maskable, plus a 180 apple-touch-icon.
