# -*- coding: utf-8 -*-
"""
HK Podravka – Admin (v9)
Popravljeno: selectbox f-string (bez escape).
Dodano: Statistika (po godinama, uzrastima, natjecanjima, medaljama) s izvozom.
"""
import os, io, json, sqlite3
from datetime import date, datetime, timedelta, time
import pandas as pd
import streamlit as st

PRIMARY_RED = "#c1121f"; GOLD = "#d4af37"; WHITE = "#ffffff"
DB_PATH = "hk_podravka.db"; UPLOAD_DIR = "uploads"; os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT, last_name TEXT, dob TEXT, gender TEXT, oib TEXT UNIQUE,
        street TEXT, city TEXT, postal_code TEXT,
        athlete_email TEXT, parent_email TEXT,
        id_card_number TEXT, id_card_issuer TEXT, id_card_valid_until TEXT,
        passport_number TEXT, passport_issuer TEXT, passport_valid_until TEXT,
        active_competitor INTEGER DEFAULT 0, veteran INTEGER DEFAULT 0, other_flag INTEGER DEFAULT 0,
        pays_fee INTEGER DEFAULT 0, fee_amount REAL DEFAULT 30.0,
        group_name TEXT, photo_path TEXT,
        application_path TEXT, consent_path TEXT,
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
        category TEXT, style TEXT, fights_total INTEGER, wins INTEGER, losses INTEGER, placement INTEGER,
        wins_detail_json TEXT, losses_detail_json TEXT, note TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, description TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS attendance_trainers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coach_id INTEGER REFERENCES coaches(id) ON DELETE SET NULL,
        coach_name TEXT, group_name TEXT,
        date TEXT, time_from TEXT, time_to TEXT, place TEXT, hours REAL
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS attendance_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        member_id INTEGER REFERENCES members(id) ON DELETE SET NULL,
        member_name TEXT, group_name TEXT,
        date TEXT, hours REAL, status TEXT
    )""")
    conn.commit(); conn.close()

def css_style():
    st.markdown(f"""
    <style>
      .app-header {{background: linear-gradient(90deg,{PRIMARY_RED},{GOLD}); color:{WHITE}; padding:14px 18px; border-radius:14px; margin-bottom:12px;}}
      .stButton>button {{background:{PRIMARY_RED}; color:white; border-radius:10px;}}
      .danger {{background:#ffd6d6!important;}}
    </style>
    """, unsafe_allow_html=True)

def page_header(title, subtitle=None):
    st.markdown(f"<div class='app-header'><h3 style='margin:0'>{title}</h3>{('<div>'+subtitle+'</div>') if subtitle else ''}</div>", unsafe_allow_html=True)

def save_upload(file, subdir):
    if not file: return ""
    path = os.path.join(UPLOAD_DIR, subdir); os.makedirs(path, exist_ok=True)
    fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}"
    full = os.path.join(path, fname)
    with open(full, "wb") as f: f.write(file.getbuffer())
    return full

def excel_bytes(df: pd.DataFrame, sheet="Sheet1"):
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name=sheet)
    return out.getvalue()

# ===== Sekcije =====
def section_coaches():
    page_header("Treneri", "Popis trenera")
    conn = get_conn()
    try:
        coaches_df = pd.read_sql_query("""SELECT id, first_name, last_name, dob, oib, email, iban, group_name FROM coaches ORDER BY last_name, first_name""", conn)
    except Exception as e:
        st.error(f"SQL greška: {e}")
        coaches_df = pd.DataFrame()
    if not coaches_df.empty:
        edited = st.data_editor(coaches_df, num_rows="dynamic", use_container_width=True, key="coaches_grid_v9")
        c1,c2,c3 = st.columns(3)
        if c1.button("Spremi izmjene (treneri)"):
            for _, r in edited.iterrows():
                conn.execute("""UPDATE coaches SET first_name=?, last_name=?, dob=?, oib=?, email=?, iban=?, group_name=? WHERE id=?""",
                             (str(r.get("first_name","")),str(r.get("last_name","")),str(r.get("dob",""))[:10],str(r.get("oib","")),str(r.get("email","")),str(r.get("iban","")),str(r.get("group_name","")),int(r["id"])))
            conn.commit(); st.success("Izmjene spremljene.")
        del_id = c2.number_input("ID za brisanje", min_value=0, step=1, value=0)
        if c3.button("Obriši trenera") and del_id>0:
            conn.execute("DELETE FROM coaches WHERE id=?", (int(del_id),)); conn.commit(); st.success("Trener obrisan."); st.rerun()
    # Unos novog
    with st.form("coach_new_v9"):
        st.subheader("Dodaj trenera")
        c1,c2,c3 = st.columns(3)
        first_name = c1.text_input("Ime"); last_name = c2.text_input("Prezime"); dob = c3.date_input("Datum rođenja", value=date(1990,1,1))
        oib = c1.text_input("OIB"); email = c2.text_input("E-mail"); iban = c3.text_input("IBAN broj")
        group_name = st.text_input("Grupa")
        submit = st.form_submit_button("Spremi")
    if submit:
        conn.execute("""INSERT INTO coaches(first_name,last_name,dob,oib,email,iban,group_name) VALUES(?,?,?,?,?,?,?)""",
                     (first_name,last_name,dob.isoformat(),oib,email,iban,group_name))
        conn.commit(); st.success("Trener dodan."); st.rerun()
    conn.close()

def highlight_medical(df):
    def style_row(r):
        col = "medical_valid_until"
        try:
            d = pd.to_datetime(str(r.get(col,"") or ""), errors="coerce")
        except Exception:
            d = pd.NaT
        if pd.isna(d):
            return ['']*len(r)
        days = (d.date() - date.today()).days
        if days <= 14:
            return ['background-color:#ffd6d6']*len(r)
        return ['']*len(r)
    return df.style.apply(style_row, axis=1)

def section_members():
    page_header("Članovi", "Isticanje liječničke potvrde 14 dana prije isteka")
    conn = get_conn()
    df = pd.read_sql_query("""SELECT id, first_name, last_name, gender, dob, oib, street, city, postal_code, athlete_email, parent_email,
        group_name, pays_fee, fee_amount, medical_valid_until FROM members ORDER BY last_name, first_name""", conn)
    if not df.empty:
        st.dataframe(highlight_medical(df), use_container_width=True)
    else:
        st.info("Nema članova u bazi.")
    conn.close()

def section_groups():
    page_header("Grupe", "Upravljanje grupama, premještaj članova")
    conn = get_conn()
    groups = pd.read_sql_query("SELECT id, name, description FROM groups ORDER BY name", conn)
    edited = st.data_editor(groups, num_rows="dynamic", use_container_width=True, key="groups_grid_v9")
    c1,c2 = st.columns(2)
    if c1.button("Spremi grupe"):
        conn.execute("DELETE FROM groups")
        for _, r in edited.iterrows():
            if str(r.get("name","")).strip():
                conn.execute("INSERT INTO groups(id,name,description) VALUES(?,?,?)",
                             (int(r["id"]) if pd.notna(r["id"]) else None, str(r["name"]), str(r.get("description",""))))
        conn.commit(); st.success("Grupe spremljene.")
    st.markdown("---"); st.subheader("Premještaj člana")
    members = pd.read_sql_query("SELECT id, first_name||' '||last_name AS full, group_name FROM members ORDER BY last_name, first_name", conn)
    mem_opts = {f"{r['id']} – {r['full']} (grupa: {r['group_name'] or ''})": r['id'] for _, r in members.iterrows()}
    sel = st.selectbox("Član", ["-"] + list(mem_opts.keys()))
    new_group = st.text_input("Nova grupa (postojeća ili nova)")
    if st.button("Premjesti") and sel != "-" and new_group.strip():
        m_id = mem_opts[sel]
        conn.execute("UPDATE members SET group_name=? WHERE id=?", (new_group.strip(), int(m_id))); conn.commit(); st.success("Premješten."); st.rerun()
    st.markdown("---"); st.subheader("Excel uvoz/izvoz članova po grupama")
    export = pd.read_sql_query("SELECT id, first_name, last_name, group_name FROM members ORDER BY group_name, last_name", conn)
    st.download_button("Skini Excel (članovi/grupe)", data=excel_bytes(export, sheet="Grupe"), file_name="clanovi_grupe.xlsx", disabled=export.empty)
    up = st.file_uploader("Učitaj Excel (kolone: id, group_name)", type=["xlsx"], key="groups_upload_v9")
    if up:
        try:
            dfu = pd.read_excel(up)
            for _, r in dfu.iterrows():
                if pd.notna(r.get("id")):
                    conn.execute("UPDATE members SET group_name=? WHERE id=?", (str(r.get("group_name","")), int(r["id"])))
            conn.commit(); st.success("Grupe ažurirane.")
        except Exception as e:
            st.error(f"Greška pri uvozu: {e}")
    conn.close()

def section_veterans():
    page_header("Veterani", "Popis i komunikacija")
    conn = get_conn()
    vets = pd.read_sql_query("""SELECT id, first_name, last_name, athlete_email, parent_email, group_name FROM members WHERE veteran=1 ORDER BY last_name""", conn)
    if vets.empty:
        st.info("Nema označenih veterana.")
    else:
        st.dataframe(vets, use_container_width=True)
        emails = ";".join([e for e in (vets["athlete_email"].tolist() + vets["parent_email"].tolist()) if isinstance(e, str) and e.strip()])
        subj = st.text_input("Predmet e-maila"); body = st.text_area("Poruka")
        st.markdown(f"[Otvori e-mail klijent](mailto:?bcc={emails}&subject={subj}&body={body})")
        st.download_button("Excel veterani", data=excel_bytes(vets,"Veterani"), file_name="veterani.xlsx")
    conn.close()

def section_attendance():
    page_header("Prisustvo", "Treneri i članovi")
    conn = get_conn()
    tab1, tab2, tab3 = st.tabs(["Treneri – evidencija","Članovi – evidencija","Sažetak"])
    with tab1:
        coaches = pd.read_sql_query("SELECT id, first_name||' '||last_name AS name FROM coaches ORDER BY last_name", conn)
        coach_opts = ["-"] + [f"{r['id']} – {r['name']}" for _, r in coaches.iterrows()]
        c_id = st.selectbox("Trener", coach_opts)
        gname = st.text_input("Grupa"); d = st.date_input("Datum", value=date.today())
        t1 = st.time_input("Od", value=time(18,0)); t2 = st.time_input("Do", value=time(19,0)); place = st.text_input("Mjesto (dvorana/igralište)")
        if st.button("Spremi prisustvo trenera"):
            hours = (datetime.combine(date.today(), t2)-datetime.combine(date.today(), t1)).seconds/3600.0
            if c_id != "-":
                coach_id = int(c_id.split(" – ")[0])
                coach_name = c_id.split(" – ")[1]
            else:
                coach_id = None; coach_name = ""
            conn.execute("""INSERT INTO attendance_trainers(coach_id,coach_name,group_name,date,time_from,time_to,place,hours)
                            VALUES(?,?,?,?,?,?,?,?)""", (coach_id,coach_name,gname,d.isoformat(),t1.isoformat(),t2.isoformat(),place,hours))
            conn.commit(); st.success("Spremljeno.")
    with tab2:
        members = pd.read_sql_query("SELECT id, first_name||' '||last_name AS name, group_name FROM members ORDER BY last_name", conn)
        mem_opts = [f"{r['id']} – {r['name']} ({r['group_name'] or ''})" for _, r in members.iterrows()]
        sel = st.multiselect("Članovi", mem_opts)
        gname = st.text_input("Grupa (ako nije ista)"); d = st.date_input("Datum", value=date.today())
        hours = st.number_input("Sati", value=1.0); status = st.selectbox("Status", ["Prisutan","Odsutan","Opravdano"])
        if st.button("Spremi prisustvo članova") and sel:
            for s in sel:
                mid = int(s.split(" – ")[0])
                mname = s.split(" – ")[1].split(" (")[0]
                conn.execute("""INSERT INTO attendance_members(member_id,member_name,group_name,date,hours,status)
                                VALUES(?,?,?,?,?,?)""", (mid,mname,gname,d.isoformat(),float(hours),status))
            conn.commit(); st.success("Spremljeno.")
    with tab3:
        month = st.selectbox("Mjesec", list(range(1,13)), index=datetime.now().month-1)
        year = st.number_input("Godina", min_value=2000, max_value=2100, value=datetime.now().year, step=1)
        tdf = pd.read_sql_query("""SELECT coach_name, group_name, date, hours FROM attendance_trainers
                                   WHERE substr(date,1,4)=? AND CAST(substr(date,6,2) AS INT)=?""", conn, params=(str(year),int(month)))
        mdf = pd.read_sql_query("""SELECT member_name, group_name, date, hours, status FROM attendance_members
                                   WHERE substr(date,1,4)=? AND CAST(substr(date,6,2) AS INT)=?""", conn, params=(str(year),int(month)))
        st.subheader("Treneri – sažetak"); st.dataframe(tdf, use_container_width=True)
        st.subheader("Članovi – sažetak"); st.dataframe(mdf, use_container_width=True)
    conn.close()

def section_mail():
    page_header("Popis članova & komunikacija", "Filtriranje i priprema e-mailova")
    conn = get_conn()
    df = pd.read_sql_query("""SELECT id, first_name, last_name, athlete_email, parent_email, group_name, medical_valid_until FROM members ORDER BY last_name""", conn)
    group = st.text_input("Filtriraj po grupi")
    if group.strip():
        df = df[df["group_name"].fillna("").str.contains(group.strip(), case=False)]
    st.dataframe(highlight_medical(df), use_container_width=True)
    emails = ";".join([e for e in (df["athlete_email"].tolist()+df["parent_email"].tolist()) if isinstance(e,str) and e.strip()])
    subj = st.text_input("Predmet"); body = st.text_area("Poruka")
    st.markdown(f"[Otvori e-mail klijent s odabranima](mailto:?bcc={emails}&subject={subj}&body={body})")
    st.download_button("Skini Excel", data=excel_bytes(df, "Popis"), file_name="popis.xlsx", disabled=df.empty)
    conn.close()

def section_statistics():
    page_header("Statistika", "Po godinama, uzrastima, natjecanjima i medaljama")
    conn = get_conn()
    # Učitamo natjecanja i rezultate
    comps = pd.read_sql_query("""SELECT id, kind, age_cat, style, name, date_from, country, team_rank FROM competitions""", conn)
    res = pd.read_sql_query("""SELECT r.id, r.competition_id, r.member_id, r.category, r.style, r.fights_total, r.wins, r.losses, r.placement
                               FROM results r""", conn)
    if comps.empty:
        st.info("Nema unesenih natjecanja.")
        conn.close(); return
    comps["year"] = pd.to_datetime(comps["date_from"], errors="coerce").dt.year
    # Filteri
    years = sorted(comps["year"].dropna().unique().tolist())
    sel_years = st.multiselect("Godine", years, default=years)
    sel_age = st.multiselect("Uzrasti", sorted(comps["age_cat"].dropna().unique().tolist()))
    sel_kind = st.multiselect("Vrste natjecanja", sorted(comps["kind"].dropna().unique().tolist()))
    filt = comps.copy()
    if sel_years: filt = filt[filt["year"].isin(sel_years)]
    if sel_age: filt = filt[filt["age_cat"].isin(sel_age)]
    if sel_kind: filt = filt[filt["kind"].isin(sel_kind)]
    st.subheader("Broj natjecanja po godini")
    by_year = filt.groupby("year").size().reset_index(name="natjecanja")
    st.dataframe(by_year, use_container_width=True)
    st.download_button("Skini (godina/natjecanja)", data=excel_bytes(by_year,"PoGodini"), file_name="stat_natjecanja_po_godini.xlsx", disabled=by_year.empty)
    st.subheader("Natjecanja po uzrastima i vrstama")
    piv = pd.pivot_table(filt, index="age_cat", columns="kind", values="id", aggfunc="count", fill_value=0)
    st.dataframe(piv, use_container_width=True)
    # Medalje: spajamo s rezultatima
    if not res.empty:
        merged = res.merge(filt[["id","year","age_cat","kind"]], left_on="competition_id", right_on="id", how="inner", suffixes=("_r","_c"))
        medals = merged.assign(
            gold = (merged["placement"]==1).astype(int),
            silver = (merged["placement"]==2).astype(int),
            bronze = (merged["placement"]==3).astype(int),
        )
        # po godinama
        byY = medals.groupby("year")[["gold","silver","bronze"]].sum().reset_index()
        st.subheader("Medalje po godinama"); st.dataframe(byY, use_container_width=True)
        st.download_button("Skini (medalje/godine)", data=excel_bytes(byY,"MedaljeGodina"), file_name="medalje_po_godinama.xlsx", disabled=byY.empty)
        # po uzrastima
        byA = medals.groupby("age_cat")[["gold","silver","bronze"]].sum().reset_index()
        st.subheader("Medalje po uzrastima"); st.dataframe(byA, use_container_width=True)
        # po vrstama natjecanja
        byK = medals.groupby("kind")[["gold","silver","bronze"]].sum().reset_index()
        st.subheader("Medalje po vrstama natjecanja"); st.dataframe(byK, use_container_width=True)
        # ukupno borbe/pobjede/porazi
        fights = medals.groupby("year")[["fights_total","wins","losses"]].sum().reset_index()
        st.subheader("Borbe/pobjede/porazi po godinama"); st.dataframe(fights, use_container_width=True)
    else:
        st.info("Još nema rezultata.")

    conn.close()

def main():
    st.set_page_config(page_title="HK Podravka – Admin", layout="wide")
    css_style(); init_db()
    menu = st.sidebar.radio("Izbornik", ["Članovi","Treneri","Grupe","Prisustvo","Veterani","Popis/Email","Statistika"])
    if menu == "Članovi": section_members()
    elif menu == "Treneri": section_coaches()
    elif menu == "Grupe": section_groups()
    elif menu == "Prisustvo": section_attendance()
    elif menu == "Veterani": section_veterans()
    elif menu == "Popis/Email": section_mail()
    else: section_statistics()

if __name__ == "__main__":
    main()
