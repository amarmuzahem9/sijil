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
};

export const AUDIT_FIELD_LABELS: Record<string, string> = {
  name: 'الاسم',
  phone: 'الهاتف',
  role: 'الدور',
  permissions: 'الصلاحيات',
  is_active: 'الحالة',
  must_change_password: 'يجب تغيير كلمة السر',
  locked_until: 'مقفل حتى',
};

export const STATE_LABELS = { active: 'فعّال', inactive: 'موقوف' } as const;

export type { Role };
