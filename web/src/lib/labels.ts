/** Arabic labels for permissions, audit actions and audit fields (specs/002 data-model.md). */
import type { Role } from './api';

export const PERMISSIONS = [
  'review',
  'link',
  'settings',
  'marketers',
  'reports',
  'commissions',
] as const;
export type Permission = (typeof PERMISSIONS)[number];

export const PERMISSION_LABELS: Record<Permission, string> = {
  review: 'مراجعة الطلبات (قبول/رفض)',
  link: 'تم الربط والتراجع عنه',
  settings: 'الإعدادات والأسعار والشرائح',
  marketers: 'إدارة المسوّقين وتصفير كلمات السر',
  reports: 'التقارير والتصدير والاستيراد',
  commissions: 'العمولات وزر تم الدفع',
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
};

export const STATE_LABELS = { active: 'فعّال', inactive: 'موقوف' } as const;

export type { Role };
