# -*- coding: utf-8 -*-
"""
HK Podravka – klupska web-admin aplikacija (Streamlit, 1-file .py)
Verzija: v6 – SVI ODJELJCI po uputama
Autor: ChatGPT (GPT-5 Thinking)

▶ Pokretanje lokalno:
    pip install -r requirements.txt
    streamlit run hk_podravka_full_v6.py
"""

import os
import io
import json
import sqlite3
from datetime import datetime, date, timedelta
from typing import Optional, List

import pandas as pd
import streamlit as st

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

# ==========================
# KONSTANTE KLUBA I STIL
# ==========================
PRIMARY_RED = "#c1121f"     # crvena
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
# POMOĆNE
# ==========================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_conn(); cur = conn.cursor()

    # CLUB
    cur.execute("""
    CREATE TABLE IF NOT EXISTS club_info (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        name TEXT, email TEXT, address TEXT, oib TEXT, web TEXT, iban TEXT,
        president TEXT, secretary TEXT, board_json TEXT, supervisory_json TEXT,
        instagram TEXT, facebook TEXT, tiktok TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS club_docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT, filename TEXT, path TEXT, uploaded_at TEXT
    )""")

    # GROUPS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )""")

    # MEMBERS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT, last_name TEXT, dob TEXT, gender TEXT, oib TEXT UNIQUE,
        street TEXT, city TEXT, postal_code TEXT,
        athlete_email TEXT, parent_email TEXT,
        id_card_number TEXT, id_card_issuer TEXT, id_card_valid_until TEXT,
        passport_number TEXT, passport_issuer TEXT, passport_valid_until TEXT,
        active_competitor INTEGER DEFAULT 0, veteran INTEGER DEFAULT 0, other_flag INTEGER DEFAULT 0,
        pays_fee INTEGER DEFAULT 0, fee_amount REAL DEFAULT 30.0, group_name TEXT,
        photo_path TEXT, application_path TEXT, consent_path TEXT,
        medical_path TEXT, medical_valid_until TEXT,
        consent_checked_date TEXT
    )""")

    # COACHES
    cur.execute("""
    CREATE TABLE IF NOT EXISTS coaches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT, last_name TEXT, dob TEXT, oib TEXT, email TEXT, iban TEXT,
        group_name TEXT, contract_path TEXT, other_docs_json TEXT, photo_path TEXT
    )""")

    # COMPETITIONS & RESULTS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS competitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT, kind_other TEXT, name TEXT,
        date_from TEXT, date_to TEXT, place TEXT,
        style TEXT, age_cat TEXT,
        country TEXT, country_iso3 TEXT,
        team_rank INTEGER, club_competitors INTEGER, total_competitors INTEGER,
        clubs_count INTEGER, countries_count INTEGER,
        coaches_json TEXT, notes TEXT, bulletin_url TEXT, gallery_paths_json TEXT, website_link TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition_id INTEGER REFERENCES competitions(id) ON DELETE CASCADE,
        member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
        category TEXT, style TEXT,
        fights_total INTEGER, wins INTEGER, losses INTEGER, placement INTEGER,
        wins_detail_json TEXT, losses_detail_json TEXT, note TEXT
    )""")

    # ATTENDANCE
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance_coaches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coach_id INTEGER REFERENCES coaches(id) ON DELETE SET NULL,
        group_name TEXT, start_time TEXT, end_time TEXT, place TEXT, minutes INTEGER
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER REFERENCES members(id) ON DELETE CASCADE,
        date TEXT, group_name TEXT, present INTEGER DEFAULT 0, minutes INTEGER DEFAULT 0,
        note TEXT, camp_flag INTEGER DEFAULT 0, camp_where TEXT, camp_coach TEXT
    )""")

    # COMM
    cur.execute("""
    CREATE TABLE IF NOT EXISTS comm_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, subject TEXT, body TEXT, recipients_json TEXT
    )""")

    # seed club
    cur.execute("SELECT 1 FROM club_info WHERE id=1")
    if cur.fetchone() is None:
        cur.execute("""INSERT INTO club_info
            (id, name, email, address, oib, web, iban, president, secretary, board_json, supervisory_json, instagram, facebook, tiktok)
            VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (KLUB_NAZIV, KLUB_EMAIL, KLUB_ADRESA, KLUB_OIB, KLUB_WEB, KLUB_IBAN, "", "", "[]", "[]", "", "", "")
        )
    conn.commit(); conn.close()

def css_style():
    st.markdown(
        f"""
        <style>
        .app-header {{ background: linear-gradient(90deg, {PRIMARY_RED}, {GOLD}); color: {WHITE}; padding: 16px 20px; border-radius: 16px; margin-bottom: 16px; }}
        .card {{ background: {LIGHT_BG}; border: 1px solid #f0e6da; border-radius: 16px; padding: 16px; margin-bottom: 12px; }}
        .danger {{ color: #b00020; font-weight: 700; }}
        .ok {{ color: #0b7a0b; font-weight: 700; }}
        </style>
        """, unsafe_allow_html=True
    )

def page_header(title: str, subtitle: Optional[str] = None):
    st.markdown(f"<div class='app-header'><h2 style='margin:0'>{title}</h2>{('<div>'+subtitle+'</div>') if subtitle else ''}</div>", unsafe_allow_html=True)

def save_uploaded_file(uploaded, subdir: str) -> str:
    if not uploaded: return ""
    fn = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded.name}"
    path = os.path.join(UPLOAD_DIR, subdir); os.makedirs(path, exist_ok=True)
    full = os.path.join(path, fn)
    with open(full, "wb") as f: f.write(uploaded.getbuffer())
    return full

