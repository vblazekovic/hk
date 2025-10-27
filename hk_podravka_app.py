# -*- coding: utf-8 -*-
"""
HK Podravka – klupska web-admin aplikacija (Streamlit, 1-file .py)
Verzija: v3 – Članovi: ime/prezime odvojeno; adresa razdvojena; uređivanje, e-mail, brisanje, prikaz rezultata
Autor: ChatGPT (GPT-5 Thinking)

▶ Pokretanje lokalno:
    pip install -r requirements.txt
    streamlit run hk_podravka_full_v3.py
"""

import os
import io
import json
import sqlite3
from datetime import datetime, date, timedelta
from typing import Optional

import pandas as pd
import streamlit as st

# PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

# ==========================
# KONSTANTE KLUBA I STIL
# ==========================
PRIMARY_RED = "#c1121f"     # klupska crvena
GOLD = "#d4af37"            # zlatna
WHITE = "#ffffff"
LIGHT_BG = "#fffaf8"

KLUB_NAZIV = "Hrvački klub Podravka"
KLUB_EMAIL = "hsk-podravka@gmail.com"
KLUB_ADRESA = "Miklinovec 6a, 48000 Koprivnica"
KLUB_OIB = "60911784858"
KLUB_WEB = "https://hk-podravka.com"
KLUB_IBAN = "HR6923860021100518154"

