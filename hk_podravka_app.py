# -*- coding: utf-8 -*-
"""
HK Podravka – Admin aplikacija (Streamlit)
Verzija: v6.3 (stabilno) — odjeljci 1–5:
1) Klub  2) Članovi  3) Treneri  4) Natjecanja i rezultati  5) Statistika
"""

import os, io, sqlite3, json
from datetime import datetime, date, timedelta
from typing import Optional
import pandas as pd
import streamlit as st

# ---- Stil (boje kluba) ----
PRIMARY_RED = "#c1121f"
GOLD = "#d4af37"
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

# ---- Pomoćne ----
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    c = get_conn()
    cur = c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS club_info (
        id INTEGER PRIMARY KEY CHECK (id=1),
        name TEXT, email TEXT, address TEXT, oib TEXT, web TEXT, iban TEXT,
        president TEXT, secretary TEXT, board_json TEXT, supervisory_json TEXT,
        instagram TEXT, facebook TEXT, tiktok TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS club_docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, filename TEXT, path TEXT, uploaded_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT, last_name TEXT, dob TEXT, gender TEXT, oib TEXT UNIQUE,
        street TEXT, city TEXT, postal_code TEXT,
        athlete_email TEXT, parent_email TEXT,
        id_card_number TEXT, id_card_issuer TEXT, id_card_valid_until TEXT,
        passport_number TEXT, passport_issuer TEXT, passport_valid_until TEXT,
        active_competitor INTEGER DEFAULT 0, veteran INTEGER DEFAULT 0, other_flag INTEGER DEFAULT 0,
        pays_fee INTEGER DEFAULT 0, fee_amount REAL DEFAULT 30.0,
        group_name TEXT,
        photo_path TEXT, application_path TEXT, consent_path TEXT,
        medical_path TEXT, medical_valid_until TEXT, consent_checked_date TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS coaches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT, last_name TEXT, dob TEXT, oib TEXT, email TEXT, iban TEXT,
        group_name TEXT, contract_path TEXT, other_docs_json TEXT, photo_path TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS competitions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT, kind_other TEXT, name TEXT,
        date_from TEXT, date_to TEXT, place TEXT,
        style TEXT, age_cat TEXT,
        country TEXT, country_iso3 TEXT,
        team_rank INTEGER, club_competitors INTEGER, total_competitors INTEGER,
        clubs_count INTEGER, countries_count INTEGER,
        coaches_json TEXT, notes TEXT, bulletin_url TEXT, website_link TEXT, gallery_paths_json TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition_id INTEGER REFERENCES competitions(id) ON DELETE CASCADE,
        member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
        category TEXT, style TEXT,
        fights_total INTEGER, wins INTEGER, losses INTEGER, placement INTEGER,
        wins_detail_json TEXT, losses_detail_json TEXT, note TEXT
    )""")
    # seed club row
    cur.execute("SELECT 1 FROM club_info WHERE id=1")
    if cur.fetchone() is None:
        cur.execute("""INSERT INTO club_info (id,name,email,address,oib,web,iban,president,secretary,board_json,supervisory_json,instagram,facebook,tiktok)
                       VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (KLUB_NAZIV, KLUB_EMAIL, KLUB_ADRESA, KLUB_OIB, KLUB_WEB, KLUB_IBAN, "", "", "[]", "[]", "", "", ""))
    c.commit(); c.close()


    try:
        return pd.read_sql_query(f"SELECT {cols} FROM coaches ORDER BY {order}", conn)
    except Exception:
        ensure_coaches_table(conn)
        return pd.read_sql_query(f"SELECT {cols} FROM coaches ORDER BY {order}", conn)



def ensure_coaches_table(conn):
    # Create coaches table if it doesn't exist
    conn.execute("""CREATE TABLE IF NOT EXISTS coaches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT, last_name TEXT, dob TEXT, oib TEXT, email TEXT, iban TEXT,
        group_name TEXT, contract_path TEXT, other_docs_json TEXT, photo_path TEXT
    )""")
    conn.commit()