def excel_bytes_from_df(df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name=sheet_name)
    return out.getvalue()

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
# 1) KLUB – bez promjena
# ==========================
def section_club():
    page_header("Klub – osnovni podaci", KLUB_NAZIV)
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM club_info WHERE id=1", conn)
    if df.empty:
        conn.execute("INSERT OR REPLACE INTO club_info (id, name, email, address, oib, web, iban) VALUES (1,?,?,?,?,?,?)",
                     (KLUB_NAZIV, KLUB_EMAIL, KLUB_ADRESA, KLUB_OIB, KLUB_WEB, KLUB_IBAN))
        conn.commit(); df = pd.read_sql_query("SELECT * FROM club_info WHERE id=1", conn)
    row = df.iloc[0]

    def _df_from_json(s):
        try:
            d = pd.read_json(s); 
            if isinstance(d, pd.DataFrame): return d
        except Exception: pass
        return pd.DataFrame(columns=["ime_prezime","telefon","email"])

    board_prefill = _df_from_json(row.get("board_json","[]"))
    superv_prefill = _df_from_json(row.get("supervisory_json","[]"))

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
        board = st.data_editor(board_prefill if not board_prefill.empty else pd.DataFrame(columns=["ime_prezime","telefon","email"]), num_rows="dynamic", key="board_editor_v6")
        st.markdown("**Nadzorni odbor**")
        superv = st.data_editor(superv_prefill if not superv_prefill.empty else pd.DataFrame(columns=["ime_prezime","telefon","email"]), num_rows="dynamic", key="superv_editor_v6")

        st.markdown("**Društvene mreže (linkovi)**")
        c3, c4, c5 = st.columns(3)
        instagram = c3.text_input("Instagram", row["instagram"] or "")
        facebook = c4.text_input("Facebook", row["facebook"] or "")
        tik_tok = c5.text_input("TikTok", row["tiktok"] or "")

        st.markdown("**Dokumenti kluba** – upload statuta ili drugih dokumenata")
        up_statut = st.file_uploader("Statut kluba (PDF)", type=["pdf"], key="statut_v6")
        up_other = st.file_uploader("Drugi dokument (PDF/IMG)", type=["pdf","png","jpg","jpeg"], key="ostalo_v6")

        submitted = st.form_submit_button("Spremi podatke kluba")

    if submitted:
        conn.execute("""UPDATE club_info SET name=?, email=?, address=?, oib=?, web=?, iban=?, president=?, secretary=?, 
                        board_json=?, supervisory_json=?, instagram=?, facebook=?, tiktok=? WHERE id=1""",
                     (name,email,address,oib,web,iban,president,secretary,
                      (pd.DataFrame(board) if isinstance(board, list) else board).to_json(),
                      (pd.DataFrame(superv) if isinstance(superv, list) else superv).to_json(),
                      instagram,facebook,tik_tok))
        if up_statut:
            path = save_uploaded_file(up_statut, "club_docs")
            conn.execute("INSERT INTO club_docs(kind, filename, path, uploaded_at) VALUES (?,?,?,?)", ("statut", up_statut.name, path, datetime.now().isoformat()))
        if up_other:
            path = save_uploaded_file(up_other, "club_docs")
            conn.execute("INSERT INTO club_docs(kind, filename, path, uploaded_at) VALUES (?,?,?,?)", ("ostalo", up_other.name, path, datetime.now().isoformat()))
        conn.commit(); st.success("Podaci kluba spremljeni.")

    docs = pd.read_sql_query("SELECT id, kind, filename, uploaded_at FROM club_docs ORDER BY uploaded_at DESC", conn)
    if not docs.empty:
        st.markdown("### Dokumenti kluba"); st.dataframe(docs, use_container_width=True)
    conn.close()

# ==========================
# 2) ČLANOVI
# ==========================
def members_template_df() -> pd.DataFrame:
    cols = ["ime","prezime","datum_rodenja(YYYY-MM-DD)","spol(M/Ž)","oib",
            "ulica_i_broj","grad","postanski_broj",
            "email_sportasa","email_roditelja",
            "br_osobne","osobna_vrijedi_do(YYYY-MM-DD)","osobna_izdavatelj",
            "br_putovnice","putovnica_vrijedi_do(YYYY-MM-DD)","putovnica_izdavatelj",
            "aktivni_natjecatelj(0/1)","veteran(0/1)","ostalo(0/1)",
            "placa_clanarinu(0/1)","iznos_clanarine(EUR)","grupa"]
    return pd.DataFrame(columns=cols)

