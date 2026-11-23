# Quickstart: validating 009

Prerequisites: the stack from 008 (`docker compose up`), the dev OTP sender, a marketer account and
an admin with `settings`. Use only made-up card values, such as national ID `199000000001` and family
number `1234A5678901234567` (no real cards).

## Automated

```bash
docker compose exec api pytest tests/unit/test_decision.py tests/unit/test_matches.py
docker compose exec api pytest tests/integration/test_return_path.py tests/integration/test_numbers_conflict.py tests/integration/test_admin_whatsapp.py
docker compose exec api pytest            # full suite, including 008 regressions
cd web && npm test
bash scripts/e2e.sh admin-first-login.spec.ts submit.spec.ts subscriber-existing.spec.ts
```

## Manual scenarios (expected results)

1. **Return by identity**:
   - Submit request A with phone P1 and the two numbers.
   - In a new draft, enter the same numbers. You see «المشترك لديه اشتراك سابق» and
     «طلب العودة للخدمة».
   - Choose it, verify P1 (allowed) and submit. Expected: «بانتظار موافقة المسؤول», type return.
2. **Return by phone**: in a new draft with new numbers, enter P1 and press «تحقّق». Expected: no code
   is sent, and both buttons are shown. «طلب العودة للخدمة» then allows P1.
3. **Phone of A, card of B**: the return is offered for B, and P1 is refused.
4. **Pending block**: while the return from step 1 is pending, try a second return for the same
   person. Expected: «يوجد طلب سابق بالانتظار لهذا المشترك».
5. **Conflict**: same national ID with another family number. Expected: the notice appears, sending
   works, and the request has reason «تعارض بالأرقام».
6. **Second subscription**: same family number, new national ID. Expected: the button reads
   «إضافة اشتراك ثاني» (008 flow).
7. **Contact admin**:
   - With the setting empty, the button is disabled with its message.
   - Set the number in «الإعدادات ← عام». The button then opens WhatsApp with the marketer's name
     only, and the audit log shows `draft.contact_admin_opened`.
8. **Dashboard**: «إضافة اشتراك لمشترك موجود» opens a new form.
9. **Privacy**: in the browser network tab, no response in steps 1–7 holds A's name, phone, username,
   tower or numbers.

See [contracts/api.md](./contracts/api.md) and [data-model.md](./data-model.md).
