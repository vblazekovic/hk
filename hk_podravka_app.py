# -*- coding: utf-8 -*-
import os, io, sqlite3
from datetime import datetime, date
import pandas as pd
import streamlit as st
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm

PRIMARY_RED="#c1121f"; GOLD="#d4af37"; WHITE="#ffffff"; LIGHT_BG="#fffaf8"
KLUB_NAZIV="Hrvački klub Podravka"; KLUB_EMAIL="hsk-podravka@gmail.com"
KLUB_ADRESA="Miklinovec 6a, 48000 Koprivnica"; KLUB_OIB="60911784858"
KLUB_WEB="https://hk-podravka.com"; KLUB_IBAN="HR6923860021100518154"
DB_PATH="hk_podravka.db"; UPLOAD_DIR="uploads"; os.makedirs(UPLOAD_DIR, exist_ok=True)

def get_conn():
    conn=sqlite3.connect(DB_PATH, check_same_thread=False); conn.execute("PRAGMA foreign_keys=ON"); return conn

def init_db():
    c=get_conn(); cur=c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS club_info(
        id INTEGER PRIMARY KEY CHECK(id=1),
        name TEXT,email TEXT,address TEXT,oib TEXT,web TEXT,iban TEXT,
        president TEXT,secretary TEXT,board_json TEXT,supervisory_json TEXT,
        instagram TEXT,facebook TEXT,tiktok TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS club_docs(
        id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, filename TEXT, path TEXT, uploaded_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS members(
        id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT, dob TEXT, gender TEXT, oib TEXT, residence TEXT,
        athlete_email TEXT, parent_email TEXT, photo_path TEXT, consent_path TEXT, application_path TEXT,
        pays_fee INTEGER DEFAULT 0, fee_amount REAL DEFAULT 30.0, group_name TEXT, medical_path TEXT, medical_valid_until TEXT)""")
    c.commit(); c.close()

def css():
    st.markdown(f"""
    <style>
    .app-header {{background:linear-gradient(90deg,{PRIMARY_RED},{GOLD});color:{WHITE};padding:16px 20px;border-radius:16px;margin-bottom:16px;}}
    .card {{background:{LIGHT_BG};border:1px solid #f0e6da;border-radius:16px;padding:16px;margin-bottom:12px;}}
    </style>""", unsafe_allow_html=True)

def header(t, s=None):
    st.markdown(f"<div class='app-header'><h2 style='margin:0'>{t}</h2>{('<div>'+s+'</div>') if s else ''}</div>", unsafe_allow_html=True)

def reg_font():
    fp=os.path.join(os.path.dirname(__file__),"DejaVuSans.ttf")
    try: pdfmetrics.registerFont(TTFont("DejaVuSans", fp)); return "DejaVuSans"
    except: return "Helvetica"

def wrap(c, text, x, y, w, lh, font, fs):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    line=""
    for word in text.split():
        t=(line+" "+word).strip()
        if stringWidth(t, font, fs)<=w: line=t
        else: c.drawString(x,y,line); y-=lh; line=word
    if line: c.drawString(x,y,line); y-=lh
    return y

def pdf_pristupnica(ime, dob, oib):
    font=reg_font(); buf=io.BytesIO(); c=canvas.Canvas(buf, pagesize=A4); W,H=A4; m=20*mm
    c.setFont(font,14); c.drawString(m,H-m,f"{ime} – {dob} – OIB: {oib}")
    c.setFont(font,10); y=H-m-24
    txt=(
    "HRVAČKI KLUB ‘PODRAVKA’ 48000 Koprivnica, Miklinovec 6a, mob:091/456-23-21 web site: www.hk-podravka.hr, e-mail: hsk.podravka@gmail.com "
    "………………………………………………………………………………………………………………………………………………………….. ………………………………………………………………………………………………………………………………………………………….. "
    f"OIB:{KLUB_OIB}, žiro-račun: {KLUB_IBAN}, Podravska banka d.d. Koprivnica\n\n"
    "STATUT KLUBA - ČLANSTVO … (skraćeno)\n\n"
    "ČLANARINA JE OBVEZUJUĆA TIJEKOM CIJELE GODINE (12 MJESECI)…\n\n"
    "IZJAVA O ODGOVORNOSTI …\n\n"
    "POTPIS ČLANA: __________________  POTPIS RODITELJA/STARATELJA: __________________  POTPIS: __________________")
    y=wrap(c, txt, m, y, W-2*m, 14, font, 10); c.showPage(); c.save(); buf.seek(0); return buf.read()

def pdf_privola(ime, oib, dob):
    font=reg_font(); buf=io.BytesIO(); c=canvas.Canvas(buf, pagesize=A4); W,H=A4; m=20*mm
    c.setFont(font,14); c.drawString(m,H-m,f"PRIVOLA – {ime} (OIB: {oib}, datum rođenja: {dob})")
    c.setFont(font,10); y=H-m-24
    txt=("GDPR privola – korištenje osobnih podataka u svrhu rada kluba, prijava na natjecanja, objave na webu i društvenim mrežama. "
         "Privola vrijedi do opoziva. Mjesto i datum: ________  Potpis: ________  Roditelj/staratelj: ________")
    y=wrap(c, txt, m, y, W-2*m, 14, font, 10); c.showPage(); c.save(); buf.seek(0); return buf.read()

def save_up(up, subdir):
    if not up: return ""
    fn=f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{up.name}"
    p=os.path.join(UPLOAD_DIR, subdir); os.makedirs(p, exist_ok=True)
    full=os.path.join(p, fn); open(full,"wb").write(up.getbuffer()); return full

def club_section():
    header("Klub – osnovni podaci", KLUB_NAZIV)
    conn=get_conn()
    df=pd.read_sql_query("SELECT * FROM club_info WHERE id=1", conn)
    if df.empty:
        conn.execute("INSERT OR REPLACE INTO club_info (id,name,email,address,oib,web,iban,instagram,facebook,tiktok) VALUES (1,?,?,?,?,?,?,?, ?, ?)", 
                     (KLUB_NAZIV, KLUB_EMAIL, KLUB_ADRESA, KLUB_OIB, KLUB_WEB, KLUB_IBAN,"","",""))
        conn.commit(); df=pd.read_sql_query("SELECT * FROM club_info WHERE id=1", conn)
    row=df.iloc[0]

    with st.form("club_form"):
        c1,c2=st.columns(2)
        name=c1.text_input("KLUB (IME)", row["name"])
        address=c1.text_input("ULICA I KUĆNI BROJ, GRAD I POŠTANSKI BROJ", row["address"])
        email=c1.text_input("E-mail", row["email"])
        web=c1.text_input("Web stranica", row["web"])
        iban=c1.text_input("IBAN račun", row["iban"])
        oib=c1.text_input("OIB", row["oib"])
        president=c2.text_input("Predsjednik kluba", row.get("president",""))
        secretary=c2.text_input("Tajnik kluba", row.get("secretary",""))

        st.markdown("**Članovi predsjedništva** – unesite ime, telefon, e-mail u svaki redak.")
        board = st.data_editor(pd.DataFrame(columns=["ime_prezime","telefon","email"]), num_rows="dynamic", key="board_editor")
        st.markdown("**Nadzorni odbor** – unesite ime, telefon, e-mail u svaki redak.")
        superv = st.data_editor(pd.DataFrame(columns=["ime_prezime","telefon","email"]), num_rows="dynamic", key="superv_editor")

        st.markdown("**Društvene mreže (linkovi)**")
        c3,c4,c5=st.columns(3)
        instagram=c3.text_input("Instagram", row.get("instagram",""))
        facebook=c4.text_input("Facebook", row.get("facebook",""))
        tiktok=c5.text_input("TikTok", row.get("tiktok",""))

        st.markdown("**Dokumenti kluba** – upload statuta ili drugih dokumenata")
        up_statut=st.file_uploader("Statut kluba (PDF)", type=["pdf"], key="statut")
        up_other=st.file_uploader("Drugi dokument (PDF/IMG)", type=["pdf","png","jpg","jpeg"], key="ostalo")

        submitted=st.form_submit_button("Spremi podatke kluba")

    if submitted:
        conn.execute("""UPDATE club_info SET name=?,email=?,address=?,oib=?,web=?,iban=?,
                         president=?,secretary=?,board_json=?,supervisory_json=?,instagram=?,facebook=?,tiktok=? WHERE id=1""",
                     (name,email,address,oib,web,iban,president,secretary,board.to_json(),superv.to_json(),instagram,facebook,tiktok))
        if up_statut:
            p=save_up(up_statut,"club_docs"); conn.execute("INSERT INTO club_docs(kind,filename,path,uploaded_at) VALUES(?,?,?,?)",("statut",up_statut.name,p,datetime.now().isoformat()))
        if up_other:
            p=save_up(up_other,"club_docs"); conn.execute("INSERT INTO club_docs(kind,filename,path,uploaded_at) VALUES(?,?,?,?)",("ostalo",up_other.name,p,datetime.now().isoformat()))
        conn.commit(); st.success("Podaci kluba spremljeni.")
    docs=pd.read_sql_query("SELECT id,kind,filename,uploaded_at FROM club_docs ORDER BY uploaded_at DESC", conn)
    if not docs.empty:
        st.markdown("### Dokumenti kluba"); st.dataframe(docs, use_container_width=True)
    conn.close()

def members_section():
    header("Članovi","Učlanjenja i dokumenti")
    conn=get_conn()

    st.markdown("#### Novi član")
    with st.form("member_form"):
        c1,c2=st.columns(2)
        ime=c1.text_input("Ime i prezime")
        dob=c1.date_input("Datum rođenja", value=date(2010,1,1))
        spol=c1.selectbox("Spol",["M","Ž"])
        oib=c1.text_input("OIB")
        preb=c1.text_input("Mjesto prebivališta")
        email_s=c1.text_input("E-mail sportaša")
        email_r=c1.text_input("E-mail roditelja")
        grupa=c1.text_input("Grupa (npr. U13, veterani...)")
        placa=c2.checkbox("Plaća članarinu", value=False)
        iznos=c2.number_input("Iznos članarine (EUR)", value=30.0, step=1.0)
        foto=st.file_uploader("Slika člana", type=["png","jpg","jpeg"])
        med=st.file_uploader("Liječnička potvrda (PDF/JPG)", type=["pdf","png","jpg","jpeg"])
        med_do=c2.date_input("Liječnička vrijedi do", value=date.today())
        submit=st.form_submit_button("Spremi člana i generiraj PDF-ove")

    if submit:
        photo_p=save_up(foto,"members/photos") if foto else ""
        med_p=save_up(med,"members/medical") if med else ""
        conn.execute("""INSERT INTO members(full_name,dob,gender,oib,residence,athlete_email,parent_email,photo_path,medical_path,medical_valid_until,pays_fee,fee_amount,group_name)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (ime,dob.isoformat(),spol,oib,preb,email_s,email_r,photo_p,med_p,med_do.isoformat(),int(placa),float(iznos),grupa))
        mid=conn.execute("SELECT last_insert_rowid()").fetchone()[0]; conn.commit()
        # PDF-ovi
        prist=pdf_pristupnica(ime, dob.isoformat(), oib)
        priv=pdf_privola(ime, oib, dob.isoformat())
        app_path=os.path.join(UPLOAD_DIR,"members/forms",f"{mid}_pristupnica.pdf"); os.makedirs(os.path.dirname(app_path), exist_ok=True)
        open(app_path,"wb").write(prist)
        cons_path=os.path.join(UPLOAD_DIR,"members/forms",f"{mid}_privola.pdf"); open(cons_path,"wb").write(priv)
        conn.execute("UPDATE members SET application_path=?, consent_path=? WHERE id=?", (app_path,cons_path,mid)); conn.commit()
        st.success("Član spremljen. PDF-ovi generirani.")
        st.download_button("Skini pristupnicu (PDF)", data=prist, file_name=f"pristupnica_{mid}.pdf")
        st.download_button("Skini privolu (PDF)", data=priv, file_name=f"privola_{mid}.pdf")

    st.markdown("---"); st.markdown("### Popis članova")
    tbl=pd.read_sql_query("SELECT id,full_name,dob,gender,oib,group_name,pays_fee,fee_amount,medical_valid_until FROM members ORDER BY full_name", conn)
    st.dataframe(tbl, use_container_width=True)
    conn.close()

def main():
    st.set_page_config(page_title="HK Podravka – Admin", page_icon="🤼", layout="wide")
    css(); init_db()
    with st.sidebar:
        st.markdown(f"## {KLUB_NAZIV}")
        st.markdown(f"**E-mail:** {KLUB_EMAIL}"); st.markdown(f"**Adresa:** {KLUB_ADRESA}")
        st.markdown(f"**OIB:** {KLUB_OIB}"); st.markdown(f"**IBAN:** {KLUB_IBAN}")
        st.markdown(f"[Web]({KLUB_WEB})")
        sec=st.radio("Navigacija", ["Klub","Članovi"])
    if sec=="Klub": club_section()
    else: members_section()

if __name__=="__main__":
    main()