def section_members():
    page_header("Članovi", "Excel upload/download + djelomičan unos + dokumenti + grupe + članarina")
    conn = get_conn()

    # Predložak
    st.download_button("Skini predložak (Excel)", data=excel_bytes_from_df(members_template_df(), "ClanoviPredlozak"), file_name="predlozak_clanovi_v6.xlsx")

    # Export
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
    st.download_button("Skini članove (Excel)", data=excel_bytes_from_df(export_df, "Clanovi"), file_name="clanovi_export_v6.xlsx", disabled=export_df.empty)

    # Import
    st.markdown("#### Učitaj članove iz Excel tablice")
    up_excel = st.file_uploader("Upload Excel", type=["xlsx"], key="members_xlsx_v6")
    if up_excel is not None:
        try:
            df_up = pd.read_excel(up_excel)
            for _, r in df_up.iterrows():
                def g(k, default=""): return str(r.get(k, default) or "").strip()
                first_name, last_name = g("ime"), g("prezime")
                dob, gender, oib = g("datum_rodenja(YYYY-MM-DD)")[:10], g("spol(M/Ž)"), g("oib")
                street, city, postal = g("ulica_i_broj"), g("grad"), g("postanski_broj")
                email_s, email_p = g("email_sportasa"), g("email_roditelja")
                id_no, id_until, id_issuer = g("br_osobne"), g("osobna_vrijedi_do(YYYY-MM-DD)")[:10], g("osobna_izdavatelj")
                pass_no, pass_until, pass_issuer = g("br_putovnice"), g("putovnica_vrijedi_do(YYYY-MM-DD)")[:10], g("putovnica_izdavatelj")
                active, veteran, other = int(r.get("aktivni_natjecatelj(0/1)",0) or 0), int(r.get("veteran(0/1)",0) or 0), int(r.get("ostalo(0/1)",0) or 0)
                pays, fee, group = int(r.get("placa_clanarinu(0/1)",0) or 0), float(r.get("iznos_clanarine(EUR)",30) or 30.0), g("grupa")
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
                """, (first_name,last_name,dob,gender,oib,street,city,postal,email_s,email_p,id_no,id_issuer,id_until,pass_no,pass_issuer,pass_until,active,veteran,other,pays,fee,group))
            conn.commit(); st.success("Članovi uvezeni/ažurirani.")
        except Exception as e:
            st.error(f"Greška pri uvozu: {e}")

    st.markdown("---")
    st.markdown("### Unos novog člana (djelomičan unos moguć)")
    groups = pd.read_sql_query("SELECT name FROM groups ORDER BY name", conn)["name"].tolist()
    default_groups = ["Hrvači","Hrvačice","Veterani","Ostalo"]
    for g in default_groups:
        try: conn.execute("INSERT INTO groups(name) VALUES(?)", (g,)); conn.commit()
        except sqlite3.IntegrityError: pass
    groups = pd.read_sql_query("SELECT name FROM groups ORDER BY name", conn)["name"].tolist()

    with st.form("member_form_v6"):
        c1, c2, c3 = st.columns(3)
        first_name = c1.text_input("Ime")
        last_name  = c2.text_input("Prezime")
        dob        = c3.date_input("Datum rođenja", value=date(2010,1,1), key="dob_v6")
        gender     = c1.selectbox("Spol", ["","M","Ž"], key="gender_v6")
        oib        = c2.text_input("OIB")

        st.markdown("**Adresa**")
        a1, a2, a3 = st.columns(3)
        street = a1.text_input("Ulica i kućni broj")
        city   = a2.text_input("Grad / mjesto")
        postal = a3.text_input("Poštanski broj")

        e1, e2 = st.columns(2)
        email_s = e1.text_input("E-mail sportaša")
        email_p = e2.text_input("E-mail roditelja")

        st.markdown("**Osobna iskaznica**")
        id1, id2, id3 = st.columns(3)
        id_no     = id1.text_input("Broj osobne")
        id_until  = id2.date_input("Osobna vrijedi do", value=date.today(), key="id_until_v6")
        id_issuer = id3.text_input("Izdavatelj osobne")

        st.markdown("**Putovnica**")
        p1, p2, p3 = st.columns(3)
        pass_no     = p1.text_input("Broj putovnice")
        pass_until  = p2.date_input("Putovnica vrijedi do", value=date.today(), key="pass_until_v6")
        pass_issuer = p3.text_input("Izdavatelj putovnice")

        st.markdown("**Status**")
        s1, s2, s3 = st.columns(3)
        active = s1.checkbox("Aktivni natjecatelj/ica", value=False)
        veteran= s2.checkbox("Veteran", value=False)
        other  = s3.checkbox("Ostalo", value=False)

        pays_fee = st.checkbox("Plaća članarinu", value=active, key="pays_fee_v6")
        fee_amt  = st.number_input("Iznos članarine (EUR)", value=30.0, step=1.0)
        group_name = st.selectbox("Grupa", options=[""]+groups, key="group_v6")

        photo   = st.file_uploader("Slika člana", type=["png","jpg","jpeg"], key="photo_v6")
        app_pdf = st.file_uploader("Pristupnica (PDF)", type=["pdf"], key="app_pdf_v6")
        con_pdf = st.file_uploader("Privola (PDF)", type=["pdf"], key="con_pdf_v6")

        submit_member = st.form_submit_button("Spremi člana")

    if submit_member:
        conn.execute("""
            INSERT INTO members(first_name,last_name,dob,gender,oib,street,city,postal_code,
                athlete_email,parent_email,id_card_number,id_card_issuer,id_card_valid_until,
                passport_number,passport_issuer,passport_valid_until,
                active_competitor,veteran,other_flag,pays_fee,fee_amount,group_name,photo_path,application_path,consent_path)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(oib) DO UPDATE SET
                first_name=excluded.first_name,last_name=excluded.last_name,dob=excluded.dob,gender=excluded.gender,
                street=excluded.street,city=excluded.city,postal_code=excluded.postal_code,
                athlete_email=excluded.athlete_email,parent_email=excluded.parent_email,
                id_card_number=excluded.id_card_number,id_card_issuer=excluded.id_card_issuer,id_card_valid_until=excluded.id_card_valid_until,
                passport_number=excluded.passport_number,passport_issuer=excluded.passport_issuer,passport_valid_until=excluded.passport_valid_until,
                active_competitor=excluded.active_competitor,veteran=excluded.veteran,other_flag=excluded.other_flag,
                pays_fee=excluded.pays_fee,fee_amount=excluded.fee_amount,group_name=excluded.group_name,
                photo_path=COALESCE(excluded.photo_path, photo_path),
                application_path=COALESCE(excluded.application_path, application_path),
                consent_path=COALESCE(excluded.consent_path, consent_path)
        """, (first_name,last_name,dob.isoformat(),gender,oib,street,city,postal,email_s,email_p,id_no,id_issuer,id_until.isoformat(),
              pass_no,pass_issuer,pass_until.isoformat(),int(active),int(veteran),int(other),int(pays_fee),float(fee_amt),group_name,
              save_uploaded_file(st.session_state.get("photo_v6"), "members/photos") if st.session_state.get("photo_v6") else "",
              save_uploaded_file(st.session_state.get("app_pdf_v6"), "members/forms") if st.session_state.get("app_pdf_v6") else "",
              save_uploaded_file(st.session_state.get("con_pdf_v6"), "members/forms") if st.session_state.get("con_pdf_v6") else ""))
        conn.commit(); st.success("Član spremljen.")

    st.markdown("---")
    st.markdown("### Popis članova, izmjene, e-mail/WhatsApp, brisanje, liječnički rok")
    members_df = pd.read_sql_query("""
        SELECT id, first_name, last_name, gender, dob, oib,
               street, city, postal_code,
               athlete_email, parent_email,
               active_competitor, veteran, other_flag,
               pays_fee, fee_amount, group_name, medical_valid_until
        FROM members ORDER BY last_name, first_name
    """, conn)

    def days_to(date_str: str) -> Optional[int]:
        try:
            d = datetime.fromisoformat(date_str).date()
            return (d - date.today()).days
        except Exception:
            return None

    if not members_df.empty:
        members_df["dana_do_ljecnicke"] = members_df["medical_valid_until"].apply(lambda x: days_to(x) if pd.notna(x) else None)
        edited = st.data_editor(members_df, num_rows="dynamic", use_container_width=True, key="members_grid_v6")
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("Spremi izmjene"):
            try:
                for _, r in edited.iterrows():
                    conn.execute("""UPDATE members SET
                        first_name=?, last_name=?, gender=?, dob=?, street=?, city=?, postal_code=?,
                        athlete_email=?, parent_email=?, active_competitor=?, veteran=?, other_flag=?,
                        pays_fee=?, fee_amount=?, group_name=?, medical_valid_until=?
                        WHERE id=?
                    """, (str(r.get("first_name","")), str(r.get("last_name","")), str(r.get("gender","")), str(r.get("dob",""))[:10],
                          str(r.get("street","")), str(r.get("city","")), str(r.get("postal_code","")),
                          str(r.get("athlete_email","")), str(r.get("parent_email","")),
                          int(r.get("active_competitor",0) or 0), int(r.get("veteran",0) or 0), int(r.get("other_flag",0) or 0),
                          int(r.get("pays_fee",0) or 0), float(r.get("fee_amount",0) or 0.0), str(r.get("group_name","")),
                          str(r.get("medical_valid_until",""))[:10] if r.get("medical_valid_until") else None,
                          int(r["id"])))
                conn.commit(); st.success("Izmjene spremljene.")
            except Exception as e:
                st.error(f"Greška: {e}")

        # Akcije nad članom
        sel = c2.selectbox("Odaberi ID člana", options=[0]+edited["id"].tolist())
        if sel and sel>0:
            m = pd.read_sql_query("SELECT * FROM members WHERE id=?", conn, params=(int(sel),)).iloc[0]
            if m["athlete_email"]: c3.link_button("E-mail sportašu", url=mailto_link(m["athlete_email"], "Obavijest kluba"))
            if m["parent_email"]:  c4.link_button("E-mail roditelju", url=mailto_link(m["parent_email"], "Obavijest kluba"))
            st.markdown(f"[WhatsApp link (ručno unesite broj)]({whatsapp_link('38591XXXXXXX','Pozdrav iz HK Podravka!')})")

            # Rezultati tog člana
            st.markdown("#### Rezultati člana")
            q = """SELECT c.date_from AS datum, COALESCE(c.name, c.kind) AS natjecanje, r.category, r.style,
                          r.fights_total AS borbi, r.wins AS pobjeda, r.losses AS poraza, r.placement AS plasman
                   FROM results r JOIN competitions c ON r.competition_id=c.id
                   WHERE r.member_id=? ORDER BY c.date_from DESC"""
            st.dataframe(pd.read_sql_query(q, conn, params=(int(sel),)), use_container_width=True)

        del_id = c4.number_input("ID za brisanje", min_value=0, step=1, value=0, key="del_id_v6")
        if st.button("Obriši člana po ID-u") and del_id>0:
            conn.execute("DELETE FROM members WHERE id=?", (int(del_id),)); conn.commit(); st.success("Član obrisan."); st.experimental_rerun()

    # Upload liječničke potvrde + praćenje roka
    st.markdown("#### Liječnička potvrda – upload i rok valjanosti")
    msel = st.selectbox("Član", options=["-"]+[f"{r.id} – {r.first_name} {r.last_name}" for r in pd.read_sql_query("SELECT id, first_name, last_name FROM members ORDER BY last_name, first_name", conn).itertuples()], key="med_sel_v6")
    if msel != "-":
        mid = int(msel.split(" – ")[0])
        up_med = st.file_uploader("Liječnička potvrda (PDF/JPG/PNG)", type=["pdf","jpg","jpeg","png"], key="med_up_v6")
        valid_to = st.date_input("Vrijedi do", value=date.today(), key="med_valid_to_v6")
        if st.button("Spremi liječničku potvrdu"):
            path = save_uploaded_file(up_med, "members/medical") if up_med else ""
            conn.execute("UPDATE members SET medical_path=?, medical_valid_until=? WHERE id=?", (path, valid_to.isoformat(), mid))
            conn.commit(); st.success("Liječnička potvrda spremljena.")
    conn.close()

# ==========================
# 3) TRENERI
# ==========================
def section_coaches():
    page_header("Treneri", "Unos trenera, dokumenti i slike")
    conn = get_conn()
    with st.form("coach_form_v6"):
        c1, c2, c3 = st.columns(3)
        first_name = c1.text_input("Ime")
        last_name  = c2.text_input("Prezime")
        dob        = c3.date_input("Datum rođenja", value=date(1990,1,1), key="coach_dob_v6")
        oib        = c1.text_input("OIB")
        email      = c2.text_input("E-mail")
        iban       = c3.text_input("IBAN broj računa")
        group_name = st.text_input("Grupa koju trenira")
        contract   = st.file_uploader("Ugovor s klubom (PDF)", type=["pdf"], key="coach_contract_v6")
        other_docs = st.file_uploader("Drugi dokumenti (više datoteka)", type=["pdf","png","jpg","jpeg"], accept_multiple_files=True, key="coach_docs_v6")
        photo      = st.file_uploader("Slika trenera", type=["png","jpg","jpeg"], key="coach_photo_v6")
        submit     = st.form_submit_button("Spremi trenera")

    if submit:
        cpath = save_uploaded_file(st.session_state.get("coach_contract_v6"), "coaches/contracts") if st.session_state.get("coach_contract_v6") else ""
        other_paths = []
        for f in (st.session_state.get("coach_docs_v6") or []):
            other_paths.append(save_uploaded_file(f, "coaches/docs"))
        ppath = save_uploaded_file(st.session_state.get("coach_photo_v6"), "coaches/photos") if st.session_state.get("coach_photo_v6") else ""
        conn.execute("""INSERT INTO coaches(first_name,last_name,dob,oib,email,iban,group_name,contract_path,other_docs_json,photo_path)
                        VALUES(?,?,?,?,?,?,?,?,?,?)""",
                     (first_name,last_name,dob.isoformat(),oib,email,iban,group_name,json.dumps(other_paths),cpath,ppath))
        conn.commit(); st.success("Trener spremljen.")

    st.markdown("---")
    st.markdown("### Popis trenera")
    coaches_df = pd.read_sql_query("SELECT id, first_name, last_name, dob, oib, email, iban, group_name FROM coaches ORDER BY last_name, first_name", conn)
    if not coaches_df.empty:
        edited = st.data_editor(coaches_df, num_rows="dynamic", use_container_width=True, key="coaches_grid_v6")
        c1, c2 = st.columns(2)
        if c1.button("Spremi izmjene (treneri)"):
            for _, r in edited.iterrows():
                conn.execute("""UPDATE coaches SET first_name=?, last_name=?, dob=?, oib=?, email=?, iban=?, group_name=? WHERE id=?""",
                             (str(r.get("first_name","")), str(r.get("last_name","")), str(r.get("dob",""))[:10],
                              str(r.get("oib","")), str(r.get("email","")), str(r.get("iban","")), str(r.get("group_name","")), int(r["id"])))
            conn.commit(); st.success("Izmjene spremljene.")
        del_id = c2.number_input("ID trenera za brisanje", min_value=0, step=1, value=0, key="del_coach_v6")
        if st.button("Obriši trenera") and del_id>0:
            conn.execute("DELETE FROM coaches WHERE id=?", (int(del_id),)); conn.commit(); st.success("Trener obrisan."); st.experimental_rerun()
    conn.close()

# ==========================
# 4) NATJECANJA I REZULTATI
# ==========================
def results_template_df() -> pd.DataFrame:
    cols = ["competition_id","member_oib","kategorija","stil(GR/FS/WW/BW/MODIFICIRANO)","borbi","pobjeda","poraza","plasman(1-100)","pobjede_detalji(ime;klub | ...)","porazi_detalji(ime;klub | ... )","napomena"]
    return pd.DataFrame(columns=cols)

def section_competitions():
    page_header("Natjecanja i rezultati", "Unos natjecanja + uvoz/ručni unos rezultata + galerija")
    conn = get_conn()

    kind = st.selectbox("Vrsta natjecanja", ["PRVENSTVO HRVATSKE","MEĐUNARODNI TURNIR","REPREZENTATIVNI NASTUP","HRVAČKA LIGA ZA SENIORE","MEĐUNARODNA HRVAČKA LIGA ZA KADETE","REGIONALNO PRVENSTVO","LIGA ZA DJEVOJČICE","OSTALO"], key="kind_v6")
    kind_other = st.text_input("Ako je OSTALO – upiši vrstu", key="kind_other_v6") if kind=="OSTALO" else ""

    name = st.text_input("Ime natjecanja (ako postoji)", key="comp_name_v6")
    c1,c2,c3 = st.columns(3)
    date_from = c1.date_input("Datum od", value=date.today(), key="comp_from_v6")
    date_to = c2.date_input("Datum do (ako 1 dan, ostavi isti)", value=date.today(), key="comp_to_v6")
    place = c3.text_input("Mjesto natjecanja", key="comp_place_v6")

    style = st.selectbox("Hrvački stil", ["GR","FS","WW","BW","MODIFICIRANO"], key="comp_style_v6")
    age = st.selectbox("Uzrast", ["POČETNICI","U11","U13","U15","U17","U20","U23","SENIORI"], key="comp_age_v6")

    ctry1, ctry2 = st.columns(2)
    country = ctry1.text_input("Država (naziv)", key="comp_country_v6")
    iso3 = ctry2.text_input("Država ISO-3 (npr. HRV)", key="comp_iso3_v6")

    c4,c5,c6,c7,c8 = st.columns(5)
    team_rank = c4.number_input("Ekipni poredak", min_value=0, step=1, key="team_rank_v6")
    club_n = c5.number_input("Broj natjecatelja iz kluba", min_value=0, step=1, key="club_n_v6")
    total_n = c6.number_input("Ukupan broj natjecatelja", min_value=0, step=1, key="total_n_v6")
    clubs_n = c7.number_input("Broj klubova", min_value=0, step=1, key="clubs_n_v6")
    countries_n = c8.number_input("Broj zemalja", min_value=0, step=1, key="countries_n_v6")

    coaches_df = pd.read_sql_query("SELECT first_name || ' ' || last_name AS full_name FROM coaches ORDER BY 1", conn)
    coach_names = st.multiselect("Trener(i) koji su vodili", options=coaches_df["full_name"].tolist(), key="coach_names_v6")

    notes = st.text_area("Kratko zapažanje trenera (za objave)", key="comp_notes_v6")
    gallery = st.file_uploader("Upload slika s natjecanja", type=["png","jpg","jpeg"], accept_multiple_files=True, key="comp_gallery_v6")
    bulletin_url = st.text_input("Poveznica na rezultate / bilten", key="comp_bulletin_v6")
    website_link = st.text_input("Poveznica na objavu na webu kluba", key="comp_site_v6")

    if st.button("Spremi natjecanje", key="save_comp_v6"):
        gallery_paths = [save_uploaded_file(f, "competitions/gallery") for f in (gallery or [])]
        conn.execute("""INSERT INTO competitions(kind,kind_other,name,date_from,date_to,place,style,age_cat,country,country_iso3,
                        team_rank,club_competitors,total_competitors,clubs_count,countries_count,coaches_json,notes,bulletin_url,gallery_paths_json,website_link)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (kind,kind_other,name,date_from.isoformat(),date_to.isoformat(),place,style,age,country,iso3,
                      int(team_rank),int(club_n),int(total_n),int(clubs_n),int(countries_n),
                      json.dumps(coach_names),notes,bulletin_url,json.dumps(gallery_paths),website_link))
        conn.commit(); st.success("Natjecanje spremljeno.")

    st.markdown("---")
    st.markdown("### Rezultati – ručni unos ili Excel")
    # Excel predložak za rezultate
    st.download_button("Skini predložak rezultata (Excel)", data=excel_bytes_from_df(results_template_df(), "RezultatiPredlozak"), file_name="predlozak_rezultati_v6.xlsx")

    comps = pd.read_sql_query("SELECT id, COALESCE(name, kind) AS title, date_from FROM competitions ORDER BY date_from DESC", conn)
    mems = pd.read_sql_query("SELECT id, oib, first_name || ' ' || last_name AS full FROM members ORDER BY last_name, first_name", conn)

    comp_map = {f"{r['id']} – {r['title']} ({r['date_from']})": r['id'] for _,r in comps.iterrows()}
    comp_label = st.selectbox("Odaberi natjecanje", options=["-"]+list(comp_map.keys()), key="res_comp_sel_v6")
    if comp_label != "-":
        comp_id = comp_map[comp_label]
        msel = st.selectbox("Član (iz baze)", options=["-"]+[f"{r.id} – {r.full}" for r in mems.itertuples()], key="res_member_sel_v6")
        if msel != "-":
            mid = int(msel.split(" – ")[0])
            c1,c2,c3 = st.columns(3)
            cat = c1.text_input("Kategorija / težina", key="res_cat_v6")
            stl = c2.selectbox("Stil", ["GR","FS","WW","BW","MODIFICIRANO"], key="res_style_v6")
            fights = c3.number_input("Ukupno borbi", min_value=0, step=1, key="res_fights_v6")
            w = c1.number_input("Pobjede", min_value=0, step=1, key="res_wins_v6")
            l = c2.number_input("Porazi", min_value=0, step=1, key="res_losses_v6")
            place = c3.number_input("Plasman (1–100)", min_value=0, max_value=100, step=1, key="res_place_v6")
            wins_d = st.text_area("Pobjede – 'ime;klub' | 'ime;klub'", key="res_winsd_v6")
            losses_d = st.text_area("Porazi – 'ime;klub' | 'ime;klub'", key="res_lossesd_v6")
            note = st.text_area("Napomena trenera", key="res_note_v6")
            if st.button("Spremi rezultat", key="save_res_v6"):
                conn.execute("""INSERT INTO results(competition_id,member_id,category,style,fights_total,wins,losses,placement,wins_detail_json,losses_detail_json,note)
                                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                             (comp_id,mid,cat,stl,int(fights),int(w),int(l),int(place),json.dumps([x.strip() for x in wins_d.split('|') if x.strip()]),json.dumps([x.strip() for x in losses_d.split('|') if x.strip()]),note))
                conn.commit(); st.success("Rezultat spremljen.")

    st.markdown("#### Uvoz rezultata iz Excela")
    up_res = st.file_uploader("Upload Excel rezultata (po predlošku)", type=["xlsx"], key="res_excel_v6")
    if up_res is not None:
        try:
            df_r = pd.read_excel(up_res)
            for _, r in df_r.iterrows():
                comp_id = int(r.get("competition_id"))
                oib = str(r.get("member_oib",""))
                m = conn.execute("SELECT id FROM members WHERE oib=?", (oib,)).fetchone()
                if not m: continue
                mid = int(m[0])
                conn.execute("""INSERT INTO results(competition_id,member_id,category,style,fights_total,wins,losses,placement,wins_detail_json,losses_detail_json,note)
                                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                             (comp_id,mid,str(r.get("kategorija","")),str(r.get("stil(GR/FS/WW/BW/MODIFICIRANO)","")),
                              int(r.get("borbi",0)),int(r.get("pobjeda",0)),int(r.get("poraza",0)),int(r.get("plasman(1-100)",0)),
                              json.dumps(str(r.get("pobjede_detalji(ime;klub | ...)","")).split('|')),
                              json.dumps(str(r.get("porazi_detalji(ime;klub | ... )","")).split('|')),
                              str(r.get("napomena",""))))
            conn.commit(); st.success("Rezultati uvezeni.")
        except Exception as e:
            st.error(f"Greška pri uvozu: {e}")
    conn.close()