DB_PATH = "hk_podravka.db"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ==========================
# POMOĆNE FUNKCIJE
# ==========================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # CLUB
    cur.execute("""
        CREATE TABLE IF NOT EXISTS club_info (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT, email TEXT, address TEXT, oib TEXT, web TEXT, iban TEXT,
            president TEXT, secretary TEXT,
            board_json TEXT, supervisory_json TEXT,
            instagram TEXT, facebook TEXT, tiktok TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS club_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT,
            filename TEXT,
            path TEXT,
            uploaded_at TEXT
        )
    """)

    # GROUPS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)

    # MEMBERS – add new columns if missing
    cur.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            first_name TEXT,
            last_name TEXT,
            dob TEXT,
            gender TEXT,
            oib TEXT UNIQUE,
            residence TEXT,
            street TEXT,
            city TEXT,
            postal_code TEXT,
            athlete_email TEXT,
            parent_email TEXT,
            id_card_number TEXT,
            id_card_issuer TEXT,
            id_card_valid_until TEXT,
            passport_number TEXT,
            passport_issuer TEXT,
            passport_valid_until TEXT,
            active_competitor INTEGER DEFAULT 0,
            veteran INTEGER DEFAULT 0,
            other_flag INTEGER DEFAULT 0,
            pays_fee INTEGER DEFAULT 0,
            fee_amount REAL DEFAULT 30.0,
            group_name TEXT,
            photo_path TEXT,
            consent_path TEXT,
            application_path TEXT,
            medical_path TEXT,
            medical_valid_until TEXT,
            consent_checked_date TEXT
        )
    """)
    # Safe ALTERs (SQLite doesn't support IF NOT EXISTS for columns; try/except)
    for col_def in [
        ("first_name", "TEXT"),
        ("last_name", "TEXT"),
        ("street", "TEXT"),
        ("city", "TEXT"),
        ("postal_code", "TEXT"),
    ]:
        try:
            cur.execute(f"ALTER TABLE members ADD COLUMN {col_def[0]} {col_def[1]}")
        except sqlite3.OperationalError:
            pass

    # COACHES
    cur.execute("""
        CREATE TABLE IF NOT EXISTS coaches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT,
            dob TEXT,
            oib TEXT,
            email TEXT,
            iban TEXT,
            group_name TEXT,
            contract_path TEXT,
            other_docs_json TEXT,
            photo_path TEXT
        )
    """)

    # COMPETITIONS / RESULTS
    cur.execute("""
        CREATE TABLE IF NOT EXISTS competitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT,
            kind_other TEXT,
            name TEXT,
            date_from TEXT,
            date_to TEXT,
            place TEXT,
            style TEXT,
            age_cat TEXT,
            country TEXT,
            country_iso3 TEXT,
            team_rank INTEGER,
            club_competitors INTEGER,
            total_competitors INTEGER,
            clubs_count INTEGER,
            countries_count INTEGER,
            coaches_json TEXT,
            notes TEXT,
            bulletin_url TEXT,
            gallery_paths_json TEXT,
            website_link TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            competition_id INTEGER REFERENCES competitions(id) ON DELETE CASCADE,
            member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
            category TEXT,
            style TEXT,
            fights_total INTEGER,
            wins INTEGER,
            losses INTEGER,
            placement INTEGER,
            wins_detail_json TEXT,
            losses_detail_json TEXT,
            note TEXT
        )
    """)

    # ATTENDANCE
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance_coaches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coach_id INTEGER REFERENCES coaches(id) ON DELETE SET NULL,
            group_name TEXT,
            start_time TEXT,
            end_time TEXT,
            place TEXT,
            minutes INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id INTEGER REFERENCES members(id) ON DELETE CASCADE,
            date TEXT,
            group_name TEXT,
            present INTEGER DEFAULT 0,
            minutes INTEGER DEFAULT 0,
            note TEXT,
            camp_flag INTEGER DEFAULT 0,
            camp_where TEXT,
            camp_coach TEXT
        )
    """)

    # COMMUNICATION
    cur.execute("""
        CREATE TABLE IF NOT EXISTS comm_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            subject TEXT,
            body TEXT,
            recipients_json TEXT
        )
    """)

    # seed club row
    cur.execute("SELECT 1 FROM club_info WHERE id=1")
    if cur.fetchone() is None:
        cur.execute("""INSERT INTO club_info
            (id, name, email, address, oib, web, iban, president, secretary, board_json, supervisory_json, instagram, facebook, tiktok)
            VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (KLUB_NAZIV, KLUB_EMAIL, KLUB_ADRESA, KLUB_OIB, KLUB_WEB, KLUB_IBAN, "", "", "[]", "[]", "", "", "")
        )

    conn.commit()
    conn.close()

def css_style():
    st.markdown(
        f"""
        <style>
        .app-header {{
            background: linear-gradient(90deg, {PRIMARY_RED}, {GOLD});
            color: {WHITE};
            padding: 16px 20px;
            border-radius: 16px;
            margin-bottom: 16px;
        }}
        .card {{
            background: {LIGHT_BG};
            border: 1px solid #f0e6da;
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 12px;
        }}
        .danger {{ color: #b00020; font-weight: 700; }}
        .ok {{ color: #0b7a0b; font-weight: 700; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

def page_header(title: str, subtitle: Optional[str] = None):
    st.markdown(
        f"<div class='app-header'><h2 style='margin:0'>{title}</h2>" +
        (f"<div>{subtitle}</div>" if subtitle else "") +
        "</div>", unsafe_allow_html=True
    )

# ==============
# PDF GENERATOR
# ==============
def register_font():
    font_path = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))
            return "DejaVuSans"
        except Exception:
            pass
    return None

def _pdf_text_wrapped(c, text, x, y, max_width, line_height, font_name, font_size):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    words = text.split()
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        if stringWidth(test, font_name, font_size) <= max_width:
            line = test
        else:
            c.drawString(x, y, line)
            y -= line_height
            line = w
    if line:
        c.drawString(x, y, line)
        y -= line_height
    return y

def make_pdf_membership(full_name: str, dob: str, oib: str) -> bytes:
    font_reg = register_font()
    font_name = font_reg if font_reg else "Helvetica"

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin = 20 * mm
    c.setFont(font_name, 14)
    c.drawString(margin, height - margin, f"{full_name} – {dob} – OIB: {oib}")

    c.setFont(font_name, 10)
    y = height - margin - 24
    header = (
        "HRVAČKI KLUB ‘PODRAVKA’ 48000 Koprivnica, Miklinovec 6a, mob:091/456-23-21 "
        "web site: www.hk-podravka.hr, e-mail: hsk.podravka@gmail.com "
        "………………………………………………………………………………………………………………………………………………………….. "
        "………………………………………………………………………………………………………………………………………………………….. "
        f"OIB:{KLUB_OIB}, žiro-račun: {KLUB_IBAN}, Podravska banka d.d. Koprivnica"
    )
    y = _pdf_text_wrapped(c, header, margin, y, width - 2*margin, 14, font_name, 10)

    statute_text = (
        "STATUT KLUBA - ČLANSTVO (sažeto)...\n"
        "ČLANARINA JE OBVEZUJUĆA TIJEKOM CIJELE GODINE (12 MJESECI)...\n"
        "IZJAVA O ODGOVORNOSTI ...\n"
        "POTPIS ČLANA / RODITELJA ..."
    )
    y = _pdf_text_wrapped(c, statute_text, margin, y, width - 2*margin, 14, font_name, 10)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

def make_pdf_consent(full_name: str, oib: str, dob: str) -> bytes:
    font_reg = register_font()
    font_name = font_reg if font_reg else "Helvetica"

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 20 * mm

    header = f"PRIVOLA – {full_name} (OIB: {oib}, datum rođenja: {dob})"
    c.setFont(font_name, 14)
    c.drawString(margin, height - margin, header)

    c.setFont(font_name, 10)
    y = height - margin - 24

    consent_text = "GDPR privola (sažeto) – vrijedi do opoziva..."
    y = _pdf_text_wrapped(c, consent_text, margin, y, width - 2*margin, 14, font_name, 10)

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()

# ==========================
# EXCEL PREDLOŠCI
# ==========================
def excel_bytes_from_df(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

def members_template_df() -> pd.DataFrame:
    cols = [
        "ime","prezime","datum_rodenja(YYYY-MM-DD)","spol(M/Ž)","oib",
        "ulica_broj","mjesto","postanski_broj",
        "email_sportasa","email_roditelja",
        "br_osobne","osobna_izdavatelj","osobna_vrijedi_do(YYYY-MM-DD)",
        "br_putovnice","putovnica_izdavatelj","putovnica_vrijedi_do(YYYY-MM-DD)",
        "aktivni_natjecatelj(0/1)","veteran(0/1)","ostalo(0/1)",
        "placa_clanarinu(0/1)","iznos_clanarine(EUR)","grupa",
    ]
    return pd.DataFrame(columns=cols)

# ==========================
# UI POMOĆNICI
# ==========================
def save_uploaded_file(uploaded, subdir: str) -> str:
    if not uploaded:
        return ""
    fn = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded.name}"
    path = os.path.join(UPLOAD_DIR, subdir)
    os.makedirs(path, exist_ok=True)
    full = os.path.join(path, fn)
    with open(full, "wb") as f:
        f.write(uploaded.getbuffer())
    return full

def mailto_link(to: str, subject: str = "", body: str = "") -> str:
    import urllib.parse as up
    q = {}
    if subject: q["subject"] = subject
    if body: q["body"] = body
    qp = up.urlencode(q)
    return f"mailto:{to}?{qp}" if qp else f"mailto:{to}"

def whatsapp_link(phone: str, text: str = "") -> str:
    import urllib.parse as up
    return f"https://wa.me/{''.join(filter(str.isdigit, phone))}?text={up.quote(text)}"

# ==========================
# ODJELJCI
# ==========================
def section_club():
    page_header("Klub – osnovni podaci", KLUB_NAZIV)

    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM club_info WHERE id=1", conn)
    if df.empty:
        conn.execute(
            "INSERT OR REPLACE INTO club_info (id, name, email, address, oib, web, iban, instagram, facebook, tiktok) VALUES (1,?,?,?,?,?,?,?, ?, ?)",
            (KLUB_NAZIV, KLUB_EMAIL, KLUB_ADRESA, KLUB_OIB, KLUB_WEB, KLUB_IBAN, "", "", ""),
        )
        conn.commit()
        df = pd.read_sql_query("SELECT * FROM club_info WHERE id=1", conn)

    row = df.iloc[0]

    # helpers to load JSON grids if exist
    def _df_from_json(s):
        try:
            d = pd.read_json(s)
            if isinstance(d, pd.DataFrame):
                return d
        except Exception:
            pass
        return pd.DataFrame(columns=["ime_prezime","telefon","email"])

    board_prefill = _df_from_json(row.get("board_json", "[]"))
    superv_prefill = _df_from_json(row.get("supervisory_json", "[]"))

    with st.form("club_form"):
        c1, c2 = st.columns(2)
        name = c1.text_input("KLUB (IME)", row["name"] or "")
        address = c1.text_input("ULICA I KUĆNI BROJ, GRAD I POŠTANSKI BROJ", row["address"] or "")
        email = c1.text_input("E-mail", row["email"] or "")
        web = c1.text_input("Web stranica", row["web"] or "")
        iban = c1.text_input("IBAN račun", row["iban"] or "")
        oib = c1.text_input("OIB", row["oib"] or "")

        president = c2.text_input("Predsjednik kluba", row["president"] or "")
        secretary = c2.text_input("Tajnik kluba", row["secretary"] or "")

        st.markdown("**Članovi predsjedništva**")
        board = st.data_editor(board_prefill if not board_prefill.empty else pd.DataFrame(columns=["ime_prezime","telefon","email"]), num_rows="dynamic", key="board_editor")

        st.markdown("**Nadzorni odbor**")
        superv = st.data_editor(superv_prefill if not superv_prefill.empty else pd.DataFrame(columns=["ime_prezime","telefon","email"]), num_rows="dynamic", key="superv_editor")

        st.markdown("**Društvene mreže (linkovi)**")
        c3, c4, c5 = st.columns(3)
        instagram = c3.text_input("Instagram", row["instagram"] or "")
        facebook = c4.text_input("Facebook", row["facebook"] or "")
        tik_tok = c5.text_input("TikTok", row["tiktok"] or "")

        st.markdown("**Dokumenti kluba** – upload statuta ili drugih dokumenata")
        up_statut = st.file_uploader("Statut kluba (PDF)", type=["pdf"], key="statut")
        up_other = st.file_uploader("Drugi dokument (PDF/IMG)", type=["pdf", "png", "jpg", "jpeg"], key="ostalo")

        submitted = st.form_submit_button("Spremi podatke kluba")

    if submitted:
        conn.execute(
            """
            UPDATE club_info SET name=?, email=?, address=?, oib=?, web=?, iban=?, president=?, secretary=?, board_json=?, supervisory_json=?, instagram=?, facebook=?, tiktok=? WHERE id=1
            """,
            (
                name, email, address, oib, web, iban,
                president, secretary,
                (board if isinstance(board, pd.DataFrame) else pd.DataFrame(board)).to_json(),
                (superv if isinstance(superv, pd.DataFrame) else pd.DataFrame(superv)).to_json(),
                instagram, facebook, tik_tok,
            ),
        )
        if up_statut:
            path = save_uploaded_file(up_statut, "club_docs")
            conn.execute("INSERT INTO club_docs(kind, filename, path, uploaded_at) VALUES (?,?,?,?)", ("statut", up_statut.name, path, datetime.now().isoformat()))
        if up_other:
            path = save_uploaded_file(up_other, "club_docs")
            conn.execute("INSERT INTO club_docs(kind, filename, path, uploaded_at) VALUES (?,?,?,?)", ("ostalo", up_other.name, path, datetime.now().isoformat()))
        conn.commit()
        st.success("Podaci kluba spremljeni.")

    docs = pd.read_sql_query("SELECT id, kind, filename, uploaded_at FROM club_docs ORDER BY uploaded_at DESC", conn)
    if not docs.empty:
        st.markdown("### Dokumenti kluba")
        st.dataframe(docs, use_container_width=True)

    conn.close()

def section_members():
    page_header("Članovi", "Učlanjenja, uređivanje i rezultati")

    conn = get_conn()

    st.markdown("#### Predložak Excel tablice za učlanjenja")
    df_t = members_template_df()
    st.download_button("Skini predložak (Excel)", data=excel_bytes_from_df(df_t, "ClanoviPredlozak"), file_name="clanovi_predlozak_v3.xlsx")

    st.markdown("#### Učitaj članove iz Excel tablice")
    up_excel = st.file_uploader("Upload Excel (po predlošku v3)", type=["xlsx"])
    if up_excel is not None:
        try:
            df_up = pd.read_excel(up_excel)
            for _, r in df_up.iterrows():
                # Accept both new and legacy columns
                first_name = str(r.get("ime", r.get("ime_prezime","").split(" ")[0])) or ""
                last_name = str(r.get("prezime", " ".join(str(r.get("ime_prezime","")).split(" ")[1:]))) or ""
                full_name = (first_name + " " + last_name).strip()
                street = str(r.get("ulica_broj", ""))
                city = str(r.get("mjesto", ""))
                postal_code = str(r.get("postanski_broj", ""))
                residence = ", ".join([p for p in [street, postal_code, city] if p])

                conn.execute(
                    """
                    INSERT INTO members(full_name, first_name, last_name, dob, gender, oib, residence, street, city, postal_code,
                                        athlete_email, parent_email,
                                        id_card_number, id_card_issuer, id_card_valid_until,
                                        passport_number, passport_issuer, passport_valid_until,
                                        active_competitor, veteran, other_flag, pays_fee, fee_amount, group_name)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(oib) DO UPDATE SET
                        full_name=excluded.full_name, first_name=excluded.first_name, last_name=excluded.last_name,
                        dob=excluded.dob, gender=excluded.gender, residence=excluded.residence, street=excluded.street,
                        city=excluded.city, postal_code=excluded.postal_code, athlete_email=excluded.athlete_email,
                        parent_email=excluded.parent_email, id_card_number=excluded.id_card_number,
                        id_card_issuer=excluded.id_card_issuer, id_card_valid_until=excluded.id_card_valid_until,
                        passport_number=excluded.passport_number, passport_issuer=excluded.passport_issuer,
                        passport_valid_until=excluded.passport_valid_until, active_competitor=excluded.active_competitor,
                        veteran=excluded.veteran, other_flag=excluded.other_flag, pays_fee=excluded.pays_fee,
                        fee_amount=excluded.fee_amount, group_name=excluded.group_name
                    """,
                    (
                        full_name, first_name, last_name, str(r.get("datum_rodenja(YYYY-MM-DD)", ""))[:10], str(r.get("spol(M/Ž)", "")),
                        str(r.get("oib","")), residence, street, city, postal_code,
                        str(r.get("email_sportasa","")), str(r.get("email_roditelja","")),
                        str(r.get("br_osobne","")), str(r.get("osobna_izdavatelj","")), str(r.get("osobna_vrijedi_do(YYYY-MM-DD)",""))[:10],
                        str(r.get("br_putovnice","")), str(r.get("putovnica_izdavatelj","")), str(r.get("putovnica_vrijedi_do(YYYY-MM-DD)",""))[:10],
                        int(r.get("aktivni_natjecatelj(0/1)", 0)), int(r.get("veteran(0/1)", 0)), int(r.get("ostalo(0/1)", 0)),
                        int(r.get("placa_clanarinu(0/1)", 0)), float(r.get("iznos_clanarine(EUR)", 30)), str(r.get("grupa",""))
                    ),
                )
            conn.commit()
            st.success("Članovi uvezeni/ažurirani iz Excela.")
        except Exception as e:
            st.error(f"Greška pri uvozu: {e}")

    st.markdown("---")
    st.markdown("### Novi/uredi člana")

    groups = pd.read_sql_query("SELECT name FROM groups ORDER BY name", conn)["name"].tolist()
    groups_opts = [""] + groups

    with st.form("member_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        first_name = c1.text_input("Ime")
        last_name = c2.text_input("Prezime")
        dob = c1.date_input("Datum rođenja", value=date(2010,1,1))
        gender = c2.selectbox("Spol", ["M", "Ž"])
        oib = c3.text_input("OIB")

        st.markdown("**Adresa**")
        a1, a2, a3 = st.columns(3)
        street = a1.text_input("Ulica i kućni broj")
        city = a2.text_input("Mjesto (grad/općina)")
        postal_code = a3.text_input("Poštanski broj")

        c4, c5 = st.columns(2)
        athlete_email = c4.text_input("E-mail sportaša")
        parent_email = c5.text_input("E-mail roditelja")

        st.markdown("**Dokumenti**")
        id_card_number = st.text_input("Broj osobne iskaznice")
        id_card_issuer = st.text_input("Tko je izdao osobnu")
        id_card_valid_until = st.date_input("Osobna vrijedi do", value=date.today())
        passport_number = st.text_input("Broj putovnice")
        passport_issuer = st.text_input("Tko je izdao putovnicu")
        passport_valid_until = st.date_input("Putovnica vrijedi do", value=date.today())

        st.markdown("**Status i grupa**")
        s1, s2, s3 = st.columns(3)
        active = s1.checkbox("Aktivni natjecatelj/ica", value=False)
        veteran = s2.checkbox("Veteran", value=False)
        other = s3.checkbox("Ostalo", value=False)
        pays_fee = st.checkbox("Plaća članarinu", value=False)
        fee_amount = st.number_input("Iznos članarine (EUR)", value=30.0, step=1.0)
        group_name = st.selectbox("Grupa", options=groups_opts)

        photo = st.file_uploader("Slika člana", type=["png","jpg","jpeg"])

        st.markdown("**Privola i liječničko**")
        consent_checked = st.checkbox("Roditelj/sportaš je pročitao privolu i slaže se s uvjetima (digitalna kvačica)")
        medical_valid_until = st.date_input("Liječnička potvrda vrijedi do", value=date.today())
        up_medical = st.file_uploader("Upload liječničke potvrde (PDF/JPG)", type=["pdf","png","jpg","jpeg"], key="medical")

        submit_member = st.form_submit_button("Spremi člana i generiraj pristupnicu/privolu")

    if submit_member:
        full_name = (first_name + " " + last_name).strip()
        residence = ", ".join([p for p in [street, postal_code, city] if p])
        photo_path = save_uploaded_file(photo, "members/photos") if photo else ""
        medical_path = save_uploaded_file(up_medical, "members/medical") if up_medical else ""
        consent_date = datetime.now().date().isoformat() if consent_checked else None

        conn.execute(
            """
            INSERT INTO members(full_name, first_name, last_name, dob, gender, oib, residence, street, city, postal_code,
                                athlete_email, parent_email,
                                id_card_number, id_card_issuer, id_card_valid_until, passport_number, passport_issuer, passport_valid_until,
                                active_competitor, veteran, other_flag, pays_fee, fee_amount, group_name, photo_path, medical_path, medical_valid_until, consent_checked_date)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(oib) DO UPDATE SET
                full_name=excluded.full_name, first_name=excluded.first_name, last_name=excluded.last_name, dob=excluded.dob, gender=excluded.gender,
                residence=excluded.residence, street=excluded.street, city=excluded.city, postal_code=excluded.postal_code,
                athlete_email=excluded.athlete_email, parent_email=excluded.parent_email,
                id_card_number=excluded.id_card_number, id_card_issuer=excluded.id_card_issuer, id_card_valid_until=excluded.id_card_valid_until,
                passport_number=excluded.passport_number, passport_issuer=excluded.passport_issuer, passport_valid_until=excluded.passport_valid_until,
                active_competitor=excluded.active_competitor, veteran=excluded.veteran, other_flag=excluded.other_flag,
                pays_fee=excluded.pays_fee, fee_amount=excluded.fee_amount, group_name=excluded.group_name,
                photo_path=COALESCE(excluded.photo_path, photo_path), medical_path=COALESCE(excluded.medical_path, medical_path), medical_valid_until=excluded.medical_valid_until,
                consent_checked_date=excluded.consent_checked_date
            """,
            (
                full_name, first_name, last_name, dob.isoformat(), gender, oib, residence, street, city, postal_code,
                athlete_email, parent_email,
                id_card_number, id_card_issuer, id_card_valid_until.isoformat(), passport_number, passport_issuer, passport_valid_until.isoformat(),
                int(active), int(veteran), int(other), int(pays_fee), float(fee_amount), group_name, photo_path, medical_path, medical_valid_until.isoformat(), consent_date
            ),
        )
        member_id = conn.execute("SELECT id FROM members WHERE oib=?", (oib,)).fetchone()[0]
        conn.commit()

        try:
            pdf_pristupnica = make_pdf_membership(full_name, dob.isoformat(), oib)
            pdf_privola = make_pdf_consent(full_name, oib, dob.isoformat())
            app_path = os.path.join(UPLOAD_DIR, "members/forms", f"{member_id}_pristupnica.pdf")
            os.makedirs(os.path.dirname(app_path), exist_ok=True)
            with open(app_path, "wb") as f:
                f.write(pdf_pristupnica)
            cons_path = os.path.join(UPLOAD_DIR, "members/forms", f"{member_id}_privola.pdf")
            with open(cons_path, "wb") as f:
                f.write(pdf_privola)
            conn.execute("UPDATE members SET application_path=?, consent_path=? WHERE id=?", (app_path, cons_path, member_id))
            conn.commit()

            st.success("Član spremljen. Pristupnica i privola generirane.")
            st.download_button("Skini pristupnicu (PDF)", data=pdf_pristupnica, file_name=f"pristupnica_{member_id}.pdf")
            st.download_button("Skini privolu (PDF)", data=pdf_privola, file_name=f"privola_{member_id}.pdf")
        except Exception as e:
            st.error(f"Greška pri generiranju PDF-a: {e}")

    st.markdown("---")
    st.markdown("### Popis članova (uredi / e-mail / obriši / rezultati)")

    members_df = pd.read_sql_query("""
        SELECT id, first_name, last_name, gender, dob, oib,
               street, city, postal_code,
               athlete_email, parent_email,
               group_name, pays_fee, fee_amount
        FROM members ORDER BY last_name, first_name
    """, conn)

    if not members_df.empty:
        edited = st.data_editor(
            members_df,
            num_rows="dynamic",
            use_container_width=True,
            key="members_grid"
        )
        if st.button("Spremi izmjene tablice"):
            try:
                # Upsert each row
                for _, r in edited.iterrows():
                    full_name = (str(r.get("first_name","")) + " " + str(r.get("last_name",""))).strip()
                    residence = ", ".join([str(r.get("street","")), str(r.get("postal_code","")), str(r.get("city",""))]).replace(",,",",").strip(", ")
                    conn.execute("""UPDATE members SET
                        first_name=?, last_name=?, full_name=?, gender=?, dob=?,
                        street=?, city=?, postal_code=?, residence=?,
                        athlete_email=?, parent_email=?, group_name=?, pays_fee=?, fee_amount=?
                        WHERE id=?
                    """, (
                        r.get("first_name",""), r.get("last_name",""), full_name, r.get("gender",""), str(r.get("dob",""))[:10],
                        r.get("street",""), r.get("city",""), str(r.get("postal_code","")), residence,
                        r.get("athlete_email",""), r.get("parent_email",""), r.get("group_name",""),
                        int(r.get("pays_fee",0) or 0), float(r.get("fee_amount",0) or 0.0),
                        int(r["id"])
                    ))
                conn.commit()
                st.success("Izmjene spremljene.")
            except Exception as e:
                st.error(f"Greška pri spremanju: {e}")

        st.markdown("#### Akcije nad članom")
        sel = st.selectbox("Odaberi člana", options=["-"] + [f"{r.id} – {r.first_name} {r.last_name}" for r in members_df.itertuples()], index=0)
        if sel != "-":
            member_id = int(sel.split(" – ")[0])
            m = pd.read_sql_query("SELECT * FROM members WHERE id=?", conn, params=(member_id,)).iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            if m["athlete_email"]:
                c1.link_button("E-mail sportašu", url=mailto_link(m["athlete_email"], subject="Obavijest kluba"))
            if m["parent_email"]:
                c2.link_button("E-mail roditelju", url=mailto_link(m["parent_email"], subject="Obavijest kluba"))
            if c3.button("Obriši člana"):
                conn.execute("DELETE FROM members WHERE id=?", (member_id,))
                conn.commit()
                st.success("Član obrisan.")
                st.experimental_rerun()
            c4.write("")

            st.markdown("##### Rezultati iz baze za ovog člana")
            q = """
            SELECT c.date_from AS datum, COALESCE(c.name, c.kind) AS natjecanje,
                   r.category AS kategorija, r.style AS stil,
                   r.fights_total AS borbi, r.wins AS pobjeda, r.losses AS poraza, r.placement AS plasman
            FROM results r JOIN competitions c ON r.competition_id=c.id
            WHERE r.member_id=?
            ORDER BY c.date_from DESC
            """
            res = pd.read_sql_query(q, conn, params=(member_id,))
            st.dataframe(res, use_container_width=True)

    conn.close()

def section_coaches():
    page_header("Treneri", "Ugovori, grupe, dokumenti")
    conn = get_conn()

    with st.form("coach_form"):
        c1, c2 = st.columns(2)
        full_name = c1.text_input("Ime i prezime")
        dob = c1.date_input("Datum rođenja", value=date(1990,1,1))
        oib = c1.text_input("OIB")
        email = c1.text_input("E-mail")
        iban = c1.text_input("IBAN broj računa")
        group_name = c1.text_input("Grupa koju trenira")
        contract = st.file_uploader("Ugovor s klubom (PDF)", type=["pdf"])
        other_docs = st.file_uploader("Drugi dokumenti (višestruko)", type=["pdf","png","jpg","jpeg"], accept_multiple_files=True)
        photo = st.file_uploader("Slika trenera", type=["png","jpg","jpeg"])
        submit = st.form_submit_button("Spremi trenera")

    if submit:
        contract_path = save_uploaded_file(contract, "coaches/contracts") if contract else ""
        other_paths = []
        for f in other_docs or []:
            other_paths.append(save_uploaded_file(f, "coaches/docs"))
        photo_path = save_uploaded_file(photo, "coaches/photos") if photo else ""
        conn.execute(
            "INSERT INTO coaches(full_name, dob, oib, email, iban, group_name, contract_path, other_docs_json, photo_path) VALUES(?,?,?,?,?,?,?,?,?)",
            (full_name, dob.isoformat(), oib, email, iban, group_name, contract_path, pd.Series(other_paths).to_json(), photo_path)
        )
        conn.commit()
        st.success("Trener spremljen.")

    coaches_df = pd.read_sql_query("SELECT id, full_name, email, group_name FROM coaches ORDER BY full_name", conn)
    st.dataframe(coaches_df, use_container_width=True)
    conn.close()

def section_competitions():
    page_header("Natjecanja i rezultati", "Unos, slike, bilteni, rezultati")
    conn = get_conn()

    kind = st.selectbox("Vrsta natjecanja", [
        "PRVENSTVO HRVATSKE", "MEĐUNARODNI TURNIR", "REPREZENTATIVNI NASTUP",
        "HRVAČKA LIGA ZA SENIORE", "MEĐUNARODNA HRVAČKA LIGA ZA KADETE", "REGIONALNO PRVENSTVO", "LIGA ZA DJEVOJČICE", "OSTALO"
    ])
    kind_other = ""
    if kind == "OSTALO":
        kind_other = st.text_input("Upiši vrstu natjecanja")

    name = st.text_input("Ime natjecanja (ako postoji)")
    c1, c2, c3 = st.columns(3)
    date_from = c1.date_input("Datum od", value=date.today())
    date_to = c2.date_input("Datum do", value=date.today())
    place = c3.text_input("Mjesto natjecanja")

    style = st.selectbox("Hrvački stil", ["GR", "FS", "WW", "BW", "MODIFICIRANO"])
    age = st.selectbox("Uzrast", ["POČETNICI","U11","U13","U15","U17","U20","U23","SENIORI"])

    country = st.text_input("Država (naziv)")
    iso3 = st.text_input("Država ISO-3 (upiši ručno, npr. HRV)")

    team_rank = st.number_input("Ekipni poredak (mjesto)", min_value=0, step=1)
    club_n = st.number_input("Broj natjecatelja iz kluba", min_value=0, step=1)
    total_n = st.number_input("Ukupan broj natjecatelja", min_value=0, step=1)
    clubs_n = st.number_input("Broj klubova", min_value=0, step=1)
    countries_n = st.number_input("Broj zemalja", min_value=0, step=1)

    coaches_df = pd.read_sql_query("SELECT id, full_name FROM coaches ORDER BY full_name", conn)
    coach_names = st.multiselect("Trener(i) koji su vodili", options=coaches_df["full_name"].tolist())

    notes = st.text_area("Kratko zapažanje trenera (za objave)")
    gallery = st.file_uploader("Upload slika s natjecanja", type=["png","jpg","jpeg"], accept_multiple_files=True)
    bulletin_url = st.text_input("Poveznica na rezultate / bilten")
    website_link = st.text_input("Poveznica na objavu na web stranici kluba")

    if st.button("Spremi natjecanje"):
        gallery_paths = []
        for g in gallery or []:
            gallery_paths.append(save_uploaded_file(g, "competitions/gallery"))
        conn.execute(
            """
            INSERT INTO competitions(kind, kind_other, name, date_from, date_to, place, style, age_cat, country, country_iso3, team_rank, club_competitors, total_competitors, clubs_count, countries_count, coaches_json, notes, bulletin_url, gallery_paths_json, website_link)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                kind, kind_other, name, date_from.isoformat(), date_to.isoformat(), place, style, age, country, iso3,
                int(team_rank), int(club_n), int(total_n), int(clubs_n), int(countries_n), pd.Series(coach_names).to_json(), notes, bulletin_url, pd.Series(gallery_paths).to_json(), website_link
            ),
        )
        conn.commit()
        st.success("Natjecanje spremljeno.")

    st.markdown("---")
    st.markdown("### Rezultati natjecatelja – ručni unos")

    comps = pd.read_sql_query("SELECT id, COALESCE(name, kind) AS title, date_from FROM competitions ORDER BY date_from DESC", conn)
    comp_opts = {f"{r['id']} – {r['title']} ({r['date_from']})": r['id'] for _, r in comps.iterrows()}
    comp_sel_label = st.selectbox("Odaberi natjecanje", options=["-"] + list(comp_opts.keys()))

    mems = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full FROM members ORDER BY last_name, first_name", conn)

    if comp_sel_label != "-":
        comp_id = comp_opts[comp_sel_label]
        msel = st.selectbox("Član", options=["-"] + [f"{r.id} – {r.full}" for r in mems.itertuples()])
        if msel != "-":
            mid = int(msel.split(" – ")[0])
            c1, c2, c3 = st.columns(3)
            cat = c1.text_input("Kategorija / težina")
            stl = c2.selectbox("Stil", ["GR","FS","WW","BW","MODIFICIRANO"])
            fights = c3.number_input("Ukupno borbi", min_value=0, step=1)
            w = c1.number_input("Pobjede", min_value=0, step=1)
            l = c2.number_input("Porazi", min_value=0, step=1)
            place = c3.number_input("Plasman (1–100)", min_value=0, max_value=100, step=1)
            wins_d = st.text_area("Pobjede – 'ime prezime;klub' razdvojeno | ")
            losses_d = st.text_area("Porazi – 'ime prezime;klub' razdvojeno | ")
            note = st.text_area("Napomena trenera")
            if st.button("Spremi rezultat"):
                conn.execute(
                    "INSERT INTO results(competition_id, member_id, category, style, fights_total, wins, losses, placement, wins_detail_json, losses_detail_json, note) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (comp_id, mid, cat, stl, int(fights), int(w), int(l), int(place), pd.Series(wins_d.split('|')).to_json(), pd.Series(losses_d.split('|')).to_json(), note)
                )
                conn.commit()
                st.success("Rezultat spremljen.")

    conn.close()

def section_stats():
    page_header("Statistika", "Po godini, natjecanju, sportašu, kategoriji")
    conn = get_conn()

    year = st.number_input("Godina", min_value=2000, max_value=2100, value=datetime.now().year, step=1)
    q = """
    SELECT c.kind, c.age_cat, r.style,
           SUM(r.fights_total) AS borbi,
           SUM(r.wins) AS pobjede,
           SUM(r.losses) AS porazi,
           SUM(CASE WHEN r.placement=1 THEN 1 ELSE 0 END) AS zlato,
           SUM(CASE WHEN r.placement=2 THEN 1 ELSE 0 END) AS srebro,
           SUM(CASE WHEN r.placement=3 THEN 1 ELSE 0 END) AS bronca
    FROM competitions c
    JOIN results r ON r.competition_id = c.id
    WHERE substr(c.date_from,1,4) = ?
    GROUP BY c.kind, c.age_cat, r.style
    ORDER BY c.kind, c.age_cat
    """
    df = pd.read_sql_query(q, conn, params=(str(year),))
    st.dataframe(df, use_container_width=True)

    st.markdown("#### Pojedinačno – odaberi sportaša/icu")
    mems = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full FROM members ORDER BY last_name, first_name", conn)
    sel = st.selectbox("Sportaš/ica", options=["-"] + [f"{r.id} – {r.full}" for r in mems.itertuples()])
    if sel != "-":
        mid = int(sel.split(" – ")[0])
        q2 = """
        SELECT c.date_from, c.kind, c.name, r.category, r.style, r.fights_total, r.wins, r.losses, r.placement
        FROM results r JOIN competitions c ON r.competition_id=c.id
        WHERE r.member_id=? AND substr(c.date_from,1,4)=?
        ORDER BY c.date_from DESC
        """
        d2 = pd.read_sql_query(q2, conn, params=(mid, str(year)))
        st.dataframe(d2, use_container_width=True)

    conn.close()

def section_groups():
    page_header("Grupe", "Upravljanje grupama i pripadnost članova")
    conn = get_conn()

    with st.form("group_form"):
        new_g = st.text_input("Dodaj novu grupu")
        add = st.form_submit_button("Dodaj")
    if add and new_g:
        try:
            conn.execute("INSERT INTO groups(name) VALUES(?)", (new_g,))
            conn.commit()
            st.success("Grupa dodana.")
        except sqlite3.IntegrityError:
            st.warning("Grupa već postoji.")

    st.markdown("### Popis grupa")
    groups_df = pd.read_sql_query("SELECT * FROM groups ORDER BY name", conn)
    st.dataframe(groups_df, use_container_width=True)

    st.markdown("### Dodijeli člana u grupu")
    mems = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full, group_name FROM members ORDER BY full", conn)
    if not mems.empty:
        msel = st.selectbox("Član", options=["-"] + [f"{r.id} – {r.full} (trenutno: {r.group_name or '-'} )" for r in mems.itertuples()])
        gsel = st.selectbox("Grupa", options=["-"] + groups_df["name"].tolist())
        if st.button("Spremi pripadnost") and msel != "-" and gsel != "-":
            mid = int(msel.split(" – ")[0])
            conn.execute("UPDATE members SET group_name=? WHERE id=?", (gsel, mid))
            conn.commit()
            st.success("Ažurirano.")

    conn.close()

def section_veterans():
    page_header("Veterani", "Popis i komunikacija")
    conn = get_conn()
    vets = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full, athlete_email, parent_email FROM members WHERE veteran=1 ORDER BY full", conn)
    st.dataframe(vets, use_container_width=True)

    if not vets.empty:
        sel = st.multiselect("Odaberi veterane", options=[f"{r.id} – {r.full}" for r in vets.itertuples()])
        subject = st.text_input("Naslov poruke")
        body = st.text_area("Tekst poruke")
        if st.button("Kreiraj e-mail link"):
            emails = []
            for s in sel:
                mid = int(s.split(" – ")[0])
                rec = vets[vets["id"]==mid].iloc[0]
                if rec["athlete_email"]:
                    emails.append(rec["athlete_email"])
                if rec["parent_email"]:
                    emails.append(rec["parent_email"])
            emails = list(dict.fromkeys(emails))
            if emails:
                st.markdown(f"[Otvorite e-mail klijent]({mailto_link(','.join(emails), subject, body)})")
            else:
                st.warning("Nema e-mail adresa za odabrane.")

    conn.close()

def section_attendance():
    page_header("Prisustvo", "Treneri i sportaši")
    conn = get_conn()

    st.markdown("### Prisustvo trenera – unos treninga")
    coaches = pd.read_sql_query("SELECT id, full_name FROM coaches ORDER BY full_name", conn)
    csel = st.selectbox("Trener", options=["-"] + [f"{r.id} – {r.full_name}" for r in coaches.itertuples()])
    group = st.text_input("Grupa")
    start = st.datetime_input("Početak treninga", value=datetime.now().replace(minute=0, second=0, microsecond=0))
    end = st.datetime_input("Kraj treninga", value=(datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)))
    place = st.selectbox("Mjesto", ["DVORANA SJEVER","IGRALIŠTE ANG","IGRALIŠTE SREDNJA","Drugo (upiši ručno)"])
    if place == "Drugo (upiši ručno)":
        place = st.text_input("Upiši mjesto")
    if st.button("Spremi trening trenera"):
        if csel != "-":
            coach_id = int(csel.split(" – ")[0])
            minutes = int((end - start).total_seconds() // 60)
            conn.execute(
                "INSERT INTO attendance_coaches(coach_id, group_name, start_time, end_time, place, minutes) VALUES(?,?,?,?,?,?)",
                (coach_id, group, start.isoformat(), end.isoformat(), place, minutes)
            )
            conn.commit()
            st.success("Trening spremljen.")

    st.markdown("### Prisustvo sportaša – evidencija")
    groups = pd.read_sql_query("SELECT DISTINCT group_name FROM members WHERE group_name IS NOT NULL AND group_name<>'' ORDER BY 1", conn)["group_name"].tolist()
    gsel = st.selectbox("Grupa", options=["-"] + groups)
    sess_date = st.date_input("Datum", value=date.today())
    if gsel != "-":
        mems = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full FROM members WHERE group_name=? ORDER BY full", conn, params=(gsel,))
        for r in mems.itertuples():
            cols = st.columns([3,1,1,3])
            cols[0].markdown(f"**{r.full}**")
            present = cols[1].checkbox("Prisutan", key=f"prs_{r.id}")
            minutes = cols[2].number_input("Min", min_value=0, value=60, step=5, key=f"min_{r.id}")
            note = cols[3].text_input("Napomena", key=f"nt_{r.id}")
            if st.button("Spremi", key=f"save_{r.id}"):
                conn.execute(
                    "INSERT INTO attendance_members(member_id, date, group_name, present, minutes, note) VALUES(?,?,?,?,?,?)",
                    (int(r.id), sess_date.isoformat(), gsel, int(present), int(minutes), note)
                )
                conn.commit()
                st.success(f"Spremljeno za {r.full}.")

    conn.close()

def section_communication():
    page_header("Komunikacija", "Masovne e-mail poruke")
    conn = get_conn()
    all_members = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full, athlete_email, parent_email, veteran, active_competitor FROM members ORDER BY full", conn)
    st.dataframe(all_members, use_container_width=True)

    st.markdown("#### Filtriraj primatelje")
    only_active = st.checkbox("Samo aktivni natjecatelji")
    only_vets = st.checkbox("Samo veterani")
    filtered = all_members.copy()
    if only_active:
        filtered = filtered[filtered["active_competitor"]==1]
    if only_vets:
        filtered = filtered[filtered["veteran"]==1]

    sel = st.multiselect("Odaberi članove", options=[f"{r.id} – {r.full}" for r in filtered.itertuples()])
    subject = st.text_input("Naslov")
    body = st.text_area("Poruka")

    if st.button("Kreiraj e-mail link"):
        emails = []
        for s in sel:
            mid = int(s.split(" – ")[0])
            rec = all_members[all_members["id"]==mid].iloc[0]
            if rec["athlete_email"]:
                emails.append(rec["athlete_email"])
            if rec["parent_email"]:
                emails.append(rec["parent_email"])
        emails = list(dict.fromkeys(emails))
        if emails:
            st.markdown(f"[Otvorite e-mail klijent]({mailto_link(','.join(emails), subject, body)})")
        else:
            st.warning("Nema e-mail adresa za odabrane.")

    st.download_button("Skini filtrirane e-mailove (Excel)", data=excel_bytes_from_df(filtered, "Primatelji"), file_name="primatelji.xlsx")
    conn.close()

def main():
    st.set_page_config(page_title="HK Podravka – Admin (v3)", page_icon="🤼", layout="wide")
    css_style()
    init_db()

    with st.sidebar:
        st.markdown(f"## {KLUB_NAZIV}")
        st.markdown(f"**E-mail:** {KLUB_EMAIL}")
        st.markdown(f"**Adresa:** {KLUB_ADRESA}")
        st.markdown(f"**OIB:** {KLUB_OIB}")
        st.markdown(f"**IBAN:** {KLUB_IBAN}")
        st.markdown(f"[Web]({KLUB_WEB})")

        section = st.radio("Navigacija", [
            "Klub", "Članovi", "Treneri", "Natjecanja i rezultati",
            "Statistika", "Grupe", "Veterani", "Prisustvo", "Komunikacija"
        ])

    if section == "Klub":
        section_club()
    elif section == "Članovi":
        section_members()
    elif section == "Treneri":
        section_coaches()
    elif section == "Natjecanja i rezultati":
        section_competitions()
    elif section == "Statistika":
        section_stats()
    elif section == "Grupe":
        section_groups()
    elif section == "Veterani":
        section_veterans()
    elif section == "Prisustvo":
        section_attendance()
    else:
        section_communication()

if __name__ == "__main__":
    main()