def ensure_coaches_exists(conn):
    # Check via sqlite_master then create if missing
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='coaches'")
    if cur.fetchone() is None:
        ensure_coaches_table(conn)


def css_style():
    st.markdown(f"""
    <style>
      .app-header {{background: linear-gradient(90deg,{PRIMARY_RED},{GOLD}); color:{WHITE}; padding:16px 20px; border-radius:16px; margin-bottom:16px;}}
      .card {{background:{LIGHT_BG}; border:1px solid #f0e6da; border-radius:16px; padding:16px; margin-bottom:12px;}}
    </style>
    """, unsafe_allow_html=True)

def page_header(title, subtitle=None):
    st.markdown(f"<div class='app-header'><h2 style='margin:0'>{title}</h2>{('<div>'+subtitle+'</div>') if subtitle else ''}</div>", unsafe_allow_html=True)

def save_uploaded_file(uploaded, subdir):
    if not uploaded: return ""
    fn = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded.name}"
    path = os.path.join(UPLOAD_DIR, subdir); os.makedirs(path, exist_ok=True)
    full = os.path.join(path, fn)
    with open(full, "wb") as f: f.write(uploaded.getbuffer())
    return full

def excel_bytes_from_df(df: pd.DataFrame, sheet_name="Sheet1") -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name=sheet_name)
    return out.getvalue()

def mailto_link(to, subject="", body=""):
    import urllib.parse as up
    q={}
    if subject: q["subject"]=subject
    if body: q["body"]=body
    qp = up.urlencode(q)
    return f"mailto:{to}?{qp}" if qp else f"mailto:{to}"

# ---- 1) KLUB ----
def section_club():
    page_header("Klub – osnovni podaci", KLUB_NAZIV)
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM club_info WHERE id=1", conn); row = df.iloc[0]

    def _to_df(js):
        try:
            d = pd.read_json(js)
            if isinstance(d, pd.DataFrame): return d
        except Exception: ...
        return pd.DataFrame(columns=["ime_prezime","telefon","email"])

    board_pref = _to_df(row.get("board_json","[]"))
    superv_pref = _to_df(row.get("supervisory_json","[]"))

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

        st.markdown("**Članovi predsjedništva** (ime, telefon, e-mail)")
        board = st.data_editor(board_pref if not board_pref.empty else pd.DataFrame(columns=["ime_prezime","telefon","email"]), num_rows="dynamic", key="board_ed")

        st.markdown("**Nadzorni odbor** (ime, telefon, e-mail)")
        superv = st.data_editor(superv_pref if not superv_pref.empty else pd.DataFrame(columns=["ime_prezime","telefon","email"]), num_rows="dynamic", key="sup_ed")

        st.markdown("**Društvene mreže**")
        c3,c4,c5 = st.columns(3)
        instagram = c3.text_input("Instagram", row["instagram"] or "")
        facebook = c4.text_input("Facebook", row["facebook"] or "")
        tiktok = c5.text_input("TikTok", row["tiktok"] or "")

        st.markdown("**Dokumenti kluba**")
        up_statut = st.file_uploader("Statut (PDF)", type=["pdf"], key="stat_pdf")
        up_other = st.file_uploader("Drugi dokument (PDF/IMG)", type=["pdf","png","jpg","jpeg"], key="oth_pdf")

        submitted = st.form_submit_button("Spremi podatke kluba")

    if submitted:
        conn.execute("""UPDATE club_info SET name=?,email=?,address=?,oib=?,web=?,iban=?,president=?,secretary=?,board_json=?,supervisory_json=?,instagram=?,facebook=?,tiktok=? WHERE id=1""",
                     (name,email,address,oib,web,iban,president,secretary,
                      (board if isinstance(board,pd.DataFrame) else pd.DataFrame(board)).to_json(),
                      (superv if isinstance(superv,pd.DataFrame) else pd.DataFrame(superv)).to_json(),
                      instagram,facebook,tiktok))
        if up_statut:
            p = save_uploaded_file(up_statut,"club_docs"); conn.execute("INSERT INTO club_docs(kind,filename,path,uploaded_at) VALUES (?,?,?,?)", ("statut", up_statut.name, p, datetime.now().isoformat()))
        if up_other:
            p = save_uploaded_file(up_other,"club_docs"); conn.execute("INSERT INTO club_docs(kind,filename,path,uploaded_at) VALUES (?,?,?,?)", ("ostalo", up_other.name, p, datetime.now().isoformat()))
        conn.commit(); st.success("Podaci kluba spremljeni.")

    docs = pd.read_sql_query("SELECT id, kind, filename, uploaded_at FROM club_docs ORDER BY uploaded_at DESC", conn)
    if not docs.empty: st.dataframe(docs, use_container_width=True)
    conn.close()

