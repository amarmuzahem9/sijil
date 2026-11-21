# UI Contract: Routes & Screens (002)

This contract changes [001 ui-routes.md](../../001-project-skeleton-auth/contracts/ui-routes.md).
All text is in Arabic and the layout is RTL. Screens are designed for phones first: on a phone,
lists are cards and dialogs are full-screen. From `md` up, lists are tables and dialogs are
centred.

## Route access (replaces the 001 admin rows)

Access follows the page map in [data-model.md](../data-model.md#permission--page-map-systemmd-10-v11).
- A page the caller cannot open is **absent from the menu**.
- Opening it by address redirects to `/admin`, with a snackbar «ليست لديك صلاحية».
- The server also refuses the page's API calls.

## /admin/admins: الأدمنية والصلاحيات (main admin)

- The main admin appears as the first row: name, phone, «أدمن رئيسي», «كل الصلاحيات». The row has
  no actions.
- Each admin row shows the name, phone, the permission chips (Arabic labels), and a «فعّال» or
  «موقوف» state chip. It has the actions «تعديل», «تصفير كلمة السر», and «إيقاف» or «إعادة
  تفعيل».
- The **«إضافة أدمن»** dialog has these fields:
  - الاسم
  - رقم الهاتف (LTR input; inline «رقم غير صالح»)
  - كلمة السر المؤقتة (show/hide)
  - «الصلاحيات»: six switches with the labels of data-model.md, all off by default
  - Buttons «حفظ» and «إلغاء»
- The **«تعديل»** dialog has the same fields without the password field.
- **«تصفير كلمة السر»** opens a dialog with one field, «كلمة السر المؤقتة الجديدة», and the
  explanation «سيُطلب من الأدمن تغييرها عند الدخول، وستنتهي جلساته الحالية». This dialog is the
  confirmation (spec FR-021); there is no second confirm step.
- **«إيقاف»** asks for confirmation: «إيقاف حساب <الاسم>؟ سيُسجَّل خروجه فوراً ولن يستطيع
  الدخول». «إعادة تفعيل» needs no confirmation.

## /admin/marketers: المسوّقون (`marketers`)

- A search box at the top (name or phone) filters on the client. Next to it is a filter: «الكل»،
  «فعّال»، «موقوف».
- Each row shows the name, phone, and state, with the actions «تعديل», «تصفير كلمة السر», and
  «إيقاف» or «إعادة تفعيل».
- **«إضافة مسوّق»** has these fields: الاسم، رقم الهاتف، كلمة السر المؤقتة.
- The dialogs and confirmations follow the admins page, with the wording «المسوّق».
- After a successful save, a snackbar shows «تم الحفظ». The temporary password is never displayed
  again.

## /admin/audit: سجل العمليات (main admin)

- **Filters**:
  - «من تاريخ» and «إلى تاريخ», as Baghdad dates
  - «المنفّذ», a select of the actors plus «النظام»
  - «مسح الفلاتر»
- **Entry**: each entry shows these items, newest first:
  - The time in Baghdad time (`formatBaghdad`)
  - The actor name, or «النظام»
  - The Arabic action label
  - The target name
  - «قبل» and «بعد» as labelled field lists. Permissions are shown with their Arabic labels, and
    booleans as «نعم» or «لا».
- **Paging**: a «تحميل المزيد» button appears while `has_more` is true.
- **States**:
  - The empty state reads «لا توجد عمليات».
  - The page is read-only, with no edit or delete controls.

## /account and /admin/account: حسابي

- **Name and phone**: name, phone (LTR), and role, all read-only.
- **Main admin only**: an «تعديل الاسم» button opens a dialog with one field. Saving updates the
  name in the top bar.
- **Buttons** (unchanged from 001): «تغيير كلمة السر» (the current password is required) and
  «تسجيل الخروج».

## Session-ended behaviour (unchanged from 001, now reachable)

A deactivated user's next request clears the local state. The user returns to `/login`, which
shows «الحساب موقوف، راجع الإدارة». After a password reset, the next request returns to `/login`.
After signing in, the change-password screen is forced.
