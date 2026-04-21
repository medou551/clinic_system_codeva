#!/usr/bin/env python3
"""
إعداد سريع لمشروع العيادة الطبية.

الاستخدام:
    python setup.py
"""
import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def run(cmd: str):
    print(f"→ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main():
    print("\n🏥 إعداد مشروع العيادة الطبية\n" + "=" * 50)
    print(f"Python: {sys.version.split()[0]}")

    run(f'"{sys.executable}" -m pip install -r requirements.txt')

    db_path = BASE_DIR / 'db.sqlite3'
    if not db_path.exists():
        print("\n🗄️ إنشاء قاعدة البيانات...")
        run(f'"{sys.executable}" manage.py migrate --noinput')
        fixture = BASE_DIR / 'clinic' / 'fixtures' / 'initial_data.json'
        if fixture.exists():
            run(f'"{sys.executable}" manage.py loaddata clinic/fixtures/initial_data.json')
        run(f'"{sys.executable}" scripts/bootstrap_demo.py')
    else:
        print("\n🗄️ قاعدة البيانات موجودة مسبقًا.")

    print("\n✅ اكتمل الإعداد.")
    print("\nبيانات الدخول الجاهزة:")
    print("- لوحة Django Admin: superadmin / admin12345")
    print("- المريض: +222 30 00 00 01 / patient123")
    print("- المريض: +222 30 00 00 02 / patient123")
    print("- المدير: +222 20 00 00 01 / 222200000001")
    print("- الاستقبال: +222 20 00 00 02 / 222200000002")
    print("- المختبر: +222 20 00 00 03 / 222200000003")
    print("- الطبيب أحمد: +222 22 11 22 33 / 22222112233")
    print("\nلتشغيل الخادم:")
    print(f'  "{sys.executable}" manage.py runserver')


if __name__ == '__main__':
    main()
