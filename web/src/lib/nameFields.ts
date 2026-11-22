/** The nine name fields of the ministry form, in page order (docs/system.md §5.1 v1.5). */
export const NAME_FIELDS = [
  'first_name',
  'father_name',
  'grandfather_name',
  'great_grandfather_name',
  'surname',
  'mother_first_name',
  'mother_second_name',
  'mother_third_name',
  'mother_surname',
] as const;

export type NameField = (typeof NAME_FIELDS)[number];

export const OPTIONAL_NAME_FIELDS: readonly NameField[] = ['mother_third_name', 'mother_surname'];

export const REQUIRED_NAME_FIELDS = NAME_FIELDS.filter(
  (f) => !OPTIONAL_NAME_FIELDS.includes(f),
) as Exclude<NameField, 'mother_third_name' | 'mother_surname'>[];

export const NAME_MAX = 50;

export const NAME_LABELS: Record<NameField, string> = {
  first_name: 'الاسم الأول',
  father_name: 'الاسم الثاني',
  grandfather_name: 'الاسم الثالث',
  great_grandfather_name: 'الاسم الرابع',
  surname: 'اسم العائلة (اللقب)',
  mother_first_name: 'اسم الأم الأول',
  mother_second_name: 'اسم الأم الثاني',
  mother_third_name: 'اسم الأم الثالث',
  mother_surname: 'لقب الأم',
};

export const isNameField = (field: string): field is NameField =>
  (NAME_FIELDS as readonly string[]).includes(field);

export type NameValues = Record<NameField, string>;
export type NullableNames = Record<NameField, string | null>;
