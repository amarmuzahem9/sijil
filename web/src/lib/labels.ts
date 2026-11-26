/** Arabic labels for permissions, audit actions and audit fields (specs/002 data-model.md). */
import type { Role } from './api';

export const PERMISSIONS = [
  'review',
  'link',
  'settings',
  'marketers',
  'reports',
  'commissions',
  'delete',
] as const;
export type Permission = (typeof PERMISSIONS)[number];

export const PERMISSION_LABELS: Record<Permission, string> = {
  review: 'مراجعة الطلبات (قبول/رفض)',
  link: 'تم الربط والتراجع عنه',
  settings: 'الإعدادات والأسعار والشرائح',
  marketers: 'إدارة المسوّقين وتصفير كلمات السر',
  reports: 'التقارير والتصدير والاستيراد',
  commissions: 'العمولات وزر تم الدفع',
  delete: 'حذف مشترك (طلب بالانتظار أو مرفوض)',
};

export const AUDIT_ACTION_LABELS: Record<string, string> = {
  'user.bootstrap_created': 'إنشاء الأدمن الرئيسي',
  'user.locked': 'قفل مؤقت بعد محاولات خاطئة',
  'user.password_changed': 'تغيير كلمة السر',
  'user.created': 'إنشاء حساب',
  'user.updated': 'تعديل بيانات حساب',
  'user.permissions_changed': 'تعديل الصلاحيات',
  'user.deactivated': 'إيقاف حساب',
  'user.reactivated': 'إعادة تفعيل حساب',
  'user.password_reset': 'تصفير كلمة السر',
  'user.archived': 'أرشفة حساب',
  'user.restored': 'استرجاع حساب من الأرشيف',
  // Settings (specs/004 data-model.md)
  'area.created': 'إضافة منطقة',
  'area.updated': 'تعديل منطقة',
  'area.deactivated': 'إيقاف منطقة',
  'area.reactivated': 'تفعيل منطقة',
  'area.deleted': 'حذف منطقة',
  'tower.created': 'إضافة برج',
  'tower.updated': 'تعديل برج',
  'tower.deactivated': 'إيقاف برج',
  'tower.reactivated': 'تفعيل برج',
  'tower.deleted': 'حذف برج',
  'plan.created': 'إضافة فئة',
  'plan.updated': 'تعديل فئة',
  'plan.deactivated': 'إيقاف فئة',
  'plan.reactivated': 'تفعيل فئة',
  'plan.deleted': 'حذف فئة',
  'reward_tiers.updated': 'تعديل شرائح المكافآت',
  'app_setting.updated': 'تعديل الإعدادات العامة',
  // specs/005: an unsubmitted draft deleted by its owner (no card data in the entry)
  'draft.deleted': 'حذف مسودة',
  // specs/008: a submission and its automatic decision, and a refused submission (no card data)
  'request.submitted': 'إرسال طلب',
  'draft.return_chosen': 'اختيار طلب العودة للخدمة',
  'draft.return_withdrawn': 'إلغاء طلب العودة للخدمة',
  'draft.contact_admin_opened': 'فتح «الاتصال بالإدارة»',
  'request.submit_refused': 'رفض إرسال طلب',
  // specs/010: the admin's decision (no card data in the entry)
  'request.approved': 'قبول طلب',
  'request.rejected': 'رفض طلب',
  'request.numbers_pinned': 'تثبيت رقم',
  // specs/011
  'request.deleted': 'حذف مشترك',
  // specs/013
  'request.linked': 'تم الربط',
  'request.unlinked': 'تراجع عن الربط',
  // specs/017
  'commission.paid': 'تسجيل دفع عمولة',
  // specs/014
  'legacy.imported': 'استيراد المشتركين القدامى',
  // specs/015
  'sas.imported': 'استيراد مشتركي SAS',
};

export const AUDIT_FIELD_LABELS: Record<string, string> = {
  name: 'الاسم',
  phone: 'الهاتف',
  role: 'الدور',
  permissions: 'الصلاحيات',
  is_active: 'الحالة',
  must_change_password: 'يجب تغيير كلمة السر',
  locked_until: 'مقفل حتى',
  archived: 'مؤرشف',
  code: 'الرمز',
  area: 'المنطقة',
  trial_price: 'سعر الشهر التجريبي',
  second_price: 'سعر الشهر الثاني',
  tiers: 'الشرائح',
  otp_validity_minutes: 'مدة صلاحية الرمز (دقيقة)',
  admin_whatsapp: 'رقم واتساب الإدارة',
  created_at: 'أُنشئت',
  updated_at: 'آخر حفظ',
  tower_code: 'البرج',
  image_count: 'عدد الصور',
  missing_count: 'عدد النواقص',
  // specs/010
  status: 'الحالة',
  type: 'النوع',
  counts_commission: 'احتساب العمولة',
  // specs/017: «تم الدفع»
  marketer_id: 'المسوّق (رقم الحساب)',
  month: 'الشهر',
  count: 'العدد',
  tier_min_count: 'الشريحة (أقل عدد)',
  rate: 'سعر المشترك',
  amount: 'المبلغ',
  despite_warnings: 'رغم التحذير',
  reason: 'السبب',
  note: 'النص',
  field: 'الحقل',
  source: 'المصدر',
  pin_id: 'رقم التثبيت',
  field_changed: 'تغيّرت القيمة',
  reasons_added: 'أسباب أُضيفت',
  reasons_not_applicable: 'أسباب لم تعد تنطبق',
  numbers_edited_resolved: 'اكتمل تثبيت الأرقام',
  // specs/011
  deleted: 'حُذفت البيانات',
  pin_count: 'عدد التثبيتات',
  // specs/014 (the legacy import counts; never a phone or family number)
  file_name: 'الملف',
  rows: 'عدد الصفوف',
  imported: 'المستورد',
  skipped: 'المتخطّى',
  already_imported: 'مستورد سابقاً',
  not_counted: 'لا يُحسب في الفحص',
  incomplete: 'غير مكتمل',
  corrected: 'أرقام عائلية مصحّحة',
  // specs/015 (the SAS import counts; never a username, phone or name)
  added: 'المضاف',
  updated: 'المحدَّث',
  unchanged: 'بلا تغيير',
  missing_marked: 'وُسم «غير موجود في آخر ملف»',
  missing_cleared: 'عاد في هذا الملف',
  without_phone: 'بلا هاتف صالح',
  prefixes_mapped: 'بادئات رُبطت',
};

