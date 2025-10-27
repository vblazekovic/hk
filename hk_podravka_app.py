# -*- coding: utf-8 -*-
"""
HK Podravka – klupska web-admin aplikacija (Streamlit, 1-file .py)
Verzija: v5 – Klub (bez promjena), Članovi (split polja + Excel + pristupnica/privola upload), Treneri
Autor: ChatGPT (GPT-5 Thinking)

▶ Pokretanje lokalno:
    pip install -r requirements.txt
    streamlit run hk_podravka_full_v5.py
"""

import os
import io
import json
import sqlite3
from datetime import datetime, date, timedelta
from typing import Optional

import pandas as pd
import streamlit as st

# PDF (za buduće generiranje – trenutno koristimo samo upload pristupnice/privole)
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

    # MEMBERS – split fields + uploads za pristupnicu/privolu/sliku
    cur.execute("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            dob TEXT,
            gender TEXT,      -- 'M' ili 'Ž'
            oib TEXT UNIQUE,
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
            application_path TEXT,   -- pristupnica (upload)
            consent_path TEXT,       -- privola (upload)
            medical_path TEXT,
            medical_valid_until TEXT
        )
    """)

    # COACHES
    cur.execute("""
        CREATE TABLE IF NOT EXISTS coaches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
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

def excel_bytes_from_df(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

# ==========================
# 1) KLUB (NE MIJENJAJ)
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

        st.markdown("**Članovi predsjedništva** – unesite ime, telefon, e-mail u svaki redak.")
        board = st.data_editor(board_prefill if not board_prefill.empty else pd.DataFrame(columns=["ime_prezime","telefon","email"]), num_rows="dynamic", key="board_editor")

        st.markdown("**Nadzorni odbor** – unesite ime, telefon, e-mail u svaki redak.")
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

# ==========================
# 2) ČLANOVI – po uputama
# ==========================
def members_template_df() -> pd.DataFrame:
    cols = [
        "ime","prezime","datum_rodenja(YYYY-MM-DD)","spol(M/Ž)","oib",
        "ulica_i_broj","grad","postanski_broj",
        "email_sportasa","email_roditelja",
        "br_osobne","osobna_vrijedi_do(YYYY-MM-DD)","osobna_izdavatelj",
        "br_putovnice","putovnica_vrijedi_do(YYYY-MM-DD)","putovnica_izdavatelj",
        "aktivni_natjecatelj(0/1)","veteran(0/1)","ostalo(0/1)",
        "placa_clanarinu(0/1)","iznos_clanarine(EUR)","grupa"
    ]
    return pd.DataFrame(columns=cols)

def section_members():
    page_header("Članovi", "Učlanjenja, Excel uvoz/izvoz, dokumenti")

    conn = get_conn()

    # Predložak za download
    tpl_df = members_template_df()
    st.download_button(
        "Skini predložak (Excel)",
        data=excel_bytes_from_df(tpl_df, "ClanoviPredlozak"),
        file_name="predlozak_clanovi.xlsx"
    )

    # Izvoz trenutnih članova
    export_df = pd.read_sql_query("""
        SELECT first_name AS ime, last_name AS prezime, dob AS datum_rodenja, gender AS spol, oib,
               street AS ulica_i_broj, city AS grad, postal_code AS postanski_broj,
               athlete_email AS email_sportasa, parent_email AS email_roditelja,
               id_card_number AS br_osobne, id_card_valid_until AS osobna_vrijedi_do, id_card_issuer AS osobna_izdavatelj,
               passport_number AS br_putovnice, passport_valid_until AS putovnica_vrijedi_do, passport_issuer AS putovnica_izdavatelj,
               active_competitor AS aktivni_natjecatelj, veteran, other_flag AS ostalo,
               pays_fee AS placa_clanarinu, fee_amount AS iznos_clanarine, group_name AS grupa
        FROM members ORDER BY last_name, first_name
    """, conn)
    st.download_button(
        "Skini članove (Excel)",
        data=excel_bytes_from_df(export_df, "Clanovi"),
        file_name="clanovi_export.xlsx",
        disabled=export_df.empty
    )

    st.markdown("#### Učitaj članove iz Excel tablice")
    up_excel = st.file_uploader("Upload Excel (po predlošku)", type=["xlsx"])
    if up_excel is not None:
        try:
            df_up = pd.read_excel(up_excel)
            for _, r in df_up.iterrows():
                first_name = str(r.get("ime","") or "").strip()
                last_name  = str(r.get("prezime","") or "").strip()
                dob        = str(r.get("datum_rodenja(YYYY-MM-DD)","") or "")[:10]
                gender     = str(r.get("spol(M/Ž)","") or "").strip()
                oib        = str(r.get("oib","") or "").strip()

                street     = str(r.get("ulica_i_broj","") or "").strip()
                city       = str(r.get("grad","") or "").strip()
                postal     = str(r.get("postanski_broj","") or "").strip()

                email_s    = str(r.get("email_sportasa","") or "").strip()
                email_p    = str(r.get("email_roditelja","") or "").strip()

                id_no      = str(r.get("br_osobne","") or "").strip()
                id_until   = str(r.get("osobna_vrijedi_do(YYYY-MM-DD)","") or "")[:10]
                id_issuer  = str(r.get("osobna_izdavatelj","") or "").strip()

                pass_no    = str(r.get("br_putovnice","") or "").strip()
                pass_until = str(r.get("putovnica_vrijedi_do(YYYY-MM-DD)","") or "")[:10]
                pass_issuer= str(r.get("putovnica_izdavatelj","") or "").strip()

                active     = int(r.get("aktivni_natjecatelj(0/1)", 0) or 0)
                veteran    = int(r.get("veteran(0/1)", 0) or 0)
                other      = int(r.get("ostalo(0/1)", 0) or 0)

                pays       = int(r.get("placa_clanarinu(0/1)", 0) or 0)
                fee        = float(r.get("iznos_clanarine(EUR)", 30) or 30.0)
                group      = str(r.get("grupa","") or "").strip()

                conn.execute("""
                    INSERT INTO members(first_name,last_name,dob,gender,oib,street,city,postal_code,
                                        athlete_email,parent_email,id_card_number,id_card_issuer,id_card_valid_until,
                                        passport_number,passport_issuer,passport_valid_until,
                                        active_competitor,veteran,other_flag,pays_fee,fee_amount,group_name)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(oib) DO UPDATE SET
                        first_name=excluded.first_name, last_name=excluded.last_name, dob=excluded.dob, gender=excluded.gender,
                        street=excluded.street, city=excluded.city, postal_code=excluded.postal_code,
                        athlete_email=excluded.athlete_email, parent_email=excluded.parent_email,
                        id_card_number=excluded.id_card_number, id_card_issuer=excluded.id_card_issuer, id_card_valid_until=excluded.id_card_valid_until,
                        passport_number=excluded.passport_number, passport_issuer=excluded.passport_issuer, passport_valid_until=excluded.passport_valid_until,
                        active_competitor=excluded.active_competitor, veteran=excluded.veteran, other_flag=excluded.other_flag,
                        pays_fee=excluded.pays_fee, fee_amount=excluded.fee_amount, group_name=excluded.group_name
                """, (first_name,last_name,dob,gender,oib,street,city,postal,email_s,email_p,id_no,id_issuer,id_until,
                      pass_no,pass_issuer,pass_until,active,veteran,other,pays,fee,group))
            conn.commit()
            st.success("Članovi uvezeni/ažurirani iz Excela.")
        except Exception as e:
            st.error(f"Greška pri uvozu: {e}")

    st.markdown("---")
    st.markdown("### Unos novog člana (djelomičan unos je dopušten)")

    groups_preset = ["Hrvači", "Hrvačice", "Veterani", "Ostalo", ""]
    with st.form("member_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        first_name = c1.text_input("Ime")
        last_name  = c2.text_input("Prezime")
        dob        = c3.date_input("Datum rođenja", value=date(2010,1,1))
        gender     = c1.selectbox("Spol (M/Ž)", ["","M","Ž"])
        oib        = c2.text_input("OIB")

        st.markdown("**Adresa**")
        a1, a2, a3 = st.columns(3)
        street     = a1.text_input("Ulica i kućni broj")
        city       = a2.text_input("Grad / mjesto prebivališta")
        postal     = a3.text_input("Poštanski broj")

        e1, e2 = st.columns(2)
        email_s  = e1.text_input("E-mail sportaša")
        email_p  = e2.text_input("E-mail roditelja")

        st.markdown("**Osobna iskaznica**")
        id1, id2, id3 = st.columns(3)
        id_no     = id1.text_input("Broj osobne")
        id_until  = id2.date_input("Vrijedi do", value=date.today())
        id_issuer = id3.text_input("Izdavatelj")

        st.markdown("**Putovnica**")
        p1, p2, p3 = st.columns(3)
        pass_no     = p1.text_input("Broj putovnice")
        pass_until  = p2.date_input("Vrijedi do", value=date.today())
        pass_issuer = p3.text_input("Izdavatelj")

        st.markdown("**Status**")
        s1, s2, s3 = st.columns(3)
        active  = s1.checkbox("Aktivni natjecatelj/ica", value=False)
        veteran = s2.checkbox("Veteran", value=False)
        other   = s3.checkbox("Ostalo", value=False)

        pays_fee = st.checkbox("Plaća članarinu", value=active)  # auto postavi ako je aktivni
        fee_amt  = st.number_input("Iznos članarine (EUR)", value=30.0, step=1.0)

        group_name = st.selectbox("Grupa", options=groups_preset)

        photo   = st.file_uploader("Slika člana", type=["png","jpg","jpeg"])
        app_pdf = st.file_uploader("Pristupnica (PDF)", type=["pdf"])
        con_pdf = st.file_uploader("Privola (PDF)", type=["pdf"])

        submit_member = st.form_submit_button("Spremi člana")

    if submit_member:
        photo_path = save_uploaded_file(photo, "members/photos") if photo else ""
        app_path   = save_uploaded_file(app_pdf, "members/forms") if app_pdf else ""
        con_path   = save_uploaded_file(con_pdf, "members/forms") if con_pdf else ""

        conn.execute("""
            INSERT INTO members(first_name,last_name,dob,gender,oib,street,city,postal_code,
                                athlete_email,parent_email,id_card_number,id_card_issuer,id_card_valid_until,
                                passport_number,passport_issuer,passport_valid_until,
                                active_competitor,veteran,other_flag,pays_fee,fee_amount,group_name,photo_path,application_path,consent_path)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(oib) DO UPDATE SET
                first_name=excluded.first_name, last_name=excluded.last_name, dob=excluded.dob, gender=excluded.gender,
                street=excluded.street, city=excluded.city, postal_code=excluded.postal_code,
                athlete_email=excluded.athlete_email, parent_email=excluded.parent_email,
                id_card_number=excluded.id_card_number, id_card_issuer=excluded.id_card_issuer, id_card_valid_until=excluded.id_card_valid_until,
                passport_number=excluded.passport_number, passport_issuer=excluded.passport_issuer, passport_valid_until=excluded.passport_valid_until,
                active_competitor=excluded.active_competitor, veteran=excluded.veteran, other_flag=excluded.other_flag,
                pays_fee=excluded.pays_fee, fee_amount=excluded.fee_amount, group_name=excluded.group_name,
                photo_path=COALESCE(excluded.photo_path, photo_path),
                application_path=COALESCE(excluded.application_path, application_path),
                consent_path=COALESCE(excluded.consent_path, consent_path)
        """, (first_name,last_name,dob.isoformat(),gender,oib,street,city,postal,email_s,email_p,id_no,id_issuer,id_until.isoformat(),
              pass_no,pass_issuer,pass_until.isoformat(),int(active),int(veteran),int(other),int(pays_fee),float(fee_amt),group_name,photo_path,app_path,con_path))
        conn.commit()
        st.success("Član spremljen.")

    st.markdown("---")
    st.markdown("### Popis članova (uređivanje i brisanje)")

    members_df = pd.read_sql_query("""
        SELECT id, first_name, last_name, dob, gender, oib,
               street, city, postal_code,
               athlete_email, parent_email,
               active_competitor, veteran, other_flag,
               pays_fee, fee_amount, group_name
        FROM members ORDER BY last_name, first_name
    """, conn)

    if not members_df.empty:
        edited = st.data_editor(members_df, num_rows="dynamic", use_container_width=True, key="members_grid_v5")
        c1, c2, c3 = st.columns(3)
        if c1.button("Spremi izmjene"):
            try:
                for _, r in edited.iterrows():
                    conn.execute("""UPDATE members SET
                        first_name=?, last_name=?, dob=?, gender=?, street=?, city=?, postal_code=?,
                        athlete_email=?, parent_email=?, active_competitor=?, veteran=?, other_flag=?,
                        pays_fee=?, fee_amount=?, group_name=?
                        WHERE id=?
                    """, (str(r.get("first_name","")), str(r.get("last_name","")), str(r.get("dob",""))[:10], str(r.get("gender","")),
                          str(r.get("street","")), str(r.get("city","")), str(r.get("postal_code","")),
                          str(r.get("athlete_email","")), str(r.get("parent_email","")),
                          int(r.get("active_competitor",0) or 0), int(r.get("veteran",0) or 0), int(r.get("other_flag",0) or 0),
                          int(r.get("pays_fee",0) or 0), float(r.get("fee_amount",0) or 0.0), str(r.get("group_name","")),
                          int(r["id"])))
                conn.commit()
                st.success("Izmjene spremljene.")
            except Exception as e:
                st.error(f"Greška pri spremanju: {e}")

        del_id = c2.number_input("ID za brisanje", min_value=0, step=1, value=0)
        if c3.button("Obriši člana po ID-u") and del_id>0:
            conn.execute("DELETE FROM members WHERE id=?", (int(del_id),))
            conn.commit()
            st.success(f"Član #{del_id} obrisan.")

    conn.close()

# ==========================
# 3) TRENERI – po uputama
# ==========================
def section_coaches():
    page_header("Treneri", "Unos trenera, dokumenti i slike")
    conn = get_conn()

    with st.form("coach_form"):
        c1, c2, c3 = st.columns(3)
        first_name = c1.text_input("Ime")
        last_name  = c2.text_input("Prezime")
        dob        = c3.date_input("Datum rođenja", value=date(1990,1,1))
        oib        = c1.text_input("OIB")
        email      = c2.text_input("E-mail")
        iban       = c3.text_input("IBAN broj računa")
        group_name = st.text_input("Grupa koju trenira (može se mijenjati)")
        contract   = st.file_uploader("Ugovor s klubom (PDF)", type=["pdf"])
        other_docs = st.file_uploader("Drugi dokumenti (višestruko)", type=["pdf","png","jpg","jpeg"], accept_multiple_files=True)
        photo      = st.file_uploader("Slika trenera", type=["png","jpg","jpeg"])
        submit     = st.form_submit_button("Spremi trenera")

    if submit:
        contract_path = save_uploaded_file(contract, "coaches/contracts") if contract else ""
        other_paths = []
        for f in other_docs or []:
            other_paths.append(save_uploaded_file(f, "coaches/docs"))
        photo_path = save_uploaded_file(photo, "coaches/photos") if photo else ""
        conn.execute(
            "INSERT INTO coaches(first_name,last_name,dob,oib,email,iban,group_name,contract_path,other_docs_json,photo_path) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (first_name, last_name, dob.isoformat(), oib, email, iban, group_name, contract_path, pd.Series(other_paths).to_json(), photo_path)
        )
        conn.commit()
        st.success("Trener spremljen.")

    st.markdown("---")
    st.markdown("### Popis trenera (uređivanje i brisanje)")
    coaches_df = pd.read_sql_query("""
        SELECT id, first_name, last_name, dob, oib, email, iban, group_name FROM coaches ORDER BY last_name, first_name
    """, conn)
    if not coaches_df.empty:
        edited = st.data_editor(coaches_df, num_rows="dynamic", use_container_width=True, key="coaches_grid_v5")
        c1, c2, c3 = st.columns(3)
        if c1.button("Spremi izmjene (treneri)"):
            try:
                for _, r in edited.iterrows():
                    conn.execute("""UPDATE coaches SET
                        first_name=?, last_name=?, dob=?, oib=?, email=?, iban=?, group_name=?
                        WHERE id=?
                    """, (str(r.get("first_name","")), str(r.get("last_name","")), str(r.get("dob",""))[:10],
                          str(r.get("oib","")), str(r.get("email","")), str(r.get("iban","")), str(r.get("group_name","")),
                          int(r["id"])))
                conn.commit()
                st.success("Izmjene spremljene.")
            except Exception as e:
                st.error(f"Greška pri spremanju: {e}")

        del_id = c2.number_input("ID trenera za brisanje", min_value=0, step=1, value=0)
        if c3.button("Obriši trenera po ID-u") and del_id>0:
            conn.execute("DELETE FROM coaches WHERE id=?", (int(del_id),))
            conn.commit()
            st.success(f"Trener #{del_id} obrisan.")

    conn.close()

# ==========================
# MAIN
# ==========================
def main():
    st.set_page_config(page_title="HK Podravka – Admin (v5)", page_icon="🤼", layout="wide")
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
    else:
        page_header(section, "U izradi – bit će dodano kasnije.")


if __name__ == "__main__":
    main()