# ---- 2) ČLANOVI ----
def members_template_df():
    return pd.DataFrame(columns=[
        "ime","prezime","datum_rodenja(YYYY-MM-DD)","spol(M/Ž)","oib",
        "ulica_i_broj","grad","postanski_broj",
        "email_sportasa","email_roditelja",
        "br_osobne","osobna_vrijedi_do(YYYY-MM-DD)","osobna_izdavatelj",
        "br_putovnice","putovnica_vrijedi_do(YYYY-MM-DD)","putovnica_izdavatelj",
        "aktivni_natjecatelj(0/1)","veteran(0/1)","ostalo(0/1)",
        "placa_clanarinu(0/1)","iznos_clanarine(EUR)","grupa"
    ])

def section_members():
    page_header("Članovi", "Uvoz/izvoz Excel, svi podaci, dokumenti")
    conn = get_conn()

    st.download_button("Skini predložak (Excel)", data=excel_bytes_from_df(members_template_df(),"ClanoviPredlozak"), file_name="predlozak_clanovi.xlsx")

    export_df = pd.read_sql_query("""SELECT first_name AS ime, last_name AS prezime, dob AS datum_rodenja, gender AS spol, oib,
        street AS ulica_i_broj, city AS grad, postal_code AS postanski_broj,
        athlete_email AS email_sportasa, parent_email AS email_roditelja,
        id_card_number AS br_osobne, id_card_valid_until AS osobna_vrijedi_do, id_card_issuer AS osobna_izdavatelj,
        passport_number AS br_putovnice, passport_valid_until AS putovnica_vrijedi_do, passport_issuer AS putovnica_izdavatelj,
        active_competitor AS aktivni_natjecatelj, veteran, other_flag AS ostalo,
        pays_fee AS placa_clanarinu, fee_amount AS iznos_clanarine, group_name AS grupa
        FROM members ORDER BY last_name, first_name""", conn)
    st.download_button("Skini članove (Excel)", data=excel_bytes_from_df(export_df,"Clanovi"), file_name="clanovi_export.xlsx", disabled=export_df.empty)

    st.markdown("#### Učitaj članove iz Excel tablice")
    up_excel = st.file_uploader("Upload Excel (po predlošku)", type=["xlsx"], key="members_excel_v63")
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
            conn.commit(); st.success("Članovi uvezeni/ažurirani iz Excela.")
        except Exception as e:
            st.error(f"Greška pri uvozu: {e}")

    st.markdown("---"); st.markdown("### Unos novog člana")
    with st.form("member_form_v63"):
        c1,c2,c3 = st.columns(3)
        first_name = c1.text_input("Ime")
        last_name  = c2.text_input("Prezime")
        dob        = c3.date_input("Datum rođenja", value=date(2010,1,1), key="dob_member_v63")
        gender     = c1.selectbox("Spol (M/Ž)", ["","M","Ž"])
        oib        = c2.text_input("OIB")
        st.markdown("**Adresa**")
        a1,a2,a3 = st.columns(3)
        street = a1.text_input("Ulica i kućni broj")
        city   = a2.text_input("Grad / mjesto prebivališta")
        postal = a3.text_input("Poštanski broj")
        e1,e2 = st.columns(2)
        email_s = e1.text_input("E-mail sportaša")
        email_p = e2.text_input("E-mail roditelja")
        st.markdown("**Osobna iskaznica**")
        id1,id2,id3 = st.columns(3)
        id_no = id1.text_input("Broj osobne")
        id_until = id2.date_input("Osobna vrijedi do", value=date.today(), key="id_card_until_v63")
        id_issuer = id3.text_input("Izdavatelj osobne")
        st.markdown("**Putovnica**")
        p1,p2,p3 = st.columns(3)
        pass_no = p1.text_input("Broj putovnice")
        pass_until = p2.date_input("Putovnica vrijedi do", value=date.today(), key="pass_until_v63")
        pass_issuer = p3.text_input("Izdavatelj putovnice")
        st.markdown("**Status i članarina**")
        s1,s2,s3 = st.columns(3)
        active = s1.checkbox("Aktivni natjecatelj/ica", value=False)
        veteran = s2.checkbox("Veteran", value=False)
        other = s3.checkbox("Ostalo", value=False)
        pays_fee = st.checkbox("Plaća članarinu", value=False)
        fee_amt = st.number_input("Iznos članarine (EUR)", value=30.0, step=1.0)
        group_name = st.selectbox("Grupa", options=["","Hrvači","Hrvačice","Veterani","Ostalo"])
        photo   = st.file_uploader("Slika člana", type=["png","jpg","jpeg"])
        app_pdf = st.file_uploader("Pristupnica (PDF)", type=["pdf"])
        con_pdf = st.file_uploader("Privola (PDF)", type=["pdf"])
        up_med  = st.file_uploader("Liječnička potvrda (PDF/JPG)", type=["pdf","png","jpg","jpeg"], key="med_upload_v63")
        med_valid = st.date_input("Liječnička potvrda vrijedi do", value=date.today(), key="med_valid_v63")
        submit_member = st.form_submit_button("Spremi člana")

    if submit_member:
        def up(f, sub): return save_uploaded_file(f, sub) if f else ""
        photo_path = up(photo, "members/photos")
        app_path   = up(app_pdf, "members/forms")
        con_path   = up(con_pdf, "members/forms")
        med_path   = up(up_med, "members/medical")
        conn.execute("""
            INSERT INTO members(first_name,last_name,dob,gender,oib,street,city,postal_code,
                athlete_email,parent_email,id_card_number,id_card_issuer,id_card_valid_until,
                passport_number,passport_issuer,passport_valid_until,
                active_competitor,veteran,other_flag,pays_fee,fee_amount,group_name,
                photo_path,application_path,consent_path,medical_path,medical_valid_until,consent_checked_date)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(oib) DO UPDATE SET
                first_name=excluded.first_name,last_name=excluded.last_name,dob=excluded.dob,gender=excluded.gender,
                street=excluded.street,city=excluded.city,postal_code=excluded.postal_code,
                athlete_email=excluded.athlete_email,parent_email=excluded.parent_email,
                id_card_number=excluded.id_card_number,id_card_issuer=excluded.id_card_issuer,id_card_valid_until=excluded.id_card_valid_until,
                passport_number=excluded.passport_number,passport_issuer=excluded.passport_issuer,passport_valid_until=excluded.passport_valid_until,
                active_competitor=excluded.active_competitor,veteran=excluded.veteran,other_flag=excluded.other_flag,
                pays_fee=excluded.pays_fee,fee_amount=excluded.fee_amount,group_name=excluded.group_name,
                photo_path=COALESCE(excluded.photo_path,photo_path),
                application_path=COALESCE(excluded.application_path,application_path),
                consent_path=COALESCE(excluded.consent_path,consent_path),
                medical_path=COALESCE(excluded.medical_path,medical_path),
                medical_valid_until=excluded.medical_valid_until,
                consent_checked_date=excluded.consent_checked_date
        """, (first_name,last_name,dob.isoformat(),gender,oib,street,city,postal,email_s,email_p,id_no,id_issuer,id_until.isoformat(),
              pass_no,pass_issuer,pass_until.isoformat(),int(active),int(veteran),int(other),int(pays_fee),float(fee_amt),group_name,
              photo_path,app_path,con_path,med_path,med_valid.isoformat(), datetime.now().date().isoformat()))
        conn.commit(); st.success("Član spremljen.")

    st.markdown("---"); st.markdown("### Popis članova")
    members_df = pd.read_sql_query("""SELECT id, first_name, last_name, gender, dob, oib, street, city, postal_code, athlete_email, parent_email,
        group_name, pays_fee, fee_amount, medical_valid_until FROM members ORDER BY last_name, first_name""", conn)
    if not members_df.empty:
        edited = st.data_editor(members_df, num_rows="dynamic", use_container_width=True, key="members_grid_v63")
        c1,c2,c3 = st.columns(3)
        if c1.button("Spremi izmjene"):
            for _, r in edited.iterrows():
                conn.execute("""UPDATE members SET first_name=?,last_name=?,gender=?,dob=?,street=?,city=?,postal_code=?,athlete_email=?,parent_email=?,group_name=?,pays_fee=?,fee_amount=?,medical_valid_until=? WHERE id=?""",
                             (str(r.get("first_name","")),str(r.get("last_name","")),str(r.get("gender","")),str(r.get("dob",""))[:10],
                              str(r.get("street","")),str(r.get("city","")),str(r.get("postal_code","")),
                              str(r.get("athlete_email","")),str(r.get("parent_email","")),
                              str(r.get("group_name","")),int(r.get("pays_fee",0) or 0),float(r.get("fee_amount",0) or 0.0),
                              str(r.get("medical_valid_until","")),int(r["id"])))
            conn.commit(); st.success("Izmjene spremljene.")
        sel = c2.selectbox("Akcije (odaberi ID)", options=[0]+edited["id"].tolist())
        if sel:
            m = pd.read_sql_query("SELECT * FROM members WHERE id=?", conn, params=(int(sel),)).iloc[0]
            if m["athlete_email"]: c3.link_button("E-mail sportašu", url=mailto_link(m["athlete_email"], "Obavijest HK Podravka"))
            if m["parent_email"]:  st.link_button("E-mail roditelju", url=mailto_link(m["parent_email"], "Obavijest HK Podravka"))
            if st.button("Obriši ovog člana"): conn.execute("DELETE FROM members WHERE id=?", (int(sel),)); conn.commit(); st.success("Član obrisan."); st.rerun()
    conn.close()