export const STATE_LABELS = { active: 'فعّال', inactive: 'موقوف' } as const;

// --- admin review (specs/010) ---

export const REQUEST_TYPE_LABELS = {
  new: 'جديد',
  additional: 'اشتراك إضافي',
  return: 'إعادة للخدمة',
} as const;

/** Pending reasons as the admin sees them (system.md §10 item 2). */
export const REASON_LABELS = {
  family_exists: 'اشتراك إضافي',
  return: 'إعادة للخدمة',
  numbers_edited: 'تعديل الأرقام',
  numbers_conflict: 'تعارض بالأرقام',
} as const;

/** «لم يعد ينطبق» / «تم التثبيت»; an open reason has no label. */
export const REASON_STATE_LABELS = {
  open: null,
  resolved: 'تم التثبيت',
  not_applicable: 'لم يعد ينطبق',
} as const;

/** Why a record is linked (system.md §6.4). */
export function linkBasisLabel(reason: string, basis: string | null): string {
  if (reason === 'return')
    return basis === 'phone' ? 'إعادة للخدمة بالهاتف' : 'إعادة للخدمة بالرقم الوطني والعائلي';
  if (reason === 'numbers_conflict') return 'تعارض بالأرقام';
  return 'عائلة موجودة';
}

export const SOURCE_LABELS: Record<string, string> = {
  sijil: 'سِجلّ',
  legacy: 'مشترك قديم',
  sas: 'مشترك SAS',
};

export type { Role };

/** The fixed rejection reasons (system.md v1.14 §6.4); mirrors api/app/core/rejection_reasons.py. */
export const REJECTION_REASON_LABELS = {
  card_unclear: 'صورة البطاقة غير واضحة',
  numbers_mismatch: 'الأرقام غير مطابقة للبطاقة',
  under_15_days: 'المتبقي من الاشتراك الأول أقل من 15 يوماً',
  active_subscription: 'المشترك لديه اشتراك فعّال',
  other: 'سبب آخر',
} as const;

export const REJECTION_NOTE_MIN = 3;
export const REJECTION_NOTE_MAX = 300;

/** The review warnings (system.md v1.14 §6.4, specs/010 FR-019a), short form (audit, dialogs). */
export const WARNING_LABELS = {
  same_person: 'نفس الشخص',
  id_conflict: 'تعارض بالأرقام',
  return_target_lost: 'لم تعد الأرقام تطابق المشترك المرتبط',
} as const;

/** The red alert on the review file, one line per warning (specs/010 FR-019a). */
export const WARNING_ALERT_LABELS = {
  same_person: 'تحذير: الأرقام المثبّتة تطابق مشتركاً موجوداً (نفس الشخص)',
  id_conflict: 'تحذير: الرقم الوطني يطابق مشتركاً آخر برقم عائلي مختلف',
  return_target_lost: 'تحذير: أرقام طلب العودة لم تعد تطابق المشترك المرتبط',
} as const;

/** Where a pinned number came from (specs/010 research R4). */
export const PIN_SOURCE_LABELS = {
  reading: 'قراءة البطاقة',
  mrz: 'MRZ',
  marketer: 'قيمة المسوّق',
  typed: 'قيمة أخرى',
} as const;

export const PIN_FIELD_LABELS = {
  national_id: 'الرقم الوطني',
  family_number: 'الرقم العائلي',
} as const;

/** The fixed deletion reasons (system.md v1.15 §7.4); mirrors api/app/core/deletion_reasons.py. */
export const DELETION_REASON_LABELS = {
  duplicate: 'طلب مكرر',
  test: 'طلب تجريبي',
  entry_error: 'خطأ إدخال',
  other: 'سبب آخر',
} as const;
export type DeletionReason = keyof typeof DELETION_REASON_LABELS;

/** The fixed reasons to undo «تم الربط» (system.md v1.18 §6.5); mirrors api/app/core/unlink_reasons.py. */
export const UNLINK_REASON_LABELS = {
  not_linked_in_sas: 'لم يُربط فعلياً في SAS',
  by_mistake: 'ضُغط بالخطأ',
  other_request_linked: 'ربط طلب آخر بدله',
  other: 'سبب آخر',
} as const;
export type UnlinkReason = keyof typeof UNLINK_REASON_LABELS;