# ==========================
# 5) STATISTIKA
# ==========================
def section_stats():
    page_header("Statistika", "Po godini/uzrastu/stilu i po sportašu")
    conn = get_conn()
    year = st.number_input("Godina", min_value=2000, max_value=2100, value=datetime.now().year, step=1, key="stat_year_v6")
    q = """
    SELECT c.kind, c.age_cat, r.style,
           COUNT(*) AS startova,
           SUM(r.fights_total) AS borbi,
           SUM(r.wins) AS pobjede,
           SUM(r.losses) AS porazi,
           SUM(CASE WHEN r.placement=1 THEN 1 ELSE 0 END) AS zlato,
           SUM(CASE WHEN r.placement=2 THEN 1 ELSE 0 END) AS srebro,
           SUM(CASE WHEN r.placement=3 THEN 1 ELSE 0 END) AS bronca
    FROM competitions c JOIN results r ON r.competition_id=c.id
    WHERE substr(c.date_from,1,4)=?
    GROUP BY c.kind, c.age_cat, r.style
    ORDER BY c.kind, c.age_cat, r.style
    """
    st.dataframe(pd.read_sql_query(q, conn, params=(str(year),)), use_container_width=True)

    st.markdown("#### Pojedinačno – sportaš/ica")
    mems = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full FROM members ORDER BY last_name, first_name", conn)
    sel = st.selectbox("Sportaš/ica", options=["-"]+[f"{r.id} – {r.full}" for r in mems.itertuples()], key="stat_member_sel_v6")
    if sel != "-":
        mid = int(sel.split(" – ")[0])
        q2 = """
        SELECT c.date_from, c.kind, c.name, r.category, r.style, r.fights_total, r.wins, r.losses, r.placement
        FROM results r JOIN competitions c ON r.competition_id=c.id
        WHERE r.member_id=? AND substr(c.date_from,1,4)=?
        ORDER BY c.date_from DESC
        """
        st.dataframe(pd.read_sql_query(q2, conn, params=(mid,str(year))), use_container_width=True)
    conn.close()

