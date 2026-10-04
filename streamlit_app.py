
import streamlit as st
import sqlite3
import pandas as pd
import io

# 1. إعدادات الصفحة
st.set_page_config(page_title="نظام إدارة المخزن", layout="wide")
st.title("📦 نظام إدارة مخزن قطع الغيار")

# 2. الاتصال بقاعدة البيانات
conn = sqlite3.connect("inventory.db", check_same_thread=False)
cursor = conn.cursor()

# 3. مسح الأقسام القديمة نهائياً وإعادة إنشاء الجداول
cursor.execute("DROP TABLE IF EXISTS categories")  # السطر ده بيمسح كل الأقسام القديمة
cursor.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT,
        category_id INTEGER,
        wholesale_price REAL,
        retail_price REAL,
        quantity INTEGER,
        FOREIGN KEY (category_id) REFERENCES categories (id)
    )
""")
conn.commit()

# 4. الأقسام الجديدة فقط (اكتب الأقسام التي تريدها هنا فقط)
DEFAULT_CATS = [
    "ثلاجه",
    "غساله هاف",
    "غساله فوق اتوماتك",
    "غساله اتوماتك",
    "ديب فليزر",
    "مراوح",
    "تكييف",
    "سخان غاز",
    "سخان كهربائي",
    "شفاط",
]

for cat in DEFAULT_CATS:
    cursor.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
conn.commit()

# 5. القائمة الجانبية (إدارة المخزون والعمليات)
st.sidebar.header("⚙️ إدارة المخزون")
action = st.sidebar.selectbox("اختر العملية:", [
    "➕ إضافة قطعة جديدة",
    "💰 بيع / سحب قطعة",
    "📥 إعادة تزويد (Restock)",
    "❌ حذف قطعة"
])

cursor.execute("SELECT name FROM categories")
cat_list = [row[0] for row in cursor.fetchall()]

if action == "➕ إضافة قطعة جديدة":
    st.sidebar.subheader("إضافة قطعة")
    p_id = st.sidebar.text_input("كود القطعة (ID)")
    p_name = st.sidebar.text_input("اسم القطعة")
    selected_cat = st.sidebar.selectbox("القسم", cat_list)
    cost = st.sidebar.number_input("سعر الجملة", min_value=0.0)
    price = st.sidebar.number_input("سعر البيع", min_value=0.0)
    qty = st.sidebar.number_input("الكمية الأوليّة", min_value=0, step=1)

    if st.sidebar.button("حفظ القطعة"):
        if p_id and p_name:
            cursor.execute("SELECT id FROM categories WHERE name = ?", (selected_cat,))
            res = cursor.fetchone()
            if res:
                cat_id = res[0]
                try:
                    cursor.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?)", (p_id, p_name, cat_id, cost, price, qty))
                    conn.commit()
                    st.sidebar.success("تمت الإضافة بنجاح!")
                    st.rerun()
                except Exception:
                    st.sidebar.error("كود القطعة موجود مسبقاً!")
        else:
            st.sidebar.warning("يرجى إدخال الكود والاسم.")

elif action == "💰 بيع / سحب قطعة":
    st.sidebar.subheader("سحب كمية")
    sell_id = st.sidebar.text_input("كود القطعة المراد سحبها")
    sell_qty = st.sidebar.number_input("الكمية المسحوبة", min_value=1, step=1)

    if st.sidebar.button("تأكيد السحب"):
        cursor.execute("SELECT quantity FROM products WHERE id = ?", (sell_id,))
        res = cursor.fetchone()
        if res:
            current_qty = res[0]
            if current_qty >= sell_qty:
                cursor.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (sell_qty, sell_id))
                conn.commit()
                st.sidebar.success(f"تم سحب {sell_qty} قطع بنجاح!")
                st.rerun()
            else:
                st.sidebar.error(f"الكمية المتاحة فقط هي {current_qty}")
        else:
            st.sidebar.error("كود القطعة غير موجود!")

elif action == "📥 إعادة تزويد (Restock)":
    st.sidebar.subheader("تزويد رصيد")
    restock_id = st.sidebar.text_input("كود القطعة")
    restock_qty = st.sidebar.number_input("الكمية المضافة", min_value=1, step=1)

    if st.sidebar.button("تأكيد التزويد"):
        cursor.execute("SELECT id FROM products WHERE id = ?", (restock_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (restock_qty, restock_id))
            conn.commit()
            st.sidebar.success("تم تحديث الكمية بنجاح!")
            st.rerun()
        else:
            st.sidebar.error("كود القطعة غير موجود!")

elif action == "❌ حذف قطعة":
    st.sidebar.subheader("حذف قطعة نهائياً")
    del_id = st.sidebar.text_input("كود القطعة للمسح")

    if st.sidebar.button("حذف القطعة"):
        cursor.execute("SELECT id FROM products WHERE id = ?", (del_id,))
        if cursor.fetchone():
            cursor.execute("DELETE FROM products WHERE id = ?", (del_id,))
            conn.commit()
            st.sidebar.success("تم الحذف بنجاح!")
            st.rerun()
        else:
            st.sidebar.error("الكود غير موجود!")

# 6. الشاشة الرئيسية: البحث وإدارة المنتجات
st.subheader("🔍 البحث وإدارة المنتجات")

col1, col2 = st.columns([2, 1])
with col1:
    search = st.text_input("ابحث بالكود أو اسم القطعة:")
with col2:
    filter_cat = st.selectbox("تصفية حسب القسم:", ["الكل"] + cat_list)

query = """
    SELECT
        p.id AS 'الكود',
        p.name AS 'اسم القطعة',
        c.name AS 'القسم',
        p.wholesale_price AS 'سعر الجملة',
        p.retail_price AS 'سعر البيع',
        p.quantity AS 'الكمية'
    FROM products p
    JOIN categories c ON p.category_id = c.id
    WHERE 1=1
"""

if search:
    query += f" AND (p.id LIKE '%{search}%' OR p.name LIKE '%{search}%')"
if filter_cat != "الكل":
    query += f" AND c.name = '{filter_cat}'"

df = pd.read_sql_query(query, conn)

# عرض إحصائيات سريعة
st.markdown("---")
m1, m2, m3 = st.columns(3)
m1.metric("إجمالي أنواع القطع", len(df))
m2.metric("إجمالي القطع بالمخزن", int(df['الكمية'].sum()) if not df.empty else 0)
m3.metric("قطع أوشكت على النفاد (<5)", len(df[df['الكمية'] < 5]) if not df.empty else 0)

# أزرار تصدير التقارير (Excel)
st.markdown("### 📥 تصدير التقارير")
btn_col1, btn_col2 = st.columns(2)

output = io.BytesIO()
with pd.ExcelWriter(output, engine='openpyxl') as writer:
    df.to_excel(writer, index=False, sheet_name='المخزون_الفعلي')
processed_data = output.getvalue()

with btn_col1:
    st.download_button(
        label="📊 تحميل تقرير المخزن بالكامل (Excel)",
        data=processed_data,
        file_name='تقرير_المخزن.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

with btn_col2:
    df_low_stock = df[df['الكمية'] < 5]
    output_low = io.BytesIO()
    with pd.ExcelWriter(output_low, engine='openpyxl') as writer:
        df_low_stock.to_excel(writer, index=False, sheet_name='نواقص_المخزن')
    processed_low_data = output_low.getvalue()

    st.download_button(
        label="⚠️ تحميل تقرير القطع الأوشكت على النفاد (Excel)",
        data=processed_low_data,
        file_name='تقرير_النواقص.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

# عرض الجدول الرئيسي
st.dataframe(df, use_container_width=True)