# ---- 3) TRENERI ----
def section_coaches():
    page_header("Treneri", "Unos trenera, dokumenti i slike")
    conn = get_conn()
    with st.form("coach_form_v63"):
        c1,c2,c3 = st.columns(3)
        first_name = c1.text_input("Ime")
        last_name  = c2.text_input("Prezime")
        dob        = c3.date_input("Datum rođenja", value=date(1990,1,1), key="coach_dob_v63")
        oib        = c1.text_input("OIB")
        email      = c2.text_input("E-mail")
        iban       = c3.text_input("IBAN broj računa")
        group_name = st.text_input("Grupa koju trenira (može se mijenjati)")
        contract   = st.file_uploader("Ugovor s klubom (PDF)", type=["pdf"], key="coach_contract_v63")
        other_docs = st.file_uploader("Drugi dokumenti (višestruko)", type=["pdf","png","jpg","jpeg"], accept_multiple_files=True, key="coach_docs_v63")
        photo      = st.file_uploader("Slika trenera", type=["png","jpg","jpeg"], key="coach_photo_v63")
        submit     = st.form_submit_button("Spremi trenera")
    if submit:
        def up(f, sub): return save_uploaded_file(f, sub) if f else ""
        contract_path = up(contract, "coaches/contracts")
        other_paths = []; 
        for f in (other_docs or []): other_paths.append(up(f, "coaches/docs"))
        photo_path = up(photo, "coaches/photos")
        conn.execute("""INSERT INTO coaches(first_name,last_name,dob,oib,email,iban,group_name,contract_path,other_docs_json,photo_path) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                     (first_name,last_name,dob.isoformat(),oib,email,iban,group_name,contract_path, pd.Series(other_paths).to_json(), photo_path))
        conn.commit(); st.success("Trener spremljen.")

    st.markdown("---"); st.markdown("### Popis trenera")
    ensure_coaches_exists(conn)
    coaches_df = pd.read_sql_query("""SELECT id, first_name, last_name, dob, oib, email, iban, group_name FROM coaches ORDER BY last_name, first_name""", conn)
    if not coaches_df.empty:
        edited = st.data_editor(coaches_df, num_rows="dynamic", use_container_width=True, key="coaches_grid_v63")
        c1,c2,c3 = st.columns(3)
        if c1.button("Spremi izmjene (treneri)"):
            for _, r in edited.iterrows():
                conn.execute("""UPDATE coaches SET first_name=?, last_name=?, dob=?, oib=?, email=?, iban=?, group_name=? WHERE id=?""",
                             (str(r.get("first_name","")),str(r.get("last_name","")),str(r.get("dob",""))[:10],str(r.get("oib","")),str(r.get("email","")),str(r.get("iban","")),str(r.get("group_name","")),int(r["id"])))
            conn.commit(); st.success("Izmjene spremljene.")
        del_id = c2.number_input("ID trenera za brisanje", min_value=0, step=1, value=0)
        if c3.button("Obriši trenera po ID-u") and del_id>0:
            conn.execute("DELETE FROM coaches WHERE id=?", (int(del_id),)); conn.commit(); st.success(f"Trener #{del_id} obrisan.")
    conn.close()

# ---- 4) NATJECANJA I REZULTATI ----
def competitions_template_df():
    return pd.DataFrame(columns=[
        "vrsta","druga_vrsta","ime_natjecanja","datum_od(YYYY-MM-DD)","datum_do(YYYY-MM-DD)","mjesto",
        "stil(GR/FS/WW/BW/MOD)","uzrast(POC/U11/U13/U15/U17/U20/U23/SEN)",
        "drzava","drzava_iso3","ekipni_poredak","br_natj_klub","br_natj_ukupno","br_klubova","br_zemalja",
        "treneri(; razdvojeno)","zapis","bilten_url","web_link"
    ])

def section_competitions():
    page_header("Natjecanja i rezultati", "Unos natjecanja + rezultata")
    conn = get_conn()
    st.download_button("Predložak (Excel)", data=excel_bytes_from_df(competitions_template_df(),"NatjecanjaPredlozak"), file_name="predlozak_natjecanja.xlsx")
    export_df = pd.read_sql_query("""SELECT id, kind, kind_other, name, date_from, date_to, place, style, age_cat, country, country_iso3, team_rank, club_competitors, total_competitors, clubs_count, countries_count, notes, bulletin_url, website_link FROM competitions ORDER BY date_from DESC""", conn)
    st.download_button("Skini natjecanja (Excel)", data=excel_bytes_from_df(export_df,"Natjecanja"), file_name="natjecanja_export.xlsx", disabled=export_df.empty)

    st.markdown("### Unos natjecanja")
    kind = st.selectbox("Vrsta", ["PRVENSTVO HRVATSKE","MEĐUNARODNI TURNIR","REPREZENTATIVNI NASTUP","HRVAČKA LIGA ZA SENIORE","MEĐUNARODNA HRVAČKA LIGA ZA KADETE","REGIONALNO PRVENSTVO","LIGA ZA DJEVOJČICE","OSTALO"])
    kind_other = st.text_input("Druga vrsta natjecanja") if kind=="OSTALO" else ""
    name = st.text_input("Ime natjecanja (ako postoji)")
    c1,c2,c3 = st.columns(3)
    date_from = c1.date_input("Datum od", value=date.today(), key="comp_from_v63")
    date_to   = c2.date_input("Datum do", value=date.today(), key="comp_to_v63")
    place     = c3.text_input("Mjesto")
    style = st.selectbox("Hrvački stil", ["GR","FS","WW","BW","MODIFICIRANO"])
    age   = st.selectbox("Uzrast", ["POČETNICI","U11","U13","U15","U17","U20","U23","SENIORI"])
    country = st.text_input("Država")
    iso3    = st.text_input("ISO-3 (npr. HRV)")
    c1,c2,c3,c4,c5 = st.columns(5)
    team_rank = c1.number_input("Ekipni poredak", min_value=0, step=1)
    club_n    = c2.number_input("Broj natjecatelja (klub)", min_value=0, step=1)
    total_n   = c3.number_input("Ukupan broj natjecatelja", min_value=0, step=1)
    clubs_n   = c4.number_input("Broj klubova", min_value=0, step=1)
    countries_n = c5.number_input("Broj zemalja", min_value=0, step=1)

    # treneri (lista imena iz coaches)
    ensure_coaches_exists(conn)
    ensure_coaches_exists(conn)
    coaches_df = pd.read_sql_query("SELECT id, first_name, last_name FROM coaches ORDER BY last_name, first_name", conn)
    coach_names = st.multiselect("Trener(i) koji su vodili", options=(coaches_df["first_name"]+" "+coaches_df["last_name"]).tolist())

    notes = st.text_area("Zapažanje trenera / opis za objavu")
    gallery = st.file_uploader("Upload slika s natjecanja", type=["png","jpg","jpeg"], accept_multiple_files=True, key="comp_gallery_v63")
    bulletin_url = st.text_input("Poveznica na rezultate / bilten")
    website_link = st.text_input("Poveznica na objavu na webu")

    if st.button("Spremi natjecanje"):
        gallery_paths = []
        for g in (gallery or []):
            gallery_paths.append(save_uploaded_file(g, "competitions/gallery"))
        conn.execute("""INSERT INTO competitions(kind,kind_other,name,date_from,date_to,place,style,age_cat,country,country_iso3,team_rank,club_competitors,total_competitors,clubs_count,countries_count,coaches_json,notes,bulletin_url,website_link,gallery_paths_json)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (kind,kind_other,name,date_from.isoformat(),date_to.isoformat(),place,style,age,country,iso3,int(team_rank),int(club_n),int(total_n),int(clubs_n),int(countries_n),
                      pd.Series(coach_names).to_json(), notes, bulletin_url, website_link, pd.Series(gallery_paths).to_json()))
        conn.commit(); st.success("Natjecanje spremljeno.")

    st.markdown("---"); st.markdown("### Rezultati – unos po natjecatelju")
    comps = pd.read_sql_query("SELECT id, COALESCE(name, kind) AS title, date_from FROM competitions ORDER BY date_from DESC", conn)
    comp_opts = {f"{r['id']} – {r['title']} ({r['date_from']})": r['id'] for _, r in comps.iterrows()}
    comp_sel_label = st.selectbox("Odaberi natjecanje", options=["-"] + list(comp_opts.keys()), key="res_comp_sel_v63")
    mems = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full FROM members ORDER BY last_name, first_name", conn)

    if comp_sel_label != "-":
        comp_id = comp_opts[comp_sel_label]
        msel = st.selectbox("Član", options=["-"] + [f"{r.id} – {r.full}" for r in mems.itertuples()], key="res_member_sel_v63")
        if msel != "-":
            mid = int(msel.split(" – ")[0])
            c1,c2,c3 = st.columns(3)
            cat = c1.text_input("Kategorija / težina", key="res_cat_v63")
            stl = c2.selectbox("Stil", ["GR","FS","WW","BW","MODIFICIRANO"], key="res_style_v63")
            fights = c3.number_input("Ukupno borbi", min_value=0, step=1, key="res_fights_v63")
            w = c1.number_input("Pobjede", min_value=0, step=1, key="res_wins_v63")
            l = c2.number_input("Porazi", min_value=0, step=1, key="res_losses_v63")
            place = c3.number_input("Plasman (1–100)", min_value=0, max_value=100, step=1, key="res_place_v63")
            wins_d = st.text_area("Pobjede – 'ime prezime;klub' razdvojeno | ", key="wins_detail_v63")
            losses_d = st.text_area("Porazi – 'ime prezime;klub' razdvojeno | ", key="loss_detail_v63")
            note = st.text_area("Napomena trenera", key="res_note_v63")
            if st.button("Spremi rezultat", key="save_result_v63"):
                conn.execute("""INSERT INTO results(competition_id,member_id,category,style,fights_total,wins,losses,placement,wins_detail_json,losses_detail_json,note)
                                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                             (comp_id, mid, cat, stl, int(fights), int(w), int(l), int(place),
                              pd.Series([s for s in wins_d.split('|') if s.strip()]).to_json(),
                              pd.Series([s for s in losses_d.split('|') if s.strip()]).to_json(), note))
                conn.commit(); st.success("Rezultat spremljen.")

    st.markdown("---"); st.markdown("### Pretraga i Excel izvoz rezultata")
    year = st.number_input("Godina", min_value=2000, max_value=2100, value=datetime.now().year, step=1, key="res_year_v63")
    df = pd.read_sql_query("""SELECT c.date_from, c.kind, c.name, c.place, c.style, c.age_cat, r.member_id,
           (SELECT first_name || ' ' || last_name FROM members m WHERE m.id=r.member_id) AS sportas,
           r.category, r.fights_total, r.wins, r.losses, r.placement
        FROM results r JOIN competitions c ON r.competition_id=c.id WHERE substr(c.date_from,1,4)=? ORDER BY c.date_from DESC""", conn, params=(str(year),))
    st.dataframe(df, use_container_width=True)
    st.download_button("Skini rezultate (Excel)", data=excel_bytes_from_df(df,"Rezultati"), file_name=f"rezultati_{year}.xlsx", disabled=df.empty)
    conn.close()

# ---- 5) STATISTIKA ----
def section_stats():
    page_header("Statistika", "Po godini, natjecanju, sportašu, kategoriji")
    conn = get_conn()
    year = st.number_input("Godina", min_value=2000, max_value=2100, value=datetime.now().year, step=1, key="stat_year_v63")
    df = pd.read_sql_query("""SELECT c.kind, c.age_cat, r.style, SUM(r.fights_total) AS borbi, SUM(r.wins) AS pobjede, SUM(r.losses) AS porazi,
        SUM(CASE WHEN r.placement=1 THEN 1 ELSE 0 END) AS zlato, SUM(CASE WHEN r.placement=2 THEN 1 ELSE 0 END) AS srebro, SUM(CASE WHEN r.placement=3 THEN 1 ELSE 0 END) AS bronca
        FROM competitions c JOIN results r ON r.competition_id = c.id WHERE substr(c.date_from,1,4)=? GROUP BY c.kind, c.age_cat, r.style ORDER BY c.kind, c.age_cat""", conn, params=(str(year),))
    st.dataframe(df, use_container_width=True)
    mems = pd.read_sql_query("SELECT id, first_name || ' ' || last_name AS full FROM members ORDER BY last_name, first_name", conn)
    sel = st.selectbox("Sportaš/ica", options=["-"] + [f"{r.id} – {r.full}" for r in mems.itertuples()], key="stat_member_v63")
    if sel != "-":
        mid = int(sel.split(" – ")[0])
        d2 = pd.read_sql_query("""SELECT c.date_from, c.kind, c.name, r.category, r.style, r.fights_total, r.wins, r.losses, r.placement
                                  FROM results r JOIN competitions c ON r.competition_id=c.id
                                  WHERE r.member_id=? AND substr(c.date_from,1,4)=? ORDER BY c.date_from DESC""", conn, params=(mid,str(year)))
        st.dataframe(d2, use_container_width=True)
    conn.close()

# ---- MAIN ----
def main():
    st.set_page_config(page_title="HK Podravka – Admin v6.3", page_icon="🤼", layout="wide")
    css_style(); init_db()
    with st.sidebar:
        st.markdown(f"## {KLUB_NAZIV}")
        st.markdown(f"**E-mail:** {KLUB_EMAIL}")
        st.markdown(f"**Adresa:** {KLUB_ADRESA}")
        st.markdown(f"**OIB:** {KLUB_OIB}")
        st.markdown(f"**IBAN:** {KLUB_IBAN}")
        st.markdown(f"[Web]({KLUB_WEB})")
        section = st.radio("Navigacija", ["Klub", "Članovi", "Treneri", "Natjecanja i rezultati", "Statistika"])

    if section == "Klub":
        section_club()
    elif section == "Članovi":
        section_members()
    elif section == "Treneri":
        section_coaches()
    elif section == "Natjecanja i rezultati":
        section_competitions()
    else:
        section_stats()

if __name__ == "__main__":
    main()