# ==========================
# 6) GRUPE
# ==========================
def section_groups():
    page_header("Grupe", "Dodavanje/brisanje grupa i premještaj članova")
    conn = get_conn()
    with st.form("group_add_v6"):
        new_g = st.text_input("Nova grupa")
        add = st.form_submit_button("Dodaj")
    if add and new_g:
        try: conn.execute("INSERT INTO groups(name) VALUES(?)",(new_g,)); conn.commit(); st.success("Grupa dodana.")
        except sqlite3.IntegrityError: st.warning("Grupa već postoji.")
    groups_df = pd.read_sql_query("SELECT * FROM groups ORDER BY name", conn); st.dataframe(groups_df, use_container_width=True)
    mems = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full, group_name FROM members ORDER BY full", conn)
    if not mems.empty:
        msel = st.selectbox("Član", options=["-"]+[f"{r.id} – {r.full} (trenutno: {r.group_name or '-'})" for r in mems.itertuples()], key="grp_member_sel_v6")
        gsel = st.selectbox("Grupa", options=["-"]+groups_df["name"].tolist(), key="grp_sel_v6")
        if st.button("Spremi pripadnost", key="grp_save_v6") and msel!="- ":
            if msel != "-" and gsel != "-":
                mid = int(msel.split(" – ")[0]); conn.execute("UPDATE members SET group_name=? WHERE id=?", (gsel, mid)); conn.commit(); st.success("Ažurirano.")
    conn.close()

# ==========================
# 7) VETERANI
# ==========================
def section_veterans():
    page_header("Veterani", "Popis + e-mail poruke + brisanje/izmjena")
    conn = get_conn()
    vets = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full, athlete_email, parent_email FROM members WHERE veteran=1 ORDER BY full", conn)
    st.dataframe(vets, use_container_width=True)
    if not vets.empty:
        sel = st.multiselect("Odaberi veterane", options=[f"{r.id} – {r.full}" for r in vets.itertuples()], key="vet_sel_v6")
        subject = st.text_input("Naslov poruke", key="vet_subject_v6")
        body = st.text_area("Tekst poruke", key="vet_body_v6")
        if st.button("Kreiraj e-mail link", key="vet_mail_v6"):
            emails = []
            for s in sel:
                mid = int(s.split(" – ")[0])
                rec = vets[vets["id"]==mid].iloc[0]
                if rec["athlete_email"]: emails.append(rec["athlete_email"])
                if rec["parent_email"]: emails.append(rec["parent_email"])
            emails = list(dict.fromkeys(emails))
            if emails:
                st.markdown(f"[Otvorite e-mail klijent]({mailto_link(','.join(emails), subject, body)})")
            else:
                st.warning("Nema e-mail adresa za odabrane.")
    conn.close()

# ==========================
# 8) PRISUSTVO
# ==========================
def section_attendance():
    page_header("Prisustvo", "Treneri + sportaši + pripreme")
    conn = get_conn()

    # Treneri
    st.markdown("### Treneri – unos treninga")
    coaches = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full FROM coaches ORDER BY full", conn)
    csel = st.selectbox("Trener", options=["-"]+[f"{r.id} – {r.full}" for r in coaches.itertuples()], key="att_coach_sel_v6")
    group = st.text_input("Grupa", key="att_group_v6")
    start = st.datetime_input("Početak", value=datetime.now().replace(minute=0, second=0, microsecond=0), key="att_start_v6")
    end = st.datetime_input("Kraj", value=(datetime.now().replace(minute=0, second=0, microsecond=0)+timedelta(hours=1)), key="att_end_v6")
    place = st.selectbox("Mjesto", ["DVORANA SJEVER","IGRALIŠTE ANG","IGRALIŠTE SREDNJA","Drugo (upiši)"], key="att_place_sel_v6")
    if place=="Drugo (upiši)": place = st.text_input("Upiši mjesto", key="att_place_txt_v6")
    if st.button("Spremi trening trenera", key="att_save_coach_v6") and csel != "-":
        coach_id = int(csel.split(" – ")[0]); minutes = int((end-start).total_seconds()//60)
        conn.execute("""INSERT INTO attendance_coaches(coach_id,group_name,start_time,end_time,place,minutes) VALUES(?,?,?,?,?,?)""",
                     (coach_id, group, start.isoformat(), end.isoformat(), place, minutes))
        conn.commit(); st.success("Trening spremljen.")

    # Članovi
    st.markdown("### Sportaši – evidencija dolazaka")
    groups = pd.read_sql_query("SELECT DISTINCT group_name FROM members WHERE group_name IS NOT NULL AND group_name<>'' ORDER BY 1", conn)["group_name"].tolist()
    gsel = st.selectbox("Grupa", options=["-"]+groups, key="att_group_sel_v6")
    sess_date = st.date_input("Datum", value=date.today(), key="att_date_v6")
    if gsel != "-":
        mems = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full FROM members WHERE group_name=? ORDER BY full", conn, params=(gsel,))
        for r in mems.itertuples():
            cols = st.columns([3,1,1,3])
            cols[0].markdown(f"**{r.full}**")
            present = cols[1].checkbox("Prisutan", key=f"prs_{r.id}_v6")
            minutes = cols[2].number_input("Min", min_value=0, value=60, step=5, key=f"min_{r.id}_v6")
            note = cols[3].text_input("Napomena", key=f"nt_{r.id}_v6")
            if st.button("Spremi", key=f"save_{r.id}_v6"):
                conn.execute("""INSERT INTO attendance_members(member_id,date,group_name,present,minutes,note) VALUES(?,?,?,?,?,?)""",
                             (int(r.id), sess_date.isoformat(), gsel, int(present), int(minutes), note))
                conn.commit(); st.success(f"Spremljeno za {r.full}.")

    # Pripreme reprezentacije
    st.markdown("### Pripreme reprezentacije")
    mems_all = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full FROM members ORDER BY full", conn)
    msel = st.selectbox("Član", options=["-"]+[f"{r.id} – {r.full}" for r in mems_all.itertuples()], key="camp_member_sel_v6")
    if msel != "-":
        mid = int(msel.split(" – ")[0])
        where = st.text_input("Gdje su pripreme?", key="camp_where_v6")
        coach = st.text_input("Voditelj priprema", key="camp_coach_v6")
        tr = st.number_input("Broj treninga", min_value=0, step=1, key="camp_trainings_v6")
        mins = st.number_input("Ukupno sati (minuta)", min_value=0, step=15, key="camp_minutes_v6")
        if st.button("Spremi pripreme", key="camp_save_v6"):
            conn.execute("""INSERT INTO attendance_members(member_id,date,group_name,present,minutes,note,camp_flag,camp_where,camp_coach)
                            VALUES(?,?,?,?,?,?,?,?,?)""",
                         (mid, date.today().isoformat(), "", 1, int(mins), f"Pripreme – {tr} treninga", 1, where, coach))
            conn.commit(); st.success("Zabilježene pripreme.")
    conn.close()

# ==========================
# 9) KOMUNIKACIJA (masovni mailovi)
# ==========================
def section_communication():
    page_header("Komunikacija", "Masovni e-mail prema članovima / roditeljima")
    conn = get_conn()
    all_members = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full, athlete_email, parent_email, veteran, active_competitor FROM members ORDER BY full", conn)
    st.dataframe(all_members, use_container_width=True)
    only_active = st.checkbox("Samo aktivni natjecatelji", key="comm_only_active_v6")
    only_vets = st.checkbox("Samo veterani", key="comm_only_vets_v6")
    filtered = all_members.copy()
    if only_active: filtered = filtered[filtered["active_competitor"]==1]
    if only_vets: filtered = filtered[filtered["veteran"]==1]
    sel = st.multiselect("Odaberi članove", options=[f"{r.id} – {r.full}" for r in filtered.itertuples()], key="comm_sel_v6")
    subject = st.text_input("Naslov", key="comm_subject_v6")
    body = st.text_area("Poruka", key="comm_body_v6")
    if st.button("Kreiraj e-mail link", key="comm_make_v6"):
        emails = []
        for s in sel:
            mid = int(s.split(" – ")[0]); rec = all_members[all_members["id"]==mid].iloc[0]
            if rec["athlete_email"]: emails.append(rec["athlete_email"])
            if rec["parent_email"]: emails.append(rec["parent_email"])
        emails = list(dict.fromkeys(emails))
        if emails: st.markdown(f"[Otvorite e-mail klijent]({mailto_link(','.join(emails), subject, body)})")
        else: st.warning("Nema e-mail adresa.")
    st.download_button("Skini filtrirane e-mailove (Excel)", data=excel_bytes_from_df(filtered, "Primatelji"), file_name="primatelji_v6.xlsx")
    conn.close()

# ==========================
# 10) RODITELJSKI PRISTUP (e-mail + OIB)
# ==========================
def section_parent_portal():
    page_header("Roditeljski/pristup sportaša", "Upload pristupnice/privole/liječnička preko e-mail + OIB")
    conn = get_conn()
    e = st.text_input("E-mail", key="pp_email_v6")
    o = st.text_input("OIB člana", key="pp_oib_v6")
    if st.button("Prijava", key="pp_login_v6"):
        row = conn.execute("SELECT * FROM members WHERE (athlete_email=? OR parent_email=?) AND oib=?", (e,e,o)).fetchone()
        if not row:
            st.error("Nema člana s tim podatcima."); return
        st.session_state["pp_mid"] = row[0]; st.success("Prijava uspješna.")
    mid = st.session_state.get("pp_mid")
    if mid:
        st.markdown("**Upload dokumenata**")
        app_pdf = st.file_uploader("Pristupnica (PDF)", type=["pdf"], key="pp_app_v6")
        con_pdf = st.file_uploader("Privola (PDF)", type=["pdf"], key="pp_con_v6")
        med = st.file_uploader("Liječnička potvrda (PDF/JPG/PNG)", type=["pdf","jpg","jpeg","png"], key="pp_med_v6")
        med_until = st.date_input("Liječnička vrijedi do", value=date.today(), key="pp_med_until_v6")
        if st.button("Spremi dokumente", key="pp_save_v6"):
            if app_pdf: conn.execute("UPDATE members SET application_path=? WHERE id=?", (save_uploaded_file(app_pdf, "members/forms"), mid))
            if con_pdf: conn.execute("UPDATE members SET consent_path=? WHERE id=?", (save_uploaded_file(con_pdf, "members/forms"), mid))
            if med: conn.execute("UPDATE members SET medical_path=?, medical_valid_until=? WHERE id=?", (save_uploaded_file(med, "members/medical"), med_until.isoformat(), mid))
            conn.commit(); st.success("Dokumenti spremljeni.")
            st.info(f"Obavijestite klub: {KLUB_EMAIL}")

# ==========================
# MAIN
# ==========================
def main():
    st.set_page_config(page_title="HK Podravka – Admin (v6)", page_icon="🤼", layout="wide")
    css_style(); init_db()
    with st.sidebar:
        st.markdown(f"## {KLUB_NAZIV}")
        st.markdown(f"**E-mail:** {KLUB_EMAIL}")
        st.markdown(f"**Adresa:** {KLUB_ADRESA}")
        st.markdown(f"**OIB:** {KLUB_OIB}")
        st.markdown(f"**IBAN:** {KLUB_IBAN}")
        st.markdown(f"[Web]({KLUB_WEB})")
        section = st.radio("Navigacija", ["Klub","Članovi","Treneri","Natjecanja i rezultati","Statistika","Grupe","Veterani","Prisustvo","Komunikacija","Roditeljski pristup"])
    if section == "Klub": section_club()
    elif section == "Članovi": section_members()
    elif section == "Treneri": section_coaches()
    elif section == "Natjecanja i rezultati": section_competitions()
    elif section == "Statistika": section_stats()
    elif section == "Grupe": section_groups()
    elif section == "Veterani": section_veterans()
    elif section == "Prisustvo": section_attendance()
    elif section == "Komunikacija": section_communication()
    else: section_parent_portal()

if __name__ == "__main__":
    main()
